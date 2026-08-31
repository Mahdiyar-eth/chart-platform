"""Payment E2E test (real merchant) — run ONLY after ZARINPAL_MERCHANT_ID is the
REAL (non-sandbox) merchant and ZARINPAL_SANDBOX=off.

Usage:  venv/bin/python scripts/payment_e2e_test.py
Prereq: a fresh user row exists (or use --user-id) so entitlement is observable.

Flow: create payment -> request (real gateway URL) -> [HUMAN pays with card]
      -> callback hits /payment/verify -> verify with gateway -> entitlement
      -> report. Prints each stage's proof.
"""
import asyncio, os, sys
sys.path.insert(0, "/root/chart-platform")

import httpx

BASE = os.getenv("ZAYCHE_BASE", "https://chart.negar.io")
MERCHANT = os.getenv("ZARINPAL_MERCHANT_ID", "")


async def main() -> None:
    print("ZAYCHE Payment E2E — REAL merchant test")
    print("=" * 60)
    if not MERCHANT:
        print("ABORT: ZARINPAL_MERCHANT_ID is empty — real merchant not configured yet.")
        return
    # 1) create a payment server-side (API must be reachable with an API key/token)
    #    Adjust to the project's actual payment-creation endpoint.
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE}/api/payments",
            json={"plan": "pro", "months": 1, "amount_toman": 100000,
                  "callback_url": f"{BASE}/payment/callback"},
            headers={"Authorization": "Bearer " + os.getenv("ZAYCHE_ADMIN_TOKEN", "")},
        )
        print("create payment:", r.status_code, r.text[:200])
        if r.status_code != 200:
            print("ABORT: payment creation failed")
            return
        pay = r.json()
    print("payment_id:", pay.get("payment_id"), "authority:", pay.get("authority"))
    # 2) request the gateway URL
    r2 = await c.post(f"{BASE}/api/payments/{pay['payment_id']}/request")
    print("request gateway:", r2.status_code, r2.text[:200])
    gw = r2.json().get("url", "")
    print("PAY AT (open in browser, use a real card):", gw)
    print("  waiting for human payment + callback ...")
    # 3) poll the payment status until done or timeout (5 min)
    for _ in range(60):
        await asyncio.sleep(5)
        r3 = await c.get(f"{BASE}/api/payments/{pay['payment_id']}")
        st = r3.json().get("status")
        print("  status:", st, flush=True)
        if st in ("paid", "verified", "active"):
            print("✅ PAYMENT VERIFIED — entitlement granted:", r3.json().get("entitlement"))
            break
        if st in ("failed", "cancelled"):
            print("❌ FAILED")
            break
    else:
        print("timeout waiting for payment")


if __name__ == "__main__":
    asyncio.run(main())