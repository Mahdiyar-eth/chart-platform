"""MASTER W3 (AC-2) — /plans sells ONLY credits.

grep «اشتراک» in plans.html must be ZERO; the only toman on the page is the
credit packs section; every product card buys via /api/purchase.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app as main_app

TPL = Path(__file__).resolve().parent.parent / "app" / "templates" / "plans.html"


def test_ac2_no_subscription_word_in_plans_html():
    html = TPL.read_text(encoding="utf-8")
    assert "اشتراک" not in html, "AC-2: the word اشتراک must not appear on /plans"
    # the removed Jinja set must be gone too
    assert "selectattr('key', 'in', ['monthly'" not in html
    assert "'monthly','yearly'" not in html


def test_plans_page_renders_credit_only():
    c = TestClient(main_app, base_url="https://testserver")
    r = c.get("/plans")
    assert r.status_code == 200
    body = r.text
    assert "اشتراک" not in body, "/plans must not render any subscription block"
    assert "اعتبار" in body, "credit is the page currency"
    # products table present
    assert "باز کردن با" in body


def test_api_plans_still_sells_credit_packs():
    """The pack endpoint keeps working — packs are the only toman product."""
    c = TestClient(main_app)
    plans = c.get("/api/plans").json()
    keys = {p["key"] for p in plans}
    assert {"credit3", "credit6", "credit12"} <= keys
