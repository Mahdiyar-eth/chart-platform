"""Drive the real browser. Assert nothing that wasn't observed."""
import os
import json, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8798")
OUT = os.environ.get("VERIFY_OUT", "/tmp")
CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
results = []

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + ((" :: " + str(detail)[:160]) if detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME,
                          args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width": 390, "height": 844},  # iPhone 14 Pro
                        device_scale_factor=3, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    errors, failed_req = [], []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("requestfailed", lambda r: failed_req.append(f"{r.url} {r.failure}"))

    # ── landing ──────────────────────────────────────────────────────────
    pg.goto(BASE + "/", wait_until="networkidle")
    check("landing renders", pg.title() != "", pg.title())
    check("htmx loaded", pg.evaluate("typeof window.htmx !== 'undefined'"))
    check("alpine loaded", pg.evaluate("typeof window.Alpine !== 'undefined'"))
    check("#app-main present", pg.locator("#app-main").count() == 1)
    check("body is boosted", pg.evaluate("document.body.getAttribute('hx-boost')") == "true")

    # ── CSS actually parsed (the bug that hid for three rounds) ──────────
    parsed = pg.evaluate("""() => {
      let out = {};
      for (const s of document.styleSheets) {
        try { out[(s.href||'inline').split('/').pop().split('?')[0]] = s.cssRules.length; }
        catch(e) { out[(s.href||'inline')] = 'BLOCKED'; }
      }
      return out; }""")
    print("    stylesheet rules:", json.dumps(parsed, ensure_ascii=False))
    check("all stylesheets parsed", all(v != 0 for v in parsed.values()), parsed)

    # ── fonts really loaded as woff2 ─────────────────────────────────────
    fonts = pg.evaluate("""async () => {
      await document.fonts.ready;
      return [...document.fonts].map(f => f.family + ' ' + f.weight + ' ' + f.status);
    }""")
    print("    fonts:", fonts)
    check("Vazirmatn loaded", any("Vazirmatn" in f and "loaded" in f for f in fonts), fonts)

    # ── client-side navigation actually happens ──────────────────────────
    pg.evaluate("window.__navMarker = 'first-load'")
    nav_ok = False
    # pick a VISIBLE nav link that leaves the current page (desktop .nav-item
    # is display:none at this viewport)
    link = None
    for i in range(pg.locator("a.bn-item").count()):
        cand = pg.locator("a.bn-item").nth(i)
        if cand.is_visible() and (cand.get_attribute("href") or "/") != "/":
            link = cand
            break
    assert link is not None, "no visible bottom-nav link to click"
    href = link.get_attribute("href")
    print("    clicking:", href)
    link.click()
    pg.wait_for_timeout(1500)
    survived = pg.evaluate("window.__navMarker")
    nav_ok = (survived == "first-load")
    check("navigation is client-side (no full reload)", nav_ok,
          f"went to {pg.url}, marker={survived}")
    check("URL changed", href in pg.url, pg.url)
    check("title updated on swap", pg.title() != "", pg.title())
    check("chrome survived swap", pg.locator(".bottomnav").count() == 1)
    check("active tab moved", pg.locator("a.bn-item.active, a.nav-item.active").count() >= 1)

    # ── progress bar exists and is wired ─────────────────────────────────
    check("#navProgress present after swap", pg.locator("#navProgress").count() == 1)

    # ── safe-area / tab bar geometry on a mobile viewport ────────────────
    bn = pg.locator(".bottomnav")
    if bn.count():
        box = bn.bounding_box()
        print("    bottomnav box:", box)
        check("bottom nav is on screen", box and box["y"] < 844 and box["height"] > 30, box)

    # ── service worker: does it INSTALL? (the P0-2 claim) ────────────────
    # SW needs a secure context; 127.0.0.1 counts as one.
    sw = pg.evaluate("""async () => {
      if (!('serviceWorker' in navigator)) return 'unsupported';
      try {
        const r = await navigator.serviceWorker.register('/sw.js');
        const reg = await navigator.serviceWorker.ready;
        // state is captured mid-transition otherwise
        for (let i = 0; i < 50 && (!reg.active || reg.active.state !== 'activated'); i++) {
          await new Promise(res => setTimeout(res, 100));
        }
        const keys = await caches.keys();
        const c = keys.length ? await caches.open(keys[0]) : null;
        const cached = c ? (await c.keys()).map(q => new URL(q.url).pathname) : [];
        return 'active:' + (reg.active ? reg.active.state : 'none') + ' caches=' +
               JSON.stringify(keys) + ' precached=' + JSON.stringify(cached);
      } catch (e) { return 'ERROR: ' + e.message; }
    }""")
    print("    serviceWorker:", sw)
    check("service worker installs and activates", str(sw).startswith("active:activated"), sw)

    # ── no console errors anywhere ───────────────────────────────────────
    check("no page errors", not errors, errors[:3])
    real_fails = [f for f in failed_req if "favicon" not in f]
    check("no failed requests", not real_fails, real_fails[:3])

    pg.screenshot(path=OUT + "/shot_after_nav.png")
    b.close()

bad = [n for n, ok, _ in results if not ok]
print(f"\n{len(results)-len(bad)}/{len(results)} passed")
if bad:
    print("FAILED: " + "; ".join(bad))
sys.exit(1 if bad else 0)
