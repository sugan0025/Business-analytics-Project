"""Google Sign-In verification, faculty authentication, and student roster matching."""
import re

from sqlalchemy import func, select

from db import faculty, students


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 403):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


_google_request = None

DIRECTOR_EMAILS = {"murugappans@bitsathy.ac.in"}
ADMIN_EMAILS = {"murugappans@bitsathy.ac.in", "suganeshs@bitsathy.ac.in", "suganesans.mb25@bitsathy.ac.in"}

DEFAULT_FACULTY_MAP = {
    "adhinarayananb@bitsathy.ac.in": 2,
    "satheeshkumart@bitsathy.ac.in": 3,
    "senthilkumar@bitsathy.ac.in": 4,
    "nandhinib@bitsathy.ac.in": 5,
    "mageswaran@bitsathy.ac.in": 6,
    "dhanabalusn@bitsathy.ac.in": 7,
    "saranyasms@bitsathy.ac.in": 8,
    "aishwariya@bitsathy.ac.in": 9,
    "suganeshs@bitsathy.ac.in": 10,
    "saraswathic@bitsathy.ac.in": 11,
}


_certs_cache = {"data": None, "expires_at": 0.0}
_session = None


class _CachedResponse:
    def __init__(self, data):
        self.status = 200
        self.data = data
        self.headers = {}


def _get_google_request():
    global _google_request, _session
    if _google_request is None:
        import time
        import requests
        from google.auth.transport import requests as g_requests

        class CachedGoogleRequest(g_requests.Request):
            def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
                if method.upper() == "GET" and "googleapis.com" in url and "certs" in url:
                    now = time.time()
                    if _certs_cache["data"] is not None and now < _certs_cache["expires_at"]:
                        return _CachedResponse(_certs_cache["data"])
                    resp = super().__call__(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
                    if resp.status == 200 and resp.data:
                        _certs_cache["data"] = resp.data
                        _certs_cache["expires_at"] = now + 21600  # Cache for 6 hours (matching Google's Cache-Control)
                    return resp
                return super().__call__(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)

        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=2)
        _session.mount("https://", adapter)
        _google_request = CachedGoogleRequest(session=_session)
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


def get_faculty_info(engine, email: str):
    """Return faculty dict for an email, or None."""
    email = (email or "").strip().lower()
    try:
        with engine.connect() as conn:
            # 1. Match email column in faculty table
            row = conn.execute(select(faculty).where(func.lower(faculty.c.email) == email)).mappings().first()
            if row is not None:
                return dict(row)
            # 2. Match DEFAULT_FACULTY_MAP fallback
            fid = DEFAULT_FACULTY_MAP.get(email)
            if fid is not None:
                row = conn.execute(select(faculty).where(faculty.c.id == fid)).mappings().first()
                if row is not None:
                    return dict(row)
    except Exception:
        pass
    return None


def email_allowed(email: str, settings) -> bool:
    """College pattern: director, faculty or student <name>.mb25@<domain>"""
    email = (email or "").strip().lower()
    local, _, domain = email.partition("@")
    if domain != settings.email_domain:
        return False
    # Director or known faculty or college staff without student suffix
    if email in DIRECTOR_EMAILS or email in DEFAULT_FACULTY_MAP or not local.endswith(settings.email_local_suffix):
        return True
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
    local, _, domain = email.partition("@")
    if domain != settings.email_domain:
        raise AuthError(
            "wrong_domain",
            f"Please sign in with your college email (@{settings.email_domain}).",
        )

    # 1. Director Identification
    if email in DIRECTOR_EMAILS:
        return {
            "role": "director",
            "is_admin": True,
            "email": email,
            "name": "Dr Murugappan S (Director)",
            "faculty_id": None,
            "capacity": 0,
            "register_no": None,
            "mode": "director",
        }

    # 2. Faculty Identification
    is_admin = email in ADMIN_EMAILS
    fac = get_faculty_info(engine, email)
    if fac is not None:
        return {
            "role": "faculty",
            "is_admin": is_admin,
            "email": email,
            "name": fac["name"],
            "faculty_id": fac["id"],
            "capacity": fac["capacity"],
            "register_no": None,
            "mode": "faculty",
        }

    # If college account is staff/faculty whose email is not yet bound to a specific faculty id
    if not local.endswith(settings.email_local_suffix):
        clean_name = display_name or local.replace(".", " ").title()
        return {
            "role": "faculty",
            "is_admin": is_admin,
            "email": email,
            "name": clean_name,
            "faculty_id": None,
            "capacity": 0,
            "register_no": None,
            "mode": "faculty",
        }

    # 3. Student Identification
    with engine.connect() as conn:
        row = conn.execute(select(students).where(students.c.email == email)).mappings().first()
    if row is not None:
        is_admin = (email in ADMIN_EMAILS) or (row["register_no"] == "7376257MB144")
        return {
            "role": "student",
            "is_admin": is_admin,
            "email": email,
            "name": row["name"],
            "register_no": row["register_no"],
            "mode": "strict",
        }
    mode = roster_mode(engine)
    if mode == "strict":
        raise AuthError("not_on_roster", "This email is not on the class list. Contact your coordinator.")
    is_admin = (email in ADMIN_EMAILS) or (email.startswith("suganesans.mb25"))
    return {
        "role": "student",
        "is_admin": is_admin,
        "email": email,
        "name": display_name or email.split("@")[0],
        "register_no": None,
        "mode": mode,
    }


def identity_from_google(engine, credential: str, settings) -> dict:
    claims = verify_google_token(credential, settings.google_client_id)
    if not claims.get("email_verified"):
        raise AuthError("unverified", "Your Google email is not verified.", 401)
    hd = claims.get("hd")
    if hd and hd.lower() != settings.email_domain:
        raise AuthError("wrong_domain", "Please sign in with your college Google account.")
    return identify(engine, claims.get("email", ""), claims.get("name", ""), settings)
