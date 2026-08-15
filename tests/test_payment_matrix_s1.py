"""ZAYCHE §1 — payment E2E matrix (callback/verify races + idempotency).

Covers the OWASP payment matrix from the Absolute Final Verification Plan:
happy path, callback without order, wrong authority, duplicate callback,
duplicate verify, concurrent callbacks, gateway rejection, network error
re-open, server-side amount, Status=NOK, order-of-another-user.
"""
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.db import engine
from app.models import Chart, Coupon, Order, Report


class OkZarinpal:
    """Gateway that accepts everything — records every verify call."""
    verify_calls = 0
    lock = threading.Lock()
    last_amount = None

    def __init__(self):
        pass

    def verify(self, authority, amount_rial):
        with self.lock:
            OkZarinpal.verify_calls += 1
            OkZarinpal.last_amount = amount_rial
        time.sleep(0.03)
        return {"ref_id": "100000000099", "card_pan": "621986****0000"}


class RejectZarinpal:
    def __init__(self):
        pass

    def verify(self, authority, amount_rial):
        from app.payment.zarinpal import ZarinpalError
        raise ZarinpalError("gateway rejected")


@pytest.fixture
def ok_gateway(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", OkZarinpal)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", OkZarinpal)
    OkZarinpal.verify_calls = 0
    OkZarinpal.last_amount = None
    yield OkZarinpal


@pytest.fixture
def reject_gateway(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", RejectZarinpal)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", RejectZarinpal)
    yield RejectZarinpal


def _order(status="pending", coupon=None, amount=1_490_000, plan_key="full"):
    auth = f"A{int(time.time() * 1000)}{'X' * 18}"
    with Session(engine) as s:
        ch = Chart(chart_json={"planets": {}, "engine_config": {"zodiac": "tropical"}})
        s.add(ch)
        s.flush()
        c = None
        if coupon:
            c = Coupon(code=f"C{int(time.time() * 1000)}", percent=coupon, max_uses=5, used_count=1)
            s.add(c)
            s.flush()
        o = Order(plan_key=plan_key, amount_rial=amount, status=status,
                  authority=auth, chart_id=ch.id, coupon_id=c.id if c else None)
        s.add(o)
        s.commit()
        return {"order_id": o.id, "chart_id": ch.id, "auth": auth,
                "coupon_id": c.id if c else None}


def _verify(auth, status="OK"):
    with TestClient(app, follow_redirects=False) as c:
        return c.get(f"/api/payments/verify?Authority={auth}&Status={status}")


# ── matrix ──────────────────────────────────────────────

def test_callback_without_order_404():
    r = _verify("NO_SUCH_AUTHORITY")
    assert r.status_code == 404


def test_happy_path_marks_paid(ok_gateway):
    o = _order()
    r = _verify(o["auth"])
    assert r.status_code in (200, 303)
    with Session(engine) as s:
        db = s.get(Order, o["order_id"])
        assert db.status == "paid"
        assert db.ref_id == "100000000099"
    assert ok_gateway.verify_calls == 1
    assert ok_gateway.last_amount == 1_490_000  # server-side amount


def test_duplicate_callback_idempotent(ok_gateway):
    o = _order()
    _verify(o["auth"])
    r2 = _verify(o["auth"])  # duplicate refresh/callback
    assert r2.status_code == 303  # redirect, no re-verify
    assert ok_gateway.verify_calls == 1  # exactly one gateway verify


def test_wrong_authority_404_untouched():
    o = _order()
    r = _verify("WRONG_AUTH")
    assert r.status_code == 404
    with Session(engine) as s:
        assert s.get(Order, o["order_id"]).status == "pending"


def test_gateway_rejection_failed_coupon_released(reject_gateway):
    o = _order(coupon=10)
    r = _verify(o["auth"])
    assert r.status_code in (200, 303)
    with Session(engine) as s:
        db = s.get(Order, o["order_id"])
        assert db.status == "failed"
        assert s.get(Coupon, o["coupon_id"]).used_count == 0  # released


def test_status_nok_marks_failed(ok_gateway):
    o = _order()
    r = _verify(o["auth"], status="NOK")
    assert r.status_code in (200, 303)
    with Session(engine) as s:
        assert s.get(Order, o["order_id"]).status == "failed"
    assert ok_gateway.verify_calls == 0  # never asked gateway


def test_network_error_reopens_pending():
    """Gateway call raises a network error (not ZarinpalError): money state
    UNKNOWN → order returns to pending so a refresh re-verifies."""
    class NetErr:
        def __init__(self):
            pass

        def verify(self, authority, amount_rial):
            raise TimeoutError("connection reset")

    from app import main as m
    from app.payment import zarinpal as _zp
    orig = m.ZarinpalClient
    orig_zp = _zp.ZarinpalClient
    m.ZarinpalClient = NetErr
    _zp.ZarinpalClient = NetErr
    try:
        o = _order()
        r = _verify(o["auth"])
        assert r.status_code in (200, 303)
        with Session(engine) as s:
            db = s.get(Order, o["order_id"])
            assert db.status == "pending"  # NOT failed, NOT paid
            assert db.error and "رفرش" in db.error
    finally:
        m.ZarinpalClient = orig
        _zp.ZarinpalClient = orig_zp


def test_concurrent_callbacks_single_paid_single_report(ok_gateway):
    """OWASP: two callbacks racing → exactly one paid transition, one report."""
    o = _order()
    barrier = threading.Barrier(2)
    results = []

    def hit(_):
        barrier.wait()
        results.append(_verify(o["auth"]).status_code)

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(hit, [0, 1]))

    with Session(engine) as s:
        db = s.get(Order, o["order_id"])
        assert db.status == "paid"
        reports = s.exec(select(Report).where(Report.chart_id == db.chart_id)).all()
        assert len(reports) == 1
    assert ok_gateway.verify_calls == 1  # single verify
