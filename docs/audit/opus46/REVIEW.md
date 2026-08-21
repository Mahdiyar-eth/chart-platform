# REVIEW.md — ZAYCHE Platform Synthesis Review

**Reviewer:** Antigravity (Architect / Auditor / Reviewer)
**Date:** 2025-07-14
**Baseline:** Commit `fef0d6e`
**Target:** `chart.negar.io`
**Scope:** MASTER_PLAN + Purchase/Return Bug Audit + UI/UX Glassmorphism Audit + Monetization/Gamification Audit + Astrology Services Audit

---

## 1. STATUS

**CHANGES_REQUIRED** — Multiple P0 bugs in the payment verification path, dead-code features that represent >40% of the product's value proposition, and user-facing `prompt()`/`confirm()`/`alert()` calls that break mobile UX. The codebase is architecturally sound but has critical wiring gaps and a missing verify handler that is the epicenter of the revenue-blocking bug.

---

## 2. FINDINGS

### CRITICAL

| ID | File:Line | Evidence | Required Fix |
|----|-----------|----------|--------------|
| C-01 | `app/routes/payments.py` (FILE MISSING) | `app/payment/orders.py:107` sets `callback_url = f"{public_base}/api/payments/verify"` — the handler for this route is not in the provided codebase. This is the primary root cause of "paid but sees free summary." | Locate or create the `GET /api/payments/verify` handler. It must: (a) atomic CAS `UPDATE orders SET status='paid' WHERE authority=:auth AND status='pending'`, (b) mirror all side-effects from `pay_order_with_balance` (Report creation for REPORT_PLANS, `activate_subscription` for SUBSCRIPTION_PLANS, `grant_credits` for CREDIT_PACKS, `reward_referral`), (c) redirect with `Chart.access_token` in URL. |
| C-02 | `app/payment/orders.py:107` + `app/models.py:73-75` | `callback_url` has no `access_token` parameter. `Chart.access_token` exists (model comment: "anonymous-ownership proof") but is never threaded through the payment flow. Anonymous buyers return from Zarinpal with no session, no cookie, no ownership proof. | Post-payment redirect URL must include `access_token`: `/chart/{chart_id}?token={access_token}&order={order_id}`. Destination page must accept `token` param and grant view access without requiring OTP login. |
| C-03 | `app/payment/orders.py:441-445` vs verify handler | Wallet path creates `Report(status="queued")` for `REPORT_PLANS`, calls `activate_subscription()`, calls `grant_credits()`, calls `reward_referral()`. The Zarinpal verify handler must mirror ALL of these. Evidence of divergence: the bug exists (users pay but see free summary), implying the verify handler either doesn't create the Report or doesn't redirect correctly. | Verify handler must have identical post-payment logic to `pay_order_with_balance` lines 430-453. Extract shared function `fulfill_order(order, session)` called by both paths. |
| C-04 | `app/report/claim_validation.py` (entire file) | `validate_advanced()` and `validate_section()` are never imported or called by `worker.py` or `qa.py`. This is the most thorough hallucination gate (house-mismatch, degree-mismatch, aspect-mismatch, retrograde-mismatch detection) and it is dead code. `grep -rn "claim_validation" app/report/worker.py app/report/qa.py` returns 0 matches. | Wire `validate_advanced(domain, section_text, chart)` into the QA loop in `worker.py` after `parse_section()` succeeds. Any `critical_hallucination == True` must trigger a retry. |
| C-05 | `app/payment/orders.py:80-88` + no cleanup job | Coupon `used_count` is incremented atomically at order creation. If user abandons payment at Zarinpal (never completes), the coupon slot is permanently consumed. No cron/scheduled job releases stale `pending` orders. | Create a scheduled job: `UPDATE orders SET status='expired' WHERE status='pending' AND created_at < NOW() - INTERVAL '2 hours'`. On expiry, decrement coupon `used_count` if coupon was applied. |
| C-06 | `app/payment/zarinpal.py:82` | `if code not in (100, 101)` — both 100 (success) and 101 (already verified) are treated as success. If the verify handler doesn't check `order.status != 'pending'` before processing side effects, a replayed callback re-triggers report creation, subscription activation, or credit grants. | Verify handler must check `order.status == 'pending'` before processing. Use atomic CAS: `UPDATE orders SET status='paid' WHERE id=:id AND status='pending' RETURNING id` — if 0 rows affected, return early (idempotent). |

### HIGH

