import allocation
from helpers import GRACE_MS, T0, TIMER_MS, claim, counts, start


def test_submit_inside_the_minute_works(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 1, T0 + 59_000).ok


def test_submit_after_the_minute_is_rejected_and_takes_no_seat(engine, students):
    start(engine, students[0], T0)
    res = claim(engine, students[0], 1, T0 + TIMER_MS + GRACE_MS + 1_000)
    assert not res.ok and res.code == "timer_expired"
    fac, n = counts(engine)
    assert n == 0 and fac[1][0] == 0


def test_small_network_delay_is_forgiven(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 1, T0 + TIMER_MS + 1_500).ok


def test_submit_without_starting_is_rejected(engine, students):
    res = claim(engine, students[0], 1)
    assert not res.ok and res.code == "no_attempt"


def test_reload_resumes_the_same_clock(engine, students):
    a = start(engine, students[0], T0)
    b = start(engine, students[0], T0 + 20_000)
    assert a.extra["started_ms"] == b.extra["started_ms"] == T0
    assert b.extra["expires_ms"] == T0 + TIMER_MS


def test_restart_after_expiry_gives_a_fresh_minute(engine, students):
    start(engine, students[0], T0)
    late = T0 + 90_000
    assert claim(engine, students[0], 1, late).code == "timer_expired"
    fresh = start(engine, students[0], late)
    assert fresh.ok and fresh.extra["started_ms"] == late
    assert claim(engine, students[0], 1, late + 10_000).ok


def test_attempt_limit(engine, students):
    t = T0
    for _ in range(5):
        assert allocation.start_attempt(engine, students[0]["email"], t, TIMER_MS, 5).ok
        t += TIMER_MS + 10_000                      # let it expire
    res = allocation.start_attempt(engine, students[0]["email"], t, TIMER_MS, 5)
    assert not res.ok and res.code == "too_many_attempts"


def test_an_attempt_cannot_be_used_twice(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 1, T0 + 1_000).ok
    allocation.reset_student(engine, students[0]["email"])      # clears attempts too
    assert claim(engine, students[0], 1, T0 + 2_000).code == "no_attempt"
