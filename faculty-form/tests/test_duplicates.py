import allocation
import db
from helpers import T0, claim, counts, start, start_and_claim


def test_same_faculty_twice_is_idempotent(engine, students):
    s = students[0]
    first = start_and_claim(engine, s, 3)
    again = claim(engine, s, 3, T0 + 5_000)
    assert first.ok and again.ok and again.already
    assert again.selection["seq"] == first.selection["seq"]
    fac, n = counts(engine)
    assert n == 1 and fac[3][0] == 1


def test_different_faculty_after_submitting_is_rejected(engine, students):
    s = students[0]
    assert start_and_claim(engine, s, 3).ok
    res = claim(engine, s, 4, T0 + 5_000)
    assert not res.ok and res.code == "already_submitted"
    assert res.selection["faculty_id"] == 3          # shows the original choice
    fac, n = counts(engine)
    assert n == 1 and fac[3][0] == 1 and fac[4][0] == 0


def test_register_number_cannot_be_reused_by_another_email(engine, students):
    a = students[0]
    assert start_and_claim(engine, a, 2).ok
    thief = {**students[1], "register_no": a["register_no"]}   # different email, same register no.
    start(engine, thief)
    res = claim(engine, thief, 3)
    assert not res.ok and res.code == "register_taken"
    assert counts(engine)[1] == 1


def test_start_after_submit_is_blocked(engine, students):
    s = students[0]
    assert start_and_claim(engine, s, 2).ok
    res = allocation.start_attempt(engine, s["email"], T0 + 10_000, 60_000, 5)
    assert not res.ok and res.code == "already_submitted"


def test_reset_frees_exactly_one_seat(engine, students):
    for s in students[:3]:
        assert start_and_claim(engine, s, 2).ok
    removed = allocation.reset_student(engine, students[1]["register_no"])
    assert removed["email"] == students[1]["email"]
    fac, n = counts(engine)
    assert n == 2 and fac[2][0] == 2
    assert start_and_claim(engine, students[1], 3).ok       # can choose again
    assert allocation.reset_student(engine, "NOPE") is None


def test_duplicate_submission_transaction_safety_and_no_seat_consumed(engine, students):
    s = students[0]
    # First successful allocation
    first = start_and_claim(engine, s, 2)
    assert first.ok
    assert first.selection["faculty_id"] == 2

    # Duplicate submission to a different faculty
    second = claim(engine, s, 3, T0 + 5_000)
    assert not second.ok
    assert second.code == "already_submitted"
    assert second.selection["faculty_id"] == 2

    # Verify no seat was consumed from faculty 3
    fac, n = counts(engine)
    assert fac[3][0] == 0       # faculty 3 has 0 students
    assert fac[2][0] == 1       # faculty 2 has 1 student
    assert n == 1               # total 1 selection in DB

    # Verify transaction can execute further operations without being aborted
    from sqlalchemy import select
    with engine.connect() as conn:
        res = conn.execute(select(db.faculty.c.name).where(db.faculty.c.id == 2)).scalar()
        assert res == "Dr Adhinarayanan B"