| ID | File:Line | Evidence | Required Fix |
|----|-----------|----------|--------------|
| H-01 | `account.html:~270` | `const v = prompt('مبلغ تسویه…')` — `prompt()` is invisible on iOS WebView, breaks PWA, violates mobile-first design rules. | Replace with Alpine.js modal with `<input type="number">` (full spec in UI/UX audit §account.html). |
| H-02 | `account.html:~276` | `alert(r.ok ? 'درخواست تسویه…' : …)` — `alert()` blocks UI thread, no styling control, breaks glass aesthetic. | Replace with inline toast/snackbar component. |
| H-03 | `admin.html:~95` | `if (!confirm('حذف مقاله؟…')) return;` — `confirm()` in CMS delete. Admin is internal but still runs on mobile tablets. | Replace with two-step inline pattern (the `regenOrder` function in the same file already demonstrates this pattern). |
| H-04 | `admin.html:~100,107,115,…` | At least 12 instances of `alert()` across admin.html. | Replace all with a reusable `.admin-toast` component (CSS spec in UI/UX audit §admin.html). |
| H-05 | `app/astrology/synastry.py` (entire file) | Complete synastry computation (cross-chart aspects, 4-domain compatibility score, verdict) with zero API endpoint, zero UI page, zero route import. `grep -rn "synastry" app/routes/` returns 0 matches. | Create `POST /api/synastry` endpoint with IDOR check (both charts must belong to authenticated user), rate limit (≤10/day/user), and UI page. |
| H-06 | `app/astrology/rectify.py` (entire file) | Complete birth-time rectification (20-min step scan, event scoring, top-3 candidates) with zero API endpoint, zero UI flow. | Create `POST /api/rectify` endpoint, run in ARQ worker (CPU-intensive: 72 charts per call), rate limit ≤5/day/user, 30s timeout, UI wizard. |
| H-07 | `app/astrology/transits.py` + `app/report/renderer.py:127` | `upcoming_transits()` is only surfaced in Gold PDF and weekly delivery. No standalone `/api/charts/{id}/transits` endpoint. No personal transit page. Transit data is rich but invisible to non-Gold users. | Create `GET /api/charts/{id}/transits?days=90` with auth + ownership check + `days` capped at 365. Create transit timeline UI page. |
| H-08 | `app/payment/orders.py:413` | Wallet path uses Python-level check `if order.status != "pending": return False` — not an atomic DB operation. Two concurrent wallet-pay requests could both pass this check. | Use atomic CAS: `UPDATE orders SET status='paid' WHERE id=:id AND status='pending' RETURNING id`. Same pattern as `resolve_withdrawal` at line ~360-370. |
| H-09 | `base.html:~230-237` | Bottom nav has 6 items + FAB = 7 total flex children in `max-width:420px`. On 320px screens (iPhone SE) this wraps or clips. | Reduce to 4 items + FAB (5 total). Move "بازبینی ساعت" and "داشبورد" to drawer only. |
| H-10 | `app/db.py:seed_plans()` lines 32-67 | `CREDIT_PACKS = {"credit3", "credit6", "credit12"}` defined in `orders.py:171` but NO credit pack plans are seeded. `grant_credits()` is dead code. Any credit-pack purchase attempt raises `LookupError("plan not found")`. | Either seed credit pack plans with `credits_grant > 0`, or remove `CREDIT_PACKS` and `grant_credits()` if product decision is credit-via-subscription-only. |
| H-11 | `app/models.py:~195` | `Plan.credits_grant` has `server_default="0"` and is never set in any seeded plan. Even subscription plans grant credits via a separate function, not via this field. The field is unused. | Set `credits_grant` on every plan in `seed_plans()`, or remove the field if credits are granted via separate logic. |
| H-12 | `app/payment/orders.py:441-445` | Report creation uses `order.chart_id` only. `Order.secondary_chart_id` (for synastry, `models.py:199`) is ignored. A synastry order would generate a single-chart report. | Pass `secondary_chart_id` to report generation worker when `plan_key == "synastry"`. |

### MEDIUM

