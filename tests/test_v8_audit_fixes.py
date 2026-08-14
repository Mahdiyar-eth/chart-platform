"""F-18..F-20 (audit v8) regression tests.

F-18 (P1): concurrent admin refunds — CAS claim/finalize ⇒ local side-effects
          (_release_coupon, close subscription) run EXACTLY once.
F-19 (P1): synastry order failure — just-created charts/profiles (incl. the
          anonymous guest Person B) are compensated, never orphaned.
F-20 (P2): wallet path with insufficient balance — fail fast BEFORE creating
          the order; no pending order + coupon reservation is left behind.
"""
import sys
import threading
import uuid as _uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

import app.main as main_mod
from app.db import engine
from app.models import BirthProfile, Chart, Coupon, Order, Subscription, User
from app.payment.orders import activate_subscription


def _mk_chart(c: TestClient) -> str:
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    }).json()
    return d["chart_id"]


def _admin_cookies() -> dict:
    from app.main import _admin_cookie_value
    return {"chart_admin": _admin_cookie_value()}


def _mk_paid_order(s: Session, cid: str, chat: str) -> Order:
    o = Order(chart_id=cid, plan_key="monthly", status="paid",
              amount_rial=99000, chat_id=chat, platform="telegram",
              authority="Q" + _uuid.uuid4().hex[:10].upper(), ref_id="REF1")
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


# ── F-18: concurrent admins refund one order — side-effects run once ──
def test_concurrent_refunds_release_coupon_exactly_once(monkeypatch):
    class _Fake:
        def __init__(self):
            self.refund_calls = 0

        def request(self, *a, **k):
            return "Q" + _uuid.uuid4().hex[:10].upper(), "https://pay.example/x"

        def verify(self, *a, **k):
            return {"ref_id": "REF" + _uuid.uuid4().hex[:6]}

        def refund(self, *a, **k):
            self.refund_calls += 1
            return {"ref_id": "RREF" + _uuid.uuid4().hex[:6]}

    fake = _Fake()
    monkeypatch.setattr("app.main.ZarinpalClient", lambda: fake)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())
    cid = _mk_chart(c)
    chat = f"tg-f18-{_uuid.uuid4().hex[:6]}"
    with Session(engine) as s:
        o = _mk_paid_order(s, cid, chat)
        cp = Coupon(code="F18-" + _uuid.uuid4().hex[:6].upper(), percent=10,
                    max_uses=1, active=True)
        s.add(cp)
        s.commit()
        o.coupon_id = cp.id
        cp.used_count = 1  # A10 reservation
        activate_subscription(s, o)
        s.commit()
        oid, cpid = o.id, cp.id

    results: list[int] = []
    barrier = threading.Barrier(3)

    def _refund():
        cc = TestClient(main_mod.app)
        cc.cookies.update(_admin_cookies())
        barrier.wait()
        r = cc.post(f"/api/admin/orders/{oid}/refund")
        results.append(r.status_code)

    threads = [threading.Thread(target=_refund) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "refunded", o.status
        # coupon slot released EXACTLY once (never negative, never doubled)
        assert s.get(Coupon, cpid).used_count == 0
        sub = s.exec(select(Subscription).where(Subscription.order_id == oid)).one()
        assert sub.active is False
    # a caller that arrives AFTER the refund finished correctly gets 409 —
    # the invariant is: final state refunded + side-effects exactly once
    assert all(st in (200, 409) for st in results), results
    assert 1 <= fake.refund_calls <= 3  # gateway may be called repeatedly


# ── F-19: synastry order failure compensates the just-created charts ──
def test_synastry_order_failure_leaves_no_orphan_data(monkeypatch):
    class _Boom:
        def request(self, *a, **k):
            raise RuntimeError("gateway unavailable")

    monkeypatch.setattr("app.main.ZarinpalClient", lambda: _Boom())
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: _Boom())
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())
    with Session(engine) as s:
        charts_before = s.exec(select(func.count()).select_from(Chart)).one()
        profiles_before = s.exec(select(func.count()).select_from(BirthProfile)).one()

    r = c.post("/api/synastry/order", data={
        "name_a": "الف", "year_a": "1373", "month_a": "6", "day_a": "1",
        "hour_a": "6", "minute_a": "10", "city_a": "تهران", "calendar_a": "jalali",
        "name_b": "ب", "year_b": "1375", "month_b": "1", "day_b": "15",
        "hour_b": "12", "minute_b": "0", "city_b": "اصفهان", "calendar_b": "jalali",
    })
    assert r.status_code in (400, 502)

    with Session(engine) as s:
        charts_after = s.exec(select(func.count()).select_from(Chart)).one()
        profiles_after = s.exec(select(func.count()).select_from(BirthProfile)).one()
    # NO orphaned charts/profiles (especially the anonymous guest Person B)
    assert charts_after == charts_before, (charts_before, charts_after)
    assert profiles_after == profiles_before, (profiles_before, profiles_after)


