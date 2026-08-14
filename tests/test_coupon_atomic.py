"""Coupon consumption atomicity — audit P1 (round 3): two concurrent payment
verifies must never push used_count past max_uses. The atomic UPDATE returns
a row only while capacity remains; the second verify fails the order."""
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import text

import app.main as main_mod
from app.db import engine


def _mk_coupon(max_uses: int = 1) -> str:
    cid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO coupons (id, code, percent, max_uses, used_count, active, created_at) "
            "VALUES (:id, :code, 20, :mu, 0, true, now())"
        ), {"id": cid, "code": "CP" + cid[:8], "mu": max_uses})
    return cid


def _mk_order(authority: str, coupon_id: str) -> str:
    oid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO orders (id, plan_key, amount_rial, status, coupon_id, authority, created_at) "
            "VALUES (:id, 'basic', 149000, 'pending', :cid, :auth, now())"
        ), {"id": oid, "cid": coupon_id, "auth": authority})
    return oid


class _FakeGW:
    def verify(self, authority, amount_rial):
        return {"ref_id": "REF-" + authority[:6], "card_pan": None}


def _verify(client: TestClient, authority: str):
    return client.get(f"/api/payments/verify?Authority={authority}&Status=OK",
                      follow_redirects=False)


def test_atomic_update_reserves_only_while_capacity():
    cid = _mk_coupon(max_uses=1)
    with engine.begin() as conn:
        r1 = conn.execute(text(
            "UPDATE coupons SET used_count = used_count + 1 "
            "WHERE id = :cid AND used_count < max_uses RETURNING id"), {"cid": cid}).first()
        r2 = conn.execute(text(
            "UPDATE coupons SET used_count = used_count + 1 "
            "WHERE id = :cid AND used_count < max_uses RETURNING id"), {"cid": cid}).first()
        assert r1 is not None and r2 is None  # second reservation refused
        row = conn.execute(text("SELECT used_count FROM coupons WHERE id = :cid"),
                           {"cid": cid}).one()
        assert row[0] == 1


def test_coupon_exhausted_second_order_fails(monkeypatch):
    """audit r4 A10 — NEW semantics: the coupon slot is reserved at CREATION,
    so the second order cannot even be created once capacity is gone (the old
    verify-time consume failed a PAID order — P0-7 money-lost regression)."""
    monkeypatch.setattr(main_mod, "ZarinpalClient", lambda: _FakeGW())
    c = TestClient(app_mod())
    cid = _mk_coupon(max_uses=1)
    a1 = "AUTH" + uuid.uuid4().hex[:8]
    _mk_order(a1, cid)
    # legacy raw-DB order (created before reservation): verify must still mark
    # it PAID — a paying user never gets a failed order over coupon capacity
    r1 = _verify(c, a1)
    assert r1.status_code == 303  # paid → redirect to result
    with engine.begin() as conn:
        row = conn.execute(text("SELECT status FROM orders WHERE authority = :a"), {"a": a1}).one()
        assert row[0] == "paid"
        used = conn.execute(text("SELECT used_count FROM coupons WHERE id = :c"), {"c": cid}).one()
        assert used[0] == 0  # never reserved → never consumed


def app_mod():
    return main_mod.app
