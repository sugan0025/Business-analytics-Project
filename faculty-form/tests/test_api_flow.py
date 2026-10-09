"""End to end through the HTTP API, the way the page uses it."""
from dataclasses import replace

import auth
import config
from app import create_app
from auth import AuthError


def client_for(settings, engine, sheets, students_by_token):
    def fake_verify(credential, client_id):
        s = students_by_token.get(credential)
        if not s:
            raise AuthError("invalid_token", "bad", 401)
        return {"email": s["email"], "email_verified": True, "hd": "bitsathy.ac.in", "name": s["name"]}
    auth.verify_google_token = fake_verify
    c = create_app(settings, engine, sheets).test_client()
    return c


def sign_in(c, token):
    assert c.post("/api/auth/google", json={"credential": token}).status_code == 200


def test_full_student_journey(settings, engine, students, sheets, clock):
    original = auth.verify_google_token
    try:
        tokens = {f"t{i}": s for i, s in enumerate(students)}
        c = client_for(settings, engine, sheets, tokens)
        sign_in(c, "t0")
        me = c.get("/api/me").get_json()
        assert me["signed_in"] and me["register_no"] == students[0]["register_no"] and me["selection"] is None

        before = {f["id"]: f["remaining"] for f in c.get("/api/availability").get_json()["faculty"]}
        start = c.post("/api/start", json={}).get_json()
        assert start["expires_ms"] - start["started_ms"] == 60_000

        clock.t += 10_000
        res = c.post("/api/submit", json={"faculty_id": 2})
        body = res.get_json()
        assert res.status_code == 200 and body["ok"] and not body["already"]
        assert body["selection"]["faculty"] == "Dr Adhinarayanan B" and body["selection"]["seq"] == 1

        # a retry / double tap shows the same confirmation
        again = c.post("/api/submit", json={"faculty_id": 2}).get_json()
        assert again["ok"] and again["already"] and again["selection"]["seq"] == 1
        # choosing someone else afterwards is refused and shows the original choice
        other = c.post("/api/submit", json={"faculty_id": 3})
        assert other.status_code == 409 and other.get_json()["selection"]["faculty_id"] == 2

        after = {f["id"]: f["remaining"] for f in c.get("/api/availability").get_json()["faculty"]}
        assert after[2] == before[2] - 1 and after[3] == before[3]
        assert c.get("/api/me").get_json()["selection"]["seq"] == 1

        # the page fires non-blocking sync-mine in background
        c.post("/api/sync-mine")

        # the sheet got the row at row seq+1 (row 1 is the header)
        row = sheets.rows[2]
        assert row[0] == 1 and row[2] == students[0]["name"] and row[4] == students[0]["email"]
        assert row[5] == "Dr Adhinarayanan B"
    finally:
        auth.verify_google_token = original


def test_full_faculty_returns_409_with_fresh_availability(settings, engine, students, sheets, clock):
    original = auth.verify_google_token
    try:
        tokens = {f"t{i}": s for i, s in enumerate(students)}
        c = client_for(settings, engine, sheets, tokens)
        for i in range(4):                                   # faculty 2 holds 4
            ci = create_app(settings, engine, sheets).test_client()
            sign_in(ci, f"t{i}")
            ci.post("/api/start", json={})
            assert ci.post("/api/submit", json={"faculty_id": 2}).status_code == 200
        sign_in(c, "t9")
        c.post("/api/start", json={})
        res = c.post("/api/submit", json={"faculty_id": 2})
        body = res.get_json()
        assert res.status_code == 409 and body["code"] == "faculty_full"
        assert {f["id"]: f["remaining"] for f in body["faculty"]}[2] == 0
        # still signed in, still able to choose another faculty
        assert c.post("/api/submit", json={"faculty_id": 6}).status_code == 200
    finally:
        auth.verify_google_token = original


def test_timer_is_enforced_by_the_server(settings, engine, students, sheets, clock):
    original = auth.verify_google_token
    try:
        c = client_for(settings, engine, sheets, {"t0": students[0]})
        sign_in(c, "t0")
        c.post("/api/start", json={})
        clock.t += 70_000                                    # a tampered page keeps the button alive
        res = c.post("/api/submit", json={"faculty_id": 2})
        assert res.status_code == 410 and res.get_json()["code"] == "timer_expired"
        assert c.post("/api/start", json={}).status_code == 200      # restart gives a fresh minute
        assert c.post("/api/submit", json={"faculty_id": 2}).status_code == 200
    finally:
        auth.verify_google_token = original


