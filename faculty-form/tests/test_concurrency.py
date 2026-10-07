"""Many students hitting the database at the same moment."""
import random
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, text

import allocation
import db
from helpers import T0, TIMER_MS, claim, counts, extra_identities, start


def _race(engine, jobs):
    """Run callables simultaneously (released together by a barrier). Returns their results."""
    barrier = threading.Barrier(len(jobs))

    def run(job):
        barrier.wait()
        return job()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(run, jobs))


def test_last_seat_goes_to_exactly_one_of_20(engine, students):
    with engine.begin() as conn:
        conn.execute(text("UPDATE faculty SET capacity = 1 WHERE id = 2"))
    racers = students[:20]
    for s in racers:
        start(engine, s)
    results = _race(engine, [lambda s=s: claim(engine, s, 2) for s in racers])
    assert sum(r.ok for r in results) == 1
    assert sum(r.code == "faculty_full" for r in results) == 19
    fac, n = counts(engine)
    assert fac[2] == (1, 1) and n == 1


def test_100_students_chasing_44_seats_never_overfill(engine, students):
    everyone = students + extra_identities(engine, 56)           # 100 students, 44 seats
    for s in everyone:
        start(engine, s)

    def student(s):
        """Like the real form: look at what's free, pick, retry if someone beat you to it."""
        rng = random.Random(s["email"])
        for _ in range(60):
            open_ids = [f["id"] for f in allocation.availability(engine) if f["remaining"] > 0]
            if not open_ids:
                return None
            res = claim(engine, s, rng.choice(open_ids))
            if res.ok or res.code != "faculty_full":
                return res
        return None

    results = _race(engine, [lambda s=s: student(s) for s in everyone])
    winners = [r for r in results if r is not None and r.ok]
    assert len(winners) == 44
    fac, n = counts(engine)
    assert n == 44
    assert all(sel == cap for sel, cap in fac.values())          # every seat taken, none overfilled
    seqs = sorted(r.selection["seq"] for r in winners)
    assert len(set(seqs)) == 44
    with engine.connect() as conn:                                # counters agree with the actual rows
        for fid, (sel, _) in fac.items():
            rows = conn.execute(select(db.selections).where(db.selections.c.faculty_id == fid)).all()
            assert len(rows) == sel


def test_random_choices_without_retry_stay_within_capacity(engine, students):
    everyone = students + extra_identities(engine, 56)
    for s in everyone:
        start(engine, s)
    rng = random.Random(7)
    picks = [(s, rng.randint(2, 11)) for s in everyone]
    _race(engine, [lambda s=s, f=f: claim(engine, s, f) for s, f in picks])
    fac, n = counts(engine)
    assert all(sel <= cap for sel, cap in fac.values())
    assert n == sum(sel for sel, _ in fac.values())


def test_same_student_ten_simultaneous_submits_make_one_row(engine, students):
    s = students[0]
    start(engine, s)
    results = _race(engine, [lambda: claim(engine, s, 2) for _ in range(10)])
    assert all(r.ok for r in results)                            # all see the same confirmation
    assert len({r.selection["seq"] for r in results}) == 1
    fac, n = counts(engine)
    assert n == 1 and fac[2][0] == 1


def test_same_student_racing_for_two_faculty_gets_only_one(engine, students):
    s = students[0]
    start(engine, s)
    jobs = [lambda f=f: claim(engine, s, f) for f in (2, 3, 4, 5) for _ in range(3)]
    results = _race(engine, jobs)
    assert sum(1 for r in results if r.ok and not r.already) <= 1
    fac, n = counts(engine)
    assert n == 1 and sum(sel for sel, _ in fac.values()) == 1
