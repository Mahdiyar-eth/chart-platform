#!/usr/bin/env bash
# CI gate (audit P2-6 + r3): tests + coverage + alembic chain check + lint +
# security scans (bandit/pip-audit/secret-scan) + brand-language scan.
# Run from repo root:  bash scripts/ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> alembic chain check (fresh EMPTY DB → upgrade head → drift check)"
# Z4/R3: the drift gate MUST run against a truly empty database. Running it on
# the dev/test DB (which has create_all artifacts) hides missing migrations —
# exactly how the subscribers table slipped through (Opus R3, P0-3).
DRIFT_DB="postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_drift"
venv/bin/python - <<PYEOF
import os, sqlalchemy as sa
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_ADMIN"] = "$DRIFT_DB"
admin = sa.create_engine("postgresql://chart_test:chart_test_pw@127.0.0.1:5432/postgres")
with admin.connect() as conn:
    conn.execution_options(isolation_level="AUTOCOMMIT")
    conn.execute(sa.text("DROP DATABASE IF EXISTS chart_platform_drift WITH (FORCE)"))
    conn.execute(sa.text("CREATE DATABASE chart_platform_drift"))
    conn.execute(sa.text("GRANT ALL PRIVILEGES ON DATABASE chart_platform_drift TO chart_test"))
print("drift db recreated (empty)")
PYEOF
# pgvector must live in the drift DB; create it. In CI the app's connection user
# (chart_test) IS the service superuser, so try via the app URL first; on a local
# box where chart_test isn't superuser, fall back to sudo -u postgres.
DATABASE_URL="$DRIFT_DB" venv/bin/python - <<PYEOF
import os, sqlalchemy as sa
try:
    e = sa.create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        c.execution_options(isolation_level="AUTOCOMMIT")
        c.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        c.execute(sa.text("GRANT ALL ON SCHEMA public TO chart_test"))
    print("vector created via app user")
except Exception as ex:  # noqa: BLE001 — fall back below
    print("app-user vector failed:", str(ex)[:80])
PYEOF
sudo -u postgres psql -d chart_platform_drift -c "CREATE EXTENSION IF NOT EXISTS vector; \
  GRANT ALL ON SCHEMA public TO chart_test;" >/dev/null 2>&1 || echo "(sudo vector step skipped)"
DATABASE_URL="$DRIFT_DB" venv/bin/alembic upgrade head
DATABASE_URL="$DRIFT_DB" venv/bin/alembic check
venv/bin/python - <<PYEOF
import sqlalchemy as sa
admin = sa.create_engine("postgresql://chart_test:chart_test_pw@127.0.0.1:5432/postgres")
with admin.connect() as conn:
    conn.execution_options(isolation_level="AUTOCOMMIT")
    conn.execute(sa.text("DROP DATABASE IF EXISTS chart_platform_drift WITH (FORCE)"))
print("drift db dropped")
PYEOF

echo "==> pytest + coverage (gate: >= 60%)"
venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing --cov-fail-under=60

echo "==> production boot smoke test (A11: fail-closed secrets honored)"
# 1) APP_ENV=production WITHOUT secrets must refuse to boot (regression for
#    the old APP_ENV=prod vs production mismatch — audit r4 A2)
set +e
APP_ENV=production AUTH_SECRET= ADMIN_SECRET= SECRETS_MASTER_KEY= \
  DATABASE_URL="${DATABASE_URL:-postgresql://x:x@127.0.0.1:5432/x}" \
  venv/bin/python -c "import app.main" 2>smoke_missing.log
RC=$?
set -e
if [ "$RC" -eq 0 ]; then
  echo "❌ prod-mode boot succeeded WITHOUT secrets (fail-closed broken)"
  exit 1
fi
echo "✓ prod-mode refuses to boot without secrets"
# 1b) audit r4 B4: prod without R2 creds must refuse to boot (fail-closed)
set +e
APP_ENV=production AUTH_SECRET=x ADMIN_SECRET=x SECRETS_MASTER_KEY=x \
  R2_ACCESS_KEY_ID= R2_SECRET_ACCESS_KEY= R2_ENDPOINT= \
  DATABASE_URL="${DATABASE_URL:-postgresql://x:x@127.0.0.1:5432/x}" \
  venv/bin/python -c "import app.storage" 2>smoke_r2.log
RC=$?
set -e
if [ "$RC" -eq 0 ]; then
  echo "❌ prod-mode boot succeeded WITHOUT R2 (fail-closed broken)"
  exit 1
fi
echo "✓ prod-mode refuses to boot without R2"
# 1c) audit r4 B5: prod with in-memory rate limit backend must refuse to boot
set +e
APP_ENV=production AUTH_SECRET=x ADMIN_SECRET=x SECRETS_MASTER_KEY=x \
  RATE_LIMIT_BACKEND=memory \
  DATABASE_URL="${DATABASE_URL:-postgresql://x:x@127.0.0.1:5432/x}" \
  venv/bin/python -c "import app.security" 2>smoke_rl.log
