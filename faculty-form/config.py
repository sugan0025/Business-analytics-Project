"""Settings, read from environment variables at call time (so tests can change them)."""
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))


def _load_dotenv():
    """Tiny .env loader for local runs (no extra dependency). Real env vars win."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def on_vercel():
    return bool(os.environ.get("VERCEL"))


def is_production():
    return os.environ.get("VERCEL_ENV") == "production"


@dataclass(frozen=True)
class Settings:
    secret_key: str
    database_url: str
    google_client_id: str
    sheet_id: str
    service_account_json: str
    service_account_file: str
    email_domain: str
    email_local_suffix: str
    timer_seconds: int
    max_attempts: int
    grace_seconds: int
    open_at: str
    form_closed: bool
    form_title: str
    form_description: str
    sync_token: str
    dev_login: bool
    session_minutes: int
    responses_tab: str
    summary_tab: str
    secure_cookies: bool
    roster_file: str = ""


def normalize_db_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def load_settings() -> Settings:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or ""
    if not db_url:
        db_url = f"sqlite:///{BASE_DIR / 'faculty.db'}"
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        if is_production():
            raise RuntimeError("SECRET_KEY environment variable is required in production.")
        secret_key = "dev-only-change-me"
    elif is_production() and secret_key == "dev-only-change-me":
        raise RuntimeError("Insecure default SECRET_KEY ('dev-only-change-me') is forbidden in production.")

    return Settings(
        secret_key=secret_key,
        database_url=normalize_db_url(db_url),
        google_client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        sheet_id=os.environ.get("GOOGLE_SHEET_ID", "1n6X-h_8SkutNImAgkLsbxogW5Qz8yD6-Z8SyhiNp2BI").strip(),
        service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip(),
        service_account_file=os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip(),
        email_domain=os.environ.get("ALLOWED_EMAIL_DOMAIN", "bitsathy.ac.in").strip().lower(),
        email_local_suffix=os.environ.get("EMAIL_LOCAL_SUFFIX", ".mb25").strip().lower(),
        timer_seconds=_int("TIMER_SECONDS", 60),
        max_attempts=_int("MAX_ATTEMPTS", 50),
        grace_seconds=_int("GRACE_SECONDS", 2),
        open_at=os.environ.get("OPEN_AT", "").strip(),
        form_closed=_flag("FORM_CLOSED"),
        form_title=os.environ.get("FORM_TITLE", "Faculty Selection - II MBA").strip(),
        form_description=os.environ.get(
            "FORM_DESCRIPTION",
            "Select one faculty member. Seats are allotted strictly first come, first served.",
        ).strip(),
        sync_token=os.environ.get("SYNC_TOKEN", "").strip(),
        dev_login=_flag("DEV_LOGIN") and not is_production(),
        session_minutes=_int("SESSION_MINUTES", 30),
        responses_tab=os.environ.get("RESPONSES_TAB", "Responses"),
        summary_tab=os.environ.get("SUMMARY_TAB", "Summary"),
        secure_cookies=on_vercel(),
        roster_file=os.environ.get("ROSTER_FILE", "").strip(),
    )


# ---- time helpers -------------------------------------------------------

def now_ms() -> int:
    return int(time.time() * 1000)


def fmt_ist(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=IST).strftime("%Y-%m-%d %H:%M:%S")


def open_at_ms(settings: Settings):
    """Parse OPEN_AT to epoch ms. Naive values are treated as IST. None if unset/invalid."""
    if not settings.open_at:
        return None
    try:
        dt = datetime.fromisoformat(settings.open_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return int(dt.timestamp() * 1000)


def form_state(settings: Settings, now: int):
    """Return (is_open, reason, opens_at_ms)."""
    if settings.form_closed:
        return False, "closed", None
    opens = open_at_ms(settings)
    if opens is not None and now < opens:
        return False, "not_open", opens
    return True, "open", opens
