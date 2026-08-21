# AUDIT: End-to-End Purchase Flow — "Paid but Sees Free Summary"

**Dimension:** Post-payment rendered state correctness
**Scenario:** Anonymous visitor → buys plan → Zarinpal redirect → returns to site → sees free-chart summary instead of paid report
**Date:** 2025-01-XX
**Status:** ROOT CAUSES IDENTIFIED — NOT LAUNCH-ACCEPTED

---

## 1. Executive Summary

The reported bug — "visitor pays, returns, still sees the free summary" — has **multiple contributing root causes** spanning the payment verify handler, the session/auth gap for anonymous buyers, and the post-payment redirect target. The core issue is an **architectural gap**: the purchase flow creates an `Order` and a `Report` (status=`queued`), but the **return URL after Zarinpal payment always redirects to a generic page that has no mechanism to show the paid report to an unauthenticated user**. The free-chart page and the paid-report page are gated by different conditions, and the post-payment redirect does not bridge them.

---

## 2. Code Path Trace

### 2.1 Order Creation (`app/payment/orders.py`)

```
create_order() → lines 40-120
```

- `callback_url` is set at **line 107**:
  ```python
  callback_url = f"{public_base}/api/payments/verify"
  ```
- The order is created with `status="pending"`, `authority` from Zarinpal.
- **Critically**: for an anonymous visitor, `new_user_id` may be `None` (no OTP login required before purchase — "lazy OTP" per `app/auth.py` docstring line 3-6).

### 2.2 Payment Verification Handler

**⚠️ THE VERIFY HANDLER CODE IS NOT PROVIDED IN THE BUNDLE.**

The bundle includes `app/payment/orders.py` and `app/payment/zarinpal.py` but **does NOT include the route handler** that Zarinpal redirects to (`GET /api/payments/verify`). This handler would live in a file like `app/routes/payments.py` or similar.

This is the **single most critical file** for this bug and it is absent from the provided code. The `app/routes/wallet.py` mentioned in the task prompt is also not provided.

**What we CAN infer from the code we have:**

### 2.3 What Must Happen After Verify (and likely doesn't)

After Zarinpal redirects the user to `GET /api/payments/verify?Authority=XXX&Status=OK`, the handler must:

1. Look up the `Order` by `authority`
2. Call `ZarinpalClient().verify(authority, order.amount_rial)`
3. Set `order.status = "paid"`
4. Create a `Report(status="queued")` and set `order.report_id`
5. **Redirect the user to a page that shows the paid report**

The wallet-payment path (`pay_order_with_balance` at `app/payment/orders.py:410-450`) **does** create the report:

```python
# app/payment/orders.py:441-445
if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
    rep = Report(chart_id=order.chart_id, status="queued",
                 plan_key=order.plan_key)
    session.add(rep)
    session.flush()
    order.report_id = rep.id
```

But this is the **wallet path only**. The Zarinpal verify handler must do the same — and we cannot confirm it does because the code is missing.

---

## 3. Identified Root Causes

### RC-1: Anonymous User Has No Session — Post-Payment Redirect Cannot Identify the Buyer

**Severity: P0 — Primary root cause of the reported bug**

| Item | Detail |
|------|--------|
| **Evidence** | `app/auth.py:3-6` — "chart form stays anonymous; OTP only when user wants dashboard/purchase" |
| **Evidence** | `app/payment/orders.py:107` — callback URL is a bare `/api/payments/verify` with no user-identifying token |
| **Evidence** | `app/auth.py:67-78` — `get_current_user()` reads `chart_user` cookie, which is only set after OTP verify |

**The gap:** A visitor who never logged in (no OTP) has no `chart_user` cookie. When Zarinpal redirects them back to `/api/payments/verify?Authority=XXX&Status=OK`:

- The verify handler can find the `Order` by `authority` ✓
- The verify handler can mark it `paid` ✓
- But the **redirect after verification** goes to... what? The handler must redirect the user somewhere. Without a session cookie, the destination page cannot identify the user as the buyer.
- The `Chart.access_token` (`app/models.py:73-75`) exists precisely for this ("anonymous-ownership proof"), but there is no evidence the verify handler uses it in the redirect URL.

**Likely behavior:** The verify handler redirects to `/chart/{chart_id}` or `/report/{report_id}` — but the destination page checks `get_current_user()`, finds `None`, and falls back to the free summary view.

### RC-2: Report Status is `queued` at Redirect Time — No Content to Show

**Severity: P0 — Even if auth worked, the user sees nothing**

| Item | Detail |
|------|--------|
| **Evidence** | `app/payment/orders.py:441-443` — `Report(status="queued")` |
| **Evidence** | Report generation is async (worker-based, per `app/models.py:156` — "queued | running | done | failed") |

The report is created with `status="queued"`. The LLM generation happens asynchronously. When the user is redirected immediately after payment:

- The report has no `sections`, no `pdf_path`
- The report page must show a "generating..." state
- If the page instead checks `report.status == "done"` and falls back to the free summary when it's not, **the user sees the free summary**

