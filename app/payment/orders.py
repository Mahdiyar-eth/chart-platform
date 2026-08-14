"""Shared order creation + subscription activation (plan v3.0 §7/§8/§12).

Used by BOTH the web API and the Telegram/Bale bots so pricing, coupon,
referral and payment flows stay in one place.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import Chart, Coupon, Order, Plan, ReferralCode, ReferralEvent, Subscription
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
        if not existing and referrer:
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

    public_base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8767")
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
    else:
        session.add(Subscription(
            chat_id=order.chat_id, platform=order.platform or "telegram",
            chart_id=order.chart_id, freq="weekly", plan_key=order.plan_key,
            active=True, expires_at=base + timedelta(days=30),
        ))


REPORT_PLANS = {"basic", "full", "gold"}
