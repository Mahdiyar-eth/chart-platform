import asyncio, httpx, json, time
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8798"
OUT = "/root/chart-qa-screens"
import os; os.makedirs(OUT, exist_ok=True)

async def main():
    phone = "0912" + str(int(time.time()))[-7:]
    # --- API: OTP login (dev code) + create chart ---
    s = httpx.Client(base_url=BASE, follow_redirects=False, timeout=30)
    rq = s.post("/api/auth/otp/request", data={"phone": phone})
    code = rq.json().get("dev_code")
    rv = s.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    chip = rv.headers.get("set-cookie", "")
    cookie_val = None
    for part in chip.split(";"):
        part = part.strip()
        if part.startswith("chart_user="):
            cookie_val = part.split("=", 1)[1]
    # city lookup
    ci = s.get("/api/cities", params={"q": "تهران"}).json()
    c0 = ci["results"][0]
    ch = s.post("/api/charts", data={
        "calendar": "jalali", "year": "1370", "month": "1", "day": "15",
        "hour": "10", "minute": "30", "city_fa": c0["city_fa"],
        "lat": str(c0["lat"]), "lon": str(c0["lon"])}, follow_redirects=False)
    cid = None
    try:
        cid = ch.json().get("chart_id") or ch.json().get("id")
    except Exception:
        cid = None
    # chart_access cookie (created while logged in? if not, the browser needs it)
    ck_cookies = []
    if cookie_val:
        ck_cookies.append({"name": "chart_user", "value": cookie_val, "url": BASE})

    # --- Browser ---
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        pages = [
            ("home", "/"), ("birth-form", "/birth-form"), ("plans", "/plans"),
            ("explore", "/explore"), ("synastry", "/synastry"), ("rectify", "/rectify"),
            ("articles", "/articles"), ("faq", "/faq"), ("learn", "/learn"),
            ("about", "/about"), ("account", "/account"), ("dashboard", "/dashboard"),
            ("admin-login", "/admin/login"),
        ]
        # auth'd pages
        for name, path in pages:
            for vp in [("m", 390, 844), ("d", 1280, 800)]:
                tag, w, h = vp
                ctx = await browser.new_context(viewport={"width": w, "height": h}, locale="fa-IR")
                await ctx.add_cookies(ck_cookies)
                pg = await ctx.new_page()
                errs = []
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                try:
                    await pg.goto(BASE + path, wait_until="networkidle", timeout=20000)
                except Exception as e:
                    errs.append("NAV:" + str(e)[:120])
                await pg.wait_for_timeout(1200)
                fp = f"{OUT}/{name}-{tag}.png"
                try:
                    await pg.screenshot(path=fp, full_page=False)
                except Exception as e:
                    errs.append("SHOT:" + str(e)[:80])
                title = await pg.title()
                print(f"[{name} {tag}] title={title!r} fpath={fp} console_errs={len(errs)}")
                for e in errs[:3]:
                    print("    ERR:", e[:120])
                await ctx.close()
        await browser.close()

asyncio.run(main())
print("DONE")
