"""A10 (audit r4): coupon RESERVATION pattern.

Regression: coupon slots were checked with a stale read at order creation and
consumed at payment verify — two users could both pass the last-slot check and
one lost money when the atomic consume failed. Now the slot is reserved
ATOMICALLY at creation and released on every no-payment path (gateway request
error, verify failure, refund, stale pending order)."""
import json
import time

from fastapi.testclient import TestClient

from app.db import engine
from app.main import app as main_app
from app.models import Coupon, Order
from sqlmodel import Session, select


class FakeZP:
    def __init__(self):
        import uuid as _u
        self.uid = _u.uuid4().hex[:10]

    def request(self, *a, **k):
        return f"Q{int(time.time())}{self.uid}", f"https://pay.zarinpal.com/pg/StartPay/Q{int(time.time())}{self.uid}"

    def verify(self, authority, amount_rial):
        return {"ref_id": "200000000001", "card_pan": "621986****0000"}

    def refund(self, *a, **k):
        return {"ref_id": "R200000000001"}  # audit r4 B6 — real refund path


class FailVerifyZP(FakeZP):
    def verify(self, authority, amount_rial):
        from app.payment.zarinpal import ZarinpalError
        raise ZarinpalError("verification rejected")


def _mk_chart(c: TestClient) -> tuple[str, str]:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def _coupon(s: Session, code: str, max_uses=1) -> Coupon:
    import uuid as _uuid
    code = f"{code}-{_uuid.uuid4().hex[:6].upper()}"  # unique per run (test DB persists)
    c = Coupon(code=code, percent=10, max_uses=max_uses, active=True)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def test_last_slot_reserved_at_creation(monkeypatch):
    """Two users racing for the LAST coupon slot: exactly one may create an order."""
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "SAVE10", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    r1 = c.post("/api/orders", data={"chart_id": cid, "plan_key": "gold", "coupon": code},
                )
    assert r1.status_code == 200, r1.text
    # second user with the same coupon — slot already reserved → 400
    cid2, tok2 = _mk_chart(c)
    ck2 = {"chart_access": json.dumps({cid2: tok2})}
    c.cookies.update(ck2)
    r2 = c.post("/api/orders", data={"chart_id": cid2, "plan_key": "gold", "coupon": code},
                )
    assert r2.status_code == 400
    assert "مصرف شده" in r2.json()["detail"]


def test_verify_failure_releases_slot(monkeypatch):
    """Payment verification fails → order failed → coupon slot returned."""
    monkeypatch.setattr("app.main.ZarinpalClient", FailVerifyZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "SAVE11", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    r = c.post("/api/orders", data={"chart_id": cid, "plan_key": "gold", "coupon": code},
               )
    oid = r.json()["order_id"]
    with Session(engine) as s:
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp.used_count == 1  # reserved at creation
        o = s.get(Order, oid)
        auth = o.authority
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    with Session(engine) as s:
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp.used_count == 0, "slot must be released after failed verify"
        o = s.get(Order, oid)
        assert o.status == "failed"


def test_gateway_down_at_creation_releases_slot(monkeypatch):
    """Zarinpal request() raises at order creation → failed order → slot released."""
    class DownZP:
        def request(self, *a, **k):
            from app.payment.zarinpal import ZarinpalError
            raise ZarinpalError("gateway down")

    monkeypatch.setattr("app.main.ZarinpalClient", DownZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", DownZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "SAVE12", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    r = c.post("/api/orders", data={"chart_id": cid, "plan_key": "gold", "coupon": code},
               )
    assert r.status_code == 502
    with Session(engine) as s:
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp.used_count == 0, "slot must be released when gateway is down"


def test_refund_returns_slot(monkeypatch):
    """Admin refund of a paid coupon order returns the reserved slot."""
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "SAVE13", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    ck = {"chart_access": json.dumps({cid: tok})}
    c.cookies.update(ck)
    oid = c.post("/api/orders", data={"chart_id": cid, "plan_key": "gold", "coupon": code},
                 ).json()["order_id"]
    with Session(engine) as s:
        auth = s.get(Order, oid).authority
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK")
    with Session(engine) as s:
        assert s.get(Order, oid).status == "paid"
        assert s.exec(select(Coupon).where(Coupon.code == code)).first().used_count == 1
    # admin refund (audit r4 B6: real Zarinpal refund call — FakeZP.refund mocked)
    from app.main import _admin_cookie_value
    admin_ck = {"chart_admin": _admin_cookie_value()}
    c.cookies.update(admin_ck)
    r = c.post(f"/api/admin/orders/{oid}/refund")
    assert r.status_code == 200, r.text
    with Session(engine) as s:
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp.used_count == 0, "refund must return the slot"
