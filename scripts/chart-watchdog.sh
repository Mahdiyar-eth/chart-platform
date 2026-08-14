#!/bin/bash
# chart-platform watchdog — health + 500/exception monitoring → Telegram alert.
# Cron: every 5 min (system crontab). AI-independent. No Hermes dependency.
# Debounce: max 1 alert per 30 min while problem persists; recovery message on clean.
set -uo pipefail

STATE=/tmp/chart-watchdog.state
HEALTH_URL="http://127.0.0.1:8767/health"
BOT_TOKEN=$(grep -E "^TELEGRAM_BOT_TOKEN" /root/voice-clone/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)
CHAT_ID="100973849"

if [ -z "$BOT_TOKEN" ]; then echo "no bot token"; exit 1; fi

# 1) health — 3 tries, 2s apart
ok=0
for i in 1 2 3; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$HEALTH_URL" 2>/dev/null)
  [ "$code" = "200" ] && ok=1 && break
  sleep 2
done

# 2) app exceptions / 500s in last 5 min (chart-web + chart-worker journals)
errs_web=$(journalctl -u chart-web.service --since "5 min ago" --no-pager 2>/dev/null | grep -cE "Exception in ASGI application|Traceback \(most recent call last\)" || true)
errs_worker=$(journalctl -u chart-worker.service --since "5 min ago" --no-pager 2>/dev/null | grep -cE "Traceback \(most recent call last\)|CRITICAL|ERROR " || true)
total_errs=$(( ${errs_web:-0} + ${errs_worker:-0} ))

now=$(date +%s)
was_bad=0; last_alert=0
[ -f "$STATE" ] && { read was_bad last_alert < "$STATE" 2>/dev/null || true; }

send() {
  curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" --data-urlencode "text=$1" -o /dev/null
}

problem=0
[ "$ok" != "1" ] && problem=1
[ "$total_errs" -ge 1 ] && problem=1

if [ "$problem" = "0" ]; then
  if [ "${was_bad:-0}" = "1" ]; then
    send "✅ زایچه برگشت — health OK و بدون خطای جدید در ۵ دقیقه اخیر"
  fi
  echo "0 0" > "$STATE"
  exit 0
fi

# still problematic — debounce 30 min
if [ "${was_bad:-0}" = "1" ] && [ $(( now - last_alert )) -lt 1800 ]; then
  echo "1 $last_alert" > "$STATE"
  exit 0
fi

msg="🚨 زایچه مشکل دارد:"
[ "$ok" != "1" ] && msg="$msg | health DOWN (3× ناموفق)"
[ "$total_errs" -ge 1 ] && msg="$msg | $total_errs استثنا/خطای 500 در ۵ دقیقه اخیر"
msg="$msg | $(date '+%H:%M')"
send "$msg"
echo "1 $now" > "$STATE"
exit 0
