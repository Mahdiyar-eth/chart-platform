"""A1 — credit data model (HERMES-PLAN-v1).

Seeded credit-price catalog + idempotency unique index + user-scoped
entitlements. The empty-DB alembic migration contract is proven separately in
the terminal (`alembic upgrade head` from empty + `alembic check` no drift);
these tests cover the seeded catalog, the idempotency guard, and the
entitlements table against the schema built on the test DB.
"""
import secrets

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import engine
from app.models import CreditPrice, CreditTransaction, Entitlement, User


def _phone() -> str:
    return f"0912{secrets.randbelow(10**7):07d}"


def test_credit_prices_seeded_with_10_rows():
    with Session(engine) as s:
        rows = s.exec(select(CreditPrice)).all()
    assert len(rows) == 10
    by_key = {r.action_key: r.credits for r in rows}
    assert by_key["explore_card"] == 1
    assert by_key["report_basic"] == 3
    assert by_key["report_full"] == 7
    assert by_key["report_gold"] == 14
    assert by_key["synastry_full"] == 10
    assert by_key["transit_3m"] == 2
    assert by_key["transit_12m"] == 5
    assert by_key["rectify"] == 2
    assert by_key["chat_pack_20"] == 2
    assert by_key["report_audio"] == 1


def test_two_transactions_same_idempotency_key_rejected():
    with Session(engine) as s:
        u = User(phone=_phone())
        s.add(u)
        s.commit()
        uid = u.id
    key = "a1-idem-" + secrets.token_hex(8)
    # first insert succeeds
    with Session(engine) as s:
        s.add(CreditTransaction(user_id=uid, amount=-1, reason="exploration",
                                ref_id=None, idempotency_key=key))
        s.commit()
    # second with the same key must be rejected by uq_credit_tx_idem_key
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(CreditTransaction(user_id=uid, amount=-1, reason="exploration",
                                    ref_id=None, idempotency_key=key))
            s.commit()


def test_entitlements_user_scoped_insert():
    with Session(engine) as s:
        u = User(phone=_phone())
        s.add(u)
        s.commit()
        ent = Entitlement(user_id=u.id, kind="transit", chart_id=None,
                          ref_id=None, quantity=1, used=0,
                          source="credit", source_ref=None)
        s.add(ent)
        s.commit()
        got = s.get(Entitlement, ent.id)
        assert got is not None
        assert got.kind == "transit"
        assert got.user_id == u.id
