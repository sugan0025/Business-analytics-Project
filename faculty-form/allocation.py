"""FCFS seat allocation. The database decides who gets a seat.

Safety comes from three things working together (identical on SQLite and Postgres):
  1. A conditional UPDATE (`selected_count < capacity`) that only one concurrent request can win per seat.
  2. UNIQUE constraints on selections (email, register_no): a student can only ever hold one seat.
  3. A CHECK constraint (`selected_count <= capacity`) as a last-resort guard.
All writes happen in a single transaction, so a failure anywhere gives the seat back.
"""
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from db import attempts, faculty, selections, students


@dataclass
class Result:
    ok: bool
    code: str = ""
    message: str = ""
    selection: Optional[dict] = None
    already: bool = False
    extra: dict = field(default_factory=dict)


class _Abort(Exception):
    def __init__(self, code):
        self.code = code


MESSAGES = {
    "faculty_full": "This faculty just filled up. Please choose another.",
    "already_submitted": "You have already submitted your selection.",
    "register_taken": "This register number has already been used.",
    "timer_expired": "Time's up. Please start again.",
    "no_attempt": "Please start the form first.",
    "invalid_faculty": "That faculty does not exist.",
    "invalid_student": "Register number not found on the class list.",
    "too_many_attempts": "Too many attempts. Please contact your coordinator.",
}


def _fail(code, **extra):
    return Result(False, code, MESSAGES.get(code, code), extra=extra)


def get_selection(conn, email=None, register_no=None):
    cond = []
    if email:
        cond.append(selections.c.email == email)
    if register_no:
        cond.append(selections.c.register_no == register_no)
    if not cond:
        return None
    from sqlalchemy import or_
    row = conn.execute(
        select(selections, faculty.c.name.label("faculty_name"))
        .join(faculty, faculty.c.id == selections.c.faculty_id)
        .where(or_(*cond))
    ).mappings().first()
    return dict(row) if row else None


def selection_view(row):
    return {
        "seq": row["seq_id"],
        "faculty_id": row["faculty_id"],
        "faculty": row["faculty_name"],
        "created_ms": row["created_ms"],
        "register_no": row["register_no"],
        "name": row["student_name"],
        "email": row["email"],
    }


def availability(engine):
    from db import FACULTY_SPECIALIZATIONS
    with engine.connect() as conn:
        rows = conn.execute(select(faculty).where(faculty.c.id != 1).order_by(faculty.c.id)).mappings().all()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "capacity": r["capacity"],
            "specialization": r.get("specialization") or FACULTY_SPECIALIZATIONS.get(r["id"], ""),
            "remaining": max(r["capacity"] - r["selected_count"], 0)
        }
        for r in rows
    ]


# ---- attempts (the 60-second timer) -------------------------------------------

def start_attempt(engine_or_conn, email, now_ms, timer_ms, max_attempts):
    """Open (or resume) a timed attempt. Reloading the page never resets the clock."""
    from sqlalchemy.engine import Connection

    def _run(conn):
        if get_selection(conn, email=email):
            return _fail("already_submitted")
        open_row = conn.execute(
            select(attempts).where(attempts.c.email == email, attempts.c.status == "open")
            .order_by(attempts.c.id.desc())
        ).mappings().first()
        if open_row and open_row["started_ms"] + timer_ms >= now_ms:
            return Result(True, extra={"started_ms": open_row["started_ms"],
                                       "expires_ms": open_row["started_ms"] + timer_ms})
        used = conn.execute(select(func.count()).select_from(attempts).where(attempts.c.email == email)).scalar()
        if used >= max_attempts:
            return _fail("too_many_attempts")
        conn.execute(update(attempts).where(attempts.c.email == email, attempts.c.status == "open")
                     .values(status="expired"))
        conn.execute(insert(attempts).values(email=email, started_ms=now_ms, status="open"))
        conn.commit()
        return Result(True, extra={"started_ms": now_ms, "expires_ms": now_ms + timer_ms})

    if isinstance(engine_or_conn, Connection):
        return _run(engine_or_conn)
    with engine_or_conn.connect() as conn:
        return _run(conn)


