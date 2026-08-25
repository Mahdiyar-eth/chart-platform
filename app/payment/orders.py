"""Shared order creation + subscription activation (plan v3.0 §7/§8/§12).

Used by BOTH the web API and the Telegram/Bale bots so pricing, coupon,
referral and payment flows stay in one place.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select
from sqlalchemy import text

from app.models import (BirthProfile, Chart, Coupon, Order, Plan, ReferralCode, ReferralEvent,
                        Report, Subscription, User, WithdrawalRequest)
from app.timeutil import ensure_utc, utcnow


REFERRAL_REWARD_PERCENT = 10  # plan v2.0 §13 — 10% of the discounted amount


def _referral_reward_rial(amount_rial: int) -> int:
    return int(amount_rial * REFERRAL_REWARD_PERCENT / 100)


def get_or_create_referral_code(session: Session, user_id: str) -> str:
    rc = session.exec(select(ReferralCode).where(ReferralCode.user_id == user_id)).first()
    if rc:
        return rc.code
    for _ in range(10):
        code = secrets.token_urlsafe(6)
        if not session.exec(select(ReferralCode).where(ReferralCode.code == code)).first():
            session.add(ReferralCode(user_id=user_id, code=code))
            session.commit()
            return code
    raise RuntimeError("could not allocate referral code")


def create_order(
    session: Session,
    plan_key: str,
    chart_id: str,
    secondary_chart_id: str | None = None,
    chat_id: str | None = None,
    platform: str | None = None,
    coupon: str | None = None,
    ref_code: str = "",
    new_user_id: str | None = None,
) -> tuple[Order, str]:
    """Create a pending order + request Zarinpal authority. Returns (order, pay_url)."""
    from app.payment.zarinpal import ZarinpalClient, ZarinpalError

    plan = session.get(Plan, plan_key)
    # R13/N3: retired toman plans (active=False) are no longer orderable —
    # the credit economy (/api/purchase + credit packs) is the only path.
    # DEEP_REPORT_ACTIONS (report_basic/full/gold) are NOT plans — they are
    # credit actions and never reach create_order; the coupon pre-check above
    # already validated them against the ledger.
    if not plan or not plan.active:
        raise LookupError("plan not found")

    amount = plan.price_rial
    coupon_row = None
    if coupon:
        coupon_row = session.exec(
            select(Coupon).where(Coupon.code == coupon.strip().upper())
        ).first()
        if not coupon_row or not coupon_row.active:
            raise ValueError("کد تخفیف نامعتبر است")
        if coupon_row.expires_at and ensure_utc(coupon_row.expires_at) < utcnow():
            raise ValueError("کد تخفیف منقضی شده")
        # §13 — LANCH20: only on the user's FIRST deep report. Enforced before
        # the atomic slot reservation so the slot is never burned for nothing.
        if coupon_row.report_only:
            # R13/N3: "first deep report" now means the first credit purchase
            # of a deep-report action (report_basic/full/gold), since toman
            # report plans are retired.
            from app.models import CreditTransaction as _CT
            if plan_key not in CREDIT_PACKS and plan_key not in DEEP_REPORT_ACTIONS:
                raise ValueError("این کد تخفیف فقط برای گزارش عمیق است")
            prior = session.exec(select(_CT).where(
                _CT.user_id == new_user_id,
                _CT.amount < 0,
                _CT.reason.in_(DEEP_REPORT_ACTIONS),
            )).first() if new_user_id else None
            if prior:
                raise ValueError("این کد تخفیف فقط برای اولین گزارش عمیق است")
        # audit r4 A10 — RESERVATION PATTERN: reserve the slot ATOMICALLY at
        # creation. A stale pre-check would let two users both pass with the
        # last slot and then lose money at payment time; the atomic UPDATE is
        # the real gate (same trick as the r3 payment claim).
        from sqlalchemy import text as _text
        reserved = session.exec(_text(
            "UPDATE coupons SET used_count = used_count + 1 "
            "WHERE id = :cid AND used_count < max_uses RETURNING id"
        ), params={"cid": coupon_row.id}).first()
        if not reserved:
            raise ValueError("کد تخفیف مصرف شده")
        session.refresh(coupon_row)
        amount = max(1, int(amount * (100 - coupon_row.percent) / 100))

    referral_event = None
    if ref_code and not coupon_row:
        existing = session.exec(
            select(Order).where(Order.chart_id == chart_id, Order.status != "failed")
        ).first()
        referrer = session.exec(
            select(ReferralCode).where(ReferralCode.code == ref_code.strip())
        ).first()
        # H1.4: self-referral must be impossible — using your OWN referral code
        # would grant 10% off + a 10% self-reward (money printer)
        self_ref = referrer is not None and new_user_id is not None and referrer.user_id == new_user_id
        if not existing and referrer and not self_ref:
            amount = max(1, int(amount * 0.9))
            referral_event = ReferralEvent(
                code=ref_code.strip(), referrer_user_id=referrer.user_id,
                new_user_id=new_user_id,
                amount_rial=amount, reward_rial=_referral_reward_rial(amount),
                status="pending",
            )
            session.add(referral_event)
            session.flush()

    # Derive profile ownership from the chart so a logged-in user's order
    # actually appears in their account (audit P1-4: was hardcoded to None).
    _chart = session.get(Chart, chart_id)
    profile_id = _chart.profile_id if _chart else None
    if not _chart:
        chart_id = None  # P6: pack orders carry no chart (FK-safe)

    order = Order(chart_id=chart_id, profile_id=profile_id, user_id=new_user_id,
                  plan_key=plan.key, amount_rial=amount, status="pending",
                  coupon_id=coupon_row.id if coupon_row else None,
                  secondary_chart_id=secondary_chart_id,
                  chat_id=chat_id, platform=platform)
    session.add(order)
    session.flush()
    if referral_event:
        referral_event.order_id = order.id

    public_base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io")
    callback_url = f"{public_base}/api/payments/verify"

    client = ZarinpalClient()
    # Only send metadata.mobile when we actually have a phone — Zarinpal rejects
    # an empty string (no-registration web flow) with error -9.
    meta = {"mobile": new_user_id} if new_user_id else {}
    try:
        authority, pay_url = client.request(
            order.amount_rial, callback_url,
            f"خرید {plan.name_fa}",
            meta,
        )
    except ZarinpalError as e:
        order.status = "failed"
        # release the coupon reservation — no payment will happen (audit r4 A10)
        if order.coupon_id:
            c = session.get(Coupon, order.coupon_id)
            if c and c.used_count > 0:
                c.used_count -= 1
        session.commit()
        raise RuntimeError(f"درگاه پرداخت در دسترس نیست: {e}") from e

    order.authority = authority
    session.commit()
    return order, pay_url


def activate_subscription(session: Session, order: Order) -> None:
    """After a paid order: activate/refresh the subscription.

    audit r4 A9: renewal EXTENDS from the later of (current expiry, now) —
    a user renewing 20 days early keeps those 20 days (was: now+30, discarding
    the remainder). Works for bot (chat_id set) and web (chat_id None) flows.
    H: yearly = 365 days, monthly = 30 days (plan v2.0 §11)."""
    if not order.chart_id:
        return
    q = select(Subscription).where(Subscription.chart_id == order.chart_id)
    if order.chat_id:
        q = q.where(Subscription.chat_id == order.chat_id)
    else:
        q = q.where(Subscription.chat_id == None)  # noqa: E711 — SQLAlchemy IS NULL
    sub = session.exec(q).first()
    now = utcnow()
    base = sub.expires_at if (sub and sub.expires_at
                              and ensure_utc(sub.expires_at) > now) else now
    days = 365 if order.plan_key == "yearly" else 30  # H
    if sub:
        sub.active = True
        sub.expires_at = base + timedelta(days=days)
        sub.plan_key = order.plan_key
        sub.platform = order.platform or sub.platform
        sub.order_id = order.id  # audit r4 B6 — latest originating order
    else:
        session.add(Subscription(
            chat_id=order.chat_id, platform=order.platform or "telegram",
            chart_id=order.chart_id, freq="weekly", plan_key=order.plan_key,
            active=True, expires_at=base + timedelta(days=days),
            order_id=order.id,  # audit r4 B6
        ))
    session.commit()  # H — caller runs inside a short-lived session


# R13/N3: legacy toman report plans are retired — the paid-report path is now
# the credit economy (/api/purchase → grant_from_credits). Credit packs pay
# toman and grant credits; reports are then unlocked per-chart with credits.
REPORT_PLANS = set()  # no plan_key auto-enqueues a report anymore
# LANCH20 scope: the coupon's "first deep report" rule now keys on the credit
# actions that unlock deep reports (report_basic/full/gold), not toman plans.
DEEP_REPORT_ACTIONS = {"report_basic", "report_full", "report_gold"}
CREDIT_PACKS = {"credit3", "credit6", "credit12"}
SUBSCRIPTION_PLANS = {"monthly", "yearly"}   # H — همراه ماهانه/سالانه
SUBSCRIPTION_MONTHLY_CREDITS = 5             # H — 5 credits/month


def _local_month_key(dt: datetime, tz_name: str = "Asia/Tehran") -> tuple[int, int]:
    """H — timezone-aware month key for the once-per-month credit grant."""
    from zoneinfo import ZoneInfo
    try:
        local = ensure_utc(dt).astimezone(ZoneInfo(tz_name))
    except Exception:
        local = ensure_utc(dt).astimezone(ZoneInfo("Asia/Tehran"))
    return (local.year, local.month)


def grant_subscription_credits(session: Session, sub: Subscription,
                               tz_name: str = "Asia/Tehran") -> bool:
    """H — monthly 5-credit grant, ONCE per local month per subscription.

    Idempotent: re-running within the same month is a no-op. The user is
    resolved from the sub's chart → profile chain. Returns True when granted.
    """
    from app.models import BirthProfile
    now = utcnow()
    last = sub.last_credit_grant_at
    if last and _local_month_key(ensure_utc(last), tz_name) == _local_month_key(now, tz_name):
        return False
    ch = session.get(Chart, sub.chart_id)
    uid = None
    if ch and ch.profile_id:
        prof = session.get(BirthProfile, ch.profile_id)
        uid = prof.user_id if prof else None
    if not uid:
        return False
    from app import credits as _credits
    _credits.grant(session, uid, SUBSCRIPTION_MONTHLY_CREDITS, "subscription",
                   idempotency_key=f"subscription:{sub.id}:{now:%Y-%m}",
                   source_ref=sub.id, commit=False)
    sub.last_credit_grant_at = now
    session.commit()
    return True


def grant_due_subscription_credits(session: Session) -> int:
    """H — cron entry: grant for every active, unexpired subscription whose
    local month has turned. Returns the number of grants performed."""
    from app.models import BirthProfile
    now = utcnow()
    subs = session.exec(
        select(Subscription).where(
            Subscription.active == True,  # noqa: E712
            (Subscription.expires_at == None) | (Subscription.expires_at > now),  # noqa: E711
        )
    ).all()
    granted = 0
    for sub in subs:
        tz = "Asia/Tehran"
        ch = session.get(Chart, sub.chart_id) if sub.chart_id else None
        if ch and ch.profile_id:
            prof = session.get(BirthProfile, ch.profile_id)
            if prof and prof.tz_name:
                tz = prof.tz_name
        if grant_subscription_credits(session, sub, tz):
            granted += 1
    return granted


def sweep_stale_orders(session: Session, stale_minutes: int | None = None) -> int:
    """C-05 (audit r4 A10): expire stale pending orders and release their coupon
    slots. An abandoned payment (order stuck 'pending' past the payment window)
    permanently consumed a coupon slot; this sweep returns the slot so max_uses
    coupons never lock up. Sets status='failed' so the buyer can make a fresh
    attempt. Idempotent (used_count>0 guard). Returns slots released."""
    from datetime import timedelta

    from sqlalchemy import text

    from app.models import Coupon, Order
    from app.timeutil import utcnow

    sm = stale_minutes if stale_minutes is not None else 30
    released = 0
    # pending orders older than the payment window
    stale = session.exec(select(Order).where(
        Order.status == "pending",
        Order.created_at < utcnow() - timedelta(minutes=sm),
    )).all()
    for o in stale:
        if o.coupon_id:
            c = session.get(Coupon, o.coupon_id)
            if c and c.used_count > 0:
                c.used_count -= 1
                released += 1
        o.status = "failed"  # give the buyer a fresh attempt
        session.add(o)
    # defensive: failed orders still holding a slot (belt & suspenders)
    bad = session.exec(text(
        "SELECT o.id FROM orders o JOIN coupons c ON c.id = o.coupon_id "
        "WHERE o.status = 'failed' AND o.coupon_id IS NOT NULL "
        "AND c.used_count > 0"
    )).all()
    if bad:
        rows = session.exec(text(
            "UPDATE coupons SET used_count = used_count - 1 "
            "FROM orders o WHERE o.coupon_id = coupons.id "
            "AND o.status = 'failed' AND coupons.used_count > 0 RETURNING coupons.id"
        )).all()
        released += len(rows)
    session.commit()
    return released


def cancel_subscription(session: Session, sub: Subscription) -> None:
    """H — cancellation: entitlement ends now (no refund on the platform side;
    gateway refunds stay an admin action)."""
    sub.active = False
    sub.expires_at = utcnow()
    session.commit()


def _order_user_id(session: Session, order: Order) -> str | None:
    """Resolve the buyer from the order (P6: direct user_id) or chart chain."""
    from app.models import Chart, BirthProfile
    if order.user_id:
        return order.user_id
    if order.chart_id:
        ch = session.get(Chart, order.chart_id)
        if ch and ch.profile_id:
            p = session.get(BirthProfile, ch.profile_id)
            if p:
                return p.user_id
    if order.profile_id:
        p = session.get(BirthProfile, order.profile_id)
        if p:
            return p.user_id
    return None


def grant_credits(session: Session, order: Order) -> None:
    """P6 — credit-pack purchase: atomic credit grant + ledger row.
    The amount is taken from plans.credits_grant (never parsed from the key)."""
    plan = session.get(Plan, order.plan_key)
    grant = plan.credits_grant if plan else 0
    if grant <= 0:
        raise ValueError(f"credit pack {order.plan_key} has no credits_grant")
    uid = _order_user_id(session, order)
    if not uid:
        raise ValueError(f"order {order.id} has no resolvable buyer")
    from app import credits as _credits
    _credits.grant(session, uid, grant, "purchase",
                   idempotency_key=f"purchase:{order.id}",
                   source_ref=order.id, commit=False)
    session.flush()


def reward_referral(session: Session, order: Order) -> ReferralEvent | None:
    """D3: once an order is PAID, credit the referrer's wallet (10% of the
    discounted amount — plan v2.0 §13) and, on the referred user's FIRST paid
    order, grant 1 exploration credit to the buyer. Idempotent — status
    pending → rewarded, once. Referral cycles (A→B→A) are voided."""
    ev = session.exec(select(ReferralEvent).where(
        ReferralEvent.order_id == order.id,
        ReferralEvent.status == "pending",
    )).first()
    if not ev or not ev.referrer_user_id:
        return None
    # H1.4: second layer of defense — if the payer IS the referrer (created
    # before the self-referral guard), void the reward instead of paying out
    owner = session.get(Chart, order.chart_id)
    if owner and owner.profile_id:
        prof = session.get(BirthProfile, owner.profile_id)
        if prof and prof.user_id == ev.referrer_user_id:
            ev.status = "voided"
            session.flush()
            return ev
    # §13 referral cycles: the referrer must not be inside the referred
    # user's own referral ancestry (A→B→A rewards nothing)
    from app.models import User as _U
    buyer = session.get(_U, ev.new_user_id) if ev.new_user_id else None
    if buyer:
        chain: set[str] = {buyer.id}
        cur = session.get(_U, ev.referrer_user_id)
        hops = 0
        while cur and cur.id not in chain and hops < 8:
            chain.add(cur.id)
            prev = session.exec(select(ReferralEvent).where(
                ReferralEvent.new_user_id == cur.id,
                ReferralEvent.status.in_(("pending", "rewarded")),
            )).first()
            cur = session.get(_U, prev.referrer_user_id) if (prev and prev.referrer_user_id) else None
            hops += 1
        if cur and cur.id in chain:
            ev.status = "voided"  # cycle → no reward
            session.flush()
            return ev
    referrer = session.get(User, ev.referrer_user_id)
    if not referrer:
        return None
    referrer.balance_rial = (referrer.balance_rial or 0) + ev.reward_rial
    ev.status = "rewarded"
    session.flush()
    # §13: 1 exploration credit to the referred user after their first paid order
    if buyer and ev.reward_rial > 0:
        paid_before = session.exec(select(Order).where(
            Order.user_id == buyer.id,
            Order.status == "paid",
            Order.id != order.id,
        )).first()
        if not paid_before:
            from app import credits as _credits
            _credits.grant(session, buyer.id, 1, "referral_bonus",
                           idempotency_key=f"referral_bonus:{ev.id}",
                           source_ref=ev.id, commit=False)
            session.flush()
    return ev


def withdraw_request(session: Session, user_id: str, amount_rial: int) -> bool:
    """D3: queue a cash-out request. One pending at a time; amount must be
    positive and within balance. Returns False on any refusal.

    F-01 (audit v5 P0): the amount is RESERVED (debited) at request time and
    returned on rejection — otherwise the same balance could be withdrawn
    repeatedly after each 'paid' resolution (unlimited admin payout).
    F-11 (audit v6 P0): the reserve is an ATOMIC conditional UPDATE and the
    'one pending' rule is enforced by a partial unique index — two concurrent
    requests can no longer both pass the ORM checks and create two withdrawals
    (overdraw). The loser hits the unique index and its debit rolls back.
    """
    # H1.4: minimum payout — 500k rial (50k toman) keeps manual bank transfers
    # worth the effort and discourages dust-level abuse
    MIN_WITHDRAW_RIAL = 500_000
    u = session.get(User, user_id)
    if not u or amount_rial < MIN_WITHDRAW_RIAL:
        return False
    # F-11: atomic conditional debit (rowcount 0 ⇒ insufficient balance / no user)
    res = session.exec(text(
        "UPDATE users SET balance_rial = balance_rial - :amt "
        "WHERE id = :uid AND balance_rial >= :amt"
    ).bindparams(amt=amount_rial, uid=user_id))
    if res.rowcount != 1:
        return False
    try:
        session.add(WithdrawalRequest(user_id=user_id, amount_rial=amount_rial))
        session.commit()
        return True
    except Exception:  # noqa: BLE001 — partial unique index (concurrent pending)
        session.rollback()  # undo the debit too
        return False


def resolve_withdrawal(session: Session, wid: str, status: str, note: str = "") -> bool:
    """D3: admin resolves a withdrawal.

    F-01 (audit v5 P0): the amount was reserved at request time; 'paid' keeps
    the debit (admin transferred the money), 'rejected' refunds the balance.
    F-15 (audit v6 P0): the pending→paid/rejected transition is an ATOMIC CAS
    (`UPDATE ... WHERE status='pending' RETURNING id`) — two concurrent admin
    requests can no longer both win the same withdrawal (double payout, or a
    rejected amount refunded twice). The refund for 'rejected' happens inside
    the SAME transaction and ONLY in the winning caller.
    """
    wr = session.get(WithdrawalRequest, wid)
    if not wr or status not in ("paid", "rejected"):
        return False
    amt = wr.amount_rial
    uid = wr.user_id
    now = datetime.now(timezone.utc)
    won = session.exec(text(
        "UPDATE withdrawal_requests SET status = :status, note = :note, "
        "resolved_at = :now WHERE id = :wid AND status = 'pending' RETURNING id"
    ).bindparams(status=status, note=note[:500], now=now, wid=wid)).first()
    if not won:
        return False  # already resolved by a concurrent caller — loser
    if status == "rejected":
        # F-15: refund inside the same transaction, exactly once
        session.exec(text(
            "UPDATE users SET balance_rial = balance_rial + :amt WHERE id = :uid"
        ).bindparams(amt=amt, uid=uid))
    session.commit()
    return True


def pay_order_with_balance(session: Session, order: Order, user: User | None) -> bool:
    """D3: settle an order entirely from the wallet. Returns True if paid by
    balance (order.status = paid, no Zarinpal round-trip). Boundary: balance
    can only pay the FULL amount — no mixed payments (wallet+gateway).

    F-02 (audit v5 P0): the debit is a single atomic conditional UPDATE
    (balance >= amount) — the old read-check-subtract allowed two concurrent
    requests to double-spend the same balance. F-10 (P2): the referrer is
    rewarded here too, like the Zarinpal path.
    """
    if not user:
        return False
    if order.status != "pending":
        return False
    # F-02: atomic conditional debit — rowcount 0 ⇒ insufficient balance
    res = session.exec(text(
        "UPDATE users SET balance_rial = balance_rial - :amt "
        "WHERE id = :uid AND balance_rial >= :amt"
    ).bindparams(amt=order.amount_rial, uid=user.id))
    if res.rowcount != 1:
        return False
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    order.note = f"پرداخت با موجودی کیف پول (referral D3) — موجودی قبلی: {(user.balance_rial or 0) + order.amount_rial:,} ریال"
    # F-29 (opus-audit verified, 2026-08-17): mirror the Zarinpal success path —
    # subscriptions (monthly AND yearly), credit packs, and report plans must
    # ALL take effect when paying from the wallet. Previously only "monthly"
    # worked: yearly paid silently and credit packs never granted credits.
    if order.plan_key in SUBSCRIPTION_PLANS:
        activate_subscription(session, order)
        sub = session.exec(
            select(Subscription).where(
                Subscription.chart_id == order.chart_id,
                Subscription.chat_id == (order.chat_id if order.chat_id else None),
            )
        ).first()
        if sub:
            grant_subscription_credits(session, sub)  # first month granted on purchase
    if order.plan_key in CREDIT_PACKS:
        grant_credits(session, order)
    if order.plan_key in DEEP_REPORT_ACTIONS and order.chart_id and not order.report_id:
        # R13/N3: deep-report actions bought via /api/purchase don't pass
        # through here (they go through entitlements), but a legacy pending
        # order with a deep-report plan_key still auto-enqueues its report.
        rep = Report(chart_id=order.chart_id, status="queued",
                     plan_key=order.plan_key)
        session.add(rep)
        session.flush()
        order.report_id = rep.id
    session.commit()
    # F-12 (audit v6 P1): reward the referrer AFTER the settlement commit —
    # a referral failure must never roll the payment back (in the Zarinpal
    # path the gateway money has already moved; rolling back would leave the
    # order unpaid while the report is generated). Best-effort + idempotent.
    try:
        reward_referral(session, order)
        session.commit()
    except Exception:  # noqa: BLE001 — referral must never break payment
        session.rollback()
    return True