| ID | File:Line | Evidence | Required Fix |
|----|-----------|----------|--------------|
| M-01 | `app/astrology/transits.py:10` | `swe.set_ephe_path("ephe")` — relative path. Compare `engine.py:27`: `EPHE_PATH = os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")`. If worker CWD ≠ project root, ephemeris lookup fails silently to analytical mode. | Use `os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")` consistently. |
| M-02 | `app/astrology/transits.py:11`, `engine.py:40`, `sky.py:19` | `swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)` called at module level in 3 files. `engine.py:38-39` warns this is global state. Currently safe (all LAHIRI) but a maintenance trap. | Single `swe.set_sid_mode()` call in one init module; others import from there. Or document that all three MUST stay identical. |
| M-03 | `app/astrology/sky.py:83-95` | `_SIGN_BARE`, `_ELEMENT`, `_MODALITY` duplicate `big_three.py:SIGNS_FA`, `ELEMENTS`, `MODALITIES` and `engine.py:SIGNS_FA`. Sign name change requires 3+ file edits. | Import from `big_three.py` or create shared `constants.py`. |
| M-04 | `base.html:~130` | `.drawer` uses `transform:translateX(-105%)` — in RTL context, some browsers (Safari) may slide the wrong direction. | Test on RTL Safari. Use `inset-inline-end:0; transform:translateX(calc(var(--dir-mult, 1) * -105%))` or verify behavior. |
| M-05 | `base.html:~160` | Footer `.footer-col a` has `padding:5px 0` = ~25px tall touch target. | Add `min-height:44px; display:flex; align-items:center;` to footer links. |
| M-06 | `account.html:~88-96` | Checkbox inputs `style="width:18px;height:18px;"` — below 44px touch target. | Wrap in `<label>` with `min-height:44px` or use custom toggle switches. |
| M-07 | `account.html:~99-100` | Quiet hours inputs `style="width:70px;"` — hard to tap on mobile. | Increase to `min-width:80px; min-height:44px;`. |
| M-08 | `account.html:~55` | PDF download button `style="font-size:.8rem; padding:6px 14px;"` — below 44px. | Add `min-height:44px; display:inline-flex; align-items:center;`. |
| M-09 | `admin.html:~multiple` | Admin action buttons have `padding:2px 7px` — ~24px tall. | Increase to `min-height:36px; padding:6px 12px;` (admin exception from 44px). |
| M-10 | `article.html:9` | Back link "→ همهی مقالات" is plain text, ~16px tall, no touch target. | Wrap in chip with `min-height:44px; display:inline-flex; align-items:center;`. |
| M-11 | `chart.html:12-14` | Funnel progress pills `padding:6px 12px` — ~28px tall. | Add `min-height:44px; display:inline-flex; align-items:center;`. |
| M-12 | `chat.html:22` | Preset question buttons `min-height:38px` — below 44px. | Change to `min-height:44px`. |
| M-13 | `help_tip.html:2` | Trigger button `width:18px; height:18px;` — well below 44px. | Increase to `width:28px; height:28px;` with 44px tap area via padding on wrapper. |
| M-14 | `app/report/generator.py` (entire file) | Dead code. Uses `asyncio.run()` inside sync function. Production uses `worker.py`. No route imports it. | Delete or mark `# DEPRECATED — use worker.py`. Ensure no import path reaches it. |
| M-15 | `app/payment/orders.py:98-99` + `:107` | Bot-originated orders set `chat_id` and `platform` but `callback_url` redirects to browser, not bot. Telegram user pays via web, returns to browser — bot never learns payment succeeded. | After verify, if `order.platform` is set, send confirmation to bot via webhook/API call. |
| M-16 | `base.html:14,19` and `base.html:20,24` | Duplicate `og:type` and `theme-color` meta tags. | Remove duplicates. |
| M-17 | `app/astrology/transits.py:upcoming_transits()` | `days` parameter is unbounded. Called with `days=7` (weekly) and `days=120` (renderer) but an API endpoint could pass `days=3650` causing 3650 ephemeris iterations. | Cap at 365: `days = min(days, 365)` in function body + API validation. |

### LOW

