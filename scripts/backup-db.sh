#!/bin/bash
# Daily chart-platform DB+config backup → R2 (cron, AI-independent).
# Silent on success, prints errors on failure (cron no_agent delivers non-empty stdout only).
set -uo pipefail
cd /root/chart-platform || { echo "FAIL: cannot cd /root/chart-platform"; exit 1; }

PY=/root/chart-platform/venv/bin/python3
LOG=/tmp/chart-backup.log

"$PY" scripts/backup_db.py > "$LOG" 2>&1
RC=$?

if [ $RC -ne 0 ]; then
  echo "CHART-PLATFORM BACKUP FAILED:"
  cat "$LOG"
  exit 1
fi

exit 0  # silent on success
