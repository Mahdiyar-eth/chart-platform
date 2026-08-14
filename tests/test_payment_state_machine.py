"""B7 (audit r4): payment verify state machine.

Regression: a network failure during Zarinpal verify() marked the order
FAILED even though the money may have moved (user charged, order failed).
Now: pending → verifying → paid | failed; only a definitive gateway rejection
fails the order, network errors put it BACK to pending so a refresh re-verifies
(Zarinpal code 101 = already verified → paid).
"""
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app as main_app
from app.db import engine
from app.models import Coupon, Order, Report
from app.payment.zarinpal import ZarinpalError


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    }).json()
    return d["chart_id"], d["access_token"]


def _paid_order(s, cid, status="pending", with_coupon=False):
    o = Order(chart_id=cid, plan_key="gold", status=status, amount_rial=99000,
              authority="AU" + uuid.uuid4().hex[:8], ref_id="REF1")
    if with_coupon:
        cp = Coupon(code="B7-" + uuid.uuid4().hex[:6].upper(), percent=10,
                    max_uses=1, active=True)
        s.add(cp)
        s.commit()
        o.coupon_id = cp.id
        cp.used_count = 1  # simulate the A10 reservation
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


class NetworkErrZP:
    """verify() dies like a dropped connection AFTER the user paid."""

    def verify(self, *a, **k):
        raise httpx.ConnectTimeout("connection dropped")

    def refund(self, *a, **k):
        return {"ref_id": "R1"}


class RejectZP:
    """Gateway definitively says the payment never happened."""

    def verify(self, *a, **k):
        raise ZarinpalError("verify code -55: تراکنش ناموفق")


class OkZP:
    def verify(self, *a, **k):
        return {"ref_id": "200000000099", "card_pan": "621986****0000"}

    def refund(self, *a, **k):
        return {"ref_id": "R1"}


def _patch(mp, cls):
    mp.setattr("app.main.ZarinpalClient", cls)
    mp.setattr("app.payment.zarinpal.ZarinpalClient", cls)


def test_network_error_keeps_order_pending_not_failed(monkeypatch):
    """Money may have moved → order must NOT be failed; user can refresh."""
    _patch(monkeypatch, NetworkErrZP)
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    ck = {"chart_access": __import__("json").dumps({cid: tok})}
    c.cookies.update(ck)
    with Session(engine) as s:
        o = _paid_order(s, cid)
        oid, auth = o.id, o.authority
    r = c.get(f"/api/payments/verify?Authority={auth}&Status=OK", follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "pending", "network error must NOT fail a possibly-paid order"
        assert "رفرش" in (o.error or "")


def test_refresh_after_network_error_completes_payment(monkeypatch):
    """Refresh re-verifies; the SECOND verify (Zarinpal code 101) → paid,
    exactly once — no duplicate reports, single subscription extension."""
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: True)  # no real queue
    _patch(monkeypatch, NetworkErrZP)
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    ck = {"chart_access": __import__("json").dumps({cid: tok})}
    c.cookies.update(ck)
    with Session(engine) as s:
        o = _paid_order(s, cid)
        oid, auth = o.id, o.authority
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK", follow_redirects=False)  # network error
    monkeypatch.setattr("app.main.ZarinpalClient", OkZP)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", OkZP)
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK", follow_redirects=False)  # refresh → paid
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "paid"
        assert o.ref_id == "200000000099"
        reports = s.exec(select(Report).where(Report.chart_id == cid)).all()
        assert len(reports) == 1, "exactly one report for one paid order"


def test_gateway_rejection_marks_failed_and_releases_coupon(monkeypatch):
    """Definitive gateway rejection (authority invalid) → failed + coupon back."""
    _patch(monkeypatch, RejectZP)
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    ck = {"chart_access": __import__("json").dumps({cid: tok})}
    c.cookies.update(ck)
    with Session(engine) as s:
        o = _paid_order(s, cid, with_coupon=True)
        oid, auth, cpid = o.id, o.authority, o.coupon_id
    c.get(f"/api/payments/verify?Authority={auth}&Status=OK", follow_redirects=False)
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "failed"
        cp = s.get(Coupon, cpid)
        assert cp.used_count == 0, "failed payment must return the coupon slot"
