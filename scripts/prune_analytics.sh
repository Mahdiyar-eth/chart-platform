#!/bin/bash
# Z15 (Opus R3 P2-6): 90-day retention for funnel_events + transit_alert_log.
# Runs via cron; silent on success (exits 0, no output unless it pruned).
set -uo pipefail
cd /root/chart-platform || exit 1
OUT=$(venv/bin/python -c "from app.rag import prune_analytics; print(prune_analytics(90))" 2>&1)
RC=$?
if [ $RC -ne 0 ]; then
  echo "❌ ANALYTICS PRUNE FAILED (rc=$RC)"
  echo "$OUT" | tail -15
else
  N=$(echo "$OUT" | tail -1)
  echo "pruned analytics rows: $N"
fi
# NOTE: even success emits a line; if you want silence, redirect to log instead.
