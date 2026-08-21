---
name: qa-browser
description: Spin up the isolated QA FastAPI instance and run Playwright browser/DOM checks (mobile 390px + desktop). Use before claiming any UI bug is fixed.
---

# QA Browser

## Isolated QA instance
Never test against the prod DB (`chart_platform`) — use `chart_platform_qa`.

```bash
cd /root/chart-platform
# Derive the QA DB URL from local .env, swapping the DB name (keeps credentials out of git):
QA_DB_URL=$(venv/bin/python - <<'PY'
import re, os
from dotenv import load_dotenv
load_dotenv('.env')
u = os.getenv('DATABASE_URL','')
u = re.sub(r'/[^/?#]+(?=[?\s#]|$)', '/chart_platform_qa', u)
print(u)
PY
)
DATABASE_URL="$QA_DB_URL" \
  OTP_DEV_MODE=true ENRICH_INSIGHTS=0 RATE_LIMIT_BACKEND=memory CREATE_ALL_ON_BOOT=1 \
  venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8798
```

Warm-up: `curl -s localhost:8798/` and `curl -s localhost:8798/account/login` → 200. Some flows (OTP) need an instance restart (rate-limit/OTP caches) — kill and re-start uvicorn.

## Check before claiming a fix
- Render the page at **mobile 390px** AND **desktop 1280px** viewport.
- Assert **zero console errors**.
- **Prefer DOM measurement over vision**: use `document.querySelector(...).getBoundingClientRect()` via browser console. The DOM is the reference — vision has mis-read several times (e.g. "third card half-done" was a misread; "5 nav items" was actually 6).
- Only after the DOM measurement passes, take a screenshot as supporting proof.
- Example (bottom nav): check center badge circle doesn't pop above the bar (`circlePopsAboveNav === false`), `margin-top:0`, and the item count.

## Prod deploy rule
Templates/Jinja are cached until the service restarts. After ANY template/UI change, run `systemctl restart chart-web chart-worker` BEFORE claiming it is live, else the user sees the old version.
