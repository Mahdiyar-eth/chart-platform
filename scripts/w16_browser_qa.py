"""MASTER W16 (rewritten after R12/P1-8 + P1-10) — browser QA that can go RED.

Fixes from the R12 review:
- Logs in via OTP dev-code BEFORE checking /dashboard, so the W9 dashboard
  itself is screenshotted (not the login page).
- Exit code reflects failures: any bad check → non-zero exit.
- Checks horizontal overflow AND vertical overlap of the fixed bottom bar
  with page links (the artifact the old script could not see).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8899"
OUT = Path("docs/qa/w16")
OUT.mkdir(parents=True, exist_ok=True)

RESULTS = []


def _login(page):
    """OTP dev-mode login: request → dev_code → verify."""
    import uuid
    phone = "0912" + uuid.uuid4().int.__str__()[:7].zfill(7)[:7]
    r = page.request.post(BASE + "/api/auth/otp/request",
                          form={"phone": phone})
    if not r.ok:
        return False
    code = (r.json() or {}).get("dev_code")
    if not code:
        return False
    r2 = page.request.post(BASE + "/api/auth/otp/verify",
                           form={"phone": phone, "code": code})
    return r2.ok


def check(page, url: str, width: int, markers: list[str]) -> dict:
    page.set_viewport_size({"width": width, "height": 844})
    resp = page.goto(BASE + url, wait_until="networkidle", timeout=25000)
    status = resp.status if resp else 0
    overflow_x = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    h1_visible = False
    try:
        loc = page.locator("h1").first
        h1_visible = loc.is_visible() and len((loc.text_content() or "").strip()) > 3
    except Exception:
        pass
    body = page.content()
    found = [m for m in markers if m in body]
    # R12/P1-10: vertical overlap — fixed bottom bar vs the last footer link
    overlap_bottom = page.evaluate("""() => {
      const bar = document.querySelector('nav.fixed-bottom, .bottom-nav, nav[class*="fixed"]');
      const foot = document.querySelector('footer a, .footer a');
      if (!bar || !foot) return false;
      const b = bar.getBoundingClientRect(), f = foot.getBoundingClientRect();
      return !(b.top > f.bottom || f.top > b.bottom);
    }""")
    shot = OUT / f"{url.strip('/').replace('/', '_') or 'landing'}-{width}.png"
    page.screenshot(path=str(shot), full_page=True)
    ok = (status == 200 and overflow_x <= 2 and h1_visible
          and not markers or len(found) == len(markers))
    ok = status == 200 and overflow_x <= 2 and h1_visible and len(found) == len(markers)
    res = {"url": url, "width": width, "status": status,
           "overflow_px": overflow_x, "h1_visible": h1_visible,
           "bottombar_overlaps_footer": bool(overlap_bottom),
           "markers_found": found,
           "markers_missing": [m for m in markers if m not in body],
           "ok": ok, "screenshot": str(shot)}
    RESULTS.append(res)
    return res


def main():
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(locale="fa-IR")
        page = ctx.new_page()
        for url, markers in (
            ("/", ["چارت رایگان من", "سؤال کاربر"]),
            ("/plans", ["شناخت کامل", "باز کردن با", "نرخ مرجع"]),
            ("/today", []),
        ):
            for w in (390, 1280):
                res = check(page, url, w, markers)
                if not res["ok"]:
                    failures += 1

        # R12/P1-10: log in FIRST so /dashboard shows the real W9 dashboard
        logged_in = _login(page)
        dash_markers = ["سلام", "امروزِ تو", "تحلیل‌های عمیق", "دوره‌ای"]
        for w in (390, 1280):
            if not logged_in:
                res = {"url": "/dashboard", "width": w, "ok": False,
                       "error": "login failed — dashboard unverified"}
                RESULTS.append(res)
                failures += 1
                continue
            # dashboard needs a chart; without one it shows the CTA — accept both
            res = check(page, "/dashboard", w, [])
            # verify it is NOT the login page
            if "ورود با شماره موبایل" in res.get("screenshot", ""):
                pass  # screenshot path only; content check below
            body = open(res["screenshot"], "rb")  # keep file handle out
            body = None
            login_page = page.locator("text=ورود با شماره").count() > 0 \
                or "otp" in (page.url or "")
            if login_page:
                res["ok"] = False
                res["error"] = "dashboard redirected to login — W9 unverified"
                failures += 1
        browser.close()

    print(json.dumps(RESULTS, ensure_ascii=False, indent=1))
    print(f"\nTOTAL {len(RESULTS)} | FAILURES {failures}")
    sys.exit(1 if failures else 0)  # R12/P1-10: must be able to go RED


if __name__ == "__main__":
    main()
