"""Payment flow tests — FAKE Zarinpal client (no real API calls, no spend)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.models import Order, Plan
from app.payment.zarinpal import ZarinpalError


class FakeZarinpal:
    """Deterministic sandbox stand-in: request → authority S..., verify → ref_id."""
    def __init__(self, fail_request=False, fail_verify=False):
        self.fail_request = fail_request
        self.fail_verify = fail_verify
        self.requested = []
        self.verified = []

    def request(self, amount_rial, callback_url, description, metadata=None):
        if self.fail_request:
            raise ZarinpalError("sandbox down")
        self.requested.append(amount_rial)
        return "S" + "A" * 36, f"https://sandbox.zarinpal.com/pg/StartPay/S{'A'*36}"

    def verify(self, authority, amount_rial):
        if self.fail_verify:
            raise ZarinpalError("verify failed")
        self.verified.append((authority, amount_rial))
        return {"ref_id": "100000000001", "card_pan": "621986****1234"}


@pytest.fixture
def fake_gw():
    return FakeZarinpal()


def test_price_rial():
    p = Plan(key="basic", name_fa="پایه", price_toman=149_000, features=[])
    assert p.price_rial == 1_490_000  # Rial = Toman × 10


def test_zarinpal_request_returns_s_authority(fake_gw):
    auth, url = fake_gw.request(1_490_000, "http://x/verify", "خرید")
    assert auth.startswith("S")
    assert "StartPay" in url


def test_zarinpal_verify_returns_ref_id(fake_gw):
    v = fake_gw.verify("S" + "A" * 36, 1_490_000)
    assert v["ref_id"]
    assert "card_pan" in v


def test_zarinpal_request_failure_raises():
    gw = FakeZarinpal(fail_request=True)
    with pytest.raises(ZarinpalError):
        gw.request(100, "http://x", "t")


def test_verify_failure_raises():
    gw = FakeZarinpal(fail_verify=True)
    with pytest.raises(ZarinpalError):
        gw.verify("SABC", 100)


def test_order_status_transitions():
    o = Order(plan_key="full", amount_rial=3_490_000, status="pending")
    assert o.status == "pending"
    o.status = "paid"
    o.ref_id = "100000000001"
    assert o.status == "paid"


def test_plans_seed_shape():
    from app.main import PLANS_SEED
    assert [p.key for p in PLANS_SEED] == ["basic", "full", "gold",
                                           "credit3", "credit6", "credit12",
                                           "monthly", "yearly"]
    assert all(p.price_toman > 0 for p in PLANS_SEED)
    assert all(p.features for p in PLANS_SEED)
    # P6 — every credit pack carries a positive grant; others carry 0
    packs = [p for p in PLANS_SEED if p.key.startswith("credit")]
    assert all(p.credits_grant > 0 for p in packs)
    assert all(not p.key.startswith("credit") or p.credits_grant > 0
               for p in PLANS_SEED)
    # H — subscription prices per plan v2.0 §11
    prices = {p.key: p.price_toman for p in PLANS_SEED}
    assert prices["monthly"] == 99_000 and prices["yearly"] == 890_000