RC=$?
set -e
if [ "$RC" -eq 0 ]; then
  echo "❌ prod-mode boot succeeded with memory rate-limit backend"
  exit 1
fi
echo "✓ prod-mode requires Redis rate-limit backend"
# 2) with all secrets → boots, /health + landing + plans respond
SMOKE_DB="${DATABASE_URL:-postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test}"
APP_ENV=production DATABASE_URL="$SMOKE_DB" \
  AUTH_SECRET="smoke-test-auth-secret-000" ADMIN_SECRET="smoke-test-admin-secret-000" \
  SECRETS_MASTER_KEY="smoke-test-master-key-000" \
  venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
import app.main as m
c = TestClient(m.app)
for path in ("/health", "/", "/plans", "/api/plans", "/robots.txt"):
    r = c.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}"
print("✓ prod-mode boot + critical routes OK")
PY

echo "==> compileall (syntax)"
venv/bin/python -m compileall -q app/ scripts/

echo "==> ruff (bug rules: F pyflakes + E9 syntax)"
venv/bin/ruff check --select F,E9 app/ tests/ scripts/

echo "==> bandit (high-confidence issues only)"
venv/bin/bandit -q -r app/ -x tests -lll

echo "==> pip-audit (dependency vulnerabilities)"
venv/bin/pip-audit -r requirements.txt

echo "==> secret scan (hardcoded keys/tokens + secret files)"
# Forbidden secret FILES (audit r3/a1: umami creds were written into deploy/ by
# setup_umami.py and leaked into the generated bundle). Presence = fail.
SECRET_FILES=$(find app/ scripts/ alembic/ deploy/ docs/ tests/ .github/ \
  \( -name 'umami-admin.txt' -o -name 'umami.env' \) 2>/dev/null || true)
if [ -n "$SECRET_FILES" ]; then
  echo "❌ forbidden secret file found:"
  echo "$SECRET_FILES"
  exit 1
fi
BAD=$(grep -rniE 'AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|sk-[A-Za-z0-9]{20,}|xox[baprs]-|ghp_[A-Za-z0-9]{30,}|AQ\.[0-9A-Za-z_-]{35,}|AIza[0-9A-Za-z_-]{30,}|^HASH_SALT=[0-9a-fA-F]{32,}|^APP_SECRET=[0-9a-fA-F]{32,}' \
  --include='*.py' --include='*.sh' --include='*.yml' --include='*.yaml' \
  --include='*.html' --include='*.md' --include='*.json' --include='*.toml' --include='*.ini' \
  app/ scripts/ alembic/ deploy/ docs/ tests/ .github/ 2>/dev/null || true)
if [ -n "$BAD" ]; then
  echo "❌ hardcoded secret found:"
  echo "$BAD"
  exit 1
fi
echo "✓ no hardcoded secrets"

echo "==> brand-language scan (فال/پیش‌بینی ممنوع)"
# Promotional fortune-telling is banned; allow: the QA detector itself (qa.py),
# the educational article contrasting natal charts with daily horoscopes,
# and the DISCLAIMER («نه تعیین سرنوشت»).
BAD=$(grep -rniE "پیش ?بینی|فال|طالع ?بینی" \
  app/templates app/content app/bots app/report app/chat --include="*.html" --include="*.json" --include="*.py" \
  | grep -v app/report/qa.py \
  | grep -viE "فال[‌ ]?[‌ ]?(بازی|گویی)|نه فال|فال قطعی|پیش‌بینی قطعی|تفاوت چارت تولد با فال روزانه|فال روزانه فقط بر اساس برج" \
  | grep -viE "پیش[‌ ]?بینی (نیست|در آسترولوژی|قطع)|پیش[‌ ]?بین" || true)

if [ -n "$BAD" ]; then
  echo "❌ banned brand-language found:"
  echo "$BAD"
  exit 1
fi
echo "✓ no banned brand-language"

echo "==> absolute-path scan (R4/W7: no hardcoded /root/chart-platform in app/)"
# A hardcoded absolute path breaks the app on ANY other host (Docker WORKDIR=/app).
# The reviewer caught 7 in R4; the sweep is now complete and must stay green.
ABSPATH=$(grep -rn "/root/chart-platform" app/ --include="*.py" 2>/dev/null || true)
if [ -n "$ABSPATH" ]; then
  echo "❌ hardcoded absolute path in app/:"
  echo "$ABSPATH"
  exit 1
fi
echo "✓ no hardcoded absolute paths (host-portable)"

echo "==> CI OK"
