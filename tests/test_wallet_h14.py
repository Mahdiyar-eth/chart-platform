"""H1.4 (HARDENING): referral self-referral prevention (2 layers) + minimum
withdrawal floor (500k rial)."""
from __future__ import annotations

import os
import uuid

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from sqlmodel import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import BirthProfile, Chart, ReferralEvent, User  # noqa: E402

SUF = uuid.uuid4().hex[:8]


def _mk_user(s: Session) -> User:
    u = User(phone=f"+98h14{SUF}{uuid.uuid4().hex[:4]}")
    s.add(u)
    s.commit()
    return u


def _mk_chart(s: Session, user_id: str | None) -> str:
    pid = None
    if user_id:
        p = BirthProfile(user_id=user_id, name="ت", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        s.add(p)
        s.commit()
        pid = p.id
    c = Chart(chart_json={"planets": {}, "angles": {}}, profile_id=pid)
    s.add(c)
    s.commit()
    return c.id


def _referral_event(s: Session, chart_id: str, referrer_id: str, buyer_id: str) -> ReferralEvent:
    ev = ReferralEvent(code="RFRH14", referrer_user_id=referrer_id,
                       new_user_id=buyer_id, order_id=f"ord-{uuid.uuid4().hex[:8]}",
                       amount_rial=250_000, reward_rial=12_500, status="pending")
    s.add(ev)
    s.commit()
    return ev


def test_self_referral_reward_is_voided():
    """Layer 2: even if a self-referral event exists, the payer==referrer must
    never receive money — the event is voided, balance stays 0."""
    from app.payment.orders import reward_referral
    with Session(engine) as s:
        me = _mk_user(s)
        cid = _mk_chart(s, me.id)
        ev = _referral_event(s, cid, me.id, me.id)  # same user both sides
        o = type("O", (), {"id": ev.order_id, "chart_id": cid})()
        res = reward_referral(s, o)
        s.refresh(me)
        assert res is not None and res.status == "voided"
        assert (me.balance_rial or 0) == 0


def test_normal_referral_still_rewards():
    from app.payment.orders import reward_referral
    with Session(engine) as s:
        ref = _mk_user(s)
        buyer = _mk_user(s)
        cid = _mk_chart(s, buyer.id)
        ev = _referral_event(s, cid, ref.id, buyer.id)
        o = type("O", (), {"id": ev.order_id, "chart_id": cid})()
        reward_referral(s, o)
        s.refresh(ref)
        assert (ref.balance_rial or 0) == 12_500
        assert ev.status == "rewarded"


def test_withdraw_below_minimum_rejected():
    from app.payment.orders import withdraw_request
    with Session(engine) as s:
        u = _mk_user(s)
        u.balance_rial = 600_000
        s.add(u)
        s.commit()
        assert withdraw_request(s, u.id, 100_000) is False   # below floor
        assert withdraw_request(s, u.id, 499_999) is False
        assert withdraw_request(s, u.id, 500_000) is True    # at floor → ok
        assert withdraw_request(s, u.id, 600_000) is False   # already pending


def test_withdraw_dust_balance_cannot_pass_floor():
    from app.payment.orders import withdraw_request
    with Session(engine) as s:
        u = _mk_user(s)
        u.balance_rial = 450_000  # below floor even with full balance
        s.add(u)
        s.commit()
        assert withdraw_request(s, u.id, 450_000) is False
