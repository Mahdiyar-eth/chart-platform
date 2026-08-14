"""A2 (audit r4): APP_ENV=prod|production must BOTH activate fail-closed mode.

Regression: code checked `APP_ENV == "prod"` while `.env.example` shipped
`APP_ENV=production` — anyone copying the template silently disabled all
production security checks. Centralized in app/env.py (IS_PROD).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def _boot(app_env: str, secrets_ok: bool) -> subprocess.CompletedProcess:
    """Import app.main in a subprocess; empty-string env vars override the
    repo .env (load_dotenv override=False skips vars that are already set)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["APP_ENV"] = app_env
    env["DATABASE_URL"] = "sqlite:////tmp/env_prod_test.db" if secrets_ok else ""
    env["AUTH_SECRET"] = "test-secret" if secrets_ok else ""
    env["ADMIN_SECRET"] = "test-admin" if secrets_ok else ""
    env["SECRETS_MASTER_KEY"] = "test-master-key" if secrets_ok else ""
    env["RATE_LIMIT_BACKEND"] = "memory"
    return subprocess.run(
        [PY, "-c", "import app.main"], cwd="/tmp", env=env,
        capture_output=True, text=True, timeout=60,
    )


def test_production_spelling_fails_closed_without_secrets():
    r = _boot("production", secrets_ok=False)
    assert r.returncode != 0
    assert "is required in production" in r.stderr


def test_prod_spelling_fails_closed_without_secrets():
    r = _boot("prod", secrets_ok=False)
    assert r.returncode != 0
    assert "is required in production" in r.stderr


def test_production_spelling_boots_with_secrets():
    r = _boot("production", secrets_ok=True)
    assert r.returncode == 0, r.stderr[-500:]


def test_prod_spelling_boots_with_secrets():
    r = _boot("prod", secrets_ok=True)
    assert r.returncode == 0, r.stderr[-500:]


def test_dev_spelling_boots_without_secrets():
    r = _boot("development", secrets_ok=False)
    assert r.returncode == 0, r.stderr[-500:]