| ID | File:Line | Evidence | Required Fix |
|----|-----------|----------|--------------|
| L-01 | `article.html:27` | `class="btn-lg"` without `.btn` — missing gradient background. | Change to `class="btn btn-lg"`. |
| L-02 | `articles_index.html:~38` | Same: `class="btn-lg"` without `.btn`. | Change to `class="btn btn-lg"`. |
| L-03 | `faq.html:24` | Same: `class="btn-lg"` without `.btn`. | Change to `class="btn btn-lg"`. |
| L-04 | `page.html:17` | Same: `class="btn-lg"` without `.btn`. | Change to `class="btn btn-lg"`. |
| L-05 | `account.html:~186` | `navigator.clipboard.writeText()` without try/catch fallback. Fails silently on older browsers. | Add try/catch with `document.execCommand('copy')` fallback + visual feedback. |
| L-06 | `chat.html:26` | `max-height:58vh` — on short phones with bottom nav + keyboard, input may be hidden. | Use `max-height:calc(100dvh - 280px)` or hide bottom nav on chat page via `body.chat-active .bottomnav { display: none; }`. |
| L-07 | `admin.html:~80,88` | `id="cms-body"` used for both container div AND textarea — DOM collision. | Rename textarea to `id="cms-body-text"`. |
| L-08 | `faq.html:13` | `<details><summary>` has no explicit `min-height` — borderline at ~42px. | Add `min-height:48px; display:flex; align-items:center;` to summary. |
| L-09 | `dashboard.html:47` | "حساب و تنظیمات" link is plain text ~16px tall. | Wrap in `min-height:44px` inline-flex. |
| L-10 | `form.html:~70` | City search results have no `max-height` — many cities can overflow viewport. | Add `max-height:200px; overflow-y:auto;` to results container. |
| L-11 | `index.html:~52` | PDF download link ~20px tall. | Add `min-height:44px; display:inline-flex; align-items:center;`. |
| L-12 | `explore.html:~72` | Evidence chips use `.chip` class (implies interactivity) but are display-only. | Remove `.chip` class or use `<span>`. |

---

## 3. REQUIRED_FIXES (Ordered)

### Phase 0 — Revenue-Blocking Bug (1-2 days)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-01 | Locate or create `GET /api/payments/verify` handler with atomic CAS, full side-effect mirroring, and `access_token` redirect | C-01, C-02, C-03, C-06 |
| RF-02 | Extract `fulfill_order(order, session)` shared function from `pay_order_with_balance` — call from both wallet and Zarinpal paths | C-03, H-12 |
| RF-03 | Add atomic CAS to wallet payment path (`UPDATE ... WHERE status='pending' RETURNING id`) | H-08 |
| RF-04 | Create scheduled job to expire stale `pending` orders (>2h) and release coupon reservations | C-05 |
| RF-05 | Ensure chart/report page accepts `?token=` param and shows "generating…" state when `report.status == 'queued'` | C-02 |

### Phase 0.5 — Hallucination Gate (0.5 days)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-06 | Wire `claim_validation.validate_advanced()` into `worker.py` QA loop | C-04 |

### Phase 1 — Mobile UX Blockers (2-3 days)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-07 | Replace `prompt()` in account.html with Alpine modal | H-01 |
| RF-08 | Replace all `alert()` in account.html with toast component | H-02 |
| RF-09 | Replace `confirm()` in admin.html with two-step inline | H-03 |
| RF-10 | Replace all `alert()` in admin.html with `.admin-toast` | H-04 |
| RF-11 | Reduce bottom nav to 4 items + FAB | H-09 |
| RF-12 | Fix all touch targets < 44px (M-06 through M-13) | M-06–M-13 |
| RF-13 | Remove duplicate meta tags | M-16 |

### Phase 2 — Wire Dead Features (1-2 weeks)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-14 | Create `POST /api/synastry` endpoint + IDOR check + rate limit + UI page | H-05 |
| RF-15 | Create `POST /api/rectify` endpoint + ARQ worker + rate limit + UI wizard | H-06 |
| RF-16 | Create `GET /api/charts/{id}/transits` endpoint + UI page + day cap | H-07, M-17 |
| RF-17 | Create `GET /api/charts/{id}/sky-today` personal daily sky endpoint + dashboard card | (F-05 from services audit) |

### Phase 3 — Monetization Cleanup (3-5 days)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-18 | Seed credit pack plans OR remove dead `CREDIT_PACKS` code | H-10 |
| RF-19 | Set `credits_grant` on all plans in `seed_plans()` OR remove unused field | H-11 |
| RF-20 | Pass `secondary_chart_id` to report worker for synastry orders | H-12 |
| RF-21 | Bot payment notification after web verify | M-15 |

### Phase 4 — Code Hygiene (1 day)

| # | Action | Findings Addressed |
|---|--------|--------------------|
| RF-22 | Fix `transits.py` ephemeris path to use env var | M-01 |
| RF-23 | Consolidate `swe.set_sid_mode()` to single init | M-02 |
| RF-24 | Deduplicate sign/element/modality constants | M-03 |
| RF-25 | Delete or deprecate `generator.py` | M-14 |
| RF-26 | Fix all `.btn-lg` without `.btn` (4 instances) | L-01–L-04 |

---

## 4. ACCEPTANCE_CRITERIA

### Phase 0 — Purchase/Return Bug

