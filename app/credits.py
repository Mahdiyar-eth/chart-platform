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
          meta: dict | None = None, commit: bool = True) -> CreditTransaction:
    """Atomic credit spend.

    1) idempotency_key already recorded -> return that tx (no double charge)
    2) atomic `UPDATE users SET credits = credits - :c WHERE credits >= :c RETURNING id`
    3) no row returned -> InsufficientCredits (ZAY-CRD-001), balance untouched
    4) ledger row with negative amount (same transaction as the decrement)
    """
    price = get_price(session, action_key)
    # X7/R21: an empty idempotency key must be REJECTED — it silently skips
    # dedupe and allows double spends. (None/"" both rejected.)
    if not idempotency_key or not str(idempotency_key).strip():
        raise CreditError("کلید idempotency الزامی است")
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
        if commit:
            session.commit()
        else:
            session.flush()  # X4: assign ids, keep atomicity for the caller's commit
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


def refund(session: Session, tx_id: str, reason: str = "refund",
           amount: int | None = None) -> CreditTransaction:
    """Refund a failed/refunded spend. Idempotent: calling twice with the same
    (tx, amount-bucket) returns the same refund tx (never credits back twice).

    X3/R3: `amount` enables PARTIAL refunds (proportional QA policy). A full
    refund is amount=None; a partial refund of a later full call uses a
    different idempotency bucket so both can coexist.

    Returns the refund ledger row (positive amount)."""
    original = session.get(CreditTransaction, tx_id)
    if not original:
        raise CreditError("تراکنش اعتباری یافت نشد")
    cost = abs(original.amount)
    # Y6/N6: cumulative cap — total refunds for this tx can never exceed `cost`.
    refunded_so_far = session.execute(text(
        "SELECT COALESCE(SUM(amount), 0) FROM credit_transactions "
        "WHERE reason = 'refund' AND ref_id = :rid"), params={"rid": original.id}).scalar() or 0
    room = cost - int(refunded_so_far)
    if amount is not None:
        if amount <= 0 or amount > cost:
            raise CreditError("مبلغ بازگشت نامعتبر است")
    else:
        amount = max(room, 0)
    if amount > room:
        amount = room  # clamp partial to remaining room (never over-refund)
    if amount <= 0:
        existing_all = _find_idempotent(session, f"refund:{original.id}")
        if existing_all:
            return existing_all
        return original  # nothing left to refund — no-op marker
    # idempotency: look for an existing refund row keyed to this tx (+bucket)
    idem = f"refund:{original.id}" if amount is None else f"refund:{original.id}:{amount}"
    existing = _find_idempotent(session, idem)
    if existing:
        return existing
    if cost <= 0:
        # nothing to refund (already free / zero); return a marker 0 row
        session.execute(text(
            "UPDATE users SET credits = credits + :c WHERE id = :uid"
        ), params={"c": 0, "uid": original.user_id})
        tx = CreditTransaction(user_id=original.user_id, amount=0,
                               reason="refund", ref_id=original.id,
                               idempotency_key=idem)
        session.add(tx)
        try:
            session.commit()  # X7/R20: concurrent duplicate → return winner's row
        except IntegrityError:
            session.rollback()
            existing = _find_idempotent(session, idem)
            if existing:
                return existing
            raise
        session.refresh(tx)
        return tx
    _back = amount if amount is not None else cost  # X3: partial support
    session.execute(text(
        "UPDATE users SET credits = credits + :c WHERE id = :uid"
    ), params={"c": _back, "uid": original.user_id})
    tx = CreditTransaction(user_id=original.user_id, amount=+_back,
                           reason=reason, ref_id=original.id,
                           idempotency_key=idem)
    session.add(tx)
    try:
        session.commit()  # X7/R20: concurrent duplicate → return winner's row
    except IntegrityError:
        session.rollback()
        existing = _find_idempotent(session, idem)
        if existing:
            return existing
        raise
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
    # X7/R21: grant also requires a real key (payment flow relies on dedupe).
    if not idempotency_key or not str(idempotency_key).strip():
        raise CreditError("کلید idempotency الزامی است")
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
        try:
            session.commit()  # X7/R20: concurrent duplicate → return winner's row
        except IntegrityError:
            session.rollback()
            existing = _find_idempotent(session, idempotency_key)
            if existing:
                return existing
            raise
        session.refresh(tx)
    return tx
