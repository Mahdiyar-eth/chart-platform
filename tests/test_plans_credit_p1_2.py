"""R.10 / P1-2 (A4 de-narrowing) — /plans must sell the UNIFIED credit model.

The F1 audit flagged \"two parallel money systems\": the back-end is credit-based,
but plans.html still called /api/orders (toman). This asserts the observable contract.
"""

import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import USER_COOKIE, _user_cookie_value
from app.db import engine
from app.main import app
from app.models import Entitlement, User


def _mk_user(n):
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, credits=n)
        s.add(u)
        s.commit()
        return u.id


def _cookie(uid):
    return {USER_COOKIE: _user_cookie_value(uid)}


def test_plans_page_renders_credit_products():
    """/plans renders the credit table from credit_prices (not hardcoded toman plans)."""
    c = TestClient(app)
    r = c.get("/plans")
    assert r.status_code == 200, r.text
    html = r.text
    # The unified table labels each row with an action_key and a /api/purchase handler.
    assert "باز کردن با" in html          # credit-buy button text
    assert "/api/purchase" in html        # the credit path is wired in
    assert "گزارش طلایی" in html or "گزارش کامل" in html


def test_plans_page_wires_api_purchase_not_only_orders():
    """The anti-narrowing gate: plans.html must call /api/purchase (≥1), not rely on /api/orders."""
    from pathlib import Path
    tpl = Path(__file__).resolve().parent.parent / "app" / "templates" / "plans.html"
    body = tpl.read_text(encoding="utf-8")
    assert body.count("api/purchase") >= 1, "plans.html must wire the credit purchase path"


def test_buy_credit_product_reaches_entitlement():
    """End-to-end from a credit product action_key → /api/purchase → Entitlement row."""
    uid = _mk_user(50)
    c = TestClient(app)
    r = c.post("/api/purchase", json={"action_key": "report_basic", "chart_id": "CHX"},
               cookies=_cookie(uid))
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    with Session(engine) as s:
        ents = s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()
        assert any(e.kind == "report" for e in ents), [e.kind for e in ents]
