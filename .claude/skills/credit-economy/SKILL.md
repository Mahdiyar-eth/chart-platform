---
name: credit-economy
description: Hard invariants of the credit economy (unit-of-money = credit). Follow for any change to explore/report/synastry/transit/chat gating, credits, or balances.
---

# Credit Economy (invariant rules)

1. **Unit of money = credit.** Anchor: 1 credit ≈ 50,000 تُمن. Existing تُمن prices do NOT change — the counting unit unifies.
2. Credits **never expire** (existing UI promise — do not break).
3. Spending is **atomic**: `UPDATE ... SET credits = credits - cost WHERE id = ? AND credits >= cost RETURNING ...` (pattern: `app/explore/service.py:218`).
4. If LLM generation fails → **auto-refund** the credit + a ledger row with `reason='refund'`.
5. Every credit movement is a row in `credit_transactions`. **Accounting invariant:** `sum(amount) == users.credits` per user — MUST have a test.
6. Credits belong to the **user**, not a chart. One user may spend across many charts.
7. Buying credits requires a **user account (OTP)**. A free chart stays account-less.
8. Backward compat: every old paid `Order` keeps its entitlement — **no existing user loses anything**.
9. If a task needs a real external key (Zarinpal merchant, Kavenegar SMS, FCM) → mark **BLOCKED** and ask the owner; never invent.
