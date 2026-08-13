"""Pytest fixtures — temp SQLite per run (NEVER prod Postgres).

IMPORTANT: DATABASE_URL must be set BEFORE app.db is imported anywhere,
otherwise tests hit the production Postgres. conftest loads first, so
setting it here (before any app import) is sufficient.
"""
import os
import sys
from pathlib import Path

_TMP_DB = "chart_platform_test"
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
os.environ["PUBLIC_BASE_URL"] = "http://127.0.0.1:8767"
os.environ["ENRICH_INSIGHTS"] = "0"  # no LLM calls in tests — deterministic fallback only

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.db import engine, init_db
from app.models import BotState  # noqa: F401 — register all models

init_db()


@pytest.fixture(scope="session", autouse=True)
def _db():
    yield
    engine.dispose()
