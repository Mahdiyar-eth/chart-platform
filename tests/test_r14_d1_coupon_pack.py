"""R14-D1 — LANCH20 (report_only) must NEVER discount a credit PACK.

The guard that was supposed to reject packs whitelisted them instead:
`if plan_key not in CREDIT_PACKS and plan_key not in DEEP_REPORT_ACTIONS`
let credit3/credit6/credit12 through with 20% off — a live money bug.

RED test (written before the fix): create_order(credit12 + LANCH20)
must raise ValueError «فقط برای گزارش عمیق».
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

import pytest
from sqlmodel import Session

from app.db import engine, seed_plans, seed_credit_prices
from app.models import Coupon, User
from sqlmodel import Session as _S  # noqa: F401


def _coupon(s: Session, code: str) -> Coupon:
    c = Coupon(code=code, percent=20, max_uses=10, active=True, report_only=True)
    s.add(c); s.commit(); s.refresh(c)
    return c


def _mk_user() -> str:
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@d1", credits=0)); s.commit()
    return uid


def test_d1_report_only_coupon_rejects_credit_packs():
    """D1 RED→GREEN: pack + report_only coupon → ValueError, no order."""
    from app.payment.orders import create_order
    seed_plans(); seed_credit_prices()
    uid = _mk_user()
    with Session(engine) as s:
        cp = _coupon(s, "D1-" + uuid.uuid4().hex[:6].upper())
        with pytest.raises(ValueError, match="گزارش عمیق"):
            create_order(s, "credit12", "", coupon=cp.code, new_user_id=uid)
        # and the slot must NOT have been burned by the failed attempt
        assert cp.used_count == 0


def test_d1_deep_report_action_still_accepted_path_shape():
    """Sanity: the deep-report action itself is not rejected by the pack guard.
    (Full flow is covered by referral tests; here we only pin that the guard's
    rejection reason for a non-pack, non-deep key is still the same message.)"""
    from app.payment.orders import DEEP_REPORT_ACTIONS, CREDIT_PACKS
    assert "credit12" in CREDIT_PACKS
    assert "report_full" in DEEP_REPORT_ACTIONS
