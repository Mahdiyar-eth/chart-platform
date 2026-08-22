"""A2 — central credit service (single source of truth for the credit economy).

Every credit mutation MUST go through this module. The rule enforced by tests:
`grep -rn "SET credits" app/ | grep -v app/credits.py` == empty.

Accounting invariant: sum(credit_transactions.amount) per user == users.credits.
All price lookups come from credit_prices (DB), never hardcoded.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import CreditTransaction, CreditPrice, User

log = logging.getLogger("zayche.credits")


class CreditError(Exception):
    """Base credit error. `.code` is a stable machine-readable identifier."""
    code = "ZAY-CRD-000"
    message = "خطای اعتبار"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)


class InsufficientCredits(CreditError):
    """Raised when a spend would push credits below zero."""
    code = "ZAY-CRD-001"

    def __init__(self, needed: int, have: int):
        self.needed = needed
        self.have = have
        super().__init__(
            f"اعتبار کافی نیست — نیاز: {needed}، موجودی شما: {have}."
        )


class UnknownAction(CreditError):
    """Raised when action_key has no price row in credit_prices."""
    code = "ZAY-CRD-002"

    def __init__(self, action_key: str):
        self.action_key = action_key
        super().__init__(f"اکشن اعتباری ناشناخته: {action_key}")


def get_price(session: Session, action_key: str) -> int:
    """Price of an action from credit_prices. Never hardcode a number.

    Raises UnknownAction (ZAY-CRD-002) when the row is missing or inactive."""
    row = session.get(CreditPrice, action_key)
    if not row or not row.active:
        raise UnknownAction(action_key)
    return int(row.credits)


def balance(session: Session, user_id: str) -> int:
    """Current credit balance for a user (0 for unknown users)."""
    u = session.get(User, user_id)
    return int(u.credits) if u else 0


def _find_idempotent(session: Session, idempotency_key: str) -> CreditTransaction | None:
    return session.exec(
        select(CreditTransaction).where(CreditTransaction.idempotency_key == idempotency_key)
    ).first()


def spend(session: Session, user_id: str, action_key: str, *,
          idempotency_key: str, chart_id: str | None = None,
          meta: dict | None = None) -> CreditTransaction:
    """Atomic credit spend.

    1) idempotency_key already recorded -> return that tx (no double charge)
    2) atomic `UPDATE users SET credits = credits - :c WHERE credits >= :c RETURNING id`
    3) no row returned -> InsufficientCredits (ZAY-CRD-001), balance untouched
    4) ledger row with negative amount (same transaction as the decrement)
    """
    price = get_price(session, action_key)
    if idempotency_key:
        existing = _find_idempotent(session, idempotency_key)
        if existing:
            return existing
    # atomic guarded decrement — safe under concurrency (RETURNING)
    row = session.execute(text(
        "UPDATE users SET credits = credits - :c WHERE id = :uid AND credits >= :c RETURNING id"
    ), params={"c": price, "uid": user_id}).first()
    if not row:
        raise InsufficientCredits(price, balance(session, user_id))
    tx = CreditTransaction(
        user_id=user_id, amount=-price,
        reason=action_key, ref_id=chart_id,
        idempotency_key=idempotency_key,
    )
    session.add(tx)
    try:
        session.commit()
    except IntegrityError:
        # concurrent duplicate idempotency_key -> whole tx rolled back (credits
        # not deducted); return the winner's tx.
        session.rollback()
        existing = _find_idempotent(session, idempotency_key)
        if existing:
            return existing
        raise
    session.refresh(tx)
    return tx


def refund(session: Session, tx_id: str, reason: str = "refund") -> CreditTransaction:
    """Refund a failed/refunded spend. Idempotent: calling twice on the same tx
    returns the same refund tx (never credits back twice).

    Returns the refund ledger row (positive amount)."""
    original = session.get(CreditTransaction, tx_id)
    if not original:
        raise CreditError("تراکنش اعتباری یافت نشد")
    # idempotency: look for an existing refund row keyed to this tx
    idem = f"refund:{original.id}"
    existing = _find_idempotent(session, idem)
    if existing:
        return existing
    cost = abs(original.amount)
    if cost <= 0:
        # nothing to refund (already free / zero); return a marker 0 row
        session.execute(text(
            "UPDATE users SET credits = credits + :c WHERE id = :uid"
        ), params={"c": 0, "uid": original.user_id})
        tx = CreditTransaction(user_id=original.user_id, amount=0,
                               reason="refund", ref_id=original.id,
                               idempotency_key=idem)
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx
    session.execute(text(
        "UPDATE users SET credits = credits + :c WHERE id = :uid"
    ), params={"c": cost, "uid": original.user_id})
    tx = CreditTransaction(user_id=original.user_id, amount=+cost,
                           reason=reason, ref_id=original.id,
                           idempotency_key=idem)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def grant(session: Session, user_id: str, amount: int, reason: str, *,
          idempotency_key: str, source_ref: str | None = None,
          commit: bool = True) -> CreditTransaction:
    """Credit a user (topup/gift/subscription). Idempotent by idempotency_key.

    `commit=False` defers the commit to the caller's surrounding transaction
    (used inside the payment flow, which must stay atomic)."""
    if amount <= 0:
        raise CreditError("مبلغ اعتبار باید مثبت باشد")
    if idempotency_key:
        existing = _find_idempotent(session, idempotency_key)
        if existing:
            return existing
    session.execute(text(
        "UPDATE users SET credits = credits + :c WHERE id = :uid"
    ), params={"c": amount, "uid": user_id})
    tx = CreditTransaction(user_id=user_id, amount=+amount, reason=reason,
                           ref_id=source_ref, idempotency_key=idempotency_key)
    session.add(tx)
    if commit:
        session.commit()
        session.refresh(tx)
    return tx
