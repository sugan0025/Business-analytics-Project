from sqlalchemy import insert, select, update

import allocation
import db

T0 = 1_700_000_000_000
TIMER_MS = 60_000
GRACE_MS = 2_000


def give_emails(engine):
    """Give every roster student an email (switches the app to strict mode). Returns identities."""
    ids = []
    with engine.begin() as conn:
        rows = conn.execute(select(db.students).order_by(db.students.c.register_no)).mappings().all()
        for i, r in enumerate(rows):
            email = f"s{i}.mb25@bitsathy.ac.in"
            conn.execute(update(db.students).where(db.students.c.register_no == r["register_no"]).values(email=email))
            ids.append({"email": email, "name": r["name"], "register_no": r["register_no"], "mode": "strict"})
    return ids


def extra_identities(engine, n, start=0):
    """Add n more students (beyond the 44) so we can test being over capacity."""
    ids = []
    with engine.begin() as conn:
        for i in range(start, start + n):
            reg, email = f"EXTRA{i:03d}", f"x{i}.mb25@bitsathy.ac.in"
            conn.execute(insert(db.students).values(register_no=reg, name=f"Extra {i}", email=email))
            ids.append({"email": email, "name": f"Extra {i}", "register_no": reg, "mode": "strict"})
    return ids


def start(engine, ident, t=T0):
    return allocation.start_attempt(engine, ident["email"], t, TIMER_MS, 5)


def claim(engine, ident, faculty_id, t=T0 + 1_000):
    return allocation.claim_seat(engine, ident, faculty_id, t, TIMER_MS, GRACE_MS)


def start_and_claim(engine, ident, faculty_id, t=T0):
    start(engine, ident, t)
    return claim(engine, ident, faculty_id, t + 1_000)


def counts(engine):
    """(selected_count per faculty, number of selection rows)."""
    with engine.connect() as conn:
        fac = {r["id"]: (r["selected_count"], r["capacity"]) for r in conn.execute(select(db.faculty)).mappings()}
        n = len(conn.execute(select(db.selections.c.seq_id)).all())
    return fac, n


class FakeSheets:
    """Stands in for the Google Sheets client. `rows` maps sheet row number -> values."""

    def __init__(self):
        self.rows = {}
        self.fail = False
        self.calls = 0

    def write_rows(self, rows):
        self.calls += 1
        if self.fail:
            raise RuntimeError("sheets down")
        for n, vals in rows:
            self.rows[n] = vals

    def clear_rows(self, row_numbers):
        for n in row_numbers:
            self.rows.pop(n, None)
