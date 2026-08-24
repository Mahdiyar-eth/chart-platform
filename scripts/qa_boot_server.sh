#!/usr/bin/env bash
# Boot the isolated QA server (throwaway DB) as a detached daemon, then verify.
set -euo pipefail
cd /root/chart-platform
export DATABASE_URL="postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_qa"
export APP_ENV=development CREATE_ALL_ON_BOOT=1 RATE_LIMIT_BACKEND=memory
export AUTH_SECRET="qa-test-auth-secret" ADMIN_SECRET="qa-admin-secret"
export SECRETS_MASTER_KEY="qa-master-key" ADMIN_PIN="601559" OTP_DEV_MODE=true
export PUBLIC_BASE_URL="http://127.0.0.1:8899"
# Kill any stale listener on 8899
if ss -tlnp 2>/dev/null | grep -q ":8899"; then
  fuser -k 8899/tcp 2>/dev/null || true; sleep 1
fi
nohup venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8899 > /tmp/qa_uv.log 2>&1 &
echo "PID=$!" > /tmp/qa_uv.pid
# Wait for readiness
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8899/health 2>/dev/null | grep -q 200; then
    echo "READY after ${i}s"; exit 0
  fi
  sleep 1
done
echo "NOT READY"; tail -20 /tmp/qa_uv.log; exit 1