| ID | Criterion | Code-Complete Gate | Launch-Accepted Gate |
|----|-----------|-------------------|---------------------|
| AC-01 | `GET /api/payments/verify` handler exists and uses `UPDATE orders SET status='paid' WHERE authority=:auth AND status='pending' RETURNING id` | Handler file exists; `grep -n "WHERE.*status.*pending.*RETURNING" app/routes/payments.py` returns match | Integration test: double-callback with same authority → second call is no-op (0 rows affected, no duplicate Report/Subscription/Credits) |
| AC-02 | Post-payment redirect includes `access_token` in URL | `grep -n "access_token" app/routes/payments.py` returns match in redirect URL construction | Manual test: anonymous user → pay via Zarinpal sandbox → redirected to chart page → sees "generating…" or paid report (not free summary) |
| AC-03 | `fulfill_order()` shared function exists, called by both wallet and Zarinpal paths | Function exists in `orders.py`; both `pay_order_with_balance` and verify handler import it | Unit test: `fulfill_order` with each plan type (`basic`, `full`, `gold`, `synastry`, `monthly`, `yearly`, `credit*`) → correct side effects |
| AC-04 | Stale order cleanup job exists | Scheduled job file exists; `grep -n "pending.*2 hours\|INTERVAL" app/` returns match | Manual test: create order, wait 2h (or mock time), verify `status='expired'` and coupon `used_count` decremented |
| AC-05 | Chart/report page shows "generating…" when `report.status == 'queued'` | Template contains conditional on `report.status` | Manual test: pay → immediate redirect → see loading/generating state → poll/refresh → see full report |
| AC-06 | Wallet payment uses atomic CAS | `grep -n "WHERE.*status.*pending.*RETURNING" app/payment/orders.py` returns match in `pay_order_with_balance` | Unit test: concurrent wallet-pay simulation → only one succeeds |

### Phase 0.5 — Hallucination Gate

| ID | Criterion | Code-Complete Gate | Launch-Accepted Gate |
|----|-----------|-------------------|---------------------|
| AC-07 | `validate_advanced()` called in QA loop | `grep -n "validate_advanced\|claim_validation" app/report/worker.py` returns match | Unit test: golden chart with known Mercury-in-Virgo, inject "Mercury in Leo" in section text → `critical_hallucination == True` → retry triggered |

### Phase 1 — Mobile UX

| ID | Criterion | Code-Complete Gate | Launch-Accepted Gate |
|----|-----------|-------------------|---------------------|
| AC-08 | Zero `prompt()`, `confirm()`, `alert()` in user-facing templates | `grep -rn "prompt(\|confirm(\|alert(" app/templates/ --include="*.html"` returns 0 matches (excluding admin if admin is internal-only) | N/A |
| AC-09 | All interactive elements ≥ 44px on mobile (36px for admin) | CSS inspection of all `.btn`, `.chip`, `input`, `a`, `button` elements | Hermes: Chrome DevTools audit on 375px viewport — tap every interactive element, verify highlight area ≥ 44×44px |
| AC-10 | Bottom nav ≤ 5 items (including FAB) | `grep -c "bn-item\|bn-fab" app/templates/base.html` returns ≤ 5 | Hermes: test on 320px viewport — no wrapping or clipping |
| AC-11 | No horizontal scroll on any page at 320px | N/A | Hermes: test every page at 320px viewport width |

### Phase 2 — Dead Features Wired

| ID | Criterion | Code-Complete Gate | Launch-Accepted Gate |
|----|-----------|-------------------|---------------------|
| AC-12 | `POST /api/synastry` returns compatibility data for two charts | Endpoint exists; unit test with two golden charts returns scores | Hermes: create two charts, request synastry, verify UI shows connections + scores + verdict |
| AC-13 | Synastry endpoint rejects if either chart doesn't belong to user (IDOR) | Unit test: user A's chart + user B's chart → 403 | N/A |
| AC-14 | `POST /api/rectify` returns top-3 candidate times | Endpoint exists; unit test with known birth data + events | Hermes: enter birth data + life events → verify candidates are astronomically plausible |
| AC-15 | `GET /api/charts/{id}/transits` returns personal transit events with `days` capped at 365 | Endpoint exists; unit test with `days=500` → capped to 365 | Hermes: view transit page, verify events match current planetary positions |
| AC-16 | Transit events include `explanation_fa` field (≥2 sentences) | Unit test: response contains `explanation_fa` with `len > 50` | Hermes: read explanations, verify they reference the user's natal placements |

