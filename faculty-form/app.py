"""Faculty selection form (Google Form look) - Flask app.

Runs locally (`flask run`) and on Vercel (api/index.py imports `app`).
"""
import logging
import time
from datetime import timedelta

from flask import Flask, jsonify, render_template, request, session
from sqlalchemy import select, text

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
        db.ensure_ready(state["engine"])
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

    def trigger_sheet_sync(engine_, sheets, background=True):
        if sheets is None:
            return
        def _do_sync():
            try:
                sheets_sync.sync_pending(engine_, sheets)
            except Exception:
                log.exception("Sheet sync error")

        if background and not app.testing:
            import threading
            threading.Thread(target=_do_sync, daemon=True).start()
        else:
            _do_sync()

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
        return dict(ident)

    def sel_json(sel):
        return {"seq": sel["seq"], "faculty_id": sel["faculty_id"], "faculty": sel["faculty"],
                "time": config.fmt_ist(sel["created_ms"]), "name": sel["name"],
                "register_no": sel["register_no"], "email": sel["email"]}

    def free_roster(engine_):
        from db import selections, students
        with engine_.connect() as conn:
            rows = conn.execute(
                select(students.c.register_no, students.c.name)
                .where(~students.c.register_no.in_(select(selections.c.register_no)))
                .order_by(students.c.register_no)
            ).all()
        return [{"register_no": r[0], "name": r[1]} for r in rows]

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
        return render_template("index.html", cfg=cfg, title=settings.form_title)

    @app.get("/healthz")
    def healthz():
        info = {"ok": True, "google_signin_configured": bool(settings.google_client_id),
                "sheets_configured": bool(settings.service_account_json or settings.service_account_file),
                "database": "postgres" if not settings.database_url.startswith("sqlite") else "sqlite"}
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            info["database_ok"] = True
        except Exception as exc:
            info.update(ok=False, database_ok=False, error=str(exc)[:200])
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
        return jsonify({"ok": True})

    @app.post("/api/dev-login")
    def dev_login():
        if not settings.dev_login:
            return err("not_found", "Not found.", 404)
        data = body_json()
        identity = auth.identify(get_engine(), data.get("email", ""), data.get("name", ""), settings)
        start_session(identity)
        return jsonify({"ok": True})

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    # ---- state ------------------------------------------------------------------------
    @app.get("/api/me")
    def me():
        t = now()
        is_open, reason, opens = config.form_state(settings, t)
        out = {"ok": True, "signed_in": False, "is_open": is_open, "reason": reason, "opens_at_ms": opens,
               "opens_at": config.fmt_ist(opens) if opens else None, "server_now": t}
        ident = session.get("identity")
        if not ident:
            return jsonify(out)
        engine_ = get_engine()
        with engine_.connect() as conn:
            existing = allocation.get_selection(conn, email=ident["email"])
        out.update(signed_in=True, email=ident["email"], name=ident["name"],
                   register_no=ident["register_no"], mode=ident["mode"], selection=None)
        if existing:
            out["selection"] = sel_json(allocation.selection_view(existing))
        elif ident["register_no"] is None:
            out["roster"] = free_roster(engine_)
        return jsonify(out)

    @app.get("/api/availability")
    def availability():
        t_now = time.time()
        if t_now - _last_sync_time[0] > 10.0:
            _last_sync_time[0] = t_now
            trigger_sheet_sync(get_engine(), get_sheets(), background=True)
        return jsonify({"ok": True, "faculty": allocation.availability(get_engine()), "server_now": now()})

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
        ident = current_identity()          # identity comes from the session, never from the request body
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
        if ident["register_no"] is None:                     # pattern mode: student names their register no.
            ident["register_no"] = str(data.get("register_no") or "").strip().upper()
            if not ident["register_no"]:
                return err("invalid_student", "Please select your register number.", 400)

        res = allocation.claim_seat(engine_, ident, faculty_id, t, settings.timer_seconds * 1000,
                                    settings.grace_seconds * 1000)
        if not res.ok:
            extra = {"selection": sel_json(res.selection)} if res.selection else {}
            if res.code == "faculty_full":
                extra["faculty"] = allocation.availability(engine_)
            return err(res.code, res.message, STATUS_FOR_CODE.get(res.code, 400), **extra)

        # Seat is committed. Mirror to the sheet asynchronously; a failure here never undoes the seat.
        trigger_sheet_sync(engine_, get_sheets(), background=True)
        return jsonify({"ok": True, "already": res.already, "selection": sel_json(res.selection)})

    @app.post("/api/sync")
    def sync():
        token = request.headers.get("X-Sync-Token", "")
        if not settings.sync_token or token != settings.sync_token:
            return err("forbidden", "Forbidden.", 403)
        return jsonify({"ok": True, **sheets_sync.sync_pending(get_engine(), get_sheets(), limit=500)})

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
        msg = str(e) if isinstance(e, RuntimeError) else "Something went wrong. Please try again."
        return err("server_error", msg, 500)

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.startswith("/api/") or request.path == "/":
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