### RC-3: No `access_token` Propagation Through Payment Flow

**Severity: P1 — Structural gap for anonymous ownership**

| Item | Detail |
|------|--------|
| **Evidence** | `app/models.py:73-75` — `Chart.access_token` field exists with comment "anonymous-ownership proof" |
| **Evidence** | `app/payment/orders.py:107` — callback URL has no `access_token` parameter |
| **Evidence** | `app/payment/orders.py:95-96` — order links to `chart_id` and `profile_id` but not `access_token` |

The `access_token` on `Chart` is designed to let anonymous users prove ownership. But:
- The Zarinpal callback URL doesn't include it
- The order doesn't store it
- After the redirect, the verify handler has no way to pass it to the frontend

### RC-4: `pay_order_with_balance` Creates Report but Zarinpal Path May Not

**Severity: P0 — Divergent post-payment behavior**

| Item | Detail |
|------|--------|
| **Evidence** | `app/payment/orders.py:430-445` — wallet path explicitly creates `Report` for `REPORT_PLANS` |
| **Evidence** | No equivalent code visible for the Zarinpal verify path |

The wallet path (`pay_order_with_balance`) has explicit handling for:
- `SUBSCRIPTION_PLANS` → `activate_subscription()` ✓
- `CREDIT_PACKS` → `grant_credits()` ✓  
- `REPORT_PLANS` → creates `Report(status="queued")` ✓

The Zarinpal verify handler **must mirror all of this**. Given the bug report, it likely doesn't — or does it partially.

---

## 4. Similar Flows Where Rendered End-State Diverges from Intent

### 4.1 Wallet Payment → Report Page (HTTP 200 ≠ correct view)

| File:Line | Issue |
|-----------|-------|
| `app/payment/orders.py:410-450` | `pay_order_with_balance` commits the order as `paid` and creates a queued report, then returns `True`. The **caller** must redirect to the right page. If the caller redirects to `/chart/{id}` without the report context, the user sees the free summary. |

### 4.2 Bot Payment Flow (Telegram/Bale)

| File:Line | Issue |
|-----------|-------|
| `app/payment/orders.py:107` | Same `callback_url` for bot-originated orders. A Telegram user who pays via web gateway returns to the browser, not the bot. The bot never learns the payment succeeded unless there's a webhook/polling mechanism (not shown). |
| `app/payment/orders.py:98-99` | `chat_id` and `platform` are set on the order, but the callback URL doesn't route back to the bot. |

### 4.3 Subscription Purchase → No Immediate Visible Change

| File:Line | Issue |
|-----------|-------|
| `app/payment/orders.py:130-160` | `activate_subscription` creates/extends a `Subscription` row. But if the post-payment redirect goes to the chart page, the user sees no indication that their subscription is active — the chart page likely doesn't check subscription status. |

### 4.4 Credit Pack Purchase → Credits Granted but User Doesn't Know

| File:Line | Issue |
|-----------|-------|
| `app/payment/orders.py:225-235` | `grant_credits` atomically adds credits. But the post-payment redirect must go to a page that shows the credit balance. If it goes to the chart page, the user sees no change. |

### 4.5 Synastry Plan → `secondary_chart_id` Ignored in Report Generation

| File:Line | Issue |
|-----------|-------|
| `app/models.py:199` | `Order.secondary_chart_id` exists for synastry |
| `app/payment/orders.py:441-445` | Report creation only uses `order.chart_id`, not `secondary_chart_id`. A synastry report would be generated as a single-chart report. |

### 4.6 Coupon Reservation Not Released on Zarinpal Timeout

| File:Line | Issue |
|-----------|-------|
| `app/payment/orders.py:80-88` | Coupon `used_count` is incremented atomically at order creation. If the user abandons payment (never completes at Zarinpal), the coupon slot is permanently consumed. |
| `app/payment/orders.py:117-120` | Release only happens on `ZarinpalError` during `client.request()`, not on user abandonment. |

**Mitigation needed:** A cron job to expire `pending` orders older than N hours and release their coupon reservations.

---

## 5. Security Findings in the Payment Path

### S-1: IDOR on Order Verification

| Severity | P1 |
|----------|-----|
| **Issue** | Zarinpal sends `Authority` as a query parameter. The verify handler looks up the order by `authority`. If the handler then redirects to `/report/{report_id}`, anyone who intercepts or guesses the authority can access the report. |
| **Evidence** | `app/payment/orders.py:106` — authority is a Zarinpal-generated string, not a secret. |
| **Mitigation** | The redirect must include `Chart.access_token` or set a session cookie. |

### S-2: No Replay Protection on Verify Endpoint

| Severity | P2 |
|----------|-----|
| **Issue** | Zarinpal's verify API returns code `101` for "already verified" (`app/payment/zarinpal.py:82`). If the verify handler treats `101` the same as `100` (success), a replayed callback could re-trigger side effects (report creation, referral reward, subscription activation). |
| **Evidence** | `app/payment/zarinpal.py:82` — `if code not in (100, 101)` — both are treated as success. |
| **Mitigation** | The verify handler must check `order.status != "pending"` before processing side effects. The wallet path does this (`app/payment/orders.py:413` — `if order.status != "pending": return False`). |

