"""D3 (audit r4): referral wallet — referrer gets 5% credited after a PAID
order, wallet pays a full order without Zarinpal, withdrawal requests go to
admin and resolve there. Zarinpal is mocked (no real gateway calls)."""
from __future__ import annotations

import uuid

import pytest

from sqlmodel import Session, select

from app.db import engine
from app.models import (BirthProfile, Chart, Order, Plan, ReferralEvent, Subscription, User, WithdrawalRequest)

CHART_JSON = {"planets": {"Sun": {"sign_fa": "اسد", "house": 10}},
              "angles": {"ASC": {"sign_fa": "اسد"}}, "birth": {}}


@pytest.fixture
def db_session():
    with Session(engine) as s:
        yield s


def _mk_user(session: Session) -> User:
    u = User(phone=f"+98{uuid.uuid4().hex[:10]}")
    session.add(u)
    session.commit()
    return u


def _mk_chart(session: Session, user_id: str | None = None) -> str:
    profile_id = None
    if user_id:
        p = BirthProfile(user_id=user_id, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        session.add(p)
        session.commit()
        profile_id = p.id
    ch = Chart(chart_json=CHART_JSON, profile_id=profile_id)
    session.add(ch)
    session.commit()
    return ch.id


def _mk_plan(session: Session) -> None:
    if not session.get(Plan, "basic"):
        session.add(Plan(key="basic", name_fa="پایه", subtitle_fa="",
                         price_toman=25_000, active=True))
        session.commit()


def _mk_order(session: Session, chart_id: str, amount: int = 250_000,
              ref_code: str = "") -> Order:
    o = Order(chart_id=chart_id, plan_key="basic", amount_rial=amount,
              status="pending", authority=f"auth-{uuid.uuid4().hex[:12]}")
    if ref_code:
        session.add(ReferralEvent(code=ref_code, order_id=o.id,
                                  new_user_id=o.profile_id, amount_rial=amount,
                                  reward_rial=int(amount * 0.05)))
    session.add(o)
    session.commit()
    return o


def test_wallet_balance_and_code(db_session):
    u = _mk_user(db_session)
    from app.payment.orders import get_or_create_referral_code
    code = get_or_create_referral_code(db_session, u.id)
    assert len(code) == 8  # token_urlsafe(6)
    db_session.refresh(u)
    assert u.balance_rial == 0


def test_referral_rewarded_after_paid(db_session):
    """Referrer wallet is credited (idempotently) once the order is paid."""
    ref = _mk_user(db_session)
    buyer = _mk_user(db_session)
    cid = _mk_chart(db_session)
    from app.payment.orders import get_or_create_referral_code, reward_referral
    code = get_or_create_referral_code(db_session, ref.id)
    o = _mk_order(db_session, cid, ref_code=code)
    # wire the event to this order (created in _mk_order with order_id=o.id)
    ev = db_session.exec(select(ReferralEvent).where(
        ReferralEvent.order_id == o.id)).first()
    ev.referrer_user_id = ref.id
    ev.new_user_id = buyer.id
    db_session.commit()

    reward_referral(db_session, o)
    reward_referral(db_session, o)  # idempotent

    db_session.refresh(ref)
    assert ref.balance_rial == int(250_000 * 0.05)  # 12_500
    ev = db_session.exec(select(ReferralEvent).where(
        ReferralEvent.order_id == o.id)).first()
    assert ev.status == "rewarded"


def test_pay_order_with_balance(db_session):
    """A wallet payment settles the order (no Zarinpal) and activates the
    subscription, and can NOT overdraw the wallet."""
    user = _mk_user(db_session)
    user.balance_rial = 300_000
    cid = _mk_chart(db_session, user_id=user.id)
    _mk_plan(db_session)
    o = _mk_order(db_session, cid, amount=250_000)
    o.plan_key = "monthly"
    db_session.commit()

    from app.payment.orders import pay_order_with_balance
    assert pay_order_with_balance(db_session, o, user) is True
    db_session.refresh(user)
    assert user.balance_rial == 50_000
    db_session.refresh(o)
    assert o.status == "paid"
    sub = db_session.exec(select(Subscription).where(
        Subscription.chart_id == cid)).first()
    assert sub and sub.active

    # not enough balance -> refused
    o2 = _mk_order(db_session, cid, amount=99_000)
    o2.plan_key = "monthly"
    db_session.commit()
    assert pay_order_with_balance(db_session, o2, user) is False
    db_session.refresh(o2)
    assert o2.status == "pending"
    db_session.refresh(user)
    assert user.balance_rial == 50_000


def test_withdrawal_lifecycle(db_session):
    """User requests cash-out; admin resolves paid/rejected; one pending at a
    time; amount cannot exceed balance."""
    u = _mk_user(db_session)
    u.balance_rial = 40_000
    db_session.commit()

    from app.payment.orders import withdraw_request
    assert withdraw_request(db_session, u.id, 10_000) is True
    assert withdraw_request(db_session, u.id, 10_000) is False  # one pending

    wr = db_session.exec(select(WithdrawalRequest).where(
        WithdrawalRequest.user_id == u.id)).first()
    assert wr.amount_rial == 10_000 and wr.status == "pending"

    assert withdraw_request(db_session, u.id, 999_999) is False  # overdraw
    assert withdraw_request(db_session, u.id, -5) is False

    from app.payment.orders import resolve_withdrawal
    assert resolve_withdrawal(db_session, wr.id, "paid", "شماره پیگیری 123") is True
    db_session.refresh(wr)
    assert wr.status == "paid" and wr.resolved_at is not None
    db_session.refresh(u)
    assert u.balance_rial == 40_000  # balance NOT auto-debited (manual payout)
