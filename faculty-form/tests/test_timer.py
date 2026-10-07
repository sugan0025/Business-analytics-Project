import allocation
from helpers import GRACE_MS, T0, TIMER_MS, claim, counts, start


def test_submit_inside_the_minute_works(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 2, T0 + 59_000).ok


def test_submit_after_the_minute_is_rejected_and_takes_no_seat(engine, students):
    start(engine, students[0], T0)
    res = claim(engine, students[0], 2, T0 + TIMER_MS + GRACE_MS + 1_000)
    assert not res.ok and res.code == "timer_expired"
    fac, n = counts(engine)
    assert n == 0 and fac[2][0] == 0


def test_small_network_delay_is_forgiven(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 2, T0 + TIMER_MS + 1_500).ok


def test_submit_with_expired_attempt_is_rejected(engine, students):
    start(engine, students[0], T0)
    res = claim(engine, students[0], 2, T0 + TIMER_MS + GRACE_MS + 5_000)
    assert not res.ok and res.code == "timer_expired"


def test_reload_resumes_the_same_clock(engine, students):
    a = start(engine, students[0], T0)
    b = start(engine, students[0], T0 + 20_000)
    assert a.extra["started_ms"] == b.extra["started_ms"] == T0
    assert b.extra["expires_ms"] == T0 + TIMER_MS


def test_restart_after_expiry_gives_a_fresh_minute(engine, students):
    start(engine, students[0], T0)
    late = T0 + 90_000
    assert claim(engine, students[0], 2, late).code == "timer_expired"
    fresh = start(engine, students[0], late)
    assert fresh.ok and fresh.extra["started_ms"] == late
    assert claim(engine, students[0], 2, late + 10_000).ok


def test_attempt_limit(engine, students):
    t = T0
    for _ in range(5):
        assert allocation.start_attempt(engine, students[0]["email"], t, TIMER_MS, 5).ok
        t += TIMER_MS + 10_000                      # let it expire
    res = allocation.start_attempt(engine, students[0]["email"], t, TIMER_MS, 5)
    assert not res.ok and res.code == "too_many_attempts"


def test_an_attempt_cannot_be_used_twice(engine, students):
    start(engine, students[0], T0)
    assert claim(engine, students[0], 2, T0 + 1_000).ok
    # Attempting to claim another faculty with the used attempt/existing selection is rejected
    assert claim(engine, students[0], 3, T0 + 2_000).code == "already_submitted"
