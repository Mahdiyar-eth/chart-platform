import asyncio, httpx, time, os, uuid
from playwright.async_api import async_playwright
from sqlmodel import Session, select
from app.db import engine
from app.models import Order, User, Chart
BASE = "http://127.0.0.1:8798"; OUT = "/root/chart-qa-screens2"
os.makedirs(OUT, exist_ok=True)
import app.main  # ensure env/models loaded

def grant_gold(chart_id, user_id):
    # insert a paid 'gold' order so chat access is allowed
    with Session(engine) as s:
        exists = s.exec(select(Order).where(Order.chart_id==chart_id, Order.status=="paid", Order.plan_key=="gold")).first()
        if not exists:
            s.add(Order(id=str(uuid.uuid4()), chart_id=chart_id, user_id=user_id,
                         plan_key="gold", amount_rial=0, status="paid", authority=f"qa-{uuid.uuid4().hex[:10]}"))
            s.commit()
            return True
    return False

async def main():
    # create user + 2 charts via API
    s = httpx.Client(base_url=BASE, timeout=30)
    phone = "0912" + str(uuid.uuid4().int)[:7]
    code = s.post("/api/auth/otp/request", data={"phone": phone}).json()["dev_code"]
    s.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    ci = s.get("/api/cities", params={"q": "تهران"}).json()["results"][0]
    def mkchart():
        ch = s.post("/api/charts", data={"calendar":"jalali","year":"1370","month":"1","day":"15","hour":"10","minute":"30","city_fa":ci["city_fa"],"lat":str(ci["lat"]),"lon":str(ci["lon"])}, follow_redirects=False)
        return ch.json().get("chart_id") or ch.json().get("id")
    cid_unlocked = mkchart()
    cid_locked = mkchart()
    # find the user by phone, grant gold on the unlocked chart
    with Session(engine) as ss:
        # find the user by cookie'd session — instead look up via query using phone
        user = ss.exec(select(User).where(User.phone==phone)).first()
        uid = user.id if user else None
        if cid_unlocked and uid:
            grant_gold(cid_unlocked, uid)
        # ensure chart owns user (charts created while logged in via cookie)
    ck=[]
    rc=s.cookies.get("chart_user")
    if rc: ck.append({"name":"chart_user","value":rc,"url":BASE})
    ca=s.cookies.get("chart_access")
    if ca: ck.append({"name":"chart_access","value":ca,"url":BASE})
    print("unlocked_cid=",cid_unlocked,"locked_cid=",cid_locked,"user=",uid)

    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        for name, path in [("chat-unlocked", f"/chat/{cid_unlocked}"), ("chat-locked", f"/chat/{cid_locked}")]:
            ctx = await b.new_context(viewport={"width":390,"height":844}, locale="fa-IR")
            await ctx.add_cookies(ck)
            pg = await ctx.new_page()
            errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
            try:
                await pg.goto(BASE+path, wait_until="networkidle", timeout=20000)
            except Exception as e:
                errs.append("NAV:"+str(e)[:100])
            await pg.wait_for_timeout(2200)  # let Alpine + fetch settle
            await pg.screenshot(path=f"{OUT}/{name}.png")
            # dump access + history state via page JS
            print(f"[{name}] errs={len(errs)} title={await pg.title()}")
            for e in errs[:4]: print("  E:",e[:110])
            await ctx.close()
        await b.close()
asyncio.run(main()); print("DONE")
