import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import allocation
from helpers import counts, extra_identities, start_and_claim


def test_seed_matches_requirements(engine):
    fac, _ = counts(engine)
    assert len(fac) == 10
    assert sum(cap for _, cap in fac.values()) == 44
    assert [fac[i][1] for i in range(1, 11)] == [5, 5, 5, 5, 4, 4, 4, 4, 4, 4]


def test_faculty_full_then_rejected_others_still_open(engine, students):
    for s in students[:5]:                       # faculty 1 has 5 seats
        assert start_and_claim(engine, s, 1).ok
    res = start_and_claim(engine, students[5], 1)
    assert not res.ok and res.code == "faculty_full"
    # the student was not recorded and can still pick someone else
    assert start_and_claim(engine, students[5], 2).ok
    fac, n = counts(engine)
    assert fac[1] == (5, 5) and fac[2][0] == 1 and n == 6
    avail = {f["id"]: f["remaining"] for f in allocation.availability(engine)}
    assert avail[1] == 0 and avail[2] == 4


def test_all_44_seats_fill_exactly_and_the_45th_is_rejected(engine, students):
    fac, _ = counts(engine)
    order = [fid for fid, (_, cap) in sorted(fac.items()) for _ in range(cap)]
    for s, fid in zip(students, order):
        assert start_and_claim(engine, s, fid).ok
    fac, n = counts(engine)
    assert n == 44 and all(sel == cap for sel, cap in fac.values())
    extra = extra_identities(engine, 1)[0]
    for fid in range(1, 11):
        res = start_and_claim(engine, extra, fid)
        assert not res.ok and res.code == "faculty_full"
    assert counts(engine)[1] == 44


def test_database_itself_refuses_to_overfill(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE faculty SET selected_count = capacity + 1 WHERE id = 1"))


def test_invalid_faculty(engine, students):
    res = start_and_claim(engine, students[0], 99)
    assert not res.ok and res.code == "invalid_faculty"
