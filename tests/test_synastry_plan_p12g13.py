"""G13 (§27) — synastry product visible on the pricing page.

R.10 / P1-2 (A4 de-narrowing): synastry was sold as a separate 499,000-toman card,
one of the "two parallel money systems". It's now a credit product (synastry_full =
10 credits) in the unified table. Assert the credit contract.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_plans_page_has_synastry_product():
    c = TestClient(app)
    r = c.get("/plans")
    assert r.status_code == 200
    # synastry is a credit product now, not a toman card
    assert "سیناستری" in r.text
    assert "باز کردن با" in r.text            # unified credit-buy button
    assert "۴۹۹,۰۰۰" not in r.text            # no parallel toman price