### Phase 3 — Monetization

| ID | Criterion | Code-Complete Gate | Launch-Accepted Gate |
|----|-----------|-------------------|---------------------|
| AC-17 | Credit pack plans exist in DB after `seed_plans()` | `alembic upgrade head` + `seed_plans()` → query `SELECT * FROM plans WHERE key LIKE 'credit%'` returns rows with `credits_grant > 0` | Manual test: purchase credit pack → user credits increase |
| AC-18 | Synastry orders pass `secondary_chart_id` to report worker | Code inspection: `fulfill_order` passes `secondary_chart_id` when `plan_key == 'synastry'` | Manual test: synastry report references both charts |

---

## 5. APPROVAL

### Verdict: **NOT APPROVED — CHANGES_REQUIRED**

### Evidence Summary

| Gate | Status | Evidence |
|------|--------|----------|
| Revenue flow works end-to-end | ❌ FAIL | Verify handler missing (C-01); anonymous user has no ownership proof after payment (C-02); report shows free summary instead of paid content |
| Payment idempotency | ❌ FAIL | No atomic CAS in verify path (C-06); wallet path uses Python-level check not DB-level (H-08) |
| Coupon integrity | ❌ FAIL | Abandoned orders permanently consume coupon slots (C-05) |
| Hallucination prevention | ❌ FAIL | Most thorough validator (`claim_validation.py`) is dead code (C-04) |
| Mobile UX | ❌ FAIL | `prompt()`, `confirm()`, `alert()` in user-facing flows (H-01–H-04); 13 touch targets below 44px |
| Core product services wired | ❌ FAIL | Synastry, rectification, personal transits — all implemented, none accessible to users (H-05–H-07) |
| Monetization model coherent | ⚠️ PARTIAL | Credit packs are dead code (H-10); `credits_grant` never set (H-11); three overlapping value-exchange mechanisms confuse users |
| Astrology engine accuracy | ✅ PASS | 14 golden charts, DST edge cases, proper timezone handling, sidereal support |
| Atomic balance operations | ✅ PASS | `UPDATE ... WHERE balance >= amount` pattern is race-safe for credits/wallet |
| Referral cycle detection | ✅ PASS | 8-hop chain walk with cycle detection + self-referral guard |
| Subscription renewal | ✅ PASS | `max(current_expiry, now) + days` preserves prepaid time |
| Coupon atomic reservation | ✅ PASS | `UPDATE ... WHERE used_count < max_uses RETURNING id` |
| QA pipeline (basic) | ✅ PASS | Forbidden patterns, evidence grounding, cross-section repetition check |
| RTL foundation | ✅ PASS | `<html lang="fa" dir="rtl">`, logical properties in base |
| Glassmorphism design system | ✅ PASS | Cohesive `--glass`, `backdrop-filter`, aurora, starfield, gold accent |
| Weekly transit delivery | ✅ PASS | Deduplication, web-only handling, push notification |
| Unknown birth time handling | ✅ PASS | Consistent across engine, prompts, SVG, big_three |

### Gates Not Met

1. **Revenue gate** — Users cannot complete purchases and see paid content (C-01, C-02, C-03)
2. **Safety gate** — LLM hallucinations pass unchecked to users (C-04)
3. **Mobile UX gate** — Native dialogs break PWA experience (H-01–H-04)
4. **Product completeness gate** — 3 of 5 highest-value services are dead code (H-05–H-07)

---

## 6. TRUTH-NOTES — What I Could NOT Verify

