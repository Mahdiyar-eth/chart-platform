# Browser verification

Checks that need a real browser and a running instance, so they cannot live in
pytest. Every one of them was written because a static check said green while
the thing was broken on screen.

Start a QA instance first:

    APP_ENV=dev OTP_DEV_MODE=true ENRICH_INSIGHTS=0 RATE_LIMIT_BACKEND=memory \
    CREATE_ALL_ON_BOOT=1 DATABASE_URL=... \
    venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8798

Then:

| script | what it proves |
|---|---|
| `app_shell.py` | stylesheets actually parse (rule counts), fonts load, navigation is client-side (a window marker survives it), the title updates, the chrome survives the swap, and the **service worker reaches `activated`** with its shell precached |
| `guest_journey.py` | the whole funnel: build a chart with no account → chart page → log in with `next=` → land back on the chart → the chart is **claimed** and shows in `/account` |
| `contrast.py <dark\|light> [paths…]` | WCAG contrast, compositing alpha up the ancestor chain and skipping gradients — a naive version reports a page of phantom failures |
| `page_sweep.py` | every public page: 200, no console errors, no failed requests |

Env: `QA_BASE` (default `http://127.0.0.1:8798`), `CHROME_PATH`, `VERIFY_OUT`
(where screenshots go).
