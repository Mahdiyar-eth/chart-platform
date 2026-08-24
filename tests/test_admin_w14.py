"""MASTER W14 — admin panel: token caps + cost/revenue report.

The price-editing endpoint already existed (A7); W14 adds:
- GET  /api/admin/token-caps            → per-product LLM ceilings
- POST /api/admin/token-caps/{product}  → set one (validated, audited)
- GET  /api/admin/cost-revenue?days=30  → revenue (credits×50k) vs LLM cost
All three are admin-only.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient

from app.main import app as main_app, _admin_cookie_value


def _admin_client() -> TestClient:
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_admin", _admin_cookie_value())
    return c


def test_w14_token_caps_list_and_set():
    c = _admin_client()
    r = c.get("/api/admin/token-caps")
    assert r.status_code == 200, r.text
    caps = r.json()["caps"]
    assert "free_preview" in caps and caps["free_preview"]["default"] == 900
    # set a new cap
    r2 = c.post("/api/admin/token-caps/daily_insight", data={"max_tokens": "240"})
    assert r2.status_code == 200 and r2.json()["max_tokens"] == 240
    r3 = c.get("/api/admin/token-caps")
    assert r3.json()["caps"]["daily_insight"]["current"] == 240
    # invalid value rejected
    r4 = c.post("/api/admin/token-caps/daily_insight", data={"max_tokens": "10"})
    assert r4.status_code == 400
    # unknown product → 404
    r5 = c.post("/api/admin/token-caps/nope", data={"max_tokens": "500"})
    assert r5.status_code == 404


def test_w14_cost_revenue_report_shape():
    c = _admin_client()
    r = c.get("/api/admin/cost-revenue?days=30")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["window_days"] == 30
    assert d["credit_rate_toman"] == 50_000
    assert isinstance(d["products"], list)
    assert "total_llm_cost_usd" in d and "total_revenue_toman" in d
    # invalid window → 400
    assert c.get("/api/admin/cost-revenue?days=999").status_code == 400


def test_w14_admin_only():
    c = TestClient(main_app)
    assert c.get("/api/admin/token-caps").status_code == 403
    assert c.get("/api/admin/cost-revenue").status_code == 403
