"""Database layer: SQLAlchemy Core. SQLite locally/tests, Postgres on Vercel."""
import csv
import hashlib
import logging
import threading

from sqlalchemy import (
    BigInteger, CheckConstraint, Column, ForeignKey, Integer, MetaData, String, Table, Text,
    create_engine, delete, event, func, insert, select, text, update,
)
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.pool import NullPool, QueuePool

from config import BASE_DIR, on_vercel

log = logging.getLogger("faculty-form")

metadata = MetaData()

faculty = Table(
    "faculty", metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(200), nullable=False),
    Column("capacity", Integer, nullable=False),
    Column("selected_count", Integer, nullable=False, server_default="0"),
    Column("email", String(200), nullable=True),
    Column("specialization", String(200), nullable=True),
    CheckConstraint("selected_count >= 0", name="ck_selected_nonneg"),
    CheckConstraint("selected_count <= capacity", name="ck_selected_le_capacity"),
)

FACULTY_SPECIALIZATIONS = {
    2: "HR, Marketing",
    3: "Analytics, Marketing, HR",
    4: "Finance & Marketing",
    5: "Analytics, HR, Marketing",
    6: "Marketing, HR",
    7: "Finance, Marketing",
    8: "Finance, Marketing",
    9: "Finance, Marketing",
    10: "Analytics, Marketing",
    11: "HR & Marketing",
}

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

faculty_student_selections = Table(
    "faculty_student_selections", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("faculty_id", Integer, ForeignKey("faculty.id"), nullable=False),
    Column("faculty_email", String(200), nullable=False),
    Column("faculty_name", String(200), nullable=False),
    Column("student_register_no", String(40), nullable=False),
    Column("student_name", String(200), nullable=False),
    Column("created_ms", BigInteger, nullable=False),
    Column("synced", Integer, nullable=False, server_default="0"),
    Column("sync_error", Text, nullable=True),
    sqlite_autoincrement=True,
)

