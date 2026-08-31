import os
import sys
from playwright.sync_api import sync_playwright
BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8798")
PATHS = ["/", "/birth-form", "/plans", "/credits", "/sky", "/synastry", "/rectify",
         "/learn", "/articles", "/faq", "/guide", "/glossary", "/about", "/contact",
         "/privacy", "/terms", "/refund", "/disclaimer", "/account/login",
         "/solar-guide", "/relocation-guide", "/deep-report", "/self-discovery"]
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
                          args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width":390,"height":844}, is_mobile=True)
    pg = ctx.new_page()
    for path in PATHS:
        errs, fails = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("requestfailed", lambda r: fails.append(r.url.split("/")[-1][:40]))
        try:
            r = pg.goto(BASE + path, wait_until="networkidle", timeout=30000)
            pg.wait_for_timeout(300)
            status = r.status if r else 0
        except Exception as e:
            status = f"EXC {str(e)[:40]}"
        fails = [f for f in fails if "favicon" not in f]
        # Alpine compiles every x-/:/@ attribute with new AsyncFunction. A
        # malformed one throws only when Alpine reaches it, so it can sit in a
        # page for months: chat.html had seven suggested-question buttons whose
        # handler had been truncated to "q = " by a |tojson quote collision.
        try:
            alpine = pg.evaluate("""() => {
              const AF = Object.getPrototypeOf(async function(){}).constructor;
              const out = [];
              document.querySelectorAll('*').forEach(el => {
                for (const a of el.attributes) {
                  const n = a.name;
                  if (!(n.startsWith('x-') || n.startsWith(':') || n.startsWith('@'))) continue;
                  if (['x-cloak','x-ref','x-transition','x-teleport'].includes(n)) continue;
                  if (n.startsWith('x-transition')) continue;
                  try { new AF(['__s'], 'with(__s){ (' + a.value + ') }'); }
                  catch (e) {
                    try { new AF(['__s'], 'with(__s){ ' + a.value + ' }'); }
                    catch (e2) { out.push(n + '=' + JSON.stringify(a.value).slice(0,50)); }
                  }
                }
              });
              return [...new Set(out)]; }""")
        except Exception:
            alpine = []
        ok = status == 200 and not errs and not fails and not alpine
        if not ok: bad += 1
        mark = "ok  " if ok else "BAD "
        extra = ""
        if errs: extra += f" errors={errs[:1]}"
        if fails: extra += f" failed={fails[:2]}"
        if alpine: extra += f" bad-alpine={alpine[:2]}"
        print(f"  {mark}{status} {path}{extra}")
        pg.remove_listener("pageerror", pg.listeners("pageerror")[-1]) if False else None
    b.close()
print(f"\n{len(PATHS)-bad}/{len(PATHS)} pages clean")
sys.exit(1 if bad else 0)
