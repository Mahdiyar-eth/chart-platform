"""Zarinpal v4 payment client — sandbox + production.

Docs: https://www.zarinpal.com/docs/paymentGateway/connectToGateway
Sandbox: any UUID works as merchant_id; authorities start with "S".
Amount unit: Rial (ریال) — multiply Toman prices by 10.
"""
from __future__ import annotations

import logging
import os
import uuid

import httpx

log = logging.getLogger("zarinpal")

SANDBOX_BASE = "https://sandbox.zarinpal.com/pg/v4"
PROD_BASE = "https://payment.zarinpal.com/pg/v4"
SANDBOX_PAY = "https://sandbox.zarinpal.com/pg/StartPay"
PROD_PAY = "https://payment.zarinpal.com/pg/StartPay"


class ZarinpalError(Exception):
    pass


class ZarinpalClient:
    def __init__(self, merchant_id: str | None = None, sandbox: bool | None = None):
        from app.secret_store import get_secret
        self.merchant_id = merchant_id or get_secret("zarinpal_merchant_id", "ZARINPAL_MERCHANT_ID", "")
        if not self.merchant_id:
            raise ZarinpalError("ZARINPAL_MERCHANT_ID is not set")
        self.sandbox = sandbox if sandbox is not None else get_secret("zarinpal_sandbox", "ZARINPAL_SANDBOX", "true").lower() == "true"
        self.base = SANDBOX_BASE if self.sandbox else PROD_BASE
        self.pay_base = SANDBOX_PAY if self.sandbox else PROD_PAY
        self.timeout = float(os.getenv("ZARINPAL_TIMEOUT", "15"))

    def request(self, amount_rial: int, callback_url: str, description: str,
                metadata: dict | None = None) -> tuple[str, str]:
        """Create a transaction. Returns (authority, payment_url)."""
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_rial,
            "callback_url": callback_url,
            "description": description,
            "metadata": metadata or {},
        }
        r = httpx.post(f"{self.base}/payment/request.json", json=payload,
                       headers={"Accept": "application/json"}, timeout=self.timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        errs = data.get("errors") or []
        if errs:
            raise ZarinpalError(f"request failed: {errs}")
        d = data.get("data") or {}
        if d.get("code") != 100:
            raise ZarinpalError(f"request code {d.get('code')}: {d.get('message')}")
        authority = d["authority"]
        return authority, f"{self.pay_base}/{authority}"

    def verify(self, authority: str, amount_rial: int) -> dict:
        """Verify a payment after callback. Returns {ref_id, card_pan} on success."""
        payload = {
            "merchant_id": self.merchant_id,
            "authority": authority,
            "amount": amount_rial,
        }
        r = httpx.post(f"{self.base}/payment/verify.json", json=payload,
                       headers={"Accept": "application/json"}, timeout=self.timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        errs = data.get("errors") or []
        if errs:
            raise ZarinpalError(f"verify failed: {errs}")
        d = data.get("data") or {}
        code = d.get("code")
        if code not in (100, 101):  # 101 = already verified (idempotent retry)
            raise ZarinpalError(f"verify code {code}: {d.get('message')}")
        return {"ref_id": d.get("ref_id", ""), "card_pan": d.get("card_pan", "")}

    def refund(self, authority: str, amount_rial: int) -> dict:
        """Refund a paid transaction (audit r4 B6). Returns {ref_id} on success.

        Zarinpal v4: POST /payment/refund.json — needs the original authority.
        A repeat call on an already-refunded authority errors (code ~ 66/67),
        which the caller must map to "already refunded".
        """
        payload = {
            "merchant_id": self.merchant_id,
            "authority": authority,
            "amount": amount_rial,
        }
        r = httpx.post(f"{self.base}/payment/refund.json", json=payload,
                       headers={"Accept": "application/json"}, timeout=self.timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        errs = data.get("errors") or []
        if errs:
            raise ZarinpalError(f"refund failed: {errs}")
        d = data.get("data") or {}
        code = d.get("code")
        if code != 100:
            raise ZarinpalError(f"refund code {code}: {d.get('message')}")
        return {"ref_id": d.get("ref_id", "")}


def fake_authority() -> str:
    return "S" + uuid.uuid4().hex[:32].upper()