# ── F-19 residual (audit v9 P1): cleanup itself MUST be fail-closed — if the
# compensation fails, surface 5xx (NOT the original 400) + audit trail, so an
# orphaned guest Person B can never be silently swallowed.
def test_synastry_cleanup_failure_is_fail_closed(monkeypatch):
    class _Boom:
        def request(self, *a, **k):
            raise RuntimeError("gateway unavailable")

    monkeypatch.setattr("app.main.ZarinpalClient", lambda: _Boom())
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: _Boom())
    # make the compensation DELETE itself fail
    monkeypatch.setattr("sqlmodel.Session.delete", lambda self, obj: (_ for _ in ()).throw(RuntimeError("db down")))
    c = TestClient(main_mod.app)
    c.cookies.update(_admin_cookies())

    r = c.post("/api/synastry/order", data={
        "name_a": "الف", "year_a": "1373", "month_a": "6", "day_a": "1",
        "hour_a": "6", "minute_a": "10", "city_a": "تهران", "calendar_a": "jalali",
        "name_b": "ب", "year_b": "1375", "month_b": "1", "day_b": "15",
        "hour_b": "12", "minute_b": "0", "city_b": "اصفهان", "calendar_b": "jalali",
    })
    # fail-closed: 5xx, NOT the payment 400 — the incomplete state is visible
    assert r.status_code == 502, r.status_code
    assert "پشتیبانی" in r.json().get("detail", "")


# ── F-20: wallet with insufficient balance creates NO order, reserves NO coupon
def test_wallet_insufficient_balance_creates_no_order():
    c = TestClient(main_mod.app)

    # a user with a wallet that can NOT cover the basic plan (1.49M rial)
    phone = "98912" + str(9_000_000 + _uuid.uuid4().int % 1_000_000)
    with Session(engine) as s:
        u = User(phone=phone, balance_rial=100_000)
        s.add(u)
        s.commit()
        s.refresh(u)
        uid = u.id

    # user session cookie FIRST, so the chart below is OWNED by this user
    from app.auth import _user_cookie_value
    c.cookies.update({"chart_user": _user_cookie_value(uid)})
    cid = _mk_chart(c)

    with Session(engine) as s:
        before = s.exec(select(func.count()).select_from(Order)).one()
        cp = Coupon(code="F20-" + _uuid.uuid4().hex[:6].upper(), percent=10,
                    max_uses=1, active=True)
        s.add(cp)
        s.commit()
        cpid, real_code = cp.id, cp.code

    r = c.post("/api/orders", data={
        "plan_key": "basic", "chart_id": cid, "coupon": real_code,
    }, headers={"x-pay-with-balance": "1"})
    assert r.status_code == 400, r.text
    assert "موجودی" in r.json().get("detail", "")

    with Session(engine) as s:
        after = s.exec(select(func.count()).select_from(Order)).one()
        assert after == before  # NO order was created at all
        assert s.get(Coupon, cpid).used_count == 0  # nothing was reserved


# ── F-20 residual (audit v9 P2): wallet pre-check must accept the DISCOUNTED
# final amount — a user who can cover 1,192,000 (1.49M − 20% coupon) but not
# the full 1,490,000 must NOT be rejected.
def test_wallet_pays_discounted_amount_with_coupon(monkeypatch):
    class _FakeZP:
        def request(self, *a, **k):
            return "Q" + _uuid.uuid4().hex[:10].upper(), "https://pay.example/x"

        def verify(self, *a, **k):
            return {"ref_id": "REF" + _uuid.uuid4().hex[:6]}

    fake = _FakeZP()
    monkeypatch.setattr("app.main.ZarinpalClient", lambda: fake)
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    c = TestClient(main_mod.app)

    phone = "98913" + str(9_000_000 + _uuid.uuid4().int % 1_000_000)
    with Session(engine) as s:
        # 1.25M — covers the discounted 1.192M basic plan, NOT the full 1.49M
        u = User(phone=phone, balance_rial=1_250_000)
        s.add(u)
        s.commit()
        s.refresh(u)
        uid = u.id
        cp = Coupon(code="F20D-" + _uuid.uuid4().hex[:6].upper(), percent=20,
                    max_uses=5, active=True)
        s.add(cp)
        s.commit()
        cpid, real_code = cp.id, cp.code

    from app.auth import _user_cookie_value
    c.cookies.update({"chart_user": _user_cookie_value(uid)})
    cid = _mk_chart(c)

    r = c.post("/api/orders", data={
        "plan_key": "basic", "chart_id": cid, "coupon": real_code,
    }, headers={"x-pay-with-balance": "1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("paid_by_balance") is True
    with Session(engine) as s:
        o = s.exec(select(Order).order_by(Order.created_at.desc())).first()
        assert o.status == "paid"
        assert o.amount_rial == 1_192_000  # 1.49M − 20%
        assert s.get(User, uid).balance_rial == 58_000  # 1.25M − 1.192M
        assert s.get(Coupon, cpid).used_count == 1
