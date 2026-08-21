import asyncio, httpx, time, os
from playwright.async_api import async_playwright
BASE = "http://127.0.0.1:8798"; OUT = "/root/chart-qa-screens2"
os.makedirs(OUT, exist_ok=True)

async def main():
    # create a chart for chat page
    s = httpx.Client(base_url=BASE, timeout=30)
    phone = "0912" + str(int(time.time()))[-7:]
    s.post("/api/auth/otp/request", data={"phone": phone})
    code = s.post("/api/auth/otp/request", data={"phone": phone}).json()["dev_code"]
    s.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    ci = s.get("/api/cities", params={"q": "تهران"}).json()["results"][0]
    ch = s.post("/api/charts", data={"calendar":"jalali","year":"1370","month":"1","day":"15","hour":"10","minute":"30","city_fa":ci["city_fa"],"lat":str(ci["lat"]),"lon":str(ci["lon"])}, follow_redirects=False)
    try:
        cid = ch.json().get("chart_id") or ch.json().get("id")
    except Exception:
        cid = None
    # cookies (chart_user + chart_access)
    rc = s.cookies.get("chart_user"); ck = []
    if rc: ck.append({"name":"chart_user","value":rc,"url":BASE})
    ca = s.cookies.get("chart_access")
    if ca: ck.append({"name":"chart_access","value":ca,"url":BASE})
    print("cid=", cid)

    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        for name, path in [("birth-form","/birth-form"),("dashboard","/dashboard"),("chat", f"/chat/{cid}" if cid else "/")]:
            ctx = await b.new_context(viewport={"width":390,"height":844}, locale="fa-IR")
            await ctx.add_cookies(ck)
            pg = await ctx.new_page()
            errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
            try:
                await pg.goto(BASE+path, wait_until="networkidle", timeout=20000)
            except Exception as e:
                errs.append("NAV:"+str(e)[:100])
            await pg.wait_for_timeout(1500)
            await pg.screenshot(path=f"{OUT}/{name}-m.png")
            print(f"[{name}] errs={len(errs)} title={await pg.title()}"); [print("  E:",e[:110]) for e in errs[:4]]
            await ctx.close()
        await b.close()
asyncio.run(main()); print("DONE")
