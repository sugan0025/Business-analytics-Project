"""Google Sign-In verification and roster matching."""
import re

from sqlalchemy import func, select

from db import students


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 403):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


_google_request = None


def _get_google_request():
    global _google_request
    if _google_request is None:
        from google.auth.transport import requests as g_requests
        _google_request = g_requests.Request()
    return _google_request


def verify_google_token(credential: str, client_id: str) -> dict:
    """Verify a Google ID token (signature, audience, expiry). Returns the claims."""
    if not client_id:
        raise AuthError("not_configured", "Google Sign-In is not configured on the server.", 500)
    from google.oauth2 import id_token
    try:
        return id_token.verify_oauth2_token(credential, _get_google_request(), client_id)
    except ValueError:
        raise AuthError("invalid_token", "Sign-in failed. Please try again.", 401)


def email_allowed(email: str, settings) -> bool:
    """college pattern: <name>.mb25@<domain>"""
    email = (email or "").strip().lower()
    local, _, domain = email.partition("@")
    if domain != settings.email_domain:
        return False
    suffix = settings.email_local_suffix
    if not local.endswith(suffix) or len(local) <= len(suffix):
        return False
    return re.fullmatch(r"[a-z0-9_][a-z0-9_.\-]*", local) is not None


def roster_mode(engine) -> str:
    """'strict' once any roster row has an email, else 'pattern'."""
    with engine.connect() as conn:
        n = conn.execute(select(func.count()).select_from(students).where(students.c.email.is_not(None))).scalar()
    return "strict" if n else "pattern"


def identify(engine, email: str, display_name: str, settings) -> dict:
    """Turn a verified email into a session identity, or raise AuthError."""
    email = (email or "").strip().lower()
    if not email_allowed(email, settings):
        raise AuthError(
            "wrong_domain",
            f"Please sign in with your college email (name{settings.email_local_suffix}@{settings.email_domain}).",
        )
    with engine.connect() as conn:
        row = conn.execute(select(students).where(students.c.email == email)).mappings().first()
    if row is not None:
        return {"email": email, "name": row["name"], "register_no": row["register_no"], "mode": "strict"}
    mode = roster_mode(engine)
    if mode == "strict":
        raise AuthError("not_on_roster", "This email is not on the class list. Contact your coordinator.")
    return {"email": email, "name": display_name or email.split("@")[0], "register_no": None, "mode": mode}


def identity_from_google(engine, credential: str, settings) -> dict:
    claims = verify_google_token(credential, settings.google_client_id)
    if not claims.get("email_verified"):
        raise AuthError("unverified", "Your Google email is not verified.", 401)
    hd = claims.get("hd")
    if hd and hd.lower() != settings.email_domain:
        raise AuthError("wrong_domain", "Please sign in with your college Google account.")
    return identify(engine, claims.get("email", ""), claims.get("name", ""), settings)
