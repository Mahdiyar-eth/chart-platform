"""R.9 / Q1 (P1) — report_gold grants the FULL bundle, not just a report.

The final audit found the catalogue sells "report_gold" as «گزارش ۱۳بخشه + چت
۳۰روزه + گذر ۱۲ماهه» (14 credits), but `_kind_for_action` collapsed it to a
single "report" — so a gold buyer got exactly what a full (7 credits) buyer got,
and had to RE-pay for transit. AC-1: gold must create report+chat+transit, the
chat gate must unlock, and transit analyze must not double-charge.
"""
import os, uuid
from pathlib import Path
sys_ = os.path.basename(__file__)
os.environ.setdefault("SWISSEPH_EPHE_PATH", str(Path(__file__).resolve().parent.parent / "ephe"))
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")

from sqlmodel import Session, select
from app.db import engine
from app.entitlements import grant_from_credits, has
from app.models import Entitlement, User


def _mk_user(credits=100):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        u = User(id=uid, phone=uid + "@t", credits=credits)
        s.add(u); s.commit()
        return uid


def test_gold_creates_three_entitlements():
    uid = _mk_user(50)
    with Session(engine) as s:
        grant_from_credits(s, uid, "report_gold", idempotency_key="g1_" + uuid.uuid4().hex,
                           chart_id="CHX")
        kinds = {e.kind for e in s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()}
        assert {"report", "chat", "transit"} <= kinds, kinds
        # report entitlement has the chart scope (per-report decision preserved)
        report = has(s, uid, "report", chart_id="CHX")
        assert report is not None
        # chat entitlement is a 30-day pack (expires)
        chat = has(s, uid, "chat", chart_id="CHX")
        assert chat is not None and chat.expires_at is not None
        # transit entitlement grants the 12-month analysis
        transit = has(s, uid, "transit", chart_id="CHX")
        assert transit is not None


def test_full_buyer_does_not_get_gold_bundle():
    """A full (7-credit) buyer must NOT get chat/transit — only the report."""
    uid = _mk_user(50)
    with Session(engine) as s:
        grant_from_credits(s, uid, "report_full", idempotency_key="f1_" + uuid.uuid4().hex,
                           chart_id="CHX")
        kinds = {e.kind for e in s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()}
        assert kinds == {"report"}, kinds
        assert has(s, uid, "chat", chart_id="CHX") is None
        assert has(s, uid, "transit", chart_id="CHX") is None


def test_gold_spends_once_and_is_idempotent():
    uid = _mk_user(50)
    with Session(engine) as s:
        key = "g2_" + uuid.uuid4().hex
        e1 = grant_from_credits(s, uid, "report_gold", idempotency_key=key, chart_id="CHX")
        bal_after = s.get(User, uid).credits
        e2 = grant_from_credits(s, uid, "report_gold", idempotency_key=key, chart_id="CHX")
        # idempotent → same report entitlement, no double spend
        assert e1.id == e2.id
        assert s.get(User, uid).credits == bal_after
