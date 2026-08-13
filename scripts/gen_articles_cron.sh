#!/bin/bash
# Guardian wrapper for the SEO article generator (cron-driven, crash-proof):
# - never runs while another instance is active
# - stops itself (empty stdout = silent) once all 30 articles exist
cd /root/chart-platform || exit 0
LOCK=/tmp/gen_articles.lock

# already complete?
COUNT=$(venv/bin/python -c "
import json
try:
    print(len(json.load(open('app/content/articles.json'))))
except Exception:
    print(0)
")
if [ "$COUNT" -ge 30 ]; then
  exit 0   # silent — nothing to report
fi

# single instance guard
if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK)" 2>/dev/null; then
  exit 0   # another run in progress — silent
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

venv/bin/python -u scripts/gen_articles.py
