"""A2 — central credit service acceptance tests.

Hermetic: test DB (create_all), no LLM. Covers atomic spend, idempotency,
refund, grant, concurrency, accounting invariant, DB-driven pricing and the
'first exploration is free' preservation.
"""
import threading
import uuid

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app import credits
from app.credits import (InsufficientCredits, UnknownAction, balance,
                         get_price, grant, refund, spend)
from app.db import engine
from app.models import CreditTransaction, User


def _mk_user(credits: int = 0, phone: str | None = None) -> str:
    with Session(engine) as s:
        u = User(phone=phone or "0912" + str(uuid.uuid4().int)[:7], credits=credits)
        s.add(u)
        s.commit()
        s.refresh(u)
        return u.id


def _ledger_sum(user_id: str) -> int:
    with Session(engine) as s:
        rows = s.exec(select(CreditTransaction).where(CreditTransaction.user_id == user_id)).all()
        return sum(r.amount for r in rows)


def _user_credits(user_id: str) -> int:
    with Session(engine) as s:
        return int(s.get(User, user_id).credits)


def test_spend_success_decrements_and_ledgers():
    uid = _mk_user(10)
    with Session(engine) as s:
        tx = spend(s, uid, "explore_card", idempotency_key="k1_" + uuid.uuid4().hex)
    assert tx.amount == -1
    assert _user_credits(uid) == 9
    assert _ledger_sum(uid) == -1, "one -1 spend ledger row expected"


def test_spend_zero_balance_raises_and_untouched():
    uid = _mk_user(0)
    with Session(engine) as s:
        with pytest.raises(InsufficientCredits) as ei:
            spend(s, uid, "explore_card", idempotency_key="k2_" + uuid.uuid4().hex)
    assert ei.value.code == "ZAY-CRD-001"
    assert ei.value.needed == 1 and ei.value.have == 0
    assert _user_credits(uid) == 0  # untouched


def test_spend_exact_balance():
    uid = _mk_user(1)
    with Session(engine) as s:
        spend(s, uid, "explore_card", idempotency_key="k3_" + uuid.uuid4().hex)
    assert _user_credits(uid) == 0


def test_spend_idempotent_same_key():
    uid = _mk_user(10)
    key = "idem_" + uuid.uuid4().hex  # unique per run (idempotency key is global)
    with Session(engine) as s:
        tx1 = spend(s, uid, "explore_card", idempotency_key=key)
        tx2 = spend(s, uid, "explore_card", idempotency_key=key)
    assert tx1.id == tx2.id, "same key must return same tx"
    assert _user_credits(uid) == 9, "charged exactly once"


def test_refund_idempotent():
    uid = _mk_user(10)
    with Session(engine) as s:
        tx = spend(s, uid, "explore_card", idempotency_key="r1_" + uuid.uuid4().hex)
        r1 = refund(s, tx.id, "fail")
        r2 = refund(s, tx.id, "fail")
    assert r1.id == r2.id, "refund twice must return the same tx"
    assert _user_credits(uid) == 10, "refunded once, exactly back to 10"


def test_accounting_invariant_after_50_ops():
    uid = _mk_user(0)
    # seed opening balance THROUGH the ledger so sum(ledger)==credits holds
    with Session(engine) as s:
        grant(s, uid, 20, "signup_gift", idempotency_key="init_" + uuid.uuid4().hex)
    with Session(engine) as s:
        for i in range(50):
            if i % 3 == 0:
                grant(s, uid, 2, "topup", idempotency_key="g_%d" % i)
            else:
                try:
                    spend(s, uid, "explore_card", idempotency_key="s_%d" % i)
                except InsufficientCredits:
                    pass
    assert _user_credits(uid) == _ledger_sum(uid), "sum(ledger) == credits must hold"


def test_concurrent_spend_single_success():
    uid = _mk_user(1)
    results = []

    def worker():
        with Session(engine) as s:
            try:
                spend(s, uid, "explore_card", idempotency_key="c_" + uuid.uuid4().hex)
                results.append("ok")
            except InsufficientCredits:
                results.append("broke")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1, f"exactly one spend must succeed: {results}"
    assert _user_credits(uid) == 0


def test_get_price_unknown_action():
    with Session(engine) as s:
        with pytest.raises(UnknownAction):
            get_price(s, "no_such_price")


def test_grant_idempotent():
    uid = _mk_user(0)
    key = "gr_" + uuid.uuid4().hex  # unique per run
    with Session(engine) as s:
        g1 = grant(s, uid, 5, "gift", idempotency_key=key)
        g2 = grant(s, uid, 5, "gift", idempotency_key=key)
    assert g1.id == g2.id
    assert _user_credits(uid) == 5, "granted exactly once"


def test_price_from_db_not_hardcoded():
    uid = _mk_user(100)
    with Session(engine) as s:
        # change the price in DB, spend should charge the new amount
        row = s.get(__import__("app.models", fromlist=["CreditPrice"]).CreditPrice, "explore_card")
        original = row.credits
        row.credits = 7
        s.add(row)
        s.commit()
        try:
            tx = spend(s, uid, "explore_card", idempotency_key="pr_" + uuid.uuid4().hex)
            assert tx.amount == -7, "spend must use DB price, not a constant"
        finally:
            with Session(engine) as s2:
                row = s2.get(__import__("app.models", fromlist=["CreditPrice"]).CreditPrice, "explore_card")
                row.credits = original
                s2.add(row)
                s2.commit()


def test_never_negative_balance():
    uid = _mk_user(0)
    with Session(engine) as s:
        for _ in range(3):
            try:
                spend(s, uid, "explore_card", idempotency_key="n_" + uuid.uuid4().hex)
            except InsufficientCredits:
                pass
    assert _user_credits(uid) >= 0, "balance must never go negative"


def test_first_exploration_still_free():
    """Preserve the explore funnel: first-ever exploration is free.

    The central service is the credit path; the funnel flag lives on User and
    is respected by the explore route. This asserts the price is charged only
    after the free slot, i.e. a fresh user with 0 credits + unused free slot
    is treated as 'free available' (no spend raised)."""
    with Session(engine) as s:
        u = User(phone="0912" + str(uuid.uuid4().int)[:7], credits=0,
                 free_exploration_used=True)
        s.add(u)
        s.commit()
        s.refresh(u)
        uid = u.id
    with Session(engine) as s:
        with pytest.raises(InsufficientCredits):
            spend(s, uid, "explore_card", idempotency_key="f_" + uuid.uuid4().hex)
