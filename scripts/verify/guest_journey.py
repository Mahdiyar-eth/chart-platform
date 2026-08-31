"""The whole guest journey, in a real browser. Assert only what is observed."""
import os, re, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8798")
CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
OUT = os.environ.get("VERIFY_OUT", "/tmp")
res = []
def check(n, ok, d=""):
    res.append((n, bool(ok), d))
    print(("  PASS  " if ok else "  FAIL  ") + n + ((" :: " + str(d)[:150]) if d else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME,
                          args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))

    # 1 ── land, go to the form via the tab bar (client-side)
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.evaluate("window.__mark='alive'")
    pg.goto(BASE + "/birth-form", wait_until="networkidle")
    check("birth form reachable", "چارت" in pg.content())
    check("form page has its own title", "چارت رایگان" in pg.title(), pg.title())

    # 2 ── fill the wizard as a guest
    def setv(label, val):
        loc = pg.get_by_label(label, exact=True)
        if loc.count() and loc.first.is_visible():
            loc.first.fill(val); return True
        return False
    for lbl, v in (("سال تولد","1373"), ("ماه تولد","6"), ("روز تولد","1")):
        check(f"field {lbl}", setv(lbl, v))
    pg.click("button:has-text('ادامه')")
    pg.wait_for_timeout(400)
    # step 2: time known
    setv("ساعت تولد", "6"); setv("دقیقهٔ تولد", "10")
    pg.click("button:has-text('ادامه')")
    pg.wait_for_timeout(400)
    # step 3: city autocomplete
    city = pg.locator("#birth-city")
    if city.count():
        city.fill("تهران")
        pg.wait_for_timeout(900)
        # step 1's calendar chips are still in the DOM but hidden — take the
        # first VISIBLE chip, which is a city result
        picked = None
        for i in range(pg.locator(".chip").count()):
            c = pg.locator(".chip").nth(i)
            if c.is_visible() and "تهران" in (c.inner_text() or ""):
                picked = c; break
        check("city autocomplete returns تهران", picked is not None)
        if picked: picked.click()
    pg.click("button:has-text('ادامه')")
    pg.wait_for_timeout(250)
    for _ in range(3):
        nxt = pg.locator("button:has-text('ادامه')").first
        if nxt.is_visible(): nxt.click(); pg.wait_for_timeout(250)
        else: break

    submit = pg.locator("button[type=submit]").first
    check("submit button reached", submit.is_visible())
    submit.click()
    pg.wait_for_url(re.compile(r"/chart/"), timeout=45000)
    chart_url = pg.url
    cid = chart_url.rstrip("/").split("/")[-1].split("?")[0]
    check("guest chart created without login", "/chart/" in chart_url, chart_url)

    # 3 ── the chart page
    pg.wait_for_timeout(2500)
    body = pg.content()
    check("chart page renders the wheel", pg.locator("svg").count() > 3)
    check("preview section present", "نگاه اول" in body or "پاسخ چارت" in body)
    check("solar is offered from the chart page", "/solar/" in body)
    check("relocation is offered from the chart page", "/relocation/" in body)
    check("explore link carries the chart", f"/explore?chart={cid}" in body)
    check("transit image carries the token", "transit-year.svg?t=" in body)
    # images are loading="lazy": scroll them into view before judging, or a
    # below-the-fold image reads as broken when it simply has not loaded
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(1500)
    pg.evaluate("window.scrollTo(0, 0)")
    pg.wait_for_timeout(500)
    imgs = pg.evaluate("""async () => {
      await Promise.all([...document.images].map(i => i.complete ? null :
        new Promise(r => { i.addEventListener('load', r); i.addEventListener('error', r); })));
      return [...document.images].map(i => ({src:(i.currentSrc||i.src).slice(-60),
                                             ok:i.complete && i.naturalWidth>0})); }""")
    broken = [i for i in imgs if not i["ok"]]
    check("no broken images", not broken, broken[:2])
    pg.screenshot(path=f"{OUT}/j_chart.png")

    # 4 ── guest identity really is anonymous right now
    me = pg.evaluate("async () => (await (await fetch('/api/auth/me')).json())")
    check("still a guest", me.get("user") is None, me)

    # 5 ── login with next=, and the chart must be claimed
    pg.goto(f"{BASE}/account/login?next=/chart/{cid}", wait_until="networkidle")
    check("login adopted next=", f'next: "/chart/{cid}"' in pg.content())
    phone = "0912" + str(abs(hash(cid)))[:8]
    pg.locator("input[x-model='phone']").first.fill(phone)
    pg.click("button[type=submit]")
    pg.wait_for_timeout(1200)
    dev = pg.locator(".u-gold").first
    code = dev.inner_text().strip() if dev.count() else ""
    check("dev OTP shown (OTP_DEV_MODE)", bool(code), code)
    pg.locator("input[x-model='code']").first.fill(code)
    pg.click("button[type=submit]")
    pg.wait_for_timeout(2500)
    check("login returned to the chart, not /account", f"/chart/{cid}" in pg.url, pg.url)

    # 6 ── the claim actually happened
    pg.goto(BASE + "/account", wait_until="networkidle")
    acct = pg.content()
    check("account page has no raw JS on screen",
          "function dashSearch" not in pg.inner_text("body"))
    check("claimed chart appears in the account", "هنوز چارتی نساخته" not in acct, )
    pg.screenshot(path=f"{OUT}/j_account.png")

    check("no page errors in the whole journey", not errs, errs[:3])
    b.close()

bad = [n for n,ok,_ in res if not ok]
print(f"\n{len(res)-len(bad)}/{len(res)} passed")
if bad: print("FAILED: " + "; ".join(bad))
sys.exit(1 if bad else 0)