# ---- the seat claim ---------------------------------------------------------------

def claim_seat(engine, identity, faculty_id, now_ms, timer_ms, grace_ms=2000):
    """Claim one seat for `identity` ({email, name, register_no}) with `faculty_id`."""
    email = identity["email"]
    register_no = identity["register_no"]
    window_ms = timer_ms + grace_ms

    with engine.begin() as conn:
        existing = get_selection(conn, email=email, register_no=register_no)
        if existing:
            return _existing_result(existing, email, faculty_id)
        fac = conn.execute(select(faculty).where(faculty.c.id == faculty_id)).mappings().first()
        if fac is None:
            return _fail("invalid_faculty")
        student = conn.execute(select(students).where(students.c.register_no == register_no)).mappings().first()
        if student is None:
            return _fail("invalid_student")
        attempt = conn.execute(
            select(attempts).where(attempts.c.email == email, attempts.c.status == "open")
            .order_by(attempts.c.id.desc())
        ).mappings().first()
        if attempt is None:
            ins = conn.execute(insert(attempts).values(email=email, started_ms=now_ms, status="open"))
            att_id = ins.inserted_primary_key[0] if ins.inserted_primary_key else 1
            attempt = {"id": att_id, "started_ms": now_ms, "status": "open"}
        elif timer_ms > 0 and timer_ms < 86400000 and now_ms > attempt["started_ms"] + window_ms:
            conn.execute(update(attempts).where(attempts.c.id == attempt["id"]).values(status="expired"))
            return _fail("timer_expired")

        # 1) take the seat: only succeeds while seats remain
        taken = conn.execute(
            update(faculty)
            .where(faculty.c.id == faculty_id, faculty.c.selected_count < faculty.c.capacity)
            .values(selected_count=faculty.c.selected_count + 1)
        )
        if taken.rowcount != 1:
            return _fail("faculty_full")

        # 2) record the selection (unique email / register_no)
        try:
            res = conn.execute(insert(selections).values(
                register_no=register_no, email=email, student_name=student["name"],
                faculty_id=faculty_id, created_ms=now_ms, synced=0))
        except IntegrityError:
            existing = get_selection(conn, email=email, register_no=register_no)
            if existing:
                return _existing_result(existing, email, faculty_id)
            return _fail("already_submitted")
        seq_id = res.inserted_primary_key[0]

        # 3) burn the attempt atomically
        conn.execute(
            update(attempts)
            .where(attempts.c.id == attempt["id"], attempts.c.status == "open")
            .values(status="used")
        )

        return Result(True, selection={
            "seq": seq_id, "faculty_id": faculty_id, "faculty": fac["name"], "created_ms": now_ms,
            "register_no": register_no, "name": student["name"], "email": email,
        })


def _existing_result(existing, email, faculty_id):
    view = selection_view(existing)
    if existing["email"] == email:
        if existing["faculty_id"] == faculty_id:
            return Result(True, selection=view, already=True)       # double tap / retry
        return Result(False, "already_submitted", MESSAGES["already_submitted"], selection=view)
    return _fail("register_taken")


# ---- admin helpers (used by manage.py) -------------------------------------------------

def reset_student(engine, key):
    """Free a student's seat. `key` = register number or email. Returns the removed selection or None."""
    key = key.strip()
    with engine.begin() as conn:
        row = conn.execute(
            select(selections).where((selections.c.register_no == key.upper()) | (selections.c.email == key.lower()))
        ).mappings().first()
        if row is None:
            return None
        conn.execute(delete(selections).where(selections.c.seq_id == row["seq_id"]))
        conn.execute(update(faculty).where(faculty.c.id == row["faculty_id"], faculty.c.selected_count > 0)
                     .values(selected_count=faculty.c.selected_count - 1))
        conn.execute(delete(attempts).where(attempts.c.email == row["email"]))
        return dict(row)
