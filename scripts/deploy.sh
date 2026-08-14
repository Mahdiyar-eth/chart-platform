#!/bin/bash
# chart-platform deploy script — audit P1 (round 3): single entrypoint for prod
# deploys: pull (ff-only) → alembic upgrade → schema drift check → restart.
# Usage: bash scripts/deploy.sh [--migrate]   (--migrate runs alembic upgrade)
set -euo pipefail
cd /root/chart-platform

echo "== 1/4 git pull (ff-only) =="
git pull --ff-only origin main

echo "== 2/4 alembic upgrade head =="
if [ "${1:-}" = "--migrate" ]; then
  venv/bin/alembic upgrade head
fi

echo "== 3/4 alembic check (schema drift) =="
venv/bin/alembic check || { echo "❌ SCHEMA DRIFT — deploy aborted"; exit 1; }

echo "== 4/4 restart services =="
systemctl restart chart-web chart-worker
sleep 3
systemctl is-active chart-web chart-worker
curl -s -o /dev/null -w "homepage: %{http_code}\n" https://chart.negar.io/ || true
echo "✅ deploy done"
