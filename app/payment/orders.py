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
        if coupon_row.expires_at and coupon_row.expires_at < datetime.now(timezone.utc):
            raise ValueError("کد تخفیف منقضی شده")
        if coupon_row.used_count >= coupon_row.max_uses:
            raise ValueError("کد تخفیف مصرف شده")
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
        session.commit()
        raise RuntimeError(f"درگاه پرداخت در دسترس نیست: {e}") from e

    order.authority = authority
    session.commit()
    return order, pay_url


def activate_subscription(session: Session, order: Order) -> None:
    """After a paid monthly order: activate/refresh the chat subscription."""
    if not order.chat_id or not order.chart_id:
        return
    sub = session.exec(
        select(Subscription).where(
            Subscription.chat_id == order.chat_id,
            Subscription.chart_id == order.chart_id,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if sub:
        sub.active = True
        sub.expires_at = now + timedelta(days=30)
        sub.plan_key = order.plan_key
        sub.platform = order.platform or sub.platform
    else:
        session.add(Subscription(
            chat_id=order.chat_id, platform=order.platform or "telegram",
            chart_id=order.chart_id, freq="weekly", plan_key=order.plan_key,
            active=True, expires_at=now + timedelta(days=30),
        ))


REPORT_PLANS = {"basic", "full", "gold"}