| # | Item | Why Unverifiable | Impact on Review |
|---|------|-----------------|------------------|
| TN-01 | The actual `GET /api/payments/verify` handler code | File not provided in the code bundle. All C-01/C-02/C-03 findings are inferred from the bug report + surrounding code. The handler may exist and partially work — I cannot confirm. | If the handler exists and already does atomic CAS + access_token redirect, C-01/C-02 may be partially resolved. C-03 (side-effect mirroring) remains likely broken given the reported bug. |
| TN-02 | The chart/report page template/route | Not provided. I cannot confirm whether it checks `report.status` and shows a "generating…" state vs. falling back to free summary. | AC-05 cannot be verified from code alone. |
| TN-03 | CORS configuration | `app/core/config.py` or main app setup not provided. Cannot verify `allow_origins` is `["https://chart.negar.io"]` vs `["*"]`. | Security risk if `*`. |
| TN-04 | Rate limiting implementation | Referenced in MASTER_PLAN §8.1 but `app/middleware/` or `slowapi` config not provided. `app/security.py:167` mentioned in purchase audit as having `pay:{ip}` scope, 20/min — but file not in bundle. | Cannot confirm rate limits exist on LLM, purchase, or auth endpoints. |
| TN-05 | Service worker (`sw.js`) and `manifest.json` | Not provided. Cannot verify PWA installability, offline behavior, or cache strategy. | P1-AC6 (PWA installable) cannot be verified. |
| TN-06 | `docs/ROUTING.md` | Referenced as "single source of truth" for LLM routing but not provided. Cannot verify that `llm_gateway.py` or `worker.py` routing matches it. | LLM model routing compliance is unverifiable. |
| TN-07 | Lighthouse scores | Requires runtime. Cannot estimate from code alone. | P1-AC5 deferred to Hermes. |
| TN-08 | Ephemeris accuracy vs astro.com | Requires runtime comparison. Golden charts test internal consistency, not external accuracy. | P3-AC2 deferred to Hermes. |
| TN-09 | LLM output quality in Persian | Requires runtime with real prompts. Prompt templates look well-structured but output quality depends on model behavior. | Deferred to Hermes. |
| TN-10 | SQL injection surface | `grep -r "text(" app/` not run (no codebase access). Cannot confirm all queries use parameterized statements. | Security risk if raw SQL with f-strings exists. |
| TN-11 | XSS via `| safe` filter | `grep -r "| safe" app/templates/` not run. Cannot confirm no user-generated content is marked safe. | Security risk if user input is rendered unescaped. |
| TN-12 | `.env` in `.gitignore` | Cannot verify secrets are not committed. | Security risk if API keys are in version control. |

---

## 7. NEW-FEATURES LIST + PRICING/GAMIFICATION RECOMMENDATION

### 7.1 New Features — Priority-Ordered

#### Tier 1: Wire Existing Code (highest ROI — zero new computation needed)

| # | Feature | Code Status | Effort | User Value |
|---|---------|-------------|--------|------------|
| NF-01 | **Synastry / Compatibility Page** | `synastry.py` complete | 12h (API + UI) | Very High — relationship compatibility is #1 requested feature in astrology apps |
| NF-02 | **Birth Time Rectification Wizard** | `rectify.py` complete | 12h (API + ARQ + UI) | High — unique differentiator, no Persian competitor offers this |
| NF-03 | **Personal Transit Timeline Page** | `transits.py` complete | 15h (API + explanations + UI) | Very High — "what's coming for ME" is core engagement driver |
| NF-04 | **Personal Daily Sky Card** | `sky.py` + `transits.py` exist | 10h (merge function + API + dashboard card) | High — daily engagement hook |
| NF-05 | **Advanced Claim Validation in Pipeline** | `claim_validation.py` complete | 2h (wire into worker) | Critical — quality gate |

#### Tier 2: New Computation + LLM Integration

| # | Feature | Effort | User Value |
|---|---------|--------|------------|
| NF-06 | **Synastry LLM Report** (human-readable compatibility narrative + PDF) | 14h | Very High |
| NF-07 | **Transit Push Notifications** (when major transit enters orb) | 8h | High — re-engagement |
| NF-08 | **Transit Explanations** (LLM-enriched, cached per transit-key) | 14h | High |
| NF-09 | **Solar Return Chart** (annual chart for birthday) | 14h | Medium-High |
| NF-10 | **Annual Profections** (which house is activated this year — deterministic) | 7h | Medium |

#### Tier 3: Advanced Astrology Services

| # | Feature | Effort | User Value |
|---|---------|--------|------------|
| NF-11 | **Secondary Progressions** | 16h | Medium |
| NF-12 | **Lunar Return** (monthly emotional cycle) | 10h | Medium |
| NF-13 | **Void-of-Course Moon Tracking** | 4h | Low-Medium |
| NF-14 | **Composite Chart** (midpoint method for relationships) | 10h | Medium |
| NF-15 | **Electional Astrology** (best time to start something) | 16h | Medium |
| NF-16 | **Horary Chart** (chart for a specific question moment) | 12h | Low-Medium |

### 7.2 Pricing Recommendation: Credit-Centric Hybrid Model

**Rationale:** The current model has three overlapping value-exchange mechanisms (one-off reports, dead credit packs, subscriptions) with unclear user-facing boundaries. A unified credit currency eliminates confusion while serving both casual buyers (event-driven: birth, marriage, Nowruz) and committed users (daily engagement).

#### Pricing Table

