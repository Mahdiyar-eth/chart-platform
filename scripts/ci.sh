#!/usr/bin/env bash
# CI gate (audit P2-6): tests + syntax + brand-language scan.
# Run from repo root:  bash scripts/ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> pytest"
venv/bin/python -m pytest tests/ -q

echo "==> compileall (syntax)"
venv/bin/python -m compileall -q app/ scripts/

echo "==> brand-language scan (فال/پیش‌بینی ممنوع)"
# Promotional fortune-telling words are banned; the DISCLAIMER
# («نه تعیین سرنوشت») is allowed and matched with the allowlist below.
BAD=$(grep -rniE "پیش ?بینی|فال|طالع ?بینی" \
  app/templates app/content app/bots app/report app/chat --include="*.html" --include="*.json" --include="*.py" \
  | grep -viE "فال‌بازی|نه فال|فال قطعی" \
  | grep -viE "پیش‌بینی نیست|پیش‌بینی در آسترولوژی|پیش‌بین" || true)

if [ -n "$BAD" ]; then
  echo "❌ banned brand-language found:"
  echo "$BAD"
  exit 1
fi
echo "✓ no banned brand-language"

echo "==> CI OK"
