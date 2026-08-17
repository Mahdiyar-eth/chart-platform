"""Tests for opus-audit fixes (2026-08-17): F-29 wallet settle dispatch,
F-11 coupon seed, F-26 house validation uses engine Placidus houses."""
import pytest
from sqlmodel import Session, select

from app.db import engine
from app.models import Coupon, Order, Plan, User
from app.payment import orders as orders_mod


@pytest.fixture()
def wallet_user():
    with Session(engine) as s:
        old = s.exec(select(User).where(User.phone == "09120000007")).first()
        if old:
            s.delete(old)
            s.commit()
    u = User(phone="09120000007")
    u.balance_rial = 10_000_000
    with Session(engine) as s:
        s.add(u)
        s.commit()
        s.refresh(u)
    return u


def _plan(key: str) -> Plan:
    with Session(engine) as s:
        return s.exec(select(Plan).where(Plan.key == key)).first()


def _order(u: User, plan_key: str, amount: int) -> tuple[Order, Session]:
    s = Session(engine)
    try:
        o = Order(user_id=u.id, plan_key=plan_key, amount_rial=amount, status="pending")
        s.add(o)
        s.commit()
        s.refresh(o)
        return o, s
    except Exception:
        s.close()
        raise


def test_wallet_dispatch_subscription(wallet_user, monkeypatch):
    """F-29: yearly (and monthly) must activate the subscription + grant the
    first-month credits (was: only 'monthly' did anything — yearly paid and
    nothing happened)."""
    u = wallet_user
    calls = []
    monkeypatch.setattr(orders_mod, "activate_subscription",
                        lambda s, o: calls.append("activate"))
    monkeypatch.setattr(orders_mod, "grant_subscription_credits",
                        lambda s, sub: calls.append("credits"))
    monkeypatch.setattr(orders_mod, "grant_credits",
                        lambda s, o: calls.append("grant"))
    # a chart + existing subscription row (what a real purchase would have)
    from app.models import Chart, Subscription
    c = Chart(chart_json={})
    with Session(engine) as s:
        s.add(c)
        s.flush()
        s.add(Subscription(chart_id=c.id, active=True))
        s.commit()
        cid = c.id
    plan = _plan("yearly")
    o, s = _order(u, "yearly", plan.price_rial)
    o.chart_id = cid
    s.add(o)
    s.commit()
    try:
        assert orders_mod.pay_order_with_balance(s, o, u) is True
        assert o.status == "paid"
        assert calls == ["activate", "credits"]  # credit grant lookup hit the row
        assert "grant" not in calls
    finally:
        s.close()


def test_wallet_dispatch_credit_pack(wallet_user, monkeypatch):
    """F-29: credit packs must grant credits (was: paid and nothing happened)."""
    u = wallet_user
    calls = []
    monkeypatch.setattr(orders_mod, "activate_subscription",
                        lambda s, o: calls.append("activate"))
    monkeypatch.setattr(orders_mod, "grant_subscription_credits",
                        lambda s, sub: calls.append("credits"))
    monkeypatch.setattr(orders_mod, "grant_credits",
                        lambda s, o: calls.append("grant"))
    plan = _plan("credit6")
    o, s = _order(u, "credit6", plan.price_rial)
    try:
        assert orders_mod.pay_order_with_balance(s, o, u) is True
        assert calls == ["grant"]
    finally:
        s.close()


def test_wallet_report_plan_creates_report(wallet_user, monkeypatch):
    """F-29: gold via wallet must queue a report like the Zarinpal path."""
    u = wallet_user
    monkeypatch.setattr(orders_mod, "activate_subscription",
                        lambda s, o: None)
    monkeypatch.setattr(orders_mod, "grant_credits", lambda s, o: None)
    plan = _plan("gold")
    from app.models import Chart
    c = Chart(chart_json={})
    with Session(engine) as s0:
        s0.add(c)
        s0.commit()
        cid = c.id
    o, s = _order(u, "gold", plan.price_rial)
    o.chart_id = cid
    s.add(o)
    s.commit()
    try:
        assert orders_mod.pay_order_with_balance(s, o, u) is True
        assert o.report_id is not None  # queued report created
    finally:
        s.close()


def test_wallet_insufficient_balance_no_partial(wallet_user):
    u = wallet_user
    s = Session(engine)
    try:
        u2 = s.get(User, u.id)
        u2.balance_rial = 100
        s.commit()
        plan = _plan("credit6")
        o = Order(user_id=u2.id, plan_key="credit6", amount_rial=plan.price_rial,
                  status="pending")
        s.add(o)
        s.commit()
        s.refresh(o)
        assert orders_mod.pay_order_with_balance(s, o, u2) is False
        assert o.status == "pending"
        s.expire_all()
        fresh = s.get(User, u2.id)
        assert fresh.balance_rial == 100  # no partial debit
    finally:
        s.close()


def test_seed_plans_creates_launch_coupon():
    """F-11: the LANCH20 coupon must actually be seeded (old code silently
    swallowed the closed-session error and never created it)."""
    from app.db import seed_plans
    seed_plans()
    with Session(engine) as s:
        c = s.exec(select(Coupon).where(Coupon.code == "LANCH20")).first()
    assert c is not None and c.percent == 20


def test_house_of_uses_engine_houses():
    """F-26: house claims must be validated against the engine's stored
    Placidus house, not a whole-sign derivation."""
    from app.report.claim_validation import house_of
    chart = {
        "planets": {"sun": {"house": 5}, "moon": {"house": 11}},
        "houses": {"h1": 0.0, "h2": 30.0},
    }
    assert house_of("sun", chart) == 5
    assert house_of("moon", chart) == 11
    # legacy chart without per-planet house → cusp fallback, not whole-sign
    chart2 = {"planets": {"sun": {"longitude": 15.0, "house": None}},
              "angles": {"asc": {"longitude": 0.0}},
              "houses": {"h1": 0.0, "h2": 30.0}}
    assert house_of("sun", chart2) == 1  # 15° < 30° → house 1 (Placidus cusp rule)