def test_form_can_be_closed_or_scheduled(settings, engine, students, sheets, clock):
    original = auth.verify_google_token
    try:
        closed = replace(settings, form_closed=True)
        c = client_for(closed, engine, sheets, {"t0": students[0]})
        sign_in(c, "t0")
        assert c.post("/api/start", json={}).status_code == 403
        assert c.post("/api/submit", json={"faculty_id": 2}).status_code == 403

        future = replace(settings, open_at="2023-11-15T10:00:00+05:30")    # after the fake clock
        c = client_for(future, engine, sheets, {"t0": students[0]})
        sign_in(c, "t0")
        me = c.get("/api/me").get_json()
        assert me["is_open"] is False and me["reason"] == "not_open" and me["opens_at_ms"]
        assert c.post("/api/start", json={}).get_json()["code"] == "not_open"
        clock.t = me["opens_at_ms"] + 1000
        assert c.post("/api/start", json={}).status_code == 200
    finally:
        auth.verify_google_token = original


def test_dev_login_only_when_enabled(settings, engine, students, sheets):
    c = create_app(settings, engine, sheets).test_client()
    assert c.post("/api/dev-login", json={"email": students[0]["email"]}).status_code == 404
    dev = create_app(replace(settings, dev_login=True), engine, sheets).test_client()
    assert dev.post("/api/dev-login", json={"email": students[0]["email"]}).status_code == 200


def test_sync_endpoint_needs_the_token(settings, engine, students, sheets):
    c = create_app(settings, engine, sheets).test_client()
    # 1. Unauthenticated request -> rejected 403
    assert c.post("/api/sync").status_code == 403
    # 2. Incorrect token -> rejected 403
    assert c.post("/api/sync", headers={"X-Sync-Token": "wrong"}).status_code == 403
    # 3. Removed hardcoded fallback token -> rejected 403
    assert c.post("/api/sync", headers={"X-Sync-Token": "bitsathy-sync-2026"}).status_code == 403
    # 4. Correct configured token -> accepted 200
    assert c.post("/api/sync", headers={"X-Sync-Token": "sync-secret"}).status_code == 200
    # 5. No configured token -> rejected safely even if token header passed
    c_no_token = create_app(replace(settings, sync_token=""), engine, sheets).test_client()
    assert c_no_token.post("/api/sync", headers={"X-Sync-Token": "sync-secret"}).status_code == 403
    assert c_no_token.post("/api/sync", headers={"X-Sync-Token": "bitsathy-sync-2026"}).status_code == 403


def test_production_secret_key_safety(monkeypatch):
    import os
    import pytest
    monkeypatch.setenv("VERCEL_ENV", "production")
    
    # Missing SECRET_KEY in production raises RuntimeError
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY environment variable is required in production"):
        config.load_settings()

    # Default dev secret in production raises RuntimeError
    monkeypatch.setenv("SECRET_KEY", "dev-only-change-me")
    with pytest.raises(RuntimeError, match="Insecure default SECRET_KEY .* is forbidden in production"):
        config.load_settings()

    # Valid secret in production succeeds
    monkeypatch.setenv("SECRET_KEY", "production-secure-key-1234567890")
    s = config.load_settings()
    assert s.secret_key == "production-secure-key-1234567890"


def test_healthz_and_page(settings, engine, sheets):
    c = create_app(settings, engine, sheets).test_client()
    h = c.get("/healthz").get_json()
    assert h["ok"] and h["database_ok"]
    page = c.get("/")
    assert page.status_code == 200 and b"Faculty Selection" in page.data
    assert c.get("/styles.css").status_code == 200 and c.get("/form.js").status_code == 200


