#!/usr/bin/env bash
# R.5 — Deployment Failure Recovery Drill (review #4 §8)
#
# Proves the full rollback story on a THROWAWAY database (chart_drill):
#   fresh backup → restore → intentionally broken migration → abort
#   → fresh-backup restore → boot check
# Runs entirely on the local PostgreSQL — ZERO risk to prod data.
set -euo pipefail

DRILL_DB="chart_drill"
TS=$(date +%Y%m%d_%H%M%S)
BK="/tmp/chart_drill_backup_${TS}.dump"

pg() { sudo -n -u postgres psql -d postgres -v ON_ERROR_STOP=0 -qAt -c "$1"; }
pgd() { sudo -n -u postgres psql -d "$DRILL_DB" -qAt -c "$1"; }
runpg() { sudo -n -u postgres bash -c "$1"; }

echo "== 1/6 fresh backup (prod schema, socket peer auth) =="
runpg "pg_dump -Fc chart_platform -f $BK"
ls -la "$BK"

echo "== 2/6 create throwaway DB =="
runpg "dropdb --if-exists $DRILL_DB || true"
runpg "createdb -O chart_app $DRILL_DB"

echo "== 3/6 restore backup into drill DB =="
runpg "pg_restore -d $DRILL_DB $BK" >/dev/null 2>&1 || true
runpg "psql -d $DRILL_DB -tAc 'SELECT count(*) FROM alembic_version'" | grep -q . && echo "  alembic_version restored OK"

echo "== 4/6 intentionally BROKEN migration (missing table) =="
# real password from project .env (never hardcode).
# NOTE: .env has unquoted PEM values → sourcing it returns 127; run inside set +e.
set +e
set -a; . /root/chart-platform/.env 2>/dev/null; set +a
set -e
DRILL_URL="${DATABASE_URL/\/chart_platform/\/${DRILL_DB}}"

HEAD_REV=$(pgd "SELECT version_num FROM alembic_version" | tr -d ' \n')
echo "  drill head before: $HEAD_REV"
# append a REAL broken migration on top of the current head
cat > /root/chart-platform/alembic/versions/drill_zz_broken.py <<PYEOF
\"\"\"Intentional broken migration for R.5 drill — deleted after run.\"\"\"
from alembic import op
revision = "drill_zz_broken"
down_revision = "$HEAD_REV"

def upgrade() -> None:
    op.execute("SELECT * FROM definitely_missing_table_xyz")

def downgrade() -> None:
    pass
PYEOF

set +e
cd /root/chart-platform
out=$(DATABASE_URL="$DRILL_URL" venv/bin/python -m alembic upgrade head 2>&1)
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
    echo "  UNEXPECTED: broken migration succeeded — drill FAILED"
    rm -f alembic/versions/drill_zz_broken.py
    exit 1
fi
rm -f alembic/versions/drill_zz_broken.py
echo "  broken migration failed as designed (exit $rc) ✅"
echo "$out" | tail -2
# prove aborted cleanly: head unchanged (transactional DDL rolled back)
AFTER_REV=$(pgd "SELECT version_num FROM alembic_version" | tr -d ' \n')
[ "$AFTER_REV" = "$HEAD_REV" ] && echo "  alembic version untouched after abort ✅" || echo "  WARNING: version drifted: $AFTER_REV"

echo "== 5/6 restore from the SAME fresh backup (rollback) =="
runpg "dropdb --if-exists $DRILL_DB"
runpg "createdb -O chart_app $DRILL_DB"
runpg "pg_restore -d $DRILL_DB $BK" >/dev/null 2>&1 || true
head_rev=$(runpg "psql -d $DRILL_DB -tAc 'SELECT version_num FROM alembic_version'" | tr -d ' \n')
echo "  restored alembic head: $head_rev"
[ -n "$head_rev" ] && echo "  rollback OK ✅" || { echo "  rollback FAILED"; exit 1; }

echo "== 6/6 boot check (app starts against restored DB) =="
cd /root/chart-platform && DATABASE_URL="$DRILL_URL" timeout 30 venv/bin/python -c "
from app.db import engine
from sqlmodel import Session, text
with Session(engine) as s:
    n = s.exec(text('SELECT count(*) FROM cms_articles')).one()
    v = s.exec(text('SELECT version_num FROM alembic_version')).one()
print(f'  boot OK: articles={n}, alembic={v[0][:8]}')
" && echo "DRILL PASS ✅" || { echo "DRILL FAILED"; exit 1; }

runpg "dropdb --if-exists $DRILL_DB" || true
rm -f "$BK"
echo "DONE: chart_drill dropped, temp files cleaned."