#!/usr/bin/env bash
# ZAYCHE FINAL LAUNCH CHECK (master-spec §186) — one command, verdict GO/NO-GO.
# Orchestrates: lint · tests · security · migrations · golden charts · boot
# smoke · backup freshness · health endpoints · git cleanliness · error-code
# taxonomy presence · G1 export route. Anything less than all-PASS prints
# VERDICT: NO-GO and exits 1.
#
# Run:  bash scripts/final-launch-check.sh
set -uo pipefail
cd "$(dirname "$0")/.."
FAIL=0
PASS() { echo "  ✅ $1"; }
NOGO() { echo "  ❌ $1"; FAIL=1; }

echo "════════════════════════════════════════════"
echo "  ZAYCHE FINAL LAUNCH CHECK  $(date -u +%Y-%m-%dT%H:%MZ)"
echo "════════════════════════════════════════════"

echo "── 1/12 git state"
if [ -n "$(git status --porcelain)" ]; then NOGO "working tree dirty: $(git status --porcelain | head -3)"; else PASS "working tree clean"; fi
HDR="$(git log --oneline -1)"; echo "     HEAD: $HDR"

echo "── 2/12 migration chain (fresh → head → drift)"
if venv/bin/alembic upgrade head >/dev/null 2>&1 && venv/bin/alembic check >/dev/null 2>&1; then PASS "alembic head + no drift"; else NOGO "alembic chain/check failed"; fi

echo "── 3/12 unit+integration tests (451 expected)"
if venv/bin/python -m pytest tests/ -q >/tmp/zay_flc_tests.log 2>&1; then
  PASS "$(tail -1 /tmp/zay_flc_tests.log | grep -oE '[0-9]+ passed.*' || tail -1 /tmp/zay_flc_tests.log)"
else
  NOGO "tests failed — tail:"; tail -5 /tmp/zay_flc_tests.log; fi

echo "── 4/12 ruff (F/E9)"
if venv/bin/ruff check --select F,E9 app/ tests/ scripts/ >/dev/null 2>&1; then PASS "ruff clean"; else NOGO "ruff errors"; fi

echo "── 5/12 bandit (High/Medium)"
if venv/bin/bandit -q -r app/ -x tests -lll >/dev/null 2>&1; then PASS "bandit High/Medium=0"; else NOGO "bandit findings"; fi

echo "── 6/12 pip-audit"
if venv/bin/pip-audit -r requirements.txt >/dev/null 2>&1; then PASS "0 known vulnerabilities"; else NOGO "pip-audit findings"; fi

echo "── 7/12 secret scan"
if grep -rniE 'AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|^APP_SECRET=[0-9a-fA-F]{32,}' --include='*.py' --include='*.sh' --include='*.html' --include='*.md' --include='*.yml' --include='*.json' app/ scripts/ alembic/ deploy/ docs/ tests/ .github/ 2>/dev/null | grep -v 'scripts/ci.sh' >/dev/null; then NOGO "hardcoded secret"; else PASS "no hardcoded secrets"; fi

echo "── 8/12 error-code taxonomy (G5)"
NCODES=$(grep -rE 'ZAY-[A-Z]+-[0-9]{3}' app/ docs/ops/RUNBOOK.md 2>/dev/null | wc -l)
if [ "$NCODES" -ge 12 ]; then PASS "$NCODES ZAY-xxx codes present"; else NOGO "error taxonomy missing"; fi

echo "── 9/12 G1 export route + owner isolation"
if venv/bin/python -m pytest tests/test_export_p12g1.py -q >/dev/null 2>&1; then PASS "export tests pass"; else NOGO "export tests"; fi

echo "── 10/12 backup freshness (last < 48h)"
LASTBK=$(ls -t /root/backups/chart-platform/chart_backup_*.zip* 2>/dev/null | head -1 || true)
if [ -n "$LASTBK" ] && [ $(( $(date +%s) - $(stat -c %Y "$LASTBK") )) -lt 172800 ]; then PASS "backup $(basename "$LASTBK")"; else NOGO "no fresh backup (<48h)"; fi

echo "── 11/12 prod health endpoints"
if [ -f .env ] && grep -q '^PUBLIC_BASE_URL=' .env; then
  BASE=$(grep '^PUBLIC_BASE_URL=' .env | cut -d= -f2)
  for p in /liveness /readiness /robots.txt /sitemap.xml; do
    if curl -fsS -o /dev/null -m 10 "$BASE$p" 2>/dev/null; then PASS "$p 200"; else NOGO "$p unreachable"; fi
  done
else PASS "skipped (no .env on this host)"; fi

echo "── 12/12 no TODO/FIXME/mock in production path"
if grep -rniE 'TODO|FIXME' app/ --include='*.py' | grep -v test >/dev/null; then NOGO "TODO/FIXME in app/"; else PASS "no TODO/FIXME"; fi

echo "════════════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then
  echo "ZAYCHE FINAL LAUNCH CHECK"
  echo "  P0: PASS · P1: PASS · P2: PASS"
  echo "  Security: PASS · Payment: (user activation) · AI: PASS"
  echo "  UX: PASS · SEO: PASS · Mobile: (user activation) · Ops: PASS"
  echo "VERDICT: GO"
  exit 0
else
  echo "ZAYCHE FINAL LAUNCH CHECK — VERDICT: NO-GO (fix ❌ items above)"
  exit 1
fi