def test_admin_reset_user_authorization(settings, engine, students, sheets):
    original = auth.verify_google_token
    try:
        accounts = {
            "admin": {"email": "murugappans@bitsathy.ac.in", "name": "Dr Murugappan S", "hd": "bitsathy.ac.in"},
            "faculty": {"email": "adhinarayananb@bitsathy.ac.in", "name": "Dr Adhinarayanan B", "hd": "bitsathy.ac.in"},
            "student": students[0],
        }
        def fake_verify(cred, client_id):
            if cred in accounts:
                return {**accounts[cred], "email_verified": True}
            raise AuthError("bad", "bad", 401)
        auth.verify_google_token = fake_verify

        # 1. Student allocates seat
        c_student = create_app(settings, engine, sheets).test_client()
        sign_in(c_student, "student")
        c_student.post("/api/start", json={})
        sub = c_student.post("/api/submit", json={"faculty_id": 2}).get_json()
        assert sub["ok"]

        # 2. Student attempts to reset themselves -> MUST BE 403 FORBIDDEN
        res_self = c_student.post("/api/admin/reset-user", json={
            "register_no": students[0]["register_no"],
            "email": students[0]["email"]
        })
        assert res_self.status_code == 403 and res_self.get_json()["code"] == "forbidden"

        # 3. Faculty attempts to reset student -> MUST BE 403 FORBIDDEN
        c_fac = create_app(settings, engine, sheets).test_client()
        sign_in(c_fac, "faculty")
        res_fac = c_fac.post("/api/admin/reset-user", json={"register_no": students[0]["register_no"]})
        assert res_fac.status_code == 403 and res_fac.get_json()["code"] == "forbidden"

        # 4. Director/Admin resets student -> MUST SUCCEED (200 OK)
        c_admin = create_app(settings, engine, sheets).test_client()
        sign_in(c_admin, "admin")
        res_admin = c_admin.post("/api/admin/reset-user", json={"register_no": students[0]["register_no"]})
        assert res_admin.status_code == 200 and res_admin.get_json()["ok"] is True
        assert res_admin.get_json()["cleared_count"] == 1
    finally:
        auth.verify_google_token = original


def test_admin_reconcile_sheets_authorization(settings, engine, students, sheets):
    original = auth.verify_google_token
    try:
        accounts = {
            "admin": {"email": "murugappans@bitsathy.ac.in", "name": "Dr Murugappan S", "hd": "bitsathy.ac.in"},
            "faculty": {"email": "adhinarayananb@bitsathy.ac.in", "name": "Dr Adhinarayanan B", "hd": "bitsathy.ac.in"},
            "student": students[0],
        }
        def fake_verify(cred, client_id):
            if cred in accounts:
                return {**accounts[cred], "email_verified": True}
            raise AuthError("bad", "bad", 401)
        auth.verify_google_token = fake_verify

        # Student -> 403
        c_student = create_app(settings, engine, sheets).test_client()
        sign_in(c_student, "student")
        assert c_student.post("/api/admin/reconcile-sheets").status_code == 403

        # Faculty -> 403
        c_fac = create_app(settings, engine, sheets).test_client()
        sign_in(c_fac, "faculty")
        assert c_fac.post("/api/admin/reconcile-sheets").status_code == 403

        # Admin -> 200
        c_admin = create_app(settings, engine, sheets).test_client()
        sign_in(c_admin, "admin")
        res_admin = c_admin.post("/api/admin/reconcile-sheets")
        assert res_admin.status_code == 200 and res_admin.get_json()["ok"] is True
    finally:
        auth.verify_google_token = original