### S-3: Race Condition on Concurrent Verify Calls

| Severity | P1 |
|----------|-----|
| **Issue** | Two concurrent `GET /api/payments/verify?Authority=XXX` requests (browser refresh, network retry) could both find `order.status == "pending"` and both process the payment. |
| **Evidence** | No atomic CAS (`UPDATE ... WHERE status='pending'`) visible in the verify path (code not provided, but the wallet path at `app/payment/orders.py:413` uses a simple Python check, not an atomic DB operation). |
| **Mitigation** | Use `UPDATE orders SET status='paid' WHERE id=:id AND status='pending' RETURNING id` — same pattern as `resolve_withdrawal` at `app/payment/orders.py:360-370`. |

---

## 6. Missing Code — Audit Blockers

The following files are **referenced or implied** but not provided in the bundle. Without them, this audit cannot be marked complete:

| File | Why Critical |
|------|-------------|
| `app/routes/payments.py` (or wherever `GET /api/payments/verify` lives) | **THE** handler that processes the Zarinpal return. This is the epicenter of the bug. |
| `app/routes/wallet.py` | Mentioned in the task prompt. Wallet payment UI + balance display. |
| The chart/report page template/route | The destination after payment — determines what the user actually sees. |
| The free-chart summary page | To compare what the free vs. paid view renders. |
| Report generation worker | To understand the queued→done pipeline and whether the UI polls for completion. |

---

## 7. Acceptance Criteria (Checkable)

### For "Code-Complete" (the bug is fixed):

- [ ] **AC-1:** `GET /api/payments/verify` handler uses atomic CAS (`UPDATE orders SET status='paid' WHERE authority=:auth AND status='pending' RETURNING id`) — no double-processing.
- [ ] **AC-2:** After successful verify, the handler creates `Report(status="queued")` for `REPORT_PLANS`, calls `activate_subscription()` for `SUBSCRIPTION_PLANS`, calls `grant_credits()` for `CREDIT_PACKS` — **mirroring** `pay_order_with_balance` exactly.
- [ ] **AC-3:** The post-payment redirect URL includes `Chart.access_token` (e.g., `/chart/{chart_id}?token={access_token}&order={order_id}`) so the anonymous user can prove ownership.
- [ ] **AC-4:** The chart/report page, when given a valid `access_token` + `order_id` with `status=paid` and `report.status=queued`, shows a "report is generating" state — NOT the free summary.
- [ ] **AC-5:** The chart/report page, when given a valid `access_token` + `order_id` with `report.status=done`, shows the full paid report sections.
- [ ] **AC-6:** Coupon reservations for abandoned orders (pending > 2 hours) are released by a cron job.
- [ ] **AC-7:** `reward_referral()` is called in the Zarinpal verify path (same as wallet path at `app/payment/orders.py:449-453`).

### For "Launch-Accepted" (production-safe):

- [ ] **AC-8:** Integration test: anonymous user → create chart → create order → fake Zarinpal callback → verify handler → assert `order.status == "paid"` AND `report` exists AND redirect includes `access_token`.
- [ ] **AC-9:** Integration test: double-callback (same authority twice) → second call is a no-op (order already paid, no duplicate report/subscription/credits).
- [ ] **AC-10:** Integration test: wallet payment for each plan type (`basic`, `full`, `gold`, `monthly`, `yearly`, `credit3`) → assert correct side effects.
- [ ] **AC-11:** The verify handler is rate-limited (already covered by `app/security.py:167` — `pay:{ip}` scope, 20/min ✓).
- [ ] **AC-12:** Bot-originated orders: after web payment, the bot is notified (webhook or polling) so the user sees confirmation in-chat.
- [ ] **AC-13:** Synastry orders: `secondary_chart_id` is passed to the report generation worker.

---

## 8. Verdict

| Dimension | Status |
|-----------|--------|
| Payment creation (`create_order`) | **Correct** — atomic coupon reservation, referral guard, self-referral prevention all solid. |
| Zarinpal client (`zarinpal.py`) | **Correct** — request/verify/refund with structured errors. |
| Wallet payment (`pay_order_with_balance`) | **Correct** — atomic debit, all plan types handled (F-29 fix). |
| Post-payment verify handler | **CANNOT AUDIT — code not provided.** This is the bug location. |
| Post-payment redirect target | **LIKELY BROKEN** — no `access_token` propagation, no "generating" state. |
| Anonymous user ownership | **BROKEN** — `access_token` exists in the model but is not threaded through the payment flow. |
| Referral reward in Zarinpal path | **UNKNOWN** — depends on verify handler code. |
| Coupon leak on abandonment | **CONFIRMED BUG** — no cleanup mechanism. |

**Overall: NOT LAUNCH-ACCEPTED.** The verify handler and post-payment redirect are the critical path, and the architectural gap (anonymous user → paid report) is a design-level issue that requires explicit `access_token` threading, not just a bug fix.