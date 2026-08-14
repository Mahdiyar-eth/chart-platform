#!/usr/bin/env bash
# CI gate (audit P2-6 + r3): tests + coverage + alembic chain check + lint +
# security scans (bandit/pip-audit/secret-scan) + brand-language scan.
# Run from repo root:  bash scripts/ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> alembic chain check (fresh DB → upgrade head → drift check)"
# Must run BEFORE pytest (which create_all's on the test DB).
venv/bin/alembic upgrade head
venv/bin/alembic check

echo "==> pytest + coverage (gate: >= 60%)"
venv/bin/python -m pytest tests/ -q --cov=app --cov-report=term-missing --cov-fail-under=60

echo "==> compileall (syntax)"
venv/bin/python -m compileall -q app/ scripts/

echo "==> ruff (bug rules: F pyflakes + E9 syntax)"
venv/bin/ruff check --select F,E9 app/ tests/ scripts/

echo "==> bandit (high-confidence issues only)"
venv/bin/bandit -q -r app/ -x tests -lll

echo "==> pip-audit (dependency vulnerabilities)"
venv/bin/pip-audit -r requirements.txt

echo "==> secret scan (hardcoded keys/tokens)"
BAD=$(grep -rniE 'AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|sk-[A-Za-z0-9]{20,}|xox[baprs]-|ghp_[A-Za-z0-9]{30,}|umami-admin\.txt|umami\.env[:.]|AQ\.[0-9A-Za-z_-]{35,}|AIza[0-9A-Za-z_-]{30,}|^HASH_SALT=[0-9a-fA-F]{32,}|^APP_SECRET=[0-9a-fA-F]{32,}' \
  --include='*.py' --include='*.sh' --include='*.yml' --include='*.yaml' \
  --include='*.html' --include='*.md' --include='*.json' --include='*.toml' --include='*.ini' \
  app/ scripts/ alembic/ deploy/ docs/ tests/ .github/ 2>/dev/null || true)
if [ -n "$BAD" ]; then
  echo "❌ hardcoded secret found:"
  echo "$BAD"
  exit 1
fi
echo "✓ no hardcoded secrets"

echo "==> brand-language scan (فال/پیش‌بینی ممنوع)"
# Promotional fortune-telling is banned; allow: the QA detector itself (qa.py),
# the educational article contrasting natal charts with daily horoscopes,
# and the DISCLAIMER («نه تعیین سرنوشت»).
BAD=$(grep -rniE "پیش ?بینی|فال|طالع ?بینی" \
  app/templates app/content app/bots app/report app/chat --include="*.html" --include="*.json" --include="*.py" \
  | grep -v app/report/qa.py \
  | grep -viE "فال‌بازی|نه فال|فال قطعی|تفاوت چارت تولد با فال روزانه|فال روزانه فقط بر اساس برج" \
  | grep -viE "پیش‌بینی نیست|پیش‌بینی در آسترولوژی|پیش‌بین" || true)

if [ -n "$BAD" ]; then
  echo "❌ banned brand-language found:"
  echo "$BAD"
  exit 1
fi
echo "✓ no banned brand-language"

echo "==> CI OK"