test_selections = Table(
    "test_selections", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tester_email", String(200), nullable=False),
    Column("tester_name", String(200), nullable=False),
    Column("faculty_id", Integer, ForeignKey("faculty.id"), nullable=False),
    Column("faculty_name", String(200), nullable=False),
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
    # Postgres. Serverless: small QueuePool so warm containers reuse authenticated TLS sockets.
    # We omit pool_pre_ping to avoid an extra SELECT 1 network roundtrip per connection.
    kwargs = {
        "pool_size": 2,
        "max_overflow": 5,
        "pool_recycle": 300,
        "pool_timeout": 10,
    }
    return create_engine(url, **kwargs)


def init_schema(engine):
    try:
        metadata.create_all(engine)
    except Exception:
        try:
            metadata.create_all(engine)
        except Exception:
            pass

    # Migrate email column on faculty table if not present
    try:
        with engine.begin() as conn:
            if "sqlite" in str(engine.url):
                try:
                    conn.execute(text("ALTER TABLE faculty ADD COLUMN email VARCHAR(200)"))
                except Exception:
                    pass
            else:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN IF NOT EXISTS email VARCHAR(200)"))
    except Exception:
        pass

    # Clean up director (id=1) from student faculty table
    try:
        with engine.begin() as conn:
            murug_sels = conn.execute(select(selections).where(selections.c.faculty_id == 1)).mappings().all()
            for s in murug_sels:
                conn.execute(delete(selections).where(selections.c.seq_id == s["seq_id"]))
            conn.execute(delete(faculty).where(faculty.c.id == 1))
    except Exception:
        pass

    # Migrate specialization column on faculty table if not present
    try:
        with engine.begin() as conn:
            if "sqlite" in str(engine.url):
                try:
                    conn.execute(text("ALTER TABLE faculty ADD COLUMN specialization VARCHAR(200)"))
                except Exception:
                    pass
            else:
                conn.execute(text("ALTER TABLE faculty ADD COLUMN IF NOT EXISTS specialization VARCHAR(200)"))
            for fid, spec in FACULTY_SPECIALIZATIONS.items():
                conn.execute(update(faculty).where(faculty.c.id == fid).values(specialization=spec))
    except Exception:
        pass

    # Set target capacity safely: cap cannot be less than current selected_count
    try:
        with engine.begin() as conn:
            for fid, cap in [(2, 4), (3, 4), (10, 4), (11, 2), (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (9, 5)]:
                row = conn.execute(select(faculty.c.selected_count).where(faculty.c.id == fid)).first()
                if row:
                    target = max(cap, row[0])
                    conn.execute(update(faculty).where(faculty.c.id == fid).values(capacity=target))
    except Exception:
        pass

    # Ensure selections are cleanly numbered 1, 2, 3... without gaps
    try:
        resequence_selections(engine)
    except Exception:
        pass


def resequence_selections(engine):
    """Ensure existing selections are numbered 1, 2, 3... sequentially with no gaps."""
    with engine.begin() as conn:
        cur_sels = conn.execute(select(selections).order_by(selections.c.created_ms, selections.c.seq_id)).mappings().all()
        if not cur_sels:
            if "sqlite" not in str(engine.url):
                try:
                    conn.execute(text("SELECT setval(pg_get_serial_sequence('selections', 'seq_id'), 1, false)"))
                except Exception:
                    pass
            return 0
        needs_resequence = any(row["seq_id"] != idx for idx, row in enumerate(cur_sels, start=1))
        if needs_resequence:
            for idx, row in enumerate(cur_sels, start=1):
                conn.execute(update(selections).where(selections.c.seq_id == row["seq_id"]).values(seq_id=-idx))
            for idx, row in enumerate(cur_sels, start=1):
                conn.execute(update(selections).where(selections.c.seq_id == -idx).values(seq_id=idx, synced=0))

        if "sqlite" in str(engine.url):
            try:
                conn.execute(text(f"UPDATE sqlite_sequence SET seq = {len(cur_sels)} WHERE name = 'selections'"))
            except Exception:
                pass
        else:
            try:
                conn.execute(text(f"SELECT setval(pg_get_serial_sequence('selections', 'seq_id'), {len(cur_sels)}, true)"))
            except Exception:
                try:
                    conn.execute(text(f"SELECT setval('selections_seq_id_seq', {len(cur_sels)})"))
                except Exception:
                    pass
    return len(cur_sels)


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

    try:
        with engine.connect() as conn:
            row = conn.execute(select(settings_kv.c.value).where(settings_kv.c.key == "seed_hash")).first()
            fac_cnt = conn.execute(select(func.count()).select_from(faculty)).scalar()
        if row and row[0] == digest and not force and fac_cnt and fac_cnt > 0:
            return False
    except Exception as exc:
        log.warning(f"Seed check error: {exc}")

    fac_rows = _read_csv(faculty_path)
    stu_rows = _read_csv(roster_path)

    emails = [r.get("email", "").lower() for r in stu_rows if r.get("email")]
    if len(emails) != len(set(emails)):
        raise ValueError("roster.csv has duplicate emails")
    regs = [r["register_no"].upper() for r in stu_rows]
    if len(regs) != len(set(regs)):
        raise ValueError("roster.csv has duplicate register numbers")
    total_capacity = sum(int(r["capacity"]) for r in fac_rows)

    with engine.begin() as conn:
        current_fids = [int(r["id"]) for r in fac_rows]
        conn.execute(delete(faculty).where(~faculty.c.id.in_(current_fids), faculty.c.selected_count == 0))
        for r in fac_rows:
            fid, cap = int(r["id"]), int(r["capacity"])
            fac_email = r.get("email", "").strip().lower() or None
            spec = r.get("specialization", "").strip() or FACULTY_SPECIALIZATIONS.get(fid)
            existing = conn.execute(select(faculty).where(faculty.c.id == fid)).mappings().first()
            if existing is None:
                conn.execute(insert(faculty).values(id=fid, name=r["name"], capacity=cap, selected_count=0, email=fac_email, specialization=spec))
            else:
                target_cap = max(cap, existing["selected_count"])
                conn.execute(update(faculty).where(faculty.c.id == fid).values(name=r["name"], capacity=target_cap, email=fac_email, specialization=spec))
        conn.execute(delete(students))
        for r in stu_rows:
            reg = r["register_no"].upper()
            email = r.get("email", "").lower() or None
            conn.execute(insert(students).values(register_no=reg, name=r["name"], email=email))

        # Safely sync any existing selections with the updated roster without register_no conflicts
        cur_sels = conn.execute(select(selections)).mappings().all()
        if cur_sels:
            roster_by_email = {r.get("email", "").lower(): (r["register_no"].upper(), r["name"]) for r in stu_rows if r.get("email")}
            # Temporary prefix to avoid collision on unique register_no
            for s in cur_sels:
                s_email = (s.get("email") or "").lower()
                if s_email in roster_by_email:
                    conn.execute(
                        update(selections)
                        .where(selections.c.seq_id == s["seq_id"])
                        .values(register_no=f"_TMP_{s['seq_id']}")
                    )
            # Final assignment with correct register_no and student_name
            for s in cur_sels:
                s_email = (s.get("email") or "").lower()
                if s_email in roster_by_email:
                    new_reg, new_name = roster_by_email[s_email]
                    conn.execute(
                        update(selections)
                        .where(selections.c.seq_id == s["seq_id"])
                        .values(register_no=new_reg, student_name=new_name, synced=0)
                    )
        try:
            conn.execute(text("DELETE FROM settings WHERE key = 'seed_hash'"))
            conn.execute(insert(settings_kv).values(key="seed_hash", value=digest))
        except Exception:
            pass
    return True


# ---- lazy, once-per-process readiness (serverless friendly) ------------------

_ready_lock = threading.Lock()
_ready_for = set()


def ensure_ready(engine):
    key = str(engine.url)
    if key in _ready_for:
        return False
    with _ready_lock:
        if key in _ready_for:
            return False
        faculty_path = BASE_DIR / "faculty.csv"
        roster_path = BASE_DIR / "roster.csv"
        digest = _files_hash(faculty_path, roster_path)
        # Ultra-fast path: if schema and seed already exist and match current files hash, return immediately
        try:
            with engine.connect() as conn:
                fac_cnt = conn.execute(select(func.count()).select_from(faculty)).scalar()
                hash_row = conn.execute(select(settings_kv.c.value).where(settings_kv.c.key == "seed_hash")).first()
            if fac_cnt and fac_cnt >= 10 and hash_row and hash_row[0] == digest:
                _ready_for.add(key)
                return False
        except Exception:
            pass

        init_schema(engine)
        seeded = seed(engine)
        _ready_for.add(key)
        return bool(seeded)


def reset_ready_cache():
    _ready_for.clear()
