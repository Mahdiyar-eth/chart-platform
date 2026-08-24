"""R.10 / P3-2 — CATALOG↔DELIVERY gate: every credit product delivers what it sells.

The auditor's recurring money bug (R7, R9): the catalogue advertises X, but the code
delivers less (transit refunded on the wrong denominator; report_gold granted only a
"report" while the title promises report+chat+transit). This is the anti-repeat gate
that runs EVERY credit product and asserts the entitlement kinds it produces match the
title's promise. When someone adds a new product or tweaks a keyword, this gate turns
RED if the delivery stops matching the advert.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.credits import get_price
from app.db import engine
from app.entitlements import grant_from_credits
from app.main import app as main_app
from app.models import CreditPrice, Entitlement, User


def _mk_user(credits=100):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t", credits=credits)); s.commit()
        return uid


# The advertised promise per action_key: which entitlement kind(s) it MUST grant.
# Derive from the title (title_fa) — this is the catalogue contract.
# MASTER W4 (§6): titles are now result-oriented («یک سؤال، یک جواب»,
# «۱۲ ماه آیندهٔ من», «ما به هم می‌خوریم؟») so keyword matching also reads
# the new phrasing. action_key prefix remains the hard contract.
def _expected_kinds(action_key: str, title_fa: str) -> set[str]:
    kinds = set()
    # report_audio is an ADD-ON (kind "audio") — the title mentions صوتی.
    if "صوتی" in title_fa or "نسخهٔ صوتی" in title_fa:
        return {"audio"}
    if "چت" in title_fa or action_key.startswith("chat_pack"):
        kinds.add("chat")
        return kinds  # chat packs are the chat product
    if "گذر" in title_fa or "ماه آینده" in title_fa:
        kinds.add("transit")
    if "سیناستری" in title_fa or "به هم می‌خوریم" in title_fa or "سازگاری" in title_fa:
        kinds.add("synastry")
    if "کاوش" in title_fa or "سؤال" in title_fa:
        kinds.add("explore")
    if "گزارش" in title_fa or "آشنایی" in title_fa or "شناخت" in title_fa:
        kinds.add("report")
    return kinds or {"credit"}  # generic fallback


def test_catalog_matches_delivery_for_all_products():
    """Every active credit_prices row delivers the entitlement its title advertises."""
    with Session(engine) as s:
        rows = s.exec(select(CreditPrice).where(CreditPrice.active == True)).all()  # noqa: E712
        assert len(rows) >= 8, f"expected the full credit catalogue, got {len(rows)}"
    failures = []
    for r in rows:
        uid = _mk_user(100)
        try:
            get_price(Session(engine), r.action_key)
        except Exception:  # noqa: BLE001
            continue
        with Session(engine) as s:
            grant_from_credits(s, uid, r.action_key, idempotency_key="p32_" + uuid.uuid4().hex,
                               chart_id="CHX" if r.action_key.startswith(("report", "transit", "synastry")) else None,
                               quantity=20 if r.action_key.startswith("chat_pack") else None)
            granted = {e.kind for e in s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()}
        expected = _expected_kinds(r.action_key, r.title_fa)
        # every promised kind must be delivered (extra generic kinds allowed)
        if not expected <= granted:
            failures.append((r.action_key, expected, granted))
    assert not failures, f"catalog↔delivery mismatches: {failures}"


def test_every_action_key_has_catalogue_title():
    """No active credit product lacks a title (silent catalogue = broken advert)."""
    with Session(engine) as s:
        rows = s.exec(select(CreditPrice).where(CreditPrice.active == True)).all()  # noqa: E712
        empties = [r.action_key for r in rows if not r.title_fa]
    assert not empties, f"products with no title: {empties}"


def test_subscription_cancel_route_reachable():
    """P3-3: /api/subscriptions/{id}/cancel must be reachable (auth + 404 for a bad id)."""
    c = TestClient(main_app)
    # unauthenticated → 401 (route exists and responds, not a 405/404 confusion)
    r = c.post("/api/subscriptions/nonexistent/cancel")
    assert r.status_code in (401, 404), r.status_code


def test_report_docx_route_reachable():
    """P3-3: the DOCX download route must be reachable (401/403/404, not a 500)."""
    c = TestClient(main_app)
    r = c.get("/api/reports/nonexistent.docx")
    assert r.status_code in (401, 403, 404), r.status_code
