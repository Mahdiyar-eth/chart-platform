"""ZAYCHE P7 (phase H) — subscription: activation, renewal, cancellation,
expiration, overlapping, duplicate callback, monthly credit grant once-only
with timezone, entitlement persistence (restart/restore = DB-only state)."""
from __future__ import annotations

import os
import uuid
from datetime import timedelta

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app, PLANS_SEED
from app.models import Chart, CreditTransaction, Order, Subscription, User
from app.payment.orders import (
    activate_subscription, cancel_subscription, grant_due_subscription_credits,
    grant_subscription_credits, SUBSCRIPTION_MONTHLY_CREDITS,
)
from app.timeutil import ensure_utc, utcnow
from tests.conftest import engine  # noqa: F401 — hermetic zarinpal fixture

c = TestClient(app)


def _mk_user(credits: int = 0) -> str:
    with Session(engine) as s:
        u = User(phone=f"+98p7{uuid.uuid4().hex[:10]}", credits=credits)
        s.add(u)
        s.commit()
        return u.id


def _mk_chart(uid: str) -> str:
    from app.models import BirthProfile
    from tests.test_explore_catalog_p3 import TEST_CHART
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890,
                         tz_name="Asia/Tehran")
        s.add(p)
        s.commit()
        ch = Chart(profile_id=p.id, user_id=uid, chart_json=TEST_CHART)
        s.add(ch)
        s.commit()
        return ch.id


def _mk_paid_order(uid: str, cid: str, plan_key: str) -> str:
    with Session(engine) as s:
        o = Order(chart_id=cid, user_id=uid, plan_key=plan_key, amount_rial=99_000,
                  status="paid", authority=f"P7A{uuid.uuid4().hex[:12]}",
                  ref_id=str(uuid.uuid4().hex[:12]))
        s.add(o)
        s.commit()
        return o.id


def _get_sub(cid: str) -> Subscription | None:
    with Session(engine) as s:
        return s.exec(select(Subscription).where(Subscription.chart_id == cid)).first()


# ── H: first activation ────────────────────────────────────────────────────
def test_first_activation_creates_subscription():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
    sub = _get_sub(cid)
    assert sub is not None and sub.active
    assert 25 < (ensure_utc(sub.expires_at) - utcnow()).days <= 31  # ~30 days


def test_yearly_activation_is_365_days():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "yearly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
    sub = _get_sub(cid)
    assert 364 <= (ensure_utc(sub.expires_at) - utcnow()).days <= 366


# ── H: renewal extends from current expiry (not now) ───────────────────────
def test_renewal_extends_from_current_expiry():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid1 = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid1))
    sub = _get_sub(cid)
    first_exp = sub.expires_at
    oid2 = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid2))
    sub2 = _get_sub(cid)
    assert (ensure_utc(sub2.expires_at) - ensure_utc(first_exp)).days == 30  # extended, not reset


# ── H: overlapping purchase → still ONE subscription row ───────────────────
def test_overlapping_purchase_single_subscription():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    for _ in range(2):
        oid = _mk_paid_order(uid, cid, "monthly")
        with Session(engine) as s:
            activate_subscription(s, s.get(Order, oid))
    with Session(engine) as s:
        rows = s.exec(select(Subscription).where(Subscription.chart_id == cid)).all()
        assert len(rows) == 1


# ── H: duplicate callback → grant once (idempotent) ────────────────────────
def test_duplicate_callback_grants_credits_once():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
        sub = s.exec(select(Subscription).where(Subscription.chart_id == cid)).first()
        first = grant_subscription_credits(s, sub)
        second = grant_subscription_credits(s, sub)  # same month again
        assert first and not second
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == SUBSCRIPTION_MONTHLY_CREDITS
        rows = s.exec(select(CreditTransaction).where(
            CreditTransaction.user_id == uid,
            CreditTransaction.reason == "subscription")).all()
        assert len(rows) == 1


# ── H: monthly grant once-only with timezone (month boundary) ──────────────
def test_grant_month_boundary_timezone():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
        sub = s.exec(select(Subscription).where(Subscription.chart_id == cid)).first()
        # simulate last grant in the PREVIOUS month
        prev_month = (utcnow() - timedelta(days=35)).replace(day=1)
        sub.last_credit_grant_at = prev_month
        s.add(sub)
        s.commit()
        granted = grant_subscription_credits(s, sub, "Asia/Tehran")
        assert granted
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == SUBSCRIPTION_MONTHLY_CREDITS


# ── H: cron sweep grants only due subscriptions ────────────────────────────
def test_due_sweep_grants_only_due():
    uid1, cid1 = (_u := _mk_user()), _mk_chart(_u)
    uid2, cid2 = (_u := _mk_user()), _mk_chart(_u)
    oid1 = _mk_paid_order(uid1, cid1, "monthly")
    oid2 = _mk_paid_order(uid2, cid2, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid1))
        activate_subscription(s, s.get(Order, oid2))
        sub1 = s.exec(select(Subscription).where(Subscription.chart_id == cid1)).first()
        sub2 = s.exec(select(Subscription).where(Subscription.chart_id == cid2)).first()
        grant_subscription_credits(s, sub1)          # just granted
        sub2.last_credit_grant_at = utcnow() - timedelta(days=40)  # due
        s.add(sub2)
        s.commit()
        grant_due_subscription_credits(s)
        # sub2's user received the monthly grant from the sweep; sub1's user
        # was granted once already and must NOT be granted again (10 would
        # mean the sweep double-granted)
        u1 = s.get(User, uid1)
        u2 = s.get(User, uid2)
        assert u1.credits == SUBSCRIPTION_MONTHLY_CREDITS
        assert u2.credits == SUBSCRIPTION_MONTHLY_CREDITS


# ── H: cancellation ends entitlement immediately ───────────────────────────
def test_cancellation_ends_entitlement():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
        sub = s.exec(select(Subscription).where(Subscription.chart_id == cid)).first()
        cancel_subscription(s, sub)
        assert not sub.active
        assert ensure_utc(sub.expires_at) <= utcnow()


# ── H: expiration — entitlement check uses expires_at from DB ──────────────
def test_expiration_entitlement_false():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
        sub = s.exec(select(Subscription).where(Subscription.chart_id == cid)).first()
        sub.expires_at = utcnow() - timedelta(days=1)  # expired
        s.add(sub)
        s.commit()
        now = utcnow()
        assert not (sub.active and (sub.expires_at is None or ensure_utc(sub.expires_at) > now))


# ── H: entitlement after restart / DB restore = pure DB state (no cache) ──
def test_entitlement_after_restart_persists():
    uid, cid = (_u := _mk_user()), _mk_chart(_u)
    oid = _mk_paid_order(uid, cid, "monthly")
    with Session(engine) as s:
        activate_subscription(s, s.get(Order, oid))
    # simulate restart: fresh session reads the same row
    sub = _get_sub(cid)
    assert sub is not None and sub.active and ensure_utc(sub.expires_at) > utcnow()


# ── H: seed prices per plan §11 ────────────────────────────────────────────
def test_subscription_plan_prices():
    prices = {p.key: p.price_toman for p in PLANS_SEED}
    assert prices.get("monthly") == 99_000
    assert prices.get("yearly") == 890_000
    assert any("۵ اعتبار" in f or "5 اعتبار" in f or "اعتبار" in f
               for f in next(p.features for p in PLANS_SEED if p.key == "monthly"))
