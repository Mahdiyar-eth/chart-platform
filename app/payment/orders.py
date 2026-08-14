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


def get_or_create_referral_code(session: Session, user_id: str) -> str:
    """Return the user's stable random referral code (no PII in the URL)."""
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
        # would grant 10% off + a 5% self-reward (money printer)
        self_ref = referrer is not None and new_user_id is not None and referrer.user_id == new_user_id
        if not existing and referrer and not self_ref:
            amount = max(1, int(amount * 0.9))
            referral_event = ReferralEvent(
                code=ref_code.strip(), referrer_user_id=referrer.user_id,
                new_user_id=new_user_id,
                amount_rial=amount, reward_rial=int(amount * 0.05), status="pending",
            )
            session.add(referral_event)
            session.flush()

    # Derive profile ownership from the chart so a logged-in user's order
    # actually appears in their account (audit P1-4: was hardcoded to None).
    _chart = session.get(Chart, chart_id)
    profile_id = _chart.profile_id if _chart else None

    order = Order(chart_id=chart_id, profile_id=profile_id, plan_key=plan.key,
                  amount_rial=amount, status="pending",
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
    """After a paid monthly order: activate/refresh the chat subscription.

    audit r4 A9: renewal EXTENDS from the later of (current expiry, now) —
    a user renewing 20 days early keeps those 20 days (was: now+30, discarding
    the remainder). Works for bot (chat_id set) and web (chat_id None) flows."""
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
    if sub:
        sub.active = True
        sub.expires_at = base + timedelta(days=30)
        sub.plan_key = order.plan_key
        sub.platform = order.platform or sub.platform
        sub.order_id = order.id  # audit r4 B6 — latest originating order
    else:
        session.add(Subscription(
            chat_id=order.chat_id, platform=order.platform or "telegram",
            chart_id=order.chart_id, freq="weekly", plan_key=order.plan_key,
            active=True, expires_at=base + timedelta(days=30),
            order_id=order.id,  # audit r4 B6
        ))


REPORT_PLANS = {"basic", "full", "gold"}


def reward_referral(session: Session, order: Order) -> ReferralEvent | None:
    """D3: once an order is PAID, credit the referrer's wallet (5% of the
    discounted amount). Idempotent — status pending → rewarded, once."""
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
    referrer = session.get(User, ev.referrer_user_id)
    if not referrer:
        return None
    referrer.balance_rial = (referrer.balance_rial or 0) + ev.reward_rial
    ev.status = "rewarded"
    session.flush()
    return ev


def withdraw_request(session: Session, user_id: str, amount_rial: int) -> bool:
    """D3: queue a cash-out request. One pending at a time; amount must be
    positive and within balance. Returns False on any refusal.

    F-01 (audit v5 P0): the amount is RESERVED (debited) at request time and
    returned on rejection — otherwise the same balance could be withdrawn
    repeatedly after each 'paid' resolution (unlimited admin payout).
    """
    # H1.4: minimum payout — 500k rial (50k toman) keeps manual bank transfers
    # worth the effort and discourages dust-level abuse
    MIN_WITHDRAW_RIAL = 500_000
    u = session.get(User, user_id)
    if not u or amount_rial < MIN_WITHDRAW_RIAL or amount_rial > (u.balance_rial or 0):
        return False
    if session.exec(select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == user_id,
            WithdrawalRequest.status == "pending")).first():
        return False
    # F-01: reserve now — reject later refunds this back
    u.balance_rial = (u.balance_rial or 0) - amount_rial
    session.add(WithdrawalRequest(user_id=user_id, amount_rial=amount_rial))
    session.commit()
    return True


def resolve_withdrawal(session: Session, wid: str, status: str, note: str = "") -> bool:
    """D3: admin resolves a withdrawal.

    F-01 (audit v5 P0): the amount was reserved at request time; 'paid' keeps
    the debit (admin transferred the money), 'rejected' refunds the balance.
    """
    wr = session.get(WithdrawalRequest, wid)
    if not wr or wr.status != "pending":
        return False
    if status not in ("paid", "rejected"):
        return False
    wr.status = status
    wr.note = note
    wr.resolved_at = datetime.now(timezone.utc)
    if status == "rejected":
        u = session.get(User, wr.user_id)
        if u:
            u.balance_rial = (u.balance_rial or 0) + wr.amount_rial
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
    # F-10: credit the referrer (5%) — same hook as the Zarinpal verify path
    try:
        reward_referral(session, order)
    except Exception:  # noqa: BLE001 — referral must never break payment
        session.rollback()
        order = session.get(Order, order.id)
    if order.plan_key == "monthly":
        activate_subscription(session, order)
    if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
        rep = Report(chart_id=order.chart_id, status="queued", plan_key=order.plan_key)
        session.add(rep)
        session.flush()
        order.report_id = rep.id
    session.commit()
    return True
