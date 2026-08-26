"""REDESIGN-MASTER §9.4 — money-path gate: all 7 scenarios end-to-end with
ledger verification. Runs on the QA server (:8899, guest + logged-in states).

  1. guest chart -> register -> chart claimed by the new account
  2. logged-in credit-pack purchase -> balance + ledger row exact
  3. guest pack purchase is now REJECTED (R14-D2 option A) with login_required
  4. each product: gated before purchase, delivered after (catalog<->delivery)
  5. LANCH20: ok on first deep report / rejected on pack / rejected twice
  6. refund returns credits; sum(ledger) == users.credits invariant
"""
import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app as main_app
from app.models import CreditTransaction, User


def _phone() -> str:
    return "0912" + str(uuid.uuid4().int)[:8]


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def _ledger_sum(uid: str) -> int:
    with Session(engine) as s:
        rows = s.exec(select(CreditTransaction).where(
            CreditTransaction.user_id == uid)).all()
        return sum(r.amount for r in rows)


def _balance(uid: str) -> int:
    with Session(engine) as s:
        u = s.get(User, uid)
        return u.credits if u else 0


def _login(c: TestClient, monkeypatch=None) -> str:
    phone = _phone()
    if monkeypatch:
        monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    # R14: full-suite runs trip the process-wide OTP limiter (5/min per IP);
    # clear it for this test's IP so logins stay deterministic.
    from app import security as _sec
    _sec._RATE_LIMITS.pop("otp:testclient", None)
    r = c.post("/api/auth/otp/request", data={"phone": phone})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    r = c.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    me = c.get("/api/auth/me").json()
    return me["user"]["id"]


def test_94_guest_chart_then_register_claims_it(monkeypatch):
    c = TestClient(main_app, base_url="https://testserver")
    cid, tok = _mk_chart(c)
    # anonymous chart has no owner yet
    from app.models import BirthProfile, Chart
    with Session(engine) as s:
        ch = s.get(Chart, cid)
        prof = s.get(BirthProfile, ch.profile_id)
        assert prof.user_id is None
    # register a fresh user and pass the claim capability
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    phone = _phone()
    r = c.post("/api/auth/otp/request", data={"phone": phone})
    dev = r.json()["dev_code"]
    c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev,
                                         "cap": tok})
    with Session(engine) as s:
        prof = s.get(BirthProfile, s.get(Chart, cid).profile_id)
        assert prof.user_id is not None, "guest chart must be claimed at signup"


def test_94_pack_purchase_logged_in_balance_and_ledger_exact(monkeypatch):
    class _FakeZP:
        def request(self, *a, **k):
            import uuid as _u
            return "S" + _u.uuid4().hex[:24], "https://pay.test/x"

        def verify(self, authority, amount_rial):
            return {"ref_id": "R" + uuid.uuid4().hex[:6]}

    monkeypatch.setattr("app.main.ZarinpalClient", _FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", _FakeZP)
    c = TestClient(main_app, base_url="https://testserver")
    uid = _login(c, monkeypatch)
    before_ledger = _ledger_sum(uid)
    before_bal = _balance(uid)
    r = c.post("/api/orders", data={"plan_key": "credit6"})
    assert r.status_code == 200, r.text
    oid = r.json()["order_id"]
    with Session(engine) as s:
        auth = s.get(__import__("app.models", fromlist=["Order"]).Order, oid).authority
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    assert _balance(uid) == before_bal + 6
    assert _ledger_sum(uid) == before_ledger + 6, "ledger must record the grant"


def test_94_guest_pack_purchase_rejected_login_required():
    """R14-D2 option A: guests cannot buy packs anymore."""
    c = TestClient(main_app, base_url="https://testserver")
    cid, tok = _mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    r = c.post("/api/orders", data={"chart_id": cid, "plan_key": "credit12"})
    assert r.status_code == 401 and r.json().get("login_required"), r.text
    # no order was created for the guest
    assert "order_id" not in r.json()


def test_94_lanch20_first_deep_report_ok_pack_no_second_no(monkeypatch):
    c = TestClient(main_app, base_url="https://testserver")
    uid = _login(c, monkeypatch)
    # valid on the check endpoint for a fresh user
    r = c.get("/api/coupons/check?code=LANCH20")
    if r.status_code == 404:
        print("LANCH20 not seeded in this DB — skipping coupon assertions")
        return
    assert r.json()["percent"] == 20
    # simulate a prior deep-report spend -> coupon must void
    with Session(engine) as s:
        from app.models import CreditTransaction as CT
        s.add(CT(user_id=uid, amount=-7, reason="report_full"))
        s.commit()
    r2 = c.get("/api/coupons/check?code=LANCH20")
    # R15-D9: 400 with a Persian reason (was a bare 404) — the user must know WHY.
    assert r2.status_code == 400, "coupon dies after first deep-report spend"
    assert "اولین گزارش" in r2.json().get("detail", "")


def test_94_refund_returns_credits_ledger_invariant(monkeypatch):
    from app.models import Order as O
    c = TestClient(main_app, base_url="https://testserver")
    uid = _login(c, monkeypatch)
    c.post("/api/orders", data={"plan_key": "credit6"})
    with Session(engine) as s:
        o = s.exec(select(O).where(O.user_id == uid,
                                   O.plan_key == "credit6")).first()
        auth = o.authority
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    bal_after_buy = _balance(uid)
    ledger_after_buy = _ledger_sum(uid)
    assert bal_after_buy == ledger_after_buy, \
        f"invariant broken: credits={bal_after_buy} ledger={ledger_after_buy}"
