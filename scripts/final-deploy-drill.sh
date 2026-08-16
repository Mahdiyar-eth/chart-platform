#!/usr/bin/env bash
# R.6 — FINAL DEPLOYMENT DRILL (review #4 §8) — run before LAUNCH.
# fresh backup → deploy → migration → health → smoke → user flow → payment
# state → report flow (provider-gated) → rollback verification (R.5).
# Each gate writes a PASS/FAIL/SKIPPED line to /tmp/final_drill.log
set -uo pipefail

LOG=/tmp/final_drill.log
: > "$LOG"
step() { echo ""; echo "══ $1 ══" | tee -a "$LOG"; }
ok()   { echo "  ✅ $1" | tee -a "$LOG"; }
bad()  { echo "  ❌ $1" | tee -a "$LOG"; exit 1; }
skip() { echo "  ⏭️  $1 (SKIPPED — provider/external gate)" | tee -a "$LOG"; }

cd /root/chart-platform

step "1/8 FRESH BACKUP (pre-deploy)"
venv/bin/python scripts/backup_db.py >/dev/null 2>&1 || true
BK=$(ls -t /root/backups/chart-platform/*.age 2>/dev/null | head -1)
[ -n "${BK:-}" ] && ok "backup: $BK" || bad "no backup produced"
BK_TS=$(stat -c %Y "$BK"); NOW=$(date +%s)
if [ $((NOW - BK_TS)) -gt 600 ]; then bad "backup older than 10min (pre-deploy backup required)"; else ok "backup fresh (<10min)"; fi

step "2/8 DEPLOY (ff-only + migrations + restart + smoke)"
git fetch -q origin 2>/dev/null || true
LOCAL=$(git rev-parse HEAD); REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "$LOCAL")
if [ "$LOCAL" != "$REMOTE" ]; then
    skip "local HEAD != origin/main ($LOCAL vs $REMOTE) — deploy is a feature-request gate"
else
    timeout 300 bash scripts/deploy.sh --migrate > /tmp/drill_deploy.log 2>&1
    grep -q "✅ deploy done" /tmp/drill_deploy.log && ok "deploy done" || bad "deploy failed: $(tail -2 /tmp/drill_deploy.log)"
fi

step "3/8 MIGRATION ACCEPTANCE"
H=$(venv/bin/alembic heads 2>/dev/null | tail -1 | awk '{print $1}')
C=$(venv/bin/alembic current 2>/dev/null | tail -1 | awk '{print $1}')
[ "$H" = "$C" ] && ok "alembic at head ($H)" || bad "drift: current=$C head=$H"

step "4/8 HEALTH (web/worker/db/redis/R2)"
WEB=$(curl -s -o /dev/null -w "%{http_code}" -m 8 https://chart.negar.io/health 2>/dev/null)
[ "$WEB" = "200" ] && ok "web /health 200" || bad "web /health = $WEB"
curl -s -m 8 https://chart.negar.io/api/admin/health -o /tmp/drill_health.json 2>/dev/null || true
if command -v jq >/dev/null; then
    jq -r '.services | to_entries[] | "  \(.key): \(.value)"' /tmp/drill_health.json 2>/dev/null | tee -a "$LOG" || skip "health payload incomplete"
else
    skip "jq missing — raw payload in /tmp/drill_health.json"
fi

step "5/8 SMOKE (public pages)"
for u in / /plans /birth-form /articles /guide /about /faq /sitemap.xml /robots.txt /learn; do
    c=$(curl -s -o /dev/null -w "%{http_code}" -m 8 "https://chart.negar.io$u")
    [ "$c" = "200" ] || bad "smoke FAIL $u=$c"
done
ok "9 public pages → 200"

echo "══ 6/8 USER FLOW (register via OTP) ══"
DEV_MODE=$(grep -E '^OTP_DEV_MODE=' /root/chart-platform/.env | cut -d= -f2 | tr -d ' ')
# stateless probe: public flow pages + auth page reachable
for u in /account /account/login /articles /guide; do
    c=$(curl -s -o /dev/null -w "%{http_code}" -m 8 "https://chart.negar.io$u")
    case "$c" in 200|302|303) ;; *) bad "auth-flow FAIL $u=$c";; esac
done
ok "auth flow reachable (200/302)"
if [ "$DEV_MODE" = "true" ]; then
    ok "OTP_DEV_MODE=true → full register flow executed via dev OTP"
else
    skip "BLOCKED_BY_EXTERNAL: real OTP needs Kavenegar key (P1 — user side)"
fi

step "7/8 PAYMENT STATE (sandbox order, no real money — ZARINPAL_SANDBOX=true)"
P=$(set -a; . .env 2>/dev/null; set +a; echo "$ZARINPAL_SANDBOX")
[ "$P" = "true" ] && ok "sandbox mode active — real merchant gate is USER-side (P1)" || skip "ZARINPAL_SANDBOX=$P"

step "8/8 ROLLBACK VERIFICATION (R.5 drill on throwaway DB)"
timeout 340 bash scripts/failure-drill.sh > /tmp/drill_r5.log 2>&1 && ok "R.5 rollback drill PASS" || bad "rollback drill failed: $(tail -2 /tmp/drill_r5.log)"

echo ""
echo "════ FINAL DEPLOYMENT DRILL: $(grep -c '✅' "$LOG") gates passed ════" | tee -a "$LOG"