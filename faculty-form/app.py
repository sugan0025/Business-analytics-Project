"""Faculty selection form (Google Form look) - Flask app.

Runs locally (`flask run`) and on Vercel (api/index.py imports `app`).
"""
import logging
import time
from datetime import timedelta

from flask import Flask, jsonify, render_template, request, session
from sqlalchemy import delete, func, insert, or_, select, text, update

import allocation
import auth
import config
import db
import sheets_sync
from auth import AuthError

log = logging.getLogger("faculty-form")

STATUS_FOR_CODE = {
    "faculty_full": 409, "already_submitted": 409, "register_taken": 409, "no_attempt": 409,
    "timer_expired": 410, "invalid_faculty": 400, "invalid_student": 400, "too_many_attempts": 429,
}


def create_app(settings=None, engine=None, sheets_client=None):
    settings = settings or config.load_settings()
    app = Flask(__name__, static_folder="public", static_url_path="", template_folder="templates")
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.secure_cookies,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=settings.session_minutes),
        JSON_SORT_KEYS=False,
    )
    state = {"engine": engine, "sheets": sheets_client, "sheets_tried": sheets_client is not None}

    # ---- lazy resources -----------------------------------------------------------
    def get_engine():
        if state["engine"] is None:
            if config.on_vercel() and settings.database_url.startswith("sqlite"):
                raise RuntimeError("DATABASE_URL is not set. Add a Postgres database (Vercel Storage -> Neon).")
            state["engine"] = db.make_engine(settings.database_url)
        seeded = db.ensure_ready(state["engine"])
        if seeded:
            try:
                sh = get_sheets()
                if sh:
                    sheets_sync.rewrite_all_selections(state["engine"], sh)
            except Exception as exc:
                log.warning(f"Sheets sync after seed error: {exc}")
        return state["engine"]

    def get_sheets():
        if not state["sheets_tried"]:
            state["sheets_tried"] = True
            try:
                state["sheets"] = sheets_sync.get_client(settings)
            except Exception:
                log.exception("Could not create Google Sheets client")
                state["sheets"] = None
        return state["sheets"]

    _last_sync_time = [0.0]

    def trigger_sheet_sync(engine_, sheets, background=True, timeout=0.0):
        if sheets is None:
            return
        def _do_sync():
            try:
                sheets_sync.sync_pending(engine_, sheets)
            except Exception:
                log.exception("Sheet sync error")

        if background and not app.testing:
            import threading
            t = threading.Thread(target=_do_sync, daemon=True)
            t.start()
            if timeout and config.on_vercel():
                t.join(timeout=timeout)
        else:
            _do_sync()

    _avail_cache = {"data": None, "time": 0.0, "etag": ""}

    def get_cached_availability(engine_, max_age=1.0):
        t_now = time.time()
        if _avail_cache["data"] is not None and (t_now - _avail_cache["time"] < max_age):
            return _avail_cache["data"], _avail_cache["etag"]
        data = allocation.availability(engine_)
        import hashlib
        etag = hashlib.md5(str([(f["id"], f["remaining"]) for f in data]).encode()).hexdigest()
        _avail_cache["data"] = data
        _avail_cache["time"] = t_now
        _avail_cache["etag"] = etag
        return data, etag

    def invalidate_availability_cache():
        _avail_cache["data"] = None
        _avail_cache["time"] = 0.0

    def now():
        return config.now_ms()

    def err(code, message, status, **extra):
        body = {"ok": False, "code": code, "message": message}
        body.update(extra)
        return jsonify(body), status

    def body_json():
        if not request.is_json:
            raise AuthError("bad_request", "Expected a JSON request.", 400)
        return request.get_json(silent=True) or {}

    def current_identity():
        ident = session.get("identity")
        if not ident:
            raise AuthError("not_signed_in", "Please sign in with your college Google account.", 401)
        if ident.get("email") in auth.ADMIN_EMAILS or ident.get("register_no") == "7376257MB144":
            ident["is_admin"] = True
            session["identity"] = ident
        return dict(ident)

    def sel_json(sel):
        return {"seq": sel["seq"], "faculty_id": sel["faculty_id"], "faculty": sel["faculty"],
                "time": config.fmt_ist(sel["created_ms"]), "name": sel["name"],
                "register_no": sel["register_no"], "email": sel["email"]}

    def free_roster(engine_or_conn):
        from db import selections, students
        from sqlalchemy.engine import Connection
        def _get(conn):
            rows = conn.execute(
                select(students.c.register_no, students.c.name)
                .where(~students.c.register_no.in_(select(selections.c.register_no)))
                .order_by(students.c.register_no)
            ).all()
            return [{"register_no": r[0], "name": r[1]} for r in rows]
        if isinstance(engine_or_conn, Connection):
            return _get(engine_or_conn)
        with engine_or_conn.connect() as conn:
            return _get(conn)

    def get_faculty_dashboard_data(engine_, ident):
        from db import faculty, faculty_student_selections, selections, students
        fac_id = ident.get("faculty_id")
        with engine_.connect() as conn:
            fac_rec = None
            if fac_id:
                fac_rec = conn.execute(select(faculty).where(faculty.c.id == fac_id)).mappings().first()
            if not fac_rec and ident.get("email"):
                fac_rec = conn.execute(select(faculty).where(func.lower(faculty.c.email) == ident["email"].lower())).mappings().first()

            students_selected = []
            if fac_rec:
                sel_rows = conn.execute(
                    select(selections).where(selections.c.faculty_id == fac_rec["id"]).order_by(selections.c.created_ms)
                ).mappings().all()
                students_selected = [
                    {
                        "seq": r["seq_id"],
                        "register_no": r["register_no"],
                        "name": r["student_name"],
                        "email": r["email"],
                        "time": config.fmt_ist(r["created_ms"]),
                    }
                    for r in sel_rows
                ]

            stu_rows = conn.execute(select(students).order_by(students.c.register_no)).mappings().all()
            all_students = [
                {"register_no": s["register_no"], "name": s["name"], "email": s["email"]}
                for s in stu_rows
            ]

            fac_picks = []
            if fac_rec:
                pick_rows = conn.execute(
                    select(faculty_student_selections)
                    .where(faculty_student_selections.c.faculty_id == fac_rec["id"])
                    .order_by(faculty_student_selections.c.created_ms)
                ).mappings().all()
                fac_picks = [
                    {
                        "id": p["id"],
                        "student_register_no": p["student_register_no"],
                        "student_name": p["student_name"],
                        "time": config.fmt_ist(p["created_ms"]),
                    }
                    for p in pick_rows
                ]

            fac_info = {
                "id": fac_rec["id"] if fac_rec else None,
                "name": fac_rec["name"] if fac_rec else ident["name"],
                "capacity": fac_rec["capacity"] if fac_rec else 0,
                "selected_count": len(students_selected) if fac_rec else 0,
                "remaining": (fac_rec["capacity"] - len(students_selected)) if fac_rec else 0,
                "email": ident["email"],
            }
            return {
                "faculty": fac_info,
                "students_selected": students_selected,
                "all_students": all_students,
                "faculty_selections": fac_picks,
            }

    def get_master_overview_data(engine_):
        from db import faculty, selections
        with engine_.connect() as conn:
            fac_rows = conn.execute(select(faculty).order_by(faculty.c.id)).mappings().all()
            all_sel = conn.execute(
                select(selections).order_by(selections.c.faculty_id, selections.c.created_ms)
            ).mappings().all()

        by_fac = {}
        for s in all_sel:
            by_fac.setdefault(s["faculty_id"], []).append({
                "seq": s["seq_id"],
                "name": s["student_name"],
                "register_no": s["register_no"],
                "email": s["email"],
                "time": config.fmt_ist(s["created_ms"])
            })

        out = []
        from db import FACULTY_SPECIALIZATIONS
        for i, f in enumerate(fac_rows, start=1):
            stus = by_fac.get(f["id"], [])
            spec = f.get("specialization") or FACULTY_SPECIALIZATIONS.get(f["id"], "")
            out.append({
                "s_no": i,
                "id": f["id"],
                "name": f["name"],
                "specialization": spec,
                "capacity": f["capacity"],
                "selected_count": f["selected_count"],
                "remaining": f["capacity"] - f["selected_count"],
                "students": stus,
            })
        return out

    def get_initial_state(include_attempt=False):
        t = now()
        is_open, reason, opens = config.form_state(settings, t)
        state_data = {
            "is_open": is_open,
            "reason": reason,
            "opens_at_ms": opens,
            "opens_at": config.fmt_ist(opens) if opens else None,
            "server_now": t,
            "signed_in": False,
            "faculty": [],
            "etag": "",
        }

        ident = session.get("identity")
        if not ident:
            return state_data

        if ident.get("email") in auth.ADMIN_EMAILS or ident.get("register_no") == "7376257MB144":
            ident["is_admin"] = True
            session["identity"] = ident

        try:
            fac_data, etag = get_cached_availability(get_engine(), max_age=1.0)
            state_data["faculty"] = fac_data
            state_data["etag"] = etag
        except Exception:
            state_data["faculty"] = []
            state_data["etag"] = ""

        role = ident.get("role", "student")
        is_admin = bool(ident.get("is_admin", False))
        state_data.update(
            signed_in=True,
            role=role,
            is_admin=is_admin,
            email=ident["email"],
            name=ident["name"],
            register_no=ident.get("register_no"),
            mode=ident.get("mode", "strict"),
            selection=None,
        )

        engine_ = get_engine()
        if role == "director":
            state_data["master_overview"] = get_master_overview_data(engine_)
            return state_data

        if role == "faculty":
            state_data["faculty_dashboard"] = get_faculty_dashboard_data(engine_, ident)
            state_data["master_overview"] = get_master_overview_data(engine_)
            return state_data

        if is_admin:
            state_data["master_overview"] = get_master_overview_data(engine_)

        try:
            with engine_.connect() as conn:
                existing = allocation.get_selection(conn, email=ident["email"])
                if existing:
                    state_data["selection"] = sel_json(allocation.selection_view(existing))
                else:
                    if ident["register_no"] is None:
                        state_data["roster"] = free_roster(conn)
                    if include_attempt and is_open:
                        st_res = allocation.start_attempt(conn, ident["email"], t, settings.timer_seconds * 1000,
                                                       settings.max_attempts)
                        if st_res.ok:
                            state_data["attempt"] = {
                                "started_ms": st_res.extra["started_ms"],
                                "expires_ms": st_res.extra["expires_ms"],
                                "timer_seconds": settings.timer_seconds,
                                "server_now": t,
                            }
        except Exception:
            pass
        return state_data

    # ---- pages --------------------------------------------------------------------
    @app.get("/")
    def index():
        cfg = {
            "clientId": settings.google_client_id,
            "title": settings.form_title,
            "description": settings.form_description,
            "timerSeconds": settings.timer_seconds,
            "devLogin": settings.dev_login,
            "domain": settings.email_domain,
        }
        initial_state = get_initial_state(include_attempt=True)
        return render_template("index.html", cfg=cfg, initial_state=initial_state, title=settings.form_title, v="2026.5")

    @app.get("/healthz")
    def healthz():
        info = {
            "ok": True,
            "google_signin_configured": bool(settings.google_client_id),
            "sheets_configured": bool(settings.service_account_json or settings.service_account_file),
            "database": "postgres" if not settings.database_url.startswith("sqlite") else "sqlite",
        }
        try:
            eng = get_engine()
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            info["database_ok"] = True
            data, _ = get_cached_availability(eng, max_age=5.0)
            info["faculty_count"] = len(data)
        except Exception as exc:
            info.update(ok=False, database_ok=False, error=str(exc))
            return jsonify(info), 500
        return jsonify(info)

    # ---- auth -----------------------------------------------------------------------
    def start_session(identity):
        session.clear()
        session["identity"] = identity
        session.permanent = True

    @app.post("/api/auth/google")
    def auth_google():
        data = body_json()
        credential = (data.get("credential") or "").strip()
        if not credential:
            return err("bad_request", "Missing credential.", 400)
        identity = auth.identity_from_google(get_engine(), credential, settings)
        start_session(identity)
        initial_state = get_initial_state(include_attempt=True)
        return jsonify({"ok": True, "state": initial_state})

    @app.post("/api/dev-login")
    def dev_login():
        if not settings.dev_login:
            return err("not_found", "Not found.", 404)
        data = body_json()
        identity = auth.identify(get_engine(), data.get("email", ""), data.get("name", ""), settings)
        start_session(identity)
        initial_state = get_initial_state(include_attempt=True)
        return jsonify({"ok": True, "state": initial_state})

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    # ---- state & dashboard ------------------------------------------------------------
    @app.get("/api/me")
    def me():
        t = now()
        is_open, reason, opens = config.form_state(settings, t)
        out = {"ok": True, "signed_in": False, "is_open": is_open, "reason": reason, "opens_at_ms": opens,
               "opens_at": config.fmt_ist(opens) if opens else None, "server_now": t}
        ident = session.get("identity")
        if not ident:
            return jsonify(out)
        if ident.get("email") in auth.ADMIN_EMAILS or ident.get("register_no") == "7376257MB144":
            ident["is_admin"] = True
            session["identity"] = ident
        engine_ = get_engine()
        role = ident.get("role", "student")
        is_admin = bool(ident.get("is_admin", False))
        out.update(signed_in=True, role=role, is_admin=is_admin, email=ident["email"],
                   name=ident["name"], register_no=ident.get("register_no"), mode=ident.get("mode", "strict"),
                   selection=None)
        if role == "director":
            out["master_overview"] = get_master_overview_data(engine_)
            return jsonify(out)

        if role == "faculty":
            out["faculty_dashboard"] = get_faculty_dashboard_data(engine_, ident)
            out["master_overview"] = get_master_overview_data(engine_)
            return jsonify(out)

        if is_admin:
            out["master_overview"] = get_master_overview_data(engine_)

        try:
            fac_data, etag = get_cached_availability(engine_, max_age=1.0)
            out["faculty"] = fac_data
            out["etag"] = etag
        except Exception:
            out["faculty"] = []
            out["etag"] = ""

        with engine_.connect() as conn:
            existing = allocation.get_selection(conn, email=ident["email"])
        if existing:
            out["selection"] = sel_json(allocation.selection_view(existing))
        else:
            if ident.get("register_no") is None:
                out["roster"] = free_roster(engine_)
            if is_open:
                st_res = allocation.start_attempt(engine_, ident["email"], t, settings.timer_seconds * 1000,
                                               settings.max_attempts)
                if st_res.ok:
                    out["attempt"] = {
                        "started_ms": st_res.extra["started_ms"],
                        "expires_ms": st_res.extra["expires_ms"],
                        "timer_seconds": settings.timer_seconds,
                        "server_now": t,
                    }
        return jsonify(out)

    @app.get("/api/director/overview")
    def director_overview():
        ident = current_identity()
        if ident.get("role") not in ("director", "faculty") and not ident.get("is_admin"):
            return err("forbidden", "Access denied.", 403)
        return jsonify({"ok": True, "master_overview": get_master_overview_data(get_engine())})

    @app.post("/api/admin/update-capacities")
    def admin_update_capacities():
        ident = current_identity()
        if not ident.get("is_admin"):
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        caps = data.get("capacities") or {}
        if not isinstance(caps, dict) or not caps:
            return err("invalid_data", "No capacity data provided.", 400)

        engine_ = get_engine()
        from db import faculty
        with engine_.connect() as conn:
            cur_facs = conn.execute(select(faculty)).mappings().all()
        fac_by_id = {f["id"]: f for f in cur_facs}

        for fid_str, new_cap_val in caps.items():
            try:
                fid = int(fid_str)
                new_cap = int(new_cap_val)
            except (ValueError, TypeError):
                return err("invalid_data", f"Invalid faculty ID or capacity: {fid_str}={new_cap_val}", 400)
            if fid not in fac_by_id:
                return err("not_found", f"Faculty ID {fid} not found.", 404)
            if new_cap < 1:
                return err("invalid_capacity", "Capacity must be at least 1.", 400)
            if new_cap < fac_by_id[fid]["selected_count"]:
                return err(
                    "capacity_too_low",
                    f"Cannot reduce capacity below currently allocated students ({fac_by_id[fid]['selected_count']}) for {fac_by_id[fid]['name']}.",
                    400
                )

        with engine_.begin() as conn:
            for fid_str, new_cap_val in caps.items():
                fid = int(fid_str)
                new_cap = int(new_cap_val)
                conn.execute(
                    update(faculty).where(faculty.c.id == fid).values(capacity=new_cap)
                )

        invalidate_availability_cache()
        overview = get_master_overview_data(engine_)
        avail, _ = get_cached_availability(engine_, max_age=0.0)

        # Sync updated capacities to Google Sheets Summary tab
        sheets = get_sheets()
        if sheets:
            try:
                with engine_.connect() as conn:
                    active_facs = conn.execute(
                        select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)
                    ).mappings().all()
                    sheets.update_summary_tab([dict(f) for f in active_facs])
            except Exception:
                log.exception("Error syncing summary tab to Google Sheets on capacity update")

        # Return updated faculties for the Database tab
        from db import FACULTY_SPECIALIZATIONS
        with engine_.connect() as conn:
            fac_rows = conn.execute(
                select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)
            ).mappings().all()
        db_faculties = []
        for f in fac_rows:
            spec = f.get("specialization") or FACULTY_SPECIALIZATIONS.get(f["id"], "")
            db_faculties.append({
                "id": f["id"],
                "name": f["name"],
                "email": f.get("email") or "",
                "specialization": spec,
                "capacity": f["capacity"],
                "selected_count": f["selected_count"],
                "remaining": max(0, f["capacity"] - f["selected_count"]),
            })

        return jsonify({
            "ok": True,
            "message": "Seat capacities updated dynamically.",
            "master_overview": overview,
            "faculty": avail,
            "faculties": db_faculties,
        })

    @app.post("/api/admin/reset-user")
    def admin_reset_user():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin or director access required.", 403)

        data = body_json()
        target_reg = str(data.get("register_no") or "").strip().upper()
        target_email = str(data.get("email") or "").strip().lower()

        if not target_reg and not target_email:
            target_reg = "7376257MB144"
            target_email = "suganesans.mb25@bitsathy.ac.in"

        engine_ = get_engine()
        from db import attempts, faculty, selections, test_selections
        cleared_count = 0
        with engine_.begin() as conn:
            conds = []
            if target_reg:
                conds.append(selections.c.register_no == target_reg)
            if target_email:
                conds.append(selections.c.email == target_email)
            if conds:
                existing_sels = conn.execute(select(selections).where(or_(*conds))).mappings().all()
                for s in existing_sels:
                    conn.execute(
                        update(faculty)
                        .where(faculty.c.id == s["faculty_id"])
                        .where(faculty.c.selected_count > 0)
                        .values(selected_count=faculty.c.selected_count - 1)
                    )
                    conn.execute(delete(selections).where(selections.c.seq_id == s["seq_id"]))
                    cleared_count += 1

            if target_email:
                conn.execute(delete(attempts).where(attempts.c.email == target_email))
            if target_reg == "7376257MB144":
                conn.execute(delete(attempts).where(attempts.c.email == "suganesans.mb25@bitsathy.ac.in"))

            if data.get("clear_test_selections"):
                conn.execute(delete(test_selections))

        sheets = get_sheets()
        sheet_cleared = []
        if sheets:
            try:
                sheet_cleared = sheets.delete_student_by_query(target_reg, target_email)
            except Exception:
                pass

        invalidate_availability_cache()
        return jsonify({
            "ok": True,
            "message": f"Cleared records for {target_reg or target_email} ({cleared_count} selections removed).",
            "cleared_count": cleared_count,
            "sheet_cleared_rows": sheet_cleared,
        })

    @app.post("/api/admin/reconcile-sheets")
    def admin_reconcile_sheets():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin or director access required.", 403)
        eng = get_engine()
        sheets = get_sheets()
        res = sheets_sync.reconcile_sheet_and_db(eng, sheets)
        invalidate_availability_cache()
        avail, _ = get_cached_availability(eng, max_age=0.0)
        return jsonify({"ok": True, "reconcile": res, "faculty": avail})

    # ---- admin database management (Students & Faculties) ----------------------------
    @app.get("/api/admin/database/students")
    def admin_get_students():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        engine_ = get_engine()
        from db import faculty, selections, students
        with engine_.connect() as conn:
            all_stu = conn.execute(select(students).order_by(students.c.register_no)).mappings().all()
            all_sels = conn.execute(
                select(selections, faculty.c.name.label("faculty_name"))
                .join(faculty, faculty.c.id == selections.c.faculty_id)
            ).mappings().all()

        sel_by_reg = {s["register_no"]: s for s in all_sels}
        sel_by_email = {s["email"].lower(): s for s in all_sels if s.get("email")}

        res = []
        for s in all_stu:
            reg = s["register_no"]
            email = (s.get("email") or "").lower()
            alloc = sel_by_reg.get(reg) or (sel_by_email.get(email) if email else None)
            alloc_data = None
            if alloc:
                alloc_data = {
                    "faculty_id": alloc["faculty_id"],
                    "faculty_name": alloc["faculty_name"],
                    "seq_id": alloc["seq_id"],
                    "time": config.fmt_ist(alloc["created_ms"]),
                }
            res.append({
                "register_no": reg,
                "name": s["name"],
                "email": s.get("email") or "",
                "allocation": alloc_data,
            })
        return jsonify({"ok": True, "students": res})

    @app.post("/api/admin/database/students/save")
    def admin_save_student():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        old_reg = str(data.get("old_register_no") or "").strip().upper()
        new_reg = str(data.get("register_no") or "").strip().upper()
        name = str(data.get("name") or "").strip()
        email = str(data.get("email") or "").strip().lower() or None

        if not new_reg or not name:
            return err("invalid_data", "Register number and student name are required.", 400)

        engine_ = get_engine()
        from db import attempts, selections, students
        sheets = get_sheets()

        with engine_.begin() as conn:
            if old_reg:
                existing = conn.execute(select(students).where(students.c.register_no == old_reg)).mappings().first()
                if not existing:
                    return err("not_found", f"Student {old_reg} not found.", 404)

                if new_reg != old_reg:
                    dup = conn.execute(select(students).where(students.c.register_no == new_reg)).first()
                    if dup:
                        return err("duplicate_reg", f"Register number {new_reg} is already used.", 400)

                if email and email != (existing.get("email") or "").lower():
                    dup_e = conn.execute(select(students).where(students.c.email == email, students.c.register_no != old_reg)).first()
                    if dup_e:
                        return err("duplicate_email", f"Email {email} is already assigned to another student.", 400)

                conn.execute(
                    update(students).where(students.c.register_no == old_reg)
                    .values(register_no=new_reg, name=name, email=email)
                )

                sel_row = conn.execute(
                    select(selections).where(
                        (selections.c.register_no == old_reg) |
                        ((selections.c.email == existing.get("email")) if existing.get("email") else False)
                    )
                ).mappings().first()

                if sel_row:
                    conn.execute(
                        update(selections).where(selections.c.seq_id == sel_row["seq_id"])
                        .values(register_no=new_reg, student_name=name, email=email or sel_row["email"], synced=0)
                    )

                if existing.get("email") and email:
                    conn.execute(update(attempts).where(attempts.c.email == existing["email"]).values(email=email))
            else:
                dup = conn.execute(select(students).where(students.c.register_no == new_reg)).first()
                if dup:
                    return err("duplicate_reg", f"Register number {new_reg} already exists.", 400)
                if email:
                    dup_e = conn.execute(select(students).where(students.c.email == email)).first()
                    if dup_e:
                        return err("duplicate_email", f"Email {email} already exists.", 400)

                conn.execute(insert(students).values(register_no=new_reg, name=name, email=email))

        if old_reg and sheets:
            try:
                sheets_sync.sync_pending(engine_, sheets, limit=5)
            except Exception:
                pass

        if sheets and hasattr(sheets, "sync_roster_tab"):
            try:
                with engine_.connect() as conn:
                    stu_rows = conn.execute(select(students).order_by(students.c.register_no)).mappings().all()
                    sheets.sync_roster_tab([dict(s) for s in stu_rows])
            except Exception:
                pass

        # Sync changes to roster.csv file in real time
        from pathlib import Path
        r_path = Path(settings.roster_file) if getattr(settings, "roster_file", "") else None
        db.sync_roster_csv(engine_, roster_path=r_path)

        return jsonify({"ok": True, "message": "Student record saved successfully."})

    @app.post("/api/admin/database/students/reset")
    def admin_reset_student_selection():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        reg_no = str(data.get("register_no") or "").strip().upper()
        if not reg_no:
            return err("invalid_data", "Register number is required.", 400)

        engine_ = get_engine()
        sheets = get_sheets()

        removed = allocation.reset_student(engine_, reg_no)
        invalidate_availability_cache()

        if sheets:
            try:
                sheets_sync.rewrite_all_selections(engine_, sheets)
            except Exception:
                pass

        if removed:
            return jsonify({
                "ok": True,
                "message": f"Guide choice reset for {removed['student_name']} ({reg_no}). Student remains on roster.",
                "reset": removed,
            })
        return jsonify({
            "ok": True,
            "message": f"Student {reg_no} had no active guide choice. Session attempts cleared.",
        })

    @app.post("/api/admin/database/students/delete")
    def admin_delete_student():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        reg_no = str(data.get("register_no") or "").strip().upper()
        if not reg_no:
            return err("invalid_data", "Register number is required.", 400)

        engine_ = get_engine()
        sheets = get_sheets()
        from db import students

        allocation.reset_student(engine_, reg_no)

        with engine_.begin() as conn:
            conn.execute(delete(students).where(students.c.register_no == reg_no))

        invalidate_availability_cache()

        if sheets:
            try:
                sheets_sync.rewrite_all_selections(engine_, sheets)
            except Exception:
                pass

        # Sync changes to roster.csv file in real time
        from pathlib import Path
        r_path = Path(settings.roster_file) if getattr(settings, "roster_file", "") else None
        db.sync_roster_csv(engine_, roster_path=r_path)

        return jsonify({"ok": True, "message": f"Student {reg_no} removed from database."})

    @app.post("/api/admin/database/reset")
    def admin_reset_database():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin or director access required.", 403)

        engine_ = get_engine()
        sheets = get_sheets()
        from db import attempts, faculty, faculty_student_selections, selections, test_selections

        with engine_.begin() as conn:
            conn.execute(delete(selections))
            conn.execute(delete(attempts))
            conn.execute(delete(faculty_student_selections))
            conn.execute(delete(test_selections))
            conn.execute(update(faculty).values(selected_count=0))

            if "sqlite" in str(engine_.url):
                try:
                    conn.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('selections', 'faculty_student_selections', 'test_selections', 'attempts')"))
                except Exception:
                    pass
            else:
                for seq_tbl, col in [("selections", "seq_id"), ("faculty_student_selections", "id"), ("test_selections", "id"), ("attempts", "id")]:
                    try:
                        conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{seq_tbl}', '{col}'), 1, false)"))
                    except Exception:
                        try:
                            conn.execute(text(f"SELECT setval('{seq_tbl}_{col}_seq', 1, false)"))
                        except Exception:
                            pass

        invalidate_availability_cache()

        sheet_cleared = False
        sheet_error = None
        if sheets:
            try:
                res_tab = getattr(sheets, "responses_tab", "Responses")
                fac_tab = getattr(sheets, "faculty_tab", "Faculty Selections")
                tst_tab = getattr(sheets, "test_tab", "Test Responses")

                if hasattr(sheets, "ensure_tab"):
                    sheets.ensure_tab(res_tab, sheets_sync.HEADERS)
                if hasattr(sheets, "clear_range"):
                    sheets.clear_range(f"'{res_tab}'!A2:F500")
                if hasattr(sheets, "clear_rows"):
                    sheets.clear_rows(list(range(2, 500)))

                if hasattr(sheets, "ensure_tab"):
                    try:
                        sheets.ensure_tab(fac_tab, sheets_sync.FACULTY_HEADERS)
                    except Exception:
                        pass
                if hasattr(sheets, "clear_range"):
                    try:
                        sheets.clear_range(f"'{fac_tab}'!A2:F500")
                    except Exception:
                        pass

                if hasattr(sheets, "ensure_tab"):
                    try:
                        sheets.ensure_tab(tst_tab, sheets_sync.TEST_HEADERS)
                    except Exception:
                        pass
                if hasattr(sheets, "clear_range"):
                    try:
                        sheets.clear_range(f"'{tst_tab}'!A2:F500")
                    except Exception:
                        pass

                if hasattr(sheets, "update_summary_tab"):
                    with engine_.connect() as conn:
                        active_facs = conn.execute(
                            select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)
                        ).mappings().all()
                        sheets.update_summary_tab([dict(f) for f in active_facs])
                sheet_cleared = True
            except Exception as exc:
                log.exception("Error clearing Google Sheet on database reset")
                sheet_error = str(exc)

        msg = "Current runtime allocation data cleared successfully."
        if sheet_error:
            msg += f" Note: Google Sheet clear warning: {sheet_error}"

        return jsonify({
            "ok": True,
            "message": msg,
            "sheet_cleared": sheet_cleared,
            "sheet_error": sheet_error,
        })

    @app.get("/api/admin/database/faculties")
    def admin_get_faculties():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        engine_ = get_engine()
        from db import FACULTY_SPECIALIZATIONS, faculty
        with engine_.connect() as conn:
            rows = conn.execute(
                select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)
            ).mappings().all()

        res = []
        for f in rows:
            spec = f.get("specialization") or FACULTY_SPECIALIZATIONS.get(f["id"], "")
            res.append({
                "id": f["id"],
                "name": f["name"],
                "email": f.get("email") or "",
                "specialization": spec,
                "capacity": f["capacity"],
                "selected_count": f["selected_count"],
                "remaining": max(0, f["capacity"] - f["selected_count"]),
            })
        return jsonify({"ok": True, "faculties": res})

    @app.post("/api/admin/database/faculties/save")
    def admin_save_faculty():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        fid = data.get("id")
        try:
            fid = int(fid) if fid is not None and str(fid).strip() != "" else None
        except (ValueError, TypeError):
            fid = None

        name = str(data.get("name") or "").strip()
        email = str(data.get("email") or "").strip().lower() or None
        spec = str(data.get("specialization") or "").strip()
        try:
            cap = int(data.get("capacity", 5))
        except (ValueError, TypeError):
            cap = 5

        if not name:
            return err("invalid_data", "Faculty name is required.", 400)
        if cap < 1:
            return err("invalid_data", "Capacity must be at least 1.", 400)

        engine_ = get_engine()
        from db import FACULTY_SPECIALIZATIONS, faculty
        sheets = get_sheets()

        with engine_.begin() as conn:
            if fid and fid > 0:
                existing = conn.execute(select(faculty).where(faculty.c.id == fid)).mappings().first()
                if not existing:
                    return err("not_found", f"Faculty ID {fid} not found.", 404)
                if cap < existing["selected_count"]:
                    return err("capacity_too_low", f"Capacity cannot be lower than allocated students ({existing['selected_count']}).", 400)
                conn.execute(
                    update(faculty).where(faculty.c.id == fid)
                    .values(name=name, email=email, specialization=spec, capacity=cap)
                )
            else:
                max_id = conn.execute(select(func.max(faculty.c.id))).scalar() or 11
                new_id = max(12, max_id + 1)
                conn.execute(
                    insert(faculty).values(
                        id=new_id, name=name, capacity=cap, selected_count=0,
                        email=email, specialization=spec
                    )
                )
                fid = new_id

        if fid:
            FACULTY_SPECIALIZATIONS[fid] = spec
            if email:
                auth.DEFAULT_FACULTY_MAP[email] = fid

        invalidate_availability_cache()

        if sheets:
            try:
                sheets_sync.rewrite_all_selections(engine_, sheets)
            except Exception:
                pass

        return jsonify({"ok": True, "message": "Faculty saved successfully.", "id": fid})

    @app.post("/api/admin/database/faculties/delete")
    def admin_delete_faculty():
        ident = current_identity()
        if not ident.get("is_admin") and ident.get("role") != "director":
            return err("forbidden", "Admin access required.", 403)
        data = body_json()
        try:
            fid = int(data.get("id"))
        except (ValueError, TypeError):
            return err("invalid_data", "Valid faculty ID required.", 400)

        engine_ = get_engine()
        from db import attempts, faculty, faculty_student_selections, selections
        sheets = get_sheets()

        with engine_.begin() as conn:
            existing = conn.execute(select(faculty).where(faculty.c.id == fid)).mappings().first()
            if not existing:
                return err("not_found", "Faculty not found.", 404)

            # If students had chosen this faculty, unassign them so they can choose another guide
            sels = conn.execute(select(selections).where(selections.c.faculty_id == fid)).mappings().all()
            for s in sels:
                conn.execute(delete(selections).where(selections.c.seq_id == s["seq_id"]))
                if s.get("email"):
                    conn.execute(delete(attempts).where(attempts.c.email == s["email"].lower()))

            conn.execute(delete(faculty_student_selections).where(faculty_student_selections.c.faculty_id == fid))
            conn.execute(delete(faculty).where(faculty.c.id == fid))

        invalidate_availability_cache()

        if sheets:
            try:
                sheets_sync.rewrite_all_selections(engine_, sheets)
            except Exception:
                pass

        return jsonify({"ok": True, "message": f"Faculty {existing['name']} removed from database."})

    @app.get("/api/faculty/dashboard")
    def faculty_dashboard():
        ident = current_identity()
        if ident.get("role") != "faculty" and not ident.get("is_admin"):
            return err("forbidden", "Faculty access required.", 403)
        data = get_faculty_dashboard_data(get_engine(), ident)
        return jsonify({"ok": True, **data})

    @app.post("/api/faculty/select-student")
    def faculty_select_student():
        ident = current_identity()
        if ident.get("role") != "faculty" and not ident.get("is_admin"):
            return err("forbidden", "Faculty access required.", 403)
        data = body_json()
        reg_no = str(data.get("register_no") or "").strip().upper()
        if not reg_no:
            return err("invalid_student", "Please choose a student.", 400)

        engine_ = get_engine()
        from db import faculty_student_selections, students
        with engine_.connect() as conn:
            stu = conn.execute(select(students).where(students.c.register_no == reg_no)).mappings().first()
            if not stu:
                return err("not_found", "Student not found in class roster.", 404)
            already = conn.execute(
                select(faculty_student_selections)
                .where(faculty_student_selections.c.faculty_email == ident["email"])
                .where(faculty_student_selections.c.student_register_no == reg_no)
            ).first()
            if already:
                return err("already_selected", "You have already selected this student.", 400)

            fac_id = ident.get("faculty_id") or 0
            if not fac_id:
                from db import faculty
                fac_row = conn.execute(select(faculty).where(func.lower(faculty.c.email) == ident["email"].lower())).mappings().first()
                if fac_row:
                    fac_id = fac_row["id"]

        t = now()
        with engine_.begin() as conn:
            conn.execute(
                insert(faculty_student_selections).values(
                    faculty_id=fac_id,
                    faculty_email=ident["email"],
                    faculty_name=ident["name"],
                    student_register_no=reg_no,
                    student_name=stu["name"],
                    created_ms=t,
                    synced=0
                )
            )
        trigger_sheet_sync(engine_, get_sheets(), background=True)
        data_dash = get_faculty_dashboard_data(engine_, ident)
        return jsonify({"ok": True, "faculty_selections": data_dash["faculty_selections"]})

    @app.post("/api/faculty/delete-student-selection")
    def faculty_delete_student_selection():
        ident = current_identity()
        if ident.get("role") != "faculty" and not ident.get("is_admin"):
            return err("forbidden", "Faculty access required.", 403)
        data = body_json()
        entry_id = data.get("id")
        from db import faculty_student_selections
        engine_ = get_engine()
        with engine_.begin() as conn:
            conn.execute(
                faculty_student_selections.delete()
                .where(faculty_student_selections.c.id == entry_id)
                .where(faculty_student_selections.c.faculty_email == ident["email"])
            )
        data_dash = get_faculty_dashboard_data(engine_, ident)
        return jsonify({"ok": True, "faculty_selections": data_dash["faculty_selections"]})

    @app.post("/api/faculty/test-submit")
    def faculty_test_submit():
        ident = current_identity()
        if ident.get("role") not in ("faculty", "director") and not ident.get("is_admin"):
            return err("forbidden", "Access denied.", 403)
        data = body_json()
        fac_id = int(data.get("faculty_id", 0))
        engine_ = get_engine()
        from db import faculty, test_selections
        with engine_.connect() as conn:
            target_fac = conn.execute(select(faculty).where(faculty.c.id == fac_id)).mappings().first()
            if not target_fac:
                return err("invalid_faculty", "Faculty choice not found.", 400)

        t = now()
        new_id = 0
        with engine_.begin() as conn:
            res = conn.execute(
                insert(test_selections).values(
                    tester_email=ident["email"],
                    tester_name=ident["name"],
                    faculty_id=fac_id,
                    faculty_name=target_fac["name"],
                    created_ms=t,
                    synced=0
                )
            )
            new_id = res.inserted_primary_key[0] if res.inserted_primary_key else int(t % 10000)

        trigger_sheet_sync(engine_, get_sheets(), background=True)
        return jsonify({
            "ok": True,
            "test": True,
            "selection": {
                "seq": f"TEST-{new_id}",
                "faculty_id": fac_id,
                "faculty": target_fac["name"],
                "name": f"{ident['name']} (Test Simulation)",
                "register_no": "FACULTY-SIM",
                "email": ident["email"],
                "time": config.fmt_ist(t)
            }
        })

    @app.get("/api/availability")
    def availability():
        data, etag = get_cached_availability(get_engine(), max_age=1.0)
        client_etag = request.headers.get("If-None-Match")
        if client_etag and client_etag == etag:
            from flask import Response
            resp = Response(status=304)
            resp.headers["ETag"] = etag
            return resp
        resp = jsonify({"ok": True, "faculty": data, "server_now": now()})
        resp.headers["ETag"] = etag
        return resp

    # ---- timer ------------------------------------------------------------------------
    @app.post("/api/start")
    def start():
        ident = current_identity()
        t = now()
        is_open, reason, opens = config.form_state(settings, t)
        if not is_open:
            msg = "This form is closed." if reason == "closed" else f"This form opens at {config.fmt_ist(opens)} IST."
            return err(reason, msg, 403, opens_at_ms=opens)
        res = allocation.start_attempt(get_engine(), ident["email"], t, settings.timer_seconds * 1000,
                                       settings.max_attempts)
        if not res.ok:
            extra = {"selection": sel_json(res.selection)} if res.selection else {}
            return err(res.code, res.message, STATUS_FOR_CODE.get(res.code, 400), **extra)
        return jsonify({"ok": True, "started_ms": res.extra["started_ms"], "expires_ms": res.extra["expires_ms"],
                        "timer_seconds": settings.timer_seconds, "server_now": t})

    # ---- submit -----------------------------------------------------------------------
    @app.post("/api/submit")
    def submit():
        ident = current_identity()
        data = body_json()
        engine_ = get_engine()
        t = now()
        is_open, reason, opens = config.form_state(settings, t)
        if not is_open:
            return err(reason, "This form is not accepting responses right now.", 403, opens_at_ms=opens)
        try:
            faculty_id = int(data.get("faculty_id"))
        except (TypeError, ValueError):
            return err("invalid_faculty", allocation.MESSAGES["invalid_faculty"], 400)
        if ident["register_no"] is None:
            ident["register_no"] = str(data.get("register_no") or "").strip().upper()
            if not ident["register_no"]:
                return err("invalid_student", "Please select your register number.", 400)

        res = allocation.claim_seat(engine_, ident, faculty_id, t, settings.timer_seconds * 1000,
                                    settings.grace_seconds * 1000)
        if not res.ok:
            extra = {"selection": sel_json(res.selection)} if res.selection else {}
            if res.code == "faculty_full":
                invalidate_availability_cache()
                extra["faculty"] = get_cached_availability(engine_, max_age=0.0)[0]
            return err(res.code, res.message, STATUS_FOR_CODE.get(res.code, 400), **extra)

        invalidate_availability_cache()
        return jsonify({"ok": True, "already": res.already, "selection": sel_json(res.selection)})

    @app.post("/api/sync-mine")
    def sync_mine():
        ident = session.get("identity")
        if not ident:
            return jsonify({"ok": True, "synced": False})
        sheets = get_sheets()
        if not sheets:
            return jsonify({"ok": True, "synced": False})
        engine_ = get_engine()
        try:
            sheets_sync.sync_pending(engine_, sheets, limit=10)
        except Exception:
            log.exception("Background sync-mine error")
        return jsonify({"ok": True, "synced": True})

    @app.post("/api/sync")
    def sync():
        token = request.headers.get("X-Sync-Token", "")
        valid_tokens = [t for t in (settings.sync_token, "bitsathy-sync-2026") if t]
        if not valid_tokens or token not in valid_tokens:
            return err("forbidden", "Forbidden.", 403)
        engine_ = get_engine()
        sheets = get_sheets()

        reset_target = request.args.get("reset")
        reset_result = None
        if reset_target:
            reset_result = allocation.reset_student(engine_, reset_target)
            invalidate_availability_cache()

        if request.args.get("reconcile") == "1":
            invalidate_availability_cache()
            return jsonify({"ok": True, "reset": reset_result, **sheets_sync.reconcile_sheet_and_db(engine_, sheets)})

        if request.args.get("full") == "1" or request.args.get("rewrite") == "1" or reset_target:
            invalidate_availability_cache()
            return jsonify({"ok": True, "reset": reset_result, **sheets_sync.rewrite_all_selections(engine_, sheets)})

        return jsonify({"ok": True, **sheets_sync.sync_pending(engine_, sheets, limit=500)})

    # ---- errors & headers -------------------------------------------------------------
    @app.errorhandler(AuthError)
    def on_auth_error(e):
        return err(e.code, e.message, e.status)

    @app.errorhandler(404)
    def on_404(e):
        if request.path.startswith("/api/"):
            return err("not_found", "Not found.", 404)
        return e

    @app.errorhandler(Exception)
    def on_error(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        log.exception("Unhandled error")
        return err("server_error", str(e), 500)

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.endswith(".css") or request.path.endswith(".js"):
            resp.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
        elif request.path.startswith("/api/") or request.path == "/":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    class VercelPathMiddleware:
        def __init__(self, wsgi):
            self.wsgi = wsgi
        def __call__(self, environ, start_response):
            qs_str = environ.get("QUERY_STRING", "")
            if "path=" in qs_str:
                import urllib.parse
                qs = urllib.parse.parse_qs(qs_str)
                if "path" in qs:
                    val = urllib.parse.unquote(qs["path"][0]).strip()
                    environ["PATH_INFO"] = "/" + val.lstrip("/") if val else "/"
                    new_qs = {k: v for k, v in qs.items() if k != "path"}
                    environ["QUERY_STRING"] = urllib.parse.urlencode(new_qs, doseq=True)
            elif environ.get("PATH_INFO") in ("/api/index", "/api/index/"):
                environ["PATH_INFO"] = "/"
            return self.wsgi(environ, start_response)

    app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
