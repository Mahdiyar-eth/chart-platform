# VERDICT-VERIFIED.md — ZAYCHE opus-4.6 audit: claim-by-claim vs REAL code

**Method:** Every claim from `docs/audit/opus46/REVIEW.md` cross-checked against the live repo at HEAD `fef0d6e` (grep + direct read). The audit bundle MISSED `app/main.py:...` (all SPA routes live there) and `app/routes/*`, so several "missing file / dead code" conclusions were drawn from absence in the bundle, not absence in the repo.

## CRITICAL (corrected)

| ID | Audit claim | Verdict (real code) | Evidence |
|----|-------------|---------------------|----------|
| C-01 | verify handler FILE MISSING = root cause of "paid but sees free" | **FALSE — already handled** | `app/main.py:870` `@app.get("/api/payments/verify")`; atomic CAS at `:895` `UPDATE orders SET status='verifying' WHERE id=:oid AND status='pending' RETURNING id` |
| C-03 | verify path diverges from wallet (no Report/activate/grant/reward) | **FALSE — mirrored** | `main.py:914-950`: activates subscription, grants credits, `Report(...)` at `:928`, `_enqueue_report`, `reward_referral` at `:950` |
| C-06 | replay re-triggers side effects | **FALSE — idempotent** | status-first CAS (`:895`) + F-29 guard; verified in `test_payment_state_machine.py` |
| H-05 | synastry dead code, zero endpoint/UI/route | **FALSE — wired** | `main.py:1000 /synastry`, `:1005 POST /api/synastry`, `:1073 /api/synastry/share`, `:1114 /api/synastry/order`, `:1180 /api/synastry/full`, `:1202 /api/synastry/access` |
| H-06 | rectify dead code | **FALSE — wired** | `main.py:1219 /rectify`, `:1224 POST /api/rectify` |
| H-07 | transits dead code | **FALSE — wired** | `main.py:589 /api/charts/{id}/transit-year.svg`, `:1637 GET /api/charts/{id}/transits` |
| H-09 | bottom nav 6+FAB = 7 items | **FALSE — already 5** | `base.html` nav = 4×`bn-item` + 1×`bn-fab` |

## CRITICAL/HIGH (REAL — to fix)

| ID | Issue | Where | Fix |
|----|-------|-------|-----|
| C-04 | `claim_validation.validate_advanced()` never called in QA loop | `app/report/worker.py`/`qa.py` (0 imports) | Wire into worker QA loop; `critical_hallucination` → retry |
| C-05 | abandoned Zarinpal orders keep coupon `used_count` reserved forever | `app/payment/orders.py` (no expiry job) | Scheduled job: expire `status='pending'` >2h, release coupon |
| H-08 | wallet `pay_order_with_balance` uses Python-level `status!='pending'` check (racy) | `app/payment/orders.py:447` | Atomic CAS `UPDATE ... WHERE id=:id AND status='pending' RETURNING id` |
| H-10 | `CREDIT_PACKS={'credit3','credit6','credit12'}` but no plans seeded | `orders.py:198` vs `db.py::seed_plans()` | Seed `credit*` plans with `credits_grant > 0` |
| H-11 | `Plan.credits_grant` never populated | `models.py:194` | Set `credits_grant` in `seed_plans()` |
| H-12 | synastry `secondary_chart_id` not passed to report worker | `orders.py` fulfillment | Pass `secondary_chart_id` when `plan_key=='synastry'` |
| H-01..H-04 | **42× `prompt()/confirm()/alert()`** in 6 templates | account/admin/explore/plans/rectify/synastry.html | Replace with Alpine modal + toast |
| C-02 | post-payment redirect lacks `access_token` in URL | verify → `/payment/result?order_id=` | Harden: include `?t=` + `/chart` already accepts `?t` |

## MEDIUM/LOW (REAL but minor)
M-01 transits `swe.set_ephe_path("ephe")` relative ; M-02/M-03 `set_sid_mode`+constants duplicated (safe, all LAHIRI) ; M-14 `generator.py` dead (`asyncio.run` in sync) ; M-16 dup `og:type`/`theme-color` meta ; L-01..L-04 `btn-lg` missing `.btn` (4).

## ACCEPTANCE NOTE
The audit's top-level "revenue gate FAIL / core services dead / NOT APPROVED" is **overstated** — driven by bundle gaps. Verified real state: revenue flow works end-to-end (reproduced via HTTP, order→paid→Report queued→/chart shows "در حال تولید"); synastry/rectify/transits wired. The genuine failing gate = **mobile UX (native dialogs)** + **hallucination gate (claim_validation unwired)** + monetization residuals (credit packs / secondary_chart_id / coupon expiry).

_Execution order: P0-residue (C-04, C-05, H-08, C-02, H-10/H-11/H-12) → P1 mobile UX (H-01..H-04, touch targets) → P2 (already wired, spot-verify) → P3/P4._
