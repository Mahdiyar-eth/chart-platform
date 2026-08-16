#!/bin/bash
# M7 (multi-provider plan): weekly restore drill — proves the newest backup
# restores into a scratch DB, migrates to head, and passes sanity checks.
# Silent on success (watchdog pattern); delivers failure details on error.
set -uo pipefail
cd /root/chart-platform || exit 1

OUT=$(bash scripts/restore-drill.sh 2>&1)
RC=$?
if [ $RC -ne 0 ]; then
  echo "❌ WEEKLY RESTORE DRILL FAILED (rc=$RC)"
  echo "$OUT" | tail -25
elif ! echo "$OUT" | grep -q '== DRILL OK =='; then
  echo "❌ RESTORE DRILL: unexpected output (no DRILL OK marker)"
  echo "$OUT" | tail -25
fi
# success → empty stdout → cron stays silent