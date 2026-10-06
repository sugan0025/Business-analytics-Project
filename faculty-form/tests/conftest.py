from dataclasses import replace

import pytest

import config
import db
from helpers import FakeSheets, give_emails


@pytest.fixture
def settings(tmp_path):
    base = config.load_settings()
    return replace(
        base, database_url=f"sqlite:///{tmp_path / 'test.db'}", google_client_id="test-client",
        secret_key="test-secret", dev_login=False, service_account_json="", service_account_file="",
        open_at="", form_closed=False, timer_seconds=60, max_attempts=5, grace_seconds=2,
        email_domain="bitsathy.ac.in", email_local_suffix=".mb25", sync_token="sync-secret",
    )


@pytest.fixture
def engine(settings):
    db.reset_ready_cache()
    eng = db.make_engine(settings.database_url)
    db.init_schema(eng)
    db.seed(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def students(engine):
    """44 roster students with emails (strict mode)."""
    return give_emails(engine)


@pytest.fixture
def sheets():
    return FakeSheets()


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        t = 1_700_000_000_000
    monkeypatch.setattr(config, "now_ms", lambda: Clock.t)
    return Clock
