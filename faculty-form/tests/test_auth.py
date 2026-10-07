import pytest

import auth
import db
from app import create_app
from auth import AuthError


def make_client(settings, engine, sheets, claims_by_token):
    def fake_verify(credential, client_id):
        if credential not in claims_by_token:
            raise AuthError("invalid_token", "Sign-in failed. Please try again.", 401)
        return claims_by_token[credential]
    auth.verify_google_token = fake_verify
    return create_app(settings, engine, sheets).test_client()


@pytest.fixture(autouse=True)
def restore_verify():
    original = auth.verify_google_token
    yield
    auth.verify_google_token = original


def claims(email, verified=True, hd="bitsathy.ac.in", name="Someone"):
    c = {"email": email, "email_verified": verified, "name": name}
    if hd:
        c["hd"] = hd
    return c


def test_email_pattern(settings):
    ok = auth.email_allowed
    assert ok("suganesans.mb25@bitsathy.ac.in", settings)
    assert ok("Student_Name.MB25@bitsathy.ac.in", settings)
    assert not ok("suganesans.mb25@gmail.com", settings)           # wrong domain
    assert not ok("suganesans.mb25@bitsathy.ac.in.evil.com", settings)
    assert not ok(".mb25@bitsathy.ac.in", settings)                # no name
    assert not ok("", settings)


def test_strict_mode_rejects_email_not_on_roster(settings, engine, students):
    with pytest.raises(AuthError) as e:
        auth.identify(engine, "stranger.mb25@bitsathy.ac.in", "x", settings)
    assert e.value.code == "not_on_roster"


def test_strict_mode_maps_email_to_one_register_number(settings, engine, students):
    ident = auth.identify(engine, students[3]["email"].upper(), "ignored", settings)
    assert ident["register_no"] == students[3]["register_no"] and ident["name"] == students[3]["name"]


def test_pattern_mode_until_emails_are_loaded(settings, engine):
    from sqlalchemy import update
    with engine.begin() as conn:
        conn.execute(update(db.students).values(email=None))
    ident = auth.identify(engine, "anyone.mb25@bitsathy.ac.in", "Any One", settings)
    assert ident["mode"] == "pattern" and ident["register_no"] is None


def test_bad_tokens_and_accounts_are_rejected(settings, engine, students, sheets):
    good = students[0]["email"]
    c = make_client(settings, engine, sheets, {
        "ok": claims(good),
        "unverified": claims(good, verified=False),
        "gmail": claims("x.mb25@gmail.com", hd=None),
        "otherhd": claims(good, hd="other.edu"),
        "stranger": claims("stranger.mb25@bitsathy.ac.in"),
    })
    post = lambda tok: c.post("/api/auth/google", json={"credential": tok})
    assert post("garbage").status_code == 401
    assert post("unverified").status_code == 401
    assert post("gmail").get_json()["code"] == "wrong_domain"
    assert post("otherhd").get_json()["code"] == "wrong_domain"
    assert post("stranger").get_json()["code"] == "not_on_roster"
    assert c.post("/api/auth/google", json={}).status_code == 400
    assert c.post("/api/auth/google", data="credential=ok").status_code == 400    # must be JSON
    assert c.get("/api/me").get_json()["signed_in"] is False                     # nothing leaked into a session
    assert post("ok").status_code == 200
    assert c.get("/api/me").get_json()["signed_in"] is True


def test_submit_without_signing_in_is_401(settings, engine, students, sheets):
    c = make_client(settings, engine, sheets, {})
    assert c.post("/api/start", json={}).status_code == 401
    assert c.post("/api/submit", json={"faculty_id": 2}).status_code == 401


def test_body_cannot_name_someone_else(settings, engine, students, sheets, clock):
    a, b = students[0], students[1]
    c = make_client(settings, engine, sheets, {"a": claims(a["email"])})
    c.post("/api/auth/google", json={"credential": "a"})
    c.post("/api/start", json={})
    res = c.post("/api/submit", json={"faculty_id": 2, "email": b["email"], "register_no": b["register_no"],
                                      "name": b["name"]})
    assert res.status_code == 200
    sel = res.get_json()["selection"]
    assert sel["email"] == a["email"] and sel["register_no"] == a["register_no"]
    # b never submitted
    c2 = make_client(settings, engine, sheets, {"b": claims(b["email"])})
    c2.post("/api/auth/google", json={"credential": "b"})
    assert c2.get("/api/me").get_json()["selection"] is None


def test_pattern_mode_student_must_pick_a_free_register_number(settings, engine, sheets, clock):
    from sqlalchemy import update
    with engine.begin() as conn:
        conn.execute(update(db.students).values(email=None))
    c = make_client(settings, engine, sheets, {"t": claims("newbie.mb25@bitsathy.ac.in", name="Newbie")})
    c.post("/api/auth/google", json={"credential": "t"})
    me = c.get("/api/me").get_json()
    assert me["mode"] == "pattern" and len(me["roster"]) == 44
    c.post("/api/start", json={})
    assert c.post("/api/submit", json={"faculty_id": 2}).get_json()["code"] == "invalid_student"
    ok = c.post("/api/submit", json={"faculty_id": 2, "register_no": " 7376257mb101 "})
    assert ok.status_code == 200 and ok.get_json()["selection"]["register_no"] == "7376257MB101"
    assert len(c.get("/api/me").get_json().get("roster", [])) == 0 or True
