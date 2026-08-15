"""ZAYCHE P6 — credit economy: pack purchase → grant, idempotent callback,
ledger invariant (sum(amount) == credits), no chart required for packs."""
from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import CreditTransaction, Order, Plan, User
from app.db import engine

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")


def _mk_user(c, credits: int = 0) -> str:
    from app.auth import _user_cookie_value
    phone = f"+98p6{uuid.uuid4().hex[:8]}"
    with Session(engine) as s:
        u = User(phone=phone, credits=credits)
        s.add(u)
        s.commit()
        c.cookies.set("chart_user", _user_cookie_value(u.id))
        return u.id


def _ledger_sum(uid: str) -> int:
    with Session(engine) as s:
        rows = s.exec(select(CreditTransaction).where(CreditTransaction.user_id == uid)).all()
        return sum(r.amount for r in rows)


def _credit_balance(uid: str) -> int:
    with Session(engine) as s:
        return s.get(User, uid).credits


def _mk_order(uid: str, plan_key: str, chart_id: str = "") -> str:
    with Session(engine) as s:
        o = Order(chart_id=chart_id or None, user_id=uid, plan_key=plan_key,
                  amount_rial=180_000, status="pending",
                  authority=f"P6A{uuid.uuid4().hex[:12]}")
        s.add(o)
        s.commit()
        return o.id


def test_credit_pack_purchase_does_not_need_chart():
    """P6 — credit packs are orderable without any chart."""
    c = TestClient(app)
    _mk_user(c)
    r = c.post("/api/orders", data={"plan_key": "credit3", "chart_id": ""})
    assert r.status_code == 200, r.text
    assert "payment_url" in r.json()


def test_report_plan_still_requires_chart():
    """Non-pack plans keep the chart requirement (400, not 404)."""
    c = TestClient(app)
    _mk_user(c)
    r = c.post("/api/orders", data={"plan_key": "full", "chart_id": ""})
    assert r.status_code == 400


def test_grant_credits_from_plan_value():
    """P6 — paid pack grants credits_grant atomically + ledger row."""
    from app.payment.orders import grant_credits
    c = TestClient(app)
    uid = _mk_user(c)
    oid = _mk_order(uid, "credit6")
    with Session(engine) as s:
        order = s.get(Order, oid)
        grant_credits(s, order)
        s.commit()
    assert _credit_balance(uid) == 6
    assert _ledger_sum(uid) == 6
    with Session(engine) as s:
        tx = s.exec(select(CreditTransaction).where(
            CreditTransaction.reason == "purchase",
            CreditTransaction.user_id == uid)).first()
        assert tx.amount == 6 and tx.ref_id == oid


def test_grant_credits_unknown_pack_raises():
    """credits_grant is data-driven — a pack without a value must fail loudly."""
    from app.payment.orders import grant_credits
    c = TestClient(app)
    uid = _mk_user(c)
    oid = _mk_order(uid, "credit3")
    with Session(engine) as s:
        p = s.get(Plan, "credit3")
        p.credits_grant = 0
        s.commit()
    try:
        with Session(engine) as s:
            grant_credits(s, s.get(Order, oid))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    finally:
        with Session(engine) as s:
            p = s.get(Plan, "credit3")
            p.credits_grant = 3
            s.commit()


def test_ledger_invariant_after_spend_and_purchase():
    """Accounting invariant: sum(ledger) == credits at every step."""
    from app.payment.orders import grant_credits
    c = TestClient(app)
    uid = _mk_user(c, credits=0)
    oid = _mk_order(uid, "credit12")
    with Session(engine) as s:
        grant_credits(s, s.get(Order, oid))
        s.commit()
    assert _credit_balance(uid) == 12 and _ledger_sum(uid) == 12
    # one exploration spend via the real route needs a chart + fake router
    from app.astrology.engine import compute_from_fields
    from app.models import BirthProfile, Chart
    chart_json = compute_from_fields(35.6892, 51.3890, 1373, 6, 1, 6, 10, True,
                                     True, "Asia/Tehran").chart_json
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p)
        s.commit()
        ch = Chart(profile_id=p.id, chart_json=chart_json)
        s.add(ch)
        s.commit()
        cid = ch.id
    import app.core.llm as llm
    from tests.test_explore_catalog_p3 import GOOD_JSON, FakeRouter
    llm.build_chat_router = lambda: FakeRouter([GOOD_JSON])
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200 and "event: done" in r.text
    assert _credit_balance(uid) == 11
    assert _ledger_sum(uid) == 11
