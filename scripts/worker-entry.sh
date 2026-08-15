#!/bin/bash
# chart-worker wrapper: ARQ needs redis at boot. If redis is down, wait (2s
# poll) instead of crash-looping. systemd keeps this process alive, so when
# redis returns the worker starts automatically — zero manual intervention.
# FIXED 2026-08-15 (§4 of Absolute Final Verification Plan)
until /usr/bin/redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 2
done
exec /root/chart-platform/venv/bin/arq app.report.worker.WorkerSettings
