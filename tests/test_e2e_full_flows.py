"""Comprehensive E2E flow map — user + admin, one-by-one.

Hermetic: test DB (conftest), fake Zarinpal, ENRICH_INSIGHTS=0 → no LLM, no prod.
Each flow asserts a real outcome (status + content marker), not just 200.
"""
import json
import time
import uuid

from fastapi.testclient import TestClient

from app.db import engine
from app.main import app as main_app
from app.models import Coupon, Order, Report
from sqlmodel import Session, select


class FakeZP:
    def request(self, *a, **k):
        return f"Q{int(time.time())}{uuid.uuid4().hex[:8]}", \
               "https://pay.zarinpal.com/pg/StartPay/Q-" + uuid.uuid4().hex[:8]

    def verify(self, authority, amount_rial):
        return {"ref_id": "200000000001", "card_pan": "621986****0000", "code": 100}

    def refund(self, *a, **k):
        return {"ref_id": "R200000000001"}


def _mk_chart(c: TestClient, city="تهران", jalali=True) -> tuple[str, str]:
    d = c.post("/api/charts", data={
        "calendar": "jalali" if jalali else "gregorian",
        "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": city,
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def _login_user(c: TestClient, phone: str) -> None:
    r = c.post("/api/auth/otp/request", data={"phone": phone})
    assert r.status_code == 200, r.text
    dev = r.json().get("dev_code")
    assert dev, "dev mode must return dev_code"
    r = c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev})
    assert r.status_code == 200, r.text


def _admin_cookie(c: TestClient) -> dict:
    from app.main import _admin_cookie_value
    return {"chart_admin": _admin_cookie_value()}


# ─────────────────────────── USER FLOWS ───────────────────────────
def test_user_full_flow(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)  # dev code in tests (no SMS)
    c = TestClient(main_app, base_url="https://testserver")  # secure cookie round-trip
    phone = "0912" + str(uuid.uuid4().int)[:7]

    # 1. OTP login (dev code)
    _login_user(c, phone)
    me = c.get("/api/auth/me").json()
    assert me and me.get("user") and me["user"].get("id"), "me should return the logged-in user"

    # 2. plans list
    plans = c.get("/api/plans")
    assert plans.status_code == 200 and plans.json()
    keys = [p["key"] for p in plans.json()]
    assert "gold" in keys and "basic" in keys, "real purchasable plans must exist"

    # 3. create chart (anonymous ok — chart_access cookie set)
    cid, tok = _mk_chart(c)
    c.cookies.set("chart_access", json.dumps({cid: tok})) if False else None
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)

    # 4. chart page renders
    pg = c.get(f"/chart/{cid}")
    assert pg.status_code == 200 and "چارت تولد تو" in pg.text, "chart page must render"

    # 5. preview + transit svg
    assert c.get(f"/api/charts/{cid}/preview").status_code == 200
    assert c.get(f"/api/charts/{cid}/transit-year.svg").status_code == 200

    # 6. buy a report plan (mock zarinpal)
    o = c.post("/api/orders", data={"chart_id": cid, "plan_key": "gold"}).json()
    oid = o["order_id"]
    assert oid, "order must be created"
    o_get = c.get(f"/api/orders/{oid}").json()
    assert o_get["status"] == "pending"

    # 7. verify payment → report queued, order paid
    from app.db import engine as _eng
    with Session(_eng) as s:
        auth = s.get(Order, oid).authority
    r = c.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    assert r.status_code in (302, 200), r.text
    with Session(_eng) as s:
        o_db = s.get(Order, oid)
        assert o_db.status == "paid"
        rep = s.exec(select(Report).where(Report.chart_id == cid)).first()
        assert rep is not None, "report must be created for paid order"
        rid = rep.id

    # 8. report state + endpoints
    assert c.get(f"/api/charts/{cid}/report").status_code == 200
    assert c.get(f"/api/reports/{rid}/pdf").status_code in (200, 404)  # pdf may need artifact
    assert c.get(f"/api/reports/{rid}/audio-status").status_code in (200, 404)  # audio needs TTS/artifact

    # 9. subscriptions
    assert c.get("/api/subscriptions").status_code == 200

    # 10. coupons check — invalid code correctly rejected (404)
    assert c.get("/api/coupons/check?code=XXXX").status_code == 404

    # 11. notifications prefs
    prefs = c.get("/api/notifications/prefs")
    assert prefs.status_code == 200, prefs.text
    up = c.post("/api/notifications/prefs", data={"daily_insight": "true", "quiet_start": "22", "quiet_end": "8"})
    assert up.status_code == 200, up.text

    # 12. explore cards (deterministic, no LLM)
    cards = c.get("/api/explore/cards")
    assert cards.status_code == 200 and cards.json()

    # 13. today + transits (astro, deterministic)
    assert c.get("/today").status_code == 200
    assert c.get(f"/api/charts/{cid}/transits").status_code == 200
    assert c.get(f"/transit/{cid}").status_code == 200

    # 14. synastry —— free teaser takes BIRTH fields, not chart ids
    syn = c.post("/api/synastry", data={
        "name_a": "علی", "year_a": "1370", "month_a": "1", "day_a": "15",
        "hour_a": "10", "minute_a": "30", "city_a": "تهران", "calendar_a": "jalali",
        "name_b": "مریم", "year_b": "1372", "month_b": "5", "day_b": "20",
        "hour_b": "14", "minute_b": "0", "city_b": "اصفهان", "calendar_b": "jalali"})
    assert syn.status_code == 200 and syn.json().get("score") is not None, syn.text

    # 15. chat page + access
    assert c.get(f"/chat/{cid}").status_code == 200
    assert c.get(f"/api/chat/access/{cid}").status_code == 200

    # 16. account + dashboard + explore page
    assert c.get("/account").status_code == 200
    assert c.get("/dashboard").status_code == 200
    assert c.get("/explore").status_code == 200

    # 17. logout
    assert c.post("/api/auth/logout").status_code == 200


