"""G13 (§27) — synastry plan card visible on the pricing page."""
from fastapi.testclient import TestClient

from app.main import app


def test_plans_page_has_synastry_card():
    c = TestClient(app)
    r = c.get("/plans")
    assert r.status_code == 200
    assert "سیناستری" in r.text
    assert "/synastry" in r.text
    assert "۴۹۹,۰۰۰" in r.text
