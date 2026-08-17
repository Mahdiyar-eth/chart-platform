#!/usr/bin/env bash
cd /root/chart-platform || exit 1
set -a; . /root/chart-platform/.env 2>/dev/null; set +a
export PYTHONPATH=/root/chart-platform
export BENCH_FRESH=1
export BENCH_GO_KEYS="$(printf '%s\n' "$GO_API_KEYS" | tr ',' '\n' | grep '@' | head -1)"
exec /root/chart-platform/venv/bin/python -u /root/chart-platform/scripts/ai_benchmark_v4.py 2 0