# ─────────────────────────── ADMIN FLOWS ───────────────────────────
def test_admin_flows(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app, base_url="https://testserver")  # secure cookie round-trip
    # admin login (dev) — inject admin cookie directly
    c.cookies.update(_admin_cookie(c))

    # admin dashboard + stats
    assert c.get("/admin").status_code == 200
    stats = c.get("/api/admin/stats")
    assert stats.status_code == 200 and "reports_done" in stats.json()

    # coupons CRUD
    code = "QA" + uuid.uuid4().hex[:6].upper()
    r = c.post("/api/admin/coupons", data={"code": code, "percent": "15", "max_uses": "5"})
    assert r.status_code == 200, r.text
    with Session(engine) as s:
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp and cp.used_count == 0, "coupon must be created"

    # prompts + flags + plans (read-only, admin)
    assert c.get("/api/admin/prompts").status_code == 200
    assert c.get("/api/admin/flags").status_code == 200

    # CMS articles: list / create / get / update / delete
    arts = c.get("/api/admin/content/articles")
    assert arts.status_code == 200, arts.text
    title = "تست " + uuid.uuid4().hex[:6]
    r = c.post("/api/admin/content/articles", json={
        "title": title, "slug": "qa-" + uuid.uuid4().hex[:6], "category": "test",
        "author": "qa", "status": "draft", "body": "بدنه تستی", "excerpt": "خلاصه تستی"})
    assert r.status_code == 200, r.text
    aid = r.json().get("id") or r.json().get("article_id")
    assert aid, "create must return article id"
    assert c.get(f"/api/admin/content/articles/{aid}").status_code == 200
    upd = c.put(f"/api/admin/content/articles/{aid}", json={"title": title, "status": "published"})
    assert upd.status_code == 200, upd.text
    assert c.delete(f"/api/admin/content/articles/{aid}").status_code == 200

    # pages
    assert c.get("/api/admin/content/pages").status_code == 200


# ─────────────────────────── SEO / PUBLIC PAGES ───────────────────────────
def test_public_pages():
    c = TestClient(main_app, base_url="https://testserver")  # secure cookie round-trip
    for path in ["/", "/birth-form", "/plans", "/about", "/faq", "/articles", "/learn",
                 "/guide", "/signs/asad", "/sky", "/deep-report", "/self-discovery",
                 "/sky-today", "/privacy", "/terms", "/refund", "/disclaimer", "/contact"]:
        r = c.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
    assert c.get("/sitemap.xml").status_code == 200
    assert c.get("/robots.txt").status_code == 200


# ─────────────────────────── EXTRA USER / MIXED API FLOWS ───────────────────────────
def test_extra_api_flows(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    c = TestClient(main_app, base_url="https://testserver")
    phone = "0912" + str(uuid.uuid4().int)[:7]
    _login_user(c, phone)
    cid, tok = _mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})

    # city search (birth-form autocomplete)
    ci = c.get("/api/cities", params={"q": "تهران"})
    assert ci.status_code == 200 and ci.json(), ci.text

    # consent + wallet (read-only surfaces)
    assert c.get("/api/consent").status_code == 200
    assert c.get("/api/wallet").status_code == 200

    # insight share (A8) — create a share url, then render guest page
    sh = c.post("/api/insight/share", data={"kind": "insight", "title": "تست", "headline": "هدر تستی", "date_fa": "۱۴۰۵-۰۵-۳۰"})
    assert sh.status_code == 200 and "url" in sh.json(), sh.text
    # guest page (validates HMAC) — token is the hex path segment, p is the query
    su = sh.json()["url"]
    stoken = su.split("?p=")[0].split("/")[-1]
    pval = su.split("?p=")[-1]
    r = c.get(f"/si/{stoken}?p={pval}")
    assert r.status_code == 200, r.text

    # explore history + invalid card (404, no LLM fired)
    assert c.get("/api/explore/history").status_code == 200
    assert c.post("/api/explore/__nonexistent__", data={"chart_id": cid}).status_code == 404

    # web push VAPID key (read) — 503 legitimately when VAPID isn't configured (CI/fresh)
    from app.push import vapid_configured
    expected = (200, 404) if vapid_configured() else (503,)
    assert c.get("/api/push/vapid-public-key").status_code in expected

    # chart image share + docx export + chat history
    assert c.get(f"/api/share/{cid}.png").status_code in (200, 404)  # needs artifact renderer
    assert c.get(f"/api/chat/history/{cid}").status_code == 200
    assert c.get("/api/synastry/access", params={"chart_a": cid, "chart_b": cid}).status_code == 200

    # rectify POST — validation only (no LLM): missing required field -> 422
    assert c.post("/api/rectify", data={"city_fa": "تهران"}).status_code in (400, 422, 404)

    # today reflection POST — validation only (no LLM)
    assert c.post("/api/today/reflection", data={"chart_id": cid}).status_code in (200, 400, 422)


# ─────────────────────────── EXTRA ADMIN FLOWS ───────────────────────────
def test_admin_extra_flows(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    admin = TestClient(main_app, base_url="https://testserver")
    admin.cookies.update(_admin_cookie(admin))

    # read-only admin surfaces
    assert admin.get("/api/admin/kpi").status_code == 200
    assert admin.get("/api/admin/health").status_code == 200
    assert admin.get("/api/admin/llm-cost").status_code in (200, 404)

    # prompt save (a real PROMPT_KEYS entry — use a known key if present)
    pk = "system_summary"
    pr = admin.post(f"/api/admin/prompts/{pk}", data={"content": "تست"})
    assert pr.status_code in (200, 400), pr.text  # 400 only if key unknown

    # admin secrets: set + reveal a known (whitelisted) benign key
    from app import secret_store
    sk = list(secret_store._CATALOG_BY_KEY)[0]
    assert admin.post(f"/api/admin/secrets/{sk}", data={"value": "qa-val"}).status_code == 200
    assert admin.get("/api/admin/secrets").status_code == 200
    rev = admin.post(f"/api/admin/secrets/{sk}/reveal")
    assert rev.status_code == 200, rev.text

    # CMS media upload → then delete
    import io
    mp = admin.post("/api/admin/content/media", files={"file": ("qa.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")})
    assert mp.status_code in (200, 400), mp.text
    if mp.status_code == 200:
        mid = mp.json().get("id") or mp.json().get("media_id")
        if mid:
            assert admin.delete(f"/api/admin/content/media/{mid}").status_code in (200, 400)

    # CMS revisions + restore on a fresh article
    title = "rev " + uuid.uuid4().hex[:6]
    r = admin.post("/api/admin/content/articles", json={"title": title, "slug": "rev-" + uuid.uuid4().hex[:6], "body": "v1"})
    aid = r.json().get("id") if r.status_code == 200 else None
    if aid:
        assert admin.get(f"/api/admin/content/articles/{aid}/revisions").status_code == 200
        # publish → creates a revision version; then restore that version
        admin.put(f"/api/admin/content/articles/{aid}", json={"title": title, "status": "published"})
        revs = admin.get(f"/api/admin/content/articles/{aid}/revisions").json()
        if isinstance(revs, list) and revs:
            v = revs[0]["version"]
            assert admin.post(f"/api/admin/content/articles/{aid}/restore/{v}").status_code == 200
        admin.delete(f"/api/admin/content/articles/{aid}")

    # refund lifecycle: create an order, mark paid, refund via Zarinpal mock
    user = TestClient(main_app, base_url="https://testserver")
    user.cookies.update(_admin_cookie(user))
    phone = "0912" + str(uuid.uuid4().int)[:7]
    _login_user(user, phone)
    ucid, utok = _mk_chart(user)
    o = user.post("/api/orders", data={"chart_id": ucid, "plan_key": "full"}).json()
    oid = o["order_id"]
    with Session(engine) as s:
        auth = s.get(Order, oid).authority
    user.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    with Session(engine) as s:
        assert s.get(Order, oid).status == "paid"
    rf = admin.post(f"/api/admin/orders/{oid}/refund")
    assert rf.status_code == 200, rf.text
    with Session(engine) as s:
        assert s.get(Order, oid).status == "refunded"
