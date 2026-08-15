#!/bin/bash
# chart-platform DR restore drill — restore the newest backup into a scratch
# database, migrate to head, sanity-check. NEVER touches prod.
#
# Usage:  scripts/restore-drill.sh
# Reads:  newest .age backup in /root/backups/chart-platform/
#         age key at /root/.hermes/keys/chart-platform-age.txt
set -uo pipefail
cd /root/chart-platform || exit 1

BK=$(ls -1t /root/backups/chart-platform/*.zip.age | head -1)
KEY=/root/.hermes/keys/chart-platform-age.txt
DB=chart_dr_$$ 
WORK=$(mktemp -d)
chmod 755 "$WORK"  # pg_restore runs as postgres; mktemp dirs are 700
echo "== restore drill: $BK -> $DB =="

age -d -i "$KEY" -o "$WORK/b.zip" "$BK" || { echo FAIL:age; exit 1; }
unzip -o -q "$WORK/b.zip" -d "$WORK"
DUMP=$(ls "$WORK"/*.dump)

sudo -u postgres psql -q -c "CREATE DATABASE $DB OWNER chart_app" || { echo FAIL:createdb; exit 1; }
sudo -u postgres pg_restore -d "$DB" --no-owner --no-privileges "$DUMP" 2>&1 | grep -cE 'ERROR' || true
# ownership → chart_app (restore ran as postgres; ALTER needs ownership, grants are not enough)
sudo -u postgres psql -q -d "$DB" -tAc "SELECT 'ALTER TABLE public.'||tablename||' OWNER TO chart_app;' FROM pg_tables WHERE schemaname='public' AND tableowner='postgres'" | sudo -u postgres psql -q -d "$DB"
sudo -u postgres psql -q -d "$DB" -tAc "SELECT 'ALTER SEQUENCE public.'||sequencename||' OWNER TO chart_app;' FROM pg_sequences WHERE schemaname='public'" | sudo -u postgres psql -q -d "$DB"
sudo -u postgres psql -q -d "$DB" -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO chart_app"
sudo -u postgres psql -q -d "$DB" -c "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO chart_app"

PW=$(grep '^DATABASE_URL' .env | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')
sudo -u postgres psql -q -d "$DB" -c "CREATE EXTENSION IF NOT EXISTS vector" 2>/dev/null || true
export DATABASE_URL="postgresql://chart_app:${PW}@127.0.0.1:5432/$DB"
if ! venv/bin/alembic upgrade head; then echo "FAIL:migrate"; exit 1; fi

echo "== sanity =="
sudo -u postgres psql -d "$DB" -tAc "SELECT 'users='||count(*) FROM users; SELECT 'paid_orders='||count(*) FROM orders WHERE status='paid'; SELECT 'migrations='||count(*) FROM alembic_version"
echo "== DRILL OK =="
sudo -u postgres psql -q -c "DROP DATABASE $DB"
rm -rf "$WORK"