def test_admin_reset_database_authorization_and_flow(settings, engine, students, sheets):
    original = auth.verify_google_token
    try:
        accounts = {
            "admin": {"email": "murugappans@bitsathy.ac.in", "name": "Dr Murugappan S", "hd": "bitsathy.ac.in"},
            "faculty": {"email": "adhinarayananb@bitsathy.ac.in", "name": "Dr Adhinarayanan B", "hd": "bitsathy.ac.in"},
            "student": students[0],
        }
        def fake_verify(cred, client_id):
            if cred in accounts:
                return {**accounts[cred], "email_verified": True}
            raise AuthError("bad", "bad", 401)
        auth.verify_google_token = fake_verify

        # 1. Unauthenticated -> 401
        c_unauth = create_app(settings, engine, sheets).test_client()
        assert c_unauth.post("/api/admin/database/reset").status_code == 401

        # 2. Student signs in and selects faculty
        c_stu = create_app(settings, engine, sheets).test_client()
        sign_in(c_stu, "student")
        c_stu.post("/api/start")
        sub_res = c_stu.post("/api/submit", json={"faculty_id": 2, "register_no": students[0]["register_no"]})
        assert sub_res.status_code == 200

        # Student attempts reset -> 403
        assert c_stu.post("/api/admin/database/reset").status_code == 403

        # 3. Faculty attempts reset -> 403
        c_fac = create_app(settings, engine, sheets).test_client()
        sign_in(c_fac, "faculty")
        assert c_fac.post("/api/admin/database/reset").status_code == 403

        # 4. Admin executes reset -> 200
        c_admin = create_app(settings, engine, sheets).test_client()
        sign_in(c_admin, "admin")
        res_reset = c_admin.post("/api/admin/database/reset")
        assert res_reset.status_code == 200
        assert res_reset.get_json()["ok"] is True

        # Verify DB runtime state: selections=0, attempts=0, counts=0
        from sqlalchemy import select, func
        import db
        with engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(db.selections)).scalar() == 0
            assert conn.execute(select(func.count()).select_from(db.attempts)).scalar() == 0
            f2_count = conn.execute(select(db.faculty.c.selected_count).where(db.faculty.c.id == 2)).scalar()
            assert f2_count == 0
            # Roster in DB is untouched
            assert conn.execute(select(func.count()).select_from(db.students)).scalar() == 44

        # 5. Student logs in again and successfully makes a new selection
        c_stu2 = create_app(settings, engine, sheets).test_client()
        sign_in(c_stu2, "student")
        me_data = c_stu2.get("/api/me").get_json()
        assert me_data["selection"] is None
        c_stu2.post("/api/start")
        sub2 = c_stu2.post("/api/submit", json={"faculty_id": 3, "register_no": students[0]["register_no"]})
        assert sub2.status_code == 200
        assert sub2.get_json()["selection"]["faculty_id"] == 3
        assert sub2.get_json()["selection"]["seq"] == 1
    finally:
        auth.verify_google_token = original


def test_admin_edit_student_flow(settings, engine, students, sheets):
    original = auth.verify_google_token
    try:
        def fake_verify(credential, client_id):
            if credential == "admin":
                return {"email": "murugappans@bitsathy.ac.in", "email_verified": True, "hd": "bitsathy.ac.in", "name": "Dr Murugappan"}
            if credential == "student":
                return {"email": students[0]["email"], "email_verified": True, "hd": "bitsathy.ac.in", "name": students[0]["name"]}
            raise AuthError("invalid_token", "bad", 401)

        auth.verify_google_token = fake_verify
        app = create_app(settings, engine, sheets)

        # 1. Unauthenticated / Student cannot save
        c_anon = app.test_client()
        assert c_anon.post("/api/admin/database/students/save", json={"register_no": "TEST", "name": "Test"}).status_code in (401, 403)

        c_stu = app.test_client()
        sign_in(c_stu, "student")
        assert c_stu.post("/api/admin/database/students/save", json={"register_no": "TEST", "name": "Test"}).status_code == 403

        # 2. Student claims a seat first
        c_stu.post("/api/start")
        assert c_stu.post("/api/submit", json={"faculty_id": 2}).status_code == 200

        # 3. Admin edits the student's register number and name
        c_admin = app.test_client()
        sign_in(c_admin, "admin")

        orig_reg = students[0]["register_no"]
        new_reg = orig_reg + "X"
        new_name = students[0]["name"] + " Updated"

        res = c_admin.post("/api/admin/database/students/save", json={
            "old_register_no": orig_reg,
            "register_no": new_reg,
            "name": new_name,
            "email": students[0]["email"],
        })
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

        # 4. Verify DB students and selections table are synchronized
        from sqlalchemy import select
        import db
        with engine.connect() as conn:
            s_row = conn.execute(select(db.students).where(db.students.c.register_no == new_reg)).mappings().first()
            assert s_row is not None
            assert s_row["name"] == new_name

            sel_row = conn.execute(select(db.selections).where(db.selections.c.email == students[0]["email"])).mappings().first()
            assert sel_row is not None
            assert sel_row["register_no"] == new_reg
            assert sel_row["student_name"] == new_name

        # 5. Duplicate checks
        dup = c_admin.post("/api/admin/database/students/save", json={
            "old_register_no": students[1]["register_no"],
            "register_no": new_reg,
            "name": "Another",
            "email": "another.mb25@bitsathy.ac.in",
        })
        assert dup.status_code == 400 and dup.get_json()["code"] == "duplicate_reg"
    finally:
        auth.verify_google_token = original

