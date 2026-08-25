"""C-05 / AC-04 — stale pending orders must release their coupon slot.

Regression (audit r4 A10): an abandoned Zarinpal payment left the Order stuck
'pending', permanently consuming a coupon slot (used_count). The hourly sweep
(scripts/release_stale_coupons.py -> app.payment.orders.sweep_stale_orders)
must expire stale pending orders and return the slot so max_uses coupons never
lock up. Idempotent (used_count>0 guard): running twice must not double-release.
"""
import json
import time
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app as main_app
from app.models import Coupon, Order
from app.payment.orders import sweep_stale_orders
from app.timeutil import utcnow


class FakeZP:
    def __init__(self):
        import uuid as _u
        self.uid = _u.uuid4().hex[:10]

    def request(self, *a, **k):
        return f"Q{int(time.time())}{self.uid}", "https://pay.zarinpal.com/pg/StartPay/Q"

    def verify(self, authority, amount_rial):
        return {"ref_id": "200000000001", "card_pan": "621986****0000"}


def _mk_chart(c: TestClient) -> tuple[str, str]:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def _coupon(s: Session, code: str, max_uses=1) -> Coupon:
    import uuid as _uuid
    code = f"{code}-{_uuid.uuid4().hex[:6].upper()}"
    c = Coupon(code=code, percent=10, max_uses=max_uses, active=True)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def test_stale_pending_order_releases_coupon(monkeypatch):
    """A pending order older than the window releases its coupon slot."""
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "STALE1", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    oid = c.post("/api/orders", data={"chart_id": cid, "plan_key": "credit12", "coupon": code}
                 ).json()["order_id"]
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "pending"
        assert o.coupon_id, "order must carry the coupon reservation"
        cp = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp.used_count == 1, "slot reserved at creation"
        # back-date the order so it's stale
        o.created_at = utcnow() - timedelta(hours=2)
        s.commit()
        released = sweep_stale_orders(s)
        assert released >= 1, "the stale pending order must release a slot"
        cp2 = s.exec(select(Coupon).where(Coupon.code == code)).first()
        assert cp2.used_count == 0, "coupon slot must be returned"
        assert s.get(Order, oid).status == "failed", "order gets a fresh-attempt status"


def test_fresh_pending_order_not_swept(monkeypatch):
    """A recent pending order (within the window) must NOT be expired."""
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "FRESH1", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    oid = c.post("/api/orders", data={"chart_id": cid, "plan_key": "credit12", "coupon": code}
                 ).json()["order_id"]
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "pending"  # just created, still fresh
        _released = sweep_stale_orders(s, stale_minutes=30)
        assert s.get(Order, oid).status == "pending", "fresh order must not be expired"
        assert s.exec(select(Coupon).where(Coupon.code == code)).first().used_count == 1


def test_sweep_is_idempotent(monkeypatch):
    """Running the sweep twice must not double-release a slot."""
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", FakeZP)
    c = TestClient(main_app)
    with Session(engine) as s:
        cp0 = _coupon(s, "IDEM1", max_uses=1)
    code = cp0.code
    cid, tok = _mk_chart(c)
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    oid = c.post("/api/orders", data={"chart_id": cid, "plan_key": "credit12", "coupon": code}
                 ).json()["order_id"]
    with Session(engine) as s:
        s.get(Order, oid).created_at = utcnow() - timedelta(hours=2)
        s.commit()
        first = sweep_stale_orders(s)
        second = sweep_stale_orders(s)  # second pass must not release again
        assert first >= 1
        assert second == 0, "idempotent — a second sweep must not double-release"
