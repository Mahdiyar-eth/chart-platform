"""Pytest fixtures — temp SQLite per run (NEVER prod Postgres).

IMPORTANT: DATABASE_URL must be set BEFORE app.db is imported anywhere,
otherwise tests hit the production Postgres. conftest loads first, so
setting it here (before any app import) is sufficient.
"""
import os
import sys
from pathlib import Path

_TMP_DB = "chart_platform_test"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["PUBLIC_BASE_URL"] = "http://127.0.0.1:8767"
os.environ["ENRICH_INSIGHTS"] = "0"  # no LLM calls in tests — deterministic fallback only
os.environ["RATE_LIMIT_BACKEND"] = "memory"  # tests stay hermetic (no shared Redis keys)
os.environ["APP_ENV"] = "development"        # tests run in dev mode — prod fail-closed gates off
os.environ["CREATE_ALL_ON_BOOT"] = "1"       # tests build schema via create_all (no Alembic in CI)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.db import engine, init_db
from app.models import BotState  # noqa: F401 — register all models

init_db()


@pytest.fixture(autouse=True)
def _bypass_rate_limit(monkeypatch):
    """All tests share the 'testclient' IP — one chart-rate-limit counter would
    trip across files (audit r4 B5 added 20/min on chart creation). Bypass by
    default; the rate-limit tests re-enable the real limiter themselves."""
    import app.main as _m
    monkeypatch.setattr(_m, "_rate_limit", lambda *a, **k: True)


class _FakeZarinpal:
    """F-P1: tests must NEVER hit the real Zarinpal sandbox — repeated suite
    runs trip its rate limit ('Too many attempts', -12) and make unrelated
    tests flake (synastry/ownership 502). Payment-focused tests that assert
    gateway behavior monkeypatch their own client AFTER this fixture."""

    def __init__(self, *a, **k):
        self.last_request = None

    def request(self, amount_rial, callback_url, description, meta=None):
        return f"S{fake_authority(16)}", "https://sandbox.zarinpal.com/pg/StartPay/S-fake"

    def verify(self, authority, amount_rial):
        return {"ref_id": "fake-ref", "code": 100}


def fake_authority(n: int = 16) -> str:
    import secrets
    return secrets.token_hex(n // 2)


@pytest.fixture(autouse=True)
def _no_real_zarinpal(monkeypatch):
    """Replace the real gateway with a deterministic fake for every test.
    Tests needing explicit gateway behavior override this by setting
    app.payment.zarinpal.ZarinpalClient (create_order imports it lazily)."""
    import app.payment.zarinpal as _zp
    monkeypatch.setattr(_zp, "ZarinpalClient", _FakeZarinpal)


@pytest.fixture(scope="session", autouse=True)
def _db():
    yield
    engine.dispose()
