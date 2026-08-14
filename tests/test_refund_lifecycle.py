"""B6 (audit r4): REAL refund lifecycle.

Regression: admin refund only flipped the DB status — money was never
returned to the customer, and an active chat subscription kept running.
Now: paid → refunding → (Zarinpal refund call) → refunded | refund_failed,
coupon slot released, originating subscription closed, retry allowed.
"""
import sys
import time
import uuid as _uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.main as main_mod
from app.db import engine
from app.models import Coupon, Order, Subscription
from app.payment.orders import activate_subscription
from app.payment.zarinpal import ZarinpalError


class _FakeZP:
    """request + verify OK; refund controlled per test."""

    def __init__(self, refund_ok: bool = True):
        self.uid = _uuid.uuid4().hex[:10]
        self.refund_ok = refund_ok
        self.refund_calls = 0

    def request(self, *a, **k):
        return f"Q{int(time.time())}{self.uid}", f"https://pay.example/Q{int(time.time())}{self.uid}"

    def verify(self, *a, **k):
        return {"ref_id": "REF" + self.uid, "card_pan": "1234"}

    def refund(self, *a, **k):
        self.refund_calls += 1
        if not self.refund_ok:
            raise ZarinpalError("refund failed: gateway timeout (network)")
        return {"ref_id": "RREF" + self.uid}


def _mk_chart(c: TestClient) -> tuple[str, str]:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    }).json()
    return d["chart_id"], d["access_token"]


def _order(s: Session, cid: str, chat: str | None) -> Order:
    o = Order(chart_id=cid, plan_key="monthly", status="paid",
              amount_rial=99000, chat_id=chat, platform="telegram",
              authority="Q" + _uuid.uuid4().hex[:10].upper(), ref_id="REF1")
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


def _admin_cookies() -> dict:
    from app.main import _admin_cookie_value
    return {"chart_admin": _admin_cookie_value()}


def test_refund_success_closes_subscription_and_releases_coupon(monkeypatch):
    fake = _FakeZP(refund_ok=True)
    monkeypatch.setattr("app.main.ZarinpalClient", lambda: fake)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())
    cid, tok = _mk_chart(c)
    chat = f"tg-refund-{_uuid.uuid4().hex[:6]}"
    with Session(engine) as s:
        o = _order(s, cid, chat)
        cp = Coupon(code="REF-" + _uuid.uuid4().hex[:6].upper(), percent=10, max_uses=1, active=True)
        s.add(cp)
        s.commit()
        o.coupon_id = cp.id
        cp.used_count = 1  # simulate the A10 reservation done at order creation
        activate_subscription(s, o)
        s.commit()
        oid, cpid = o.id, cp.id
    # paid order with a reserved coupon slot + active subscription
    with Session(engine) as s:
        assert s.get(Coupon, cpid).used_count == 1
        sub = s.exec(select(Subscription).where(Subscription.order_id == oid)).one()
        assert sub.active

    r = c.post(f"/api/admin/orders/{oid}/refund")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "refunded"
    assert fake.refund_calls == 1

    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "refunded"
        assert o.ref_id.startswith("RREF")
        # coupon slot returned
        assert s.get(Coupon, cpid).used_count == 0
        # originating subscription closed (chat access revoked)
        sub = s.exec(select(Subscription).where(Subscription.order_id == oid)).one()
        assert sub.active is False
        assert ensure_utc(sub.expires_at) <= datetime.now(timezone.utc)


def test_refund_gateway_error_marks_failed_and_allows_retry(monkeypatch):
    fake = _FakeZP(refund_ok=False)
    monkeypatch.setattr("app.main.ZarinpalClient", lambda: fake)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        o = _order(s, cid, f"tg-rf-{_uuid.uuid4().hex[:6]}")
        s.commit()
        oid = o.id

    r = c.post(f"/api/admin/orders/{oid}/refund")
    assert r.status_code == 502
    assert fake.refund_calls == 1
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "refund_failed"
        assert "ریفاند ناموفق" in o.error

    # retry allowed once the gateway is back
    fake.refund_ok = True
    r2 = c.post(f"/api/admin/orders/{oid}/refund")
    assert r2.status_code == 200, r2.text
    assert fake.refund_calls == 2
    with Session(engine) as s:
        assert s.get(Order, oid).status == "refunded"


def test_refund_rejects_pending_and_already_refunded(monkeypatch):
    fake = _FakeZP(refund_ok=True)
    monkeypatch.setattr("app.main.ZarinpalClient", lambda: fake)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        o = _order(s, cid, f"tg-rr-{_uuid.uuid4().hex[:6]}")
        o.status = "pending"
        s.commit()
        oid = o.id
    r = c.post(f"/api/admin/orders/{oid}/refund")
    assert r.status_code == 409  # F-18: CAS claim — non-refundable state → 409 Conflict

    with Session(engine) as s:
        o = s.get(Order, oid)
        o.status = "refunded"
        s.commit()
    r2 = c.post(f"/api/admin/orders/{oid}/refund")
    assert r2.status_code == 409
    assert fake.refund_calls == 0  # never hit the gateway


from app.timeutil import ensure_utc  # noqa: E402