| Plan Key | Name (FA) | Price (Toman) | Credits Granted | Primary Use |
|----------|-----------|---------------|-----------------|-------------|
| `starter` | شروع | 0 (free) | 3 | 1 basic report preview + 2 explorations |
| `basic` | گزارش پایه | 149,000 | 15 | Basic report (costs 10) + 5 leftover |
| `full` | گزارش کامل | 349,000 | 40 | Full report (costs 30) + 10 leftover |
| `gold` | گزارش طلایی | 699,000 | 90 | Gold report (costs 50) + 40 for chat/explore |
| `synastry` | سیناستری | 499,000 | 50 | Synastry report (costs 40) + 10 leftover |
| `credit10` | ۱۰ اعتبار | 99,000 | 10 | Pure top-up |
| `credit30` | ۳۰ اعتبار | 249,000 | 30 | 17% bonus vs credit10 |
| `credit60` | ۶۰ اعتبار | 449,000 | 60 | 33% bonus |
| `monthly` | همراه ماهانه | 99,000/mo | 20/month | Daily insight + weekly reflection + transit alerts |
| `yearly` | همراه سالانه | 890,000/yr | 25/month | Same + 2 months free + priority queue |

#### Credit Costs

| Action | Credits | Rationale |
|--------|---------|-----------|
| Basic report | 10 | ~15k toman per section |
| Full report | 30 | 13 sections, heavier LLM |
| Gold report | 50 | 13 sections + chat + transit |
| Synastry report | 40 | Two charts, complex analysis |
| Exploration card | 1 | Impulse-friendly |
| AI chat question | 1 | Fair metering |
| Rectification | 5 | CPU-intensive |
| Transit page (30-day) | 0 (paid users) / 3 (free) | Engagement driver for subscribers |
| Daily reflection | 0 | Free — engagement driver |

### 7.3 Gamification Recommendation

#### Onboarding Credits (Replace `free_exploration_used` flag)

| Trigger | Credits | Implementation |
|---------|---------|----------------|
| Account creation | 3 | `CreditTransaction(reason="signup_gift")` |
| Complete birth profile | 2 | `CreditTransaction(reason="profile_complete")` |
| First share (OG card) | 1 | `CreditTransaction(reason="first_share")` |
| **Total free** | **6** | Enough for 1 basic report preview + explorations |

#### Streak System (Leverage existing `DailyReflection` with `UniqueConstraint("chart_id", "day_local")`)

| Streak | Reward | Badge (FA) |
|--------|--------|------------|
| 3 days | 1 credit | — |
| 7 days | 3 credits | هفتهی درخشان |
| 30 days | 10 credits | ماه کامل |
| 90 days | 30 credits | فصل ستارگان |

#### Loyalty Tiers (Computed from `SUM(credits purchased)`, no new table)

| Lifetime Credits | Tier | Benefit |
|-----------------|------|---------|
| 0–49 | ستاره (Star) | Base pricing |
| 50–149 | ماه (Moon) | 5% bonus credits |
| 150–499 | خورشید (Sun) | 10% bonus + priority queue |
| 500+ | کهکشان (Galaxy) | 15% bonus + early access |

#### Enhanced Referral

| Event | Referrer Gets | Referred Gets |
|-------|--------------|---------------|
| Signup | 2 credits | 3 credits (signup gift) |
| First paid order | 10% rial + 3 credits | 1 credit (existing) |
| 5 successful referrals | "سفیر زایچه" badge + 10 credits | — |
| 20 referrals | 15% commission (up from 10%) | — |

#### Seasonal Events

| Event | Mechanic | Frequency |
|-------|----------|-----------|
| Nowruz (نوروز) | Double credits on purchases for 13 days | Annual |
| Yalda (یلدا) | Free 5 credits to active users | Annual |
| Mercury retrograde | 1 free themed exploration | ~3×/year |
| User's solar return | 3 free credits + personalized message | Per-user annual |

#### Required New Models

```
Achievement: id, user_id, key, title_fa, credits_awarded, created_at
  UniqueConstraint("user_id", "key")

Plan: add credits_cost field (how many credits an action costs)
User: remove free_exploration_used; add referral_code (unique, URL-safe, 8 chars)
```

---

*End of REVIEW.md — Antigravity, Architect/Auditor/Reviewer*

*Hermes: execute REQUIRED_FIXES in order (RF-01 through RF-26). Report back with evidence for each acceptance criterion. I will audit the evidence before granting LAUNCH-ACCEPTED status.*