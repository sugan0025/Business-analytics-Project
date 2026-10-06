"""Database layer: SQLAlchemy Core. SQLite locally/tests, Postgres on Vercel."""
import csv
import hashlib
import threading

from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Integer, MetaData, String, Table, Text,
    create_engine, event, insert, select, text, update,
)
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.pool import NullPool

from config import BASE_DIR, on_vercel

metadata = MetaData()

faculty = Table(
    "faculty", metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(200), nullable=False),
    Column("capacity", Integer, nullable=False),
    Column("selected_count", Integer, nullable=False, server_default="0"),
    CheckConstraint("selected_count >= 0", name="ck_selected_nonneg"),
    CheckConstraint("selected_count <= capacity", name="ck_selected_le_capacity"),
)

students = Table(
    "students", metadata,
    Column("register_no", String(40), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("email", String(200), unique=True, nullable=True),
)

attempts = Table(
    "attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(200), nullable=False, index=True),
    Column("started_ms", BigInteger, nullable=False),
    Column("status", String(20), nullable=False, server_default="open"),
)

selections = Table(
    "selections", metadata,
    Column("seq_id", Integer, primary_key=True, autoincrement=True),
    Column("register_no", String(40), nullable=False, unique=True),
    Column("email", String(200), nullable=False, unique=True),
    Column("student_name", String(200), nullable=False),
    Column("faculty_id", Integer, ForeignKey("faculty.id"), nullable=False),
    Column("created_ms", BigInteger, nullable=False),
    Column("synced", Integer, nullable=False, server_default="0"),
    Column("sync_error", Text, nullable=True),
    sqlite_autoincrement=True,
)

settings_kv = Table(
    "settings", metadata,
    Column("key", String(100), primary_key=True),
    Column("value", Text, nullable=False),
)


def make_engine(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"timeout": 30, "check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    # Postgres. Serverless: no connection pooling inside the function (use the host's pooled URL).
    kwargs = {"pool_pre_ping": True}
    if on_vercel():
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


def init_schema(engine):
    try:
        metadata.create_all(engine)
    except (OperationalError, ProgrammingError, IntegrityError):
        # Two cold starts racing to create tables: the second just retries.
        metadata.create_all(engine)


# ---- seeding from the CSV config files ------------------------------------

def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _files_hash(faculty_path, roster_path):
    h = hashlib.sha256()
    for p in (faculty_path, roster_path):
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def seed(engine, faculty_path=None, roster_path=None, force=False):
    """Load faculty.csv and roster.csv into the database (idempotent)."""
    faculty_path = faculty_path or BASE_DIR / "faculty.csv"
    roster_path = roster_path or BASE_DIR / "roster.csv"
    digest = _files_hash(faculty_path, roster_path)

    with engine.connect() as conn:
        row = conn.execute(select(settings_kv.c.value).where(settings_kv.c.key == "seed_hash")).first()
    if row and row[0] == digest and not force:
        return False

    fac_rows = _read_csv(faculty_path)
    stu_rows = _read_csv(roster_path)

    emails = [r.get("email", "").lower() for r in stu_rows if r.get("email")]
    if len(emails) != len(set(emails)):
        raise ValueError("roster.csv has duplicate emails")
    regs = [r["register_no"].upper() for r in stu_rows]
    if len(regs) != len(set(regs)):
        raise ValueError("roster.csv has duplicate register numbers")
    total_capacity = sum(int(r["capacity"]) for r in fac_rows)
    if total_capacity < len(stu_rows):
        raise ValueError(f"Total faculty capacity ({total_capacity}) is less than students ({len(stu_rows)})")

    with engine.begin() as conn:
        for r in fac_rows:
            fid, cap = int(r["id"]), int(r["capacity"])
            existing = conn.execute(select(faculty).where(faculty.c.id == fid)).mappings().first()
            if existing is None:
                conn.execute(insert(faculty).values(id=fid, name=r["name"], capacity=cap, selected_count=0))
            else:
                if cap < existing["selected_count"]:
                    raise ValueError(f"Capacity for {r['name']} ({cap}) is below seats already taken "
                                     f"({existing['selected_count']})")
                conn.execute(update(faculty).where(faculty.c.id == fid).values(name=r["name"], capacity=cap))
        for r in stu_rows:
            reg = r["register_no"].upper()
            email = r.get("email", "").lower() or None
            existing = conn.execute(select(students).where(students.c.register_no == reg)).mappings().first()
            if existing is None:
                conn.execute(insert(students).values(register_no=reg, name=r["name"], email=email))
            else:
                conn.execute(update(students).where(students.c.register_no == reg)
                             .values(name=r["name"], email=email))
        conn.execute(text("DELETE FROM settings WHERE key = 'seed_hash'"))
        conn.execute(insert(settings_kv).values(key="seed_hash", value=digest))
    return True


# ---- lazy, once-per-process readiness (serverless friendly) ------------------

_ready_lock = threading.Lock()
_ready_for = set()


def ensure_ready(engine):
    key = str(engine.url)
    if key in _ready_for:
        return
    with _ready_lock:
        if key in _ready_for:
            return
        init_schema(engine)
        seed(engine)
        _ready_for.add(key)


def reset_ready_cache():
    _ready_for.clear()
