#!/usr/bin/env bash
# R4/W5: the alembic drift gate against a TRULY EMPTY database.
# Extracted from ci.sh so CI can isolate a drift failure from test failures.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> alembic chain check (fresh EMPTY DB → upgrade head → drift check)"
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
# pgvector must live in the drift DB. Try the app user (superuser in CI), else sudo.
DATABASE_URL="$DRIFT_DB" venv/bin/python - <<PYEOF
import os, sqlalchemy as sa
try:
    e = sa.create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        c.execution_options(isolation_level="AUTOCOMMIT")
        c.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        c.execute(sa.text("GRANT ALL ON SCHEMA public TO chart_test"))
    print("vector created via app user")
except Exception as ex:  # noqa: BLE001
    print("app-user vector failed:", str(ex)[:80])
PYEOF
sudo -u postgres psql -d chart_platform_drift -c "CREATE EXTENSION IF NOT EXISTS vector; \
  GRANT ALL ON SCHEMA public TO chart_test;" >/dev/null 2>&1 || echo "(sudo vector step skipped)"
DATABASE_URL="$DRIFT_DB" venv/bin/alembic upgrade head
DATABASE_URL="$DRIFT_DB" venv/bin/alembic check && echo "DRIFT-GATE: CLEAN"
venv/bin/python - <<PYEOF
import sqlalchemy as sa
admin = sa.create_engine("postgresql://chart_test:chart_test_pw@127.0.0.1:5432/postgres")
with admin.connect() as conn:
    conn.execution_options(isolation_level="AUTOCOMMIT")
    conn.execute(sa.text("DROP DATABASE IF EXISTS chart_platform_drift WITH (FORCE)"))
print("drift db dropped")
PYEOF
echo "==> drift gate OK"
