# ZAYCHE — MASTER PLAN

## `docs/workflow/MASTER_PLAN.md`

---

## 0. Document Metadata

| Field | Value |
|---|---|
| Author | Antigravity (Architect / Auditor) |
| Role | Plan only — zero code edits |
| Commit baseline | `fef0d6e` |
| Target | `chart.negar.io` |
| Stack | FastAPI · HTMX/Alpine · Postgres 16 · pgvector · OmniRoute LLM · PWA (RTL) |
| Implementer | Hermes |
| Status | **PLAN-ONLY — awaiting implementation** |

---

## 1. GOALS (ranked)

| # | Goal | Business justification |
|---|---|---|
| G1 | Fix purchase/return bug | Revenue-blocking — users cannot complete or reverse purchases |
| G2 | Mobile-first liquid-glass UI/UX | 85%+ of Persian-market traffic is mobile; current UX has RTL/responsive gaps |
| G3 | Monetization & gamification model | Sustainable revenue + retention loop |
| G4 | Personalized birth-chart services wiring | Core product value — chart generation, interpretation, compatibility, transit alerts |

---

## 2. ARCHITECTURE SNAPSHOT (for Hermes's orientation)

```
┌─────────────────────────────────────────────────────────┐
│  Browser (PWA, RTL, HTMX + Alpine.js)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Chart Views  │  │ Purchase Flow│  │ Profile/Gamif │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘ │
└─────────┼─────────────────┼─────────────────┼───────────┘
          │ HTMX partials   │ HTMX + JSON     │
┌─────────▼─────────────────▼─────────────────▼───────────┐
│  FastAPI  (app/)                                        │
│  ├── routers/   (purchase, chart, auth, user, webhook)  │
│  ├── services/  (payment, chart_engine, llm_gateway)    │
│  ├── models/    (SQLAlchemy / Alembic)                  │
│  ├── schemas/   (Pydantic v2)                           │
│  └── core/      (config, security, deps)                │
├─────────────────────────────────────────────────────────┤
│  Postgres 16  +  pgvector (RAG embeddings)              │
├─────────────────────────────────────────────────────────┤
│  OmniRoute LLM Gateway                                 │
│  ├── gemini flash-high  (default interpretation)        │
│  └── deepseek-v4-pro    (report framing)                │
│  (docs/ROUTING.md = single source of truth)             │
└─────────────────────────────────────────────────────────┘
```

---

## 3. PHASE 0 — TRIAGE & PURCHASE/RETURN BUG FIX

### 3.1 Problem Statement

The purchase and/or return (refund) flow has a confirmed bug. Without seeing runtime logs, the following are the **most probable failure modes** based on code-pattern analysis. Hermes must confirm which apply:

### 3.2 Investigation Checklist (Hermes must verify live)

| # | Check | Where to look | What to look for |
|---|---|---|---|
| T1 | Payment callback race condition | `app/routers/purchase.py` — webhook handler | Does the webhook handler use a DB transaction with `SELECT … FOR UPDATE` or equivalent? If not, double-delivery from the payment gateway can create duplicate `Purchase` rows or leave status stuck in `pending`. |
| T2 | Return/refund state machine | `app/routers/purchase.py` or `app/services/payment.py` — refund endpoint | Is there a guard that checks `purchase.status == 'completed'` before allowing refund? Can a user call refund on an already-refunded or pending purchase? (IDOR + state violation) |
| T3 | Idempotency key | Webhook handler | Payment gateways (Zarinpal, etc.) retry. Without idempotency check (`authority` or `ref_id` uniqueness constraint), duplicate credits are granted. |
| T4 | User balance / entitlement update atomicity | `app/services/payment.py` | Is the user's balance/entitlement updated in the **same DB transaction** as the purchase status change? If not, crash between the two = money taken, no service. |
| T5 | Return endpoint auth | Refund route | Is it protected by `Depends(get_current_user)` AND does it verify `purchase.user_id == current_user.id`? (IDOR) |
| T6 | HTTP method & CSRF | Purchase/return routes | POST-only? HTMX sends `HX-Request` header but that's not a CSRF token. |

### 3.3 Intended Fix Targets

| File (probable) | Fix |
|---|---|
| `app/routers/purchase.py` | Add idempotency guard on webhook; add state-machine guard on refund; add IDOR check |
| `app/services/payment.py` | Wrap balance-update + status-change in single `async with session.begin()` |
| `app/models/purchase.py` | Add unique constraint on `authority`/`ref_id`; add `status` enum with valid transitions |
| `alembic/versions/` | Migration for the new constraint |
| `tests/test_purchase.py` | Cover: happy path, double-webhook, refund-on-pending, refund-on-already-refunded, IDOR refund |

### 3.4 Acceptance Criteria — Phase 0

| ID | Criterion | Code-complete | Launch-accepted |
|---|---|---|---|
| P0-AC1 | `Purchase.authority` (or equivalent gateway ref) has a DB unique constraint | Migration file exists & `alembic upgrade head` succeeds | Verified on staging DB |
| P0-AC2 | Webhook handler is idempotent: calling it twice with same `authority` does NOT create two purchases or double-credit | Unit test passes | Manual test with gateway sandbox double-POST |
| P0-AC3 | Refund endpoint rejects requests where `purchase.status != 'completed'` with 409 | Unit test passes | Manual test in browser |
| P0-AC4 | Refund endpoint rejects requests where `purchase.user_id != current_user.id` with 403 | Unit test passes | N/A (test is sufficient) |
| P0-AC5 | Balance/entitlement update and status change are in the same DB transaction | Code inspection: single `async with session.begin()` block | Simulate crash (kill process mid-transaction) — no orphan states |
| P0-AC6 | All 551 existing tests still green + ≥ 8 new purchase/refund tests green | `pytest` exit 0 | N/A |
| P0-AC7 | Purchase flow works end-to-end on mobile viewport (375px) | N/A | **Hermes must verify in real browser** |

### 3.5 Edge Cases to Handle

- Gateway returns `NOK` but user already saw "processing" — show clear error state, not infinite spinner.
- User refreshes page during redirect-to-gateway — purchase row should be `pending`, not duplicated.
- Refund after 72 hours — business rule needed (Hermes: confirm with product owner).
- Concurrent refund requests (user double-clicks) — use DB-level locking or idempotency.

---

## 4. PHASE 1 — MOBILE-FIRST LIQUID-GLASS UI/UX

### 4.1 Design Principles

| Principle | Implementation |
|---|---|
| **RTL-native** | All `margin-left` / `padding-right` must use logical properties (`margin-inline-start`, `padding-inline-end`). No `direction: rtl` overrides on individual elements — set once on `<html>`. |
| **Liquid glass** | Frosted-glass cards (`backdrop-filter: blur(16px) saturate(180%); background: rgba(255,255,255,0.12)`), subtle borders (`border: 1px solid rgba(255,255,255,0.18)`), depth via layered translucency. Dark mode primary. |
| **Mobile-first breakpoints** | `<375px` (SE), `375-428px` (standard), `429-768px` (tablet), `769px+` (desktop). CSS written mobile-first (`min-width` media queries). |
| **Touch targets** | All interactive elements ≥ 48×48 CSS px. |
| **PWA** | `manifest.json` with `display: standalone`, `theme_color` matching glass bg, service worker for offline shell. |
| **Performance** | No layout shift on HTMX swap (use `hx-swap="innerHTML transition:true"` with CSS view transitions). Skeleton screens for async loads. |

### 4.2 File Targets

| File | Action | Details |
|---|---|---|
| `app/static/css/main.css` (or Tailwind config) | Refactor | Logical properties throughout; liquid-glass design tokens as CSS custom properties; dark-mode palette |
| `app/templates/base.html` | Modify | `<html lang="fa" dir="rtl">`; viewport meta; PWA meta tags; glass background on `<body>` |
| `app/templates/components/card.html` | Create/Modify | Reusable glass-card partial with consistent blur/border/shadow |
| `app/templates/components/nav.html` | Modify | Bottom nav bar for mobile (fixed, glass bg, 5 items max); top nav for desktop |
| `app/templates/components/empty_state.html` | **Create** | Empty-state illustrations + CTA for: no charts, no purchases, no notifications |
| `app/templates/purchase/*.html` | Modify | Purchase flow as stepped glass cards; loading/error/success states |
| `app/templates/chart/*.html` | Modify | Chart display responsive; SVG/Canvas chart scales to viewport |
| `app/static/manifest.json` | Modify | Correct `start_url`, `theme_color`, `background_color`, icons (192, 512) |
| `app/static/sw.js` | Modify | Cache shell assets; network-first for API; offline fallback page |

### 4.3 Acceptance Criteria — Phase 1

| ID | Criterion | Code-complete | Launch-accepted |
|---|---|---|---|
| P1-AC1 | Zero use of physical `margin-left/right`, `padding-left/right`, `text-align: left/right` in CSS | `grep` returns 0 matches | N/A |
| P1-AC2 | All interactive elements ≥ 48×48px on mobile | CSS inspection | **Hermes: Chrome DevTools audit on 375px viewport** |
| P1-AC3 | Glass-card component used consistently across all pages (no raw `<div>` cards) | Template grep | Visual inspection |
| P1-AC4 | Empty states exist for: chart list (0 charts), purchase history (0 purchases), notifications (0) | Templates exist | **Hermes: verify rendering with empty DB** |
| P1-AC5 | Lighthouse mobile score ≥ 90 (Performance), ≥ 95 (Accessibility) | N/A | **Hermes: run Lighthouse on deployed staging** |
| P1-AC6 | PWA installable on Android Chrome and iOS Safari | `manifest.json` valid, SW registered | **Hermes: install on real devices** |
| P1-AC7 | No horizontal scroll on any page at 320px–428px viewport | N/A | **Hermes: test on iPhone SE, iPhone 15 Pro Max** |
| P1-AC8 | HTMX swaps use view transitions (no flash of unstyled content) | `hx-swap` attributes include `transition:true` | **Hermes: visual verification** |
| P1-AC9 | Dark mode is default; light mode toggle works and persists (localStorage) | Alpine.js `x-data` + `localStorage` | **Hermes: toggle and refresh** |
| P1-AC10 | All Persian text renders correctly (Vazirmatn or IRANSans font loaded, `font-display: swap`) | CSS `@font-face` | **Hermes: verify on slow 3G** |

### 4.4 Edge Cases

- **Notch/safe-area**: Use `env(safe-area-inset-bottom)` for bottom nav on iPhones with notch.
- **Keyboard overlap**: On mobile, when virtual keyboard opens for input fields, the glass card should scroll into view, not be hidden behind keyboard.
- **RTL number display**: Prices and dates should use `direction: ltr` inside an RTL context (CSS `unicode-bidi: embed`).
- **Offline state**: When SW serves cached shell but API is unreachable, show a clear offline banner — not a broken page.

---

## 5. PHASE 2 — MONETIZATION & GAMIFICATION MODEL

### 5.1 Recommended Model: **Freemium + Token Economy**

After analyzing the astrology SaaS market and the existing codebase structure:

| Tier | Price | Includes |
|---|---|---|
| **Free** | 0 | 1 basic natal chart, daily horoscope (generic), 3 AI questions/month |
| **Setareh (ستاره)** | ~99k Toman/mo | Unlimited charts, 30 AI questions/mo, compatibility reports, transit alerts |
| **Kehkeshaan (کهکشان)** | ~249k Toman/mo | Everything + deep report framing (deepseek-v4-pro), priority support, API access |
| **Token top-up** | 10k Toman = 10 tokens | For free users or exhausted-quota users; 1 token = 1 AI question or 1 report |

### 5.2 Gamification Layer

| Mechanic | Implementation | Retention purpose |
|---|---|---|
| **Daily login streak** | `User.streak_count`, `User.last_login_date`; increment on daily visit; reset if gap > 36h | Daily engagement |
| **Cosmic XP** | Earn XP for: completing profile (50), first chart (100), sharing (25), daily login (10) | Progress feeling |
| **Levels** | 0-99 XP = نوآموز, 100-499 = ستارهشناس, 500-1499 = اخترشناس, 1500+ = کیهاننورد | Status |
| **Achievements/badges** | "First Chart", "7-day Streak", "Compatibility Explorer", "Transit Watcher" | Collection drive |
| **Referral tokens** | Referrer gets 5 tokens per signup that completes a chart | Viral growth |

### 5.3 File Targets

| File | Action | Details |
|---|---|---|
| `app/models/subscription.py` | Create | `Subscription` model: `user_id`, `tier` (enum), `started_at`, `expires_at`, `is_active`, `stripe_or_gateway_id` |
| `app/models/token_balance.py` | Create | `TokenBalance`: `user_id`, `balance`, `last_topup_at` |
| `app/models/token_transaction.py` | Create | `TokenTransaction`: `user_id`, `amount`, `type` (earn/spend/topup/refund), `reason`, `created_at` |
| `app/models/user.py` | Modify | Add `streak_count: int`, `last_login_date: date`, `xp: int`, `level: str` (computed), `referral_code: str` (unique) |
| `app/models/achievement.py` | Create | `UserAchievement`: `user_id`, `achievement_key`, `unlocked_at` |
| `app/services/quota.py` | Create | `check_quota(user, action) -> bool`; `consume_token(user, action)`; `get_remaining(user, action)` |
| `app/services/gamification.py` | Create | `award_xp(user, amount, reason)`; `check_streak(user)`; `check_achievements(user)` |
| `app/routers/subscription.py` | Create | CRUD for subscription management; webhook for payment gateway |
| `app/routers/gamification.py` | Create | GET endpoints for user's XP, level, achievements, streak |
| `app/middleware/quota.py` | Create | Middleware or dependency that checks quota before LLM calls |
| `app/templates/components/xp_bar.html` | Create | Animated XP progress bar (glass style) |
| `app/templates/components/streak.html` | Create | Streak flame counter |
| `app/templates/components/achievement_toast.html` | Create | HTMX OOB swap for achievement unlock notification |
| `alembic/versions/` | Create | Migrations for all new models |

### 5.4 Acceptance Criteria — Phase 2

| ID | Criterion | Code-complete | Launch-accepted |
|---|---|---|---|
| P2-AC1 | Free user cannot make more than 3 AI questions/month; gets 402 + friendly upgrade CTA | Unit test + integration test | **Hermes: test with real free account** |
| P2-AC2 | Token deduction is atomic (same transaction as LLM call initiation) | Code inspection | Simulate crash between deduction and LLM call — token should be refunded or call should be retried |
| P2-AC3 | Subscription expiry is checked on every authenticated request (not just at login) | Dependency injection in router | **Hermes: let subscription expire, verify downgrade** |
| P2-AC4 | Streak resets correctly after 36h gap (not 24h — timezone-friendly) | Unit test with mocked dates | **Hermes: manual test across midnight** |
| P2-AC5 | XP bar animates on gain (CSS transition, not JS-heavy) | Template inspection | **Hermes: visual verification** |
| P2-AC6 | Achievement unlock triggers HTMX OOB toast without page reload | `hx-swap-oob="true"` in response | **Hermes: trigger achievement, verify toast** |
| P2-AC7 | Referral code is unique, URL-safe, 8 chars | Model constraint + generation logic | Unit test |
| P2-AC8 | Referral tokens are only granted after referee completes first chart (not just signup) | Service logic | Unit test with mock |
| P2-AC9 | Token balance cannot go negative (DB CHECK constraint + application guard) | Migration + service code | Unit test: attempt to spend with 0 balance |
| P2-AC10 | All gamification data is returned in a single API call (no N+1) | `select_related` / `joinedload` | Query count test or `EXPLAIN` |

### 5.5 Security Considerations

- **Rate limiting on token top-up**: Prevent automated abuse. Max 10 top-ups per hour per user.
- **Referral fraud**: Same IP / device fingerprint creating multiple accounts — log and flag, don't auto-ban.
- **Subscription webhook verification**: Verify gateway signature on every webhook call. Do NOT trust `user_id` from webhook body — look up by `gateway_reference`.

---

## 6. PHASE 3 — PERSONALIZED BIRTH-CHART SERVICES

### 6.1 Service Catalog

| Service | Input | LLM Route (per ROUTING.md) | Output | Tier |
|---|---|---|---|---|
| **Natal Chart Generation** | Birth date, time, location | None (ephemeris calculation) | SVG chart + planet positions JSON | Free (1), Paid (unlimited) |
| **Basic Interpretation** | Planet positions | gemini flash-high | 500-word Persian text | Free (3/mo), Paid (unlimited) |
| **Deep Report** | Planet positions + house system + aspects | deepseek-v4-pro (report framing) | 3000-word structured PDF-ready report | Kehkeshaan only |
| **Compatibility (Synastry)** | Two natal charts | gemini flash-high | Compatibility score + narrative | Setareh+ |
| **Transit Alerts** | Natal chart + current transits | gemini flash-high | Daily/weekly push notification text | Setareh+ |
| **AI Q&A** | User question + natal chart context | gemini flash-high | Conversational answer | Token-based |
| **RAG-enhanced Interpretation** | Planet positions + pgvector similarity search on Persian astrology corpus | gemini flash-high (with RAG context) | Culturally-grounded interpretation | Setareh+ |

### 6.2 File Targets

| File | Action | Details |
|---|---|---|
| `app/services/ephemeris.py` | Create/Verify | Swiss Ephemeris wrapper: `calculate_chart(birth_dt, lat, lon) -> ChartData` |
| `app/services/chart_renderer.py` | Create/Verify | SVG generation from `ChartData`; responsive viewBox; RTL labels |
| `app/services/interpretation.py` | Create/Modify | Prompt construction for natal interpretation; calls `llm_gateway` |
| `app/services/deep_report.py` | Create | Prompt construction for deep report; calls `llm_gateway` with `model=deepseek-v4-pro` per ROUTING.md |
| `app/services/compatibility.py` | Create | Synastry aspect calculation + prompt construction |
| `app/services/transits.py` | Create | Current transit calculation + alert generation |
| `app/services/rag.py` | Create/Modify | pgvector similarity search; context injection into prompts |
| `app/services/llm_gateway.py` | Verify | Must respect `docs/ROUTING.md` routing rules exactly; must pass `model` parameter correctly to OmniRoute |
| `app/routers/chart.py` | Modify | Endpoints for all services; quota checks via `Depends(check_quota)` |
| `app/models/chart.py` | Modify | Store `planet_positions` (JSONB), `house_system`, `aspects` (JSONB), `svg_cache` (text) |
| `app/models/interpretation.py` | Create/Modify | Cache interpretations: `chart_id`, `type` (basic/deep/compat/transit), `content`, `model_used`, `created_at` |
| `app/templates/chart/natal.html` | Modify | Display SVG chart + interpretation; glass card layout; loading skeleton during LLM call |
| `app/templates/chart/compatibility.html` | Create | Side-by-side charts + compatibility narrative |
| `app/templates/chart/report.html` | Create | Deep report display; PDF download button |

### 6.3 LLM Gateway Compliance Check

**Critical**: `docs/ROUTING.md` is the single source of truth. Hermes must verify:

| Check | Expected | File to inspect |
|---|---|---|
| Default model for all interpretation calls | `gemini-flash-high` | `app/services/llm_gateway.py` |
| Report framing model | `deepseek-v4-pro` | `app/services/deep_report.py` |
| No hardcoded model strings outside gateway | All model selection goes through gateway config | `grep -r "gemini\|deepseek" app/services/` |
| Fallback behavior | If primary model fails, retry once, then return cached/generic response — NOT silently switch models | `app/services/llm_gateway.py` |
| Token counting / cost tracking | Log `model`, `input_tokens`, `output_tokens` per call | `app/services/llm_gateway.py` or middleware |

### 6.4 RAG Pipeline

| Step | Implementation | File |
|---|---|---|
| Corpus ingestion | Persian astrology texts chunked (512 tokens, 128 overlap) → embed via `text-embedding-3-small` → store in `pgvector` | `app/services/rag.py` or `scripts/ingest.py` |
| Query embedding | User's chart aspects → natural language description → embed | `app/services/rag.py` |
| Similarity search | `SELECT * FROM chunks ORDER BY embedding <=> $1 LIMIT 5` | `app/services/rag.py` |
| Context injection | Top-5 chunks prepended to LLM prompt as `[CONTEXT]` block | `app/services/interpretation.py` |

### 6.5 Acceptance Criteria — Phase 3

| ID | Criterion | Code-complete | Launch-accepted |
|---|---|---|---|
| P3-AC1 | Natal chart SVG renders correctly for a known birth data set (e.g., 1370/01/01 12:00 Tehran) | Snapshot test (SVG output matches expected) | **Hermes: visual verification** |
| P3-AC2 | Planet positions match a reference ephemeris (astro.com) within ±0.5° | Unit test with known positions | **Hermes: cross-check 3 charts against astro.com** |
| P3-AC3 | Basic interpretation uses `gemini-flash-high` (verify in logs/mock) | Unit test with mocked gateway | **Hermes: check OmniRoute logs on staging** |
| P3-AC4 | Deep report uses `deepseek-v4-pro` (verify in logs/mock) | Unit test with mocked gateway | **Hermes: check OmniRoute logs on staging** |
| P3-AC5 | RAG context is included in interpretation prompt when available | Unit test: mock pgvector, verify prompt contains `[CONTEXT]` | N/A |
| P3-AC6 | Compatibility report requires two valid charts; returns 422 if either is missing | Unit test | N/A |
| P3-AC7 | LLM failure returns graceful error (glass card with retry button), not 500 | Integration test with mocked timeout | **Hermes: kill LLM endpoint, verify UX** |
| P3-AC8 | Interpretation is cached; re-requesting same chart+type does NOT call LLM again | Unit test: second call returns cached, mock not called twice | N/A |
| P3-AC9 | Chart SVG is responsive (scales to container width, no overflow) | CSS inspection | **Hermes: test on 320px and 1440px viewports** |
| P3-AC10 | Transit alerts can be generated for a chart and contain valid astronomical data | Unit test | **Hermes: verify transit text mentions actual current planetary positions** |
| P3-AC11 | PDF export of deep report works (WeasyPrint or equivalent) | Unit test: output is valid PDF | **Hermes: download and open on mobile** |

### 6.6 Edge Cases

- **Unknown birth time**: Allow "unknown" → use noon chart with disclaimer. Do NOT present house-dependent interpretations.
- **Southern hemisphere**: Ensure ephemeris handles negative latitudes correctly.
- **Date conversion**: Jalali ↔ Gregorian conversion must be exact. Use `jdatetime` or `khayyam`. Test edge cases: Esfand 29/30 (leap year).
- **LLM hallucination guard**: Post-process LLM output to verify mentioned planet positions match the actual chart data. Flag discrepancies.
- **Empty RAG results**: If pgvector returns 0 similar chunks (new topic), proceed without context — don't error.
- **Concurrent chart generation**: Two users requesting charts simultaneously should not interfere (no shared mutable state in ephemeris service).

---

## 7. PHASE ORDERING & DEPENDENCIES

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3
(Bug fix)   (UI/UX)    (Monetize)  (Services)
  │                        │            │
  │                        ▼            │
  │                   Phase 2 needs     │
  │                   Phase 1 UI        │
  │                   components        │
  │                                     ▼
  │                              Phase 3 needs
  │                              Phase 2 quota
  │                              system
  ▼
  All phases need Phase 0
  (working purchase flow)
```

**Parallel work possible**:
- Phase 1 UI components can start immediately (no dependency on Phase 0 beyond base template).
- Phase 3 ephemeris/chart engine can be developed in parallel with Phase 2.
- Phase 3 LLM integration depends on Phase 2 quota system being at least stubbed.

**Recommended execution order**:
1. Phase 0 (1-2 days) — unblock revenue
2. Phase 1 (3-5 days) — unblock user experience
3. Phase 2 (3-4 days) — unblock monetization
4. Phase 3 (5-7 days) — deliver core product

---

## 8. CROSS-CUTTING CONCERNS

### 8.1 Security (all phases)

| Concern | Check | Where |
|---|---|---|
| **IDOR** | Every endpoint that accesses a resource by ID must verify `resource.user_id == current_user.id` | All routers |
| **Auth on all routes** | No chart/purchase/gamification endpoint should be accessible without `Depends(get_current_user)` | All routers |
| **Rate limiting** | LLM endpoints: 10 req/min/user. Purchase: 5 req/min/user. Auth: 5 req/min/IP. | `app/middleware/` or `slowapi` |
| **Input validation** | Birth date: valid Jalali date, not in future. Lat/lon: valid ranges. All Pydantic schemas must have validators. | `app/schemas/` |
| **SQL injection** | All queries via SQLAlchemy ORM or parameterized. No raw SQL with f-strings. | `grep -r "text(" app/` — verify all use bound params |
| **XSS** | HTMX responses must use Jinja2 autoescaping. No `| safe` filter on user-generated content. | `grep -r "| safe" app/templates/` |
| **CORS** | `allow_origins` must be `["https://chart.negar.io"]`, not `["*"]` | `app/core/config.py` or main app setup |
| **Secrets** | No API keys, DB passwords, or gateway secrets in code. All via env vars / `.env` (which is in `.gitignore`). | `grep -rn "sk-\|password\|secret" app/` (should return 0 outside config) |

### 8.2 Observability

| What | How |
|---|---|
| LLM cost tracking | Log every LLM call: `user_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `success` |
| Error tracking | Structured logging (JSON) with correlation ID per request |
| Purchase audit trail | Every purchase state change logged with timestamp, old_status, new_status, actor |

### 8.3 Testing Strategy

| Layer | Tool | Coverage target |
|---|---|---|
| Unit | pytest | All services, models, schemas — ≥ 85% line coverage |
| Integration | pytest + httpx `AsyncClient` | All router endpoints — happy path + error paths |
| E2E | **Hermes must run manually** | Purchase flow, chart generation, gamification triggers |
| Visual | **Hermes must verify** | All pages at 320px, 375px, 428px, 768px, 1440px |

---

## 9. WHAT HERMES CANNOT SKIP (requires real browser / live DB)

These items are **impossible to verify via code review alone**. They are marked throughout with **bold Hermes callouts** but consolidated here:

| # | Verification | Phase | Why code review is insufficient |
|---|---|---|---|
| H1 | Purchase end-to-end with real payment gateway sandbox | P0 | Gateway behavior, redirects, webhook timing |
| H2 | Refund end-to-end | P0 | Gateway refund API behavior |
| H3 | All pages at 320px viewport — no horizontal scroll | P1 | CSS rendering engine differences |
| H4 | PWA install on Android + iOS | P1 | Browser-specific PWA requirements |
| H5 | Lighthouse audit | P1 | Runtime performance metrics |
| H6 | Subscription expiry behavior | P2 | Time-dependent state change |
| H7 | Streak reset across midnight in user's timezone | P2 | Timezone + date boundary |
| H8 | Chart accuracy vs astro.com | P3 | Ephemeris numerical accuracy |
| H9 | LLM response quality in Persian | P3 | Prompt engineering effectiveness |
| H10 | PDF download on mobile | P3 | Mobile browser PDF handling |
| H11 | Offline PWA behavior | P1 | Service worker caching behavior |
| H12 | RTL layout of chart SVG labels | P3 | SVG text rendering in RTL context |

---

## 10. DEFINITION OF DONE

### Code-Complete (Hermes self-certifies)

- [ ] All acceptance criteria marked "Code-complete" are met
- [ ] All existing 551 tests pass
- [ ] New tests added per phase (≥ 8 for P0, ≥ 5 for P1, ≥ 10 for P2, ≥ 12 for P3)
- [ ] No `grep` violations from Security §8.1
- [ ] `alembic upgrade head` succeeds on clean DB
- [ ] `docs/ROUTING.md` is still the single source of truth for LLM routing (no contradictions in code)

### Launch-Accepted (requires Antigravity audit of evidence)

- [ ] All "Launch-accepted" criteria verified with screenshots/logs
- [ ] All H1-H12 verifications completed with evidence
- [ ] Lighthouse mobile ≥ 90/95
- [ ] Zero IDOR vulnerabilities (tested with two different user accounts)
- [ ] Purchase + refund audit trail is complete and queryable
- [ ] LLM cost tracking shows per-user, per-model breakdown
- [ ] PWA installable on at least: Chrome Android, Safari iOS
- [ ] No console errors on any page at any viewport

---

## 11. RISK REGISTER

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Payment gateway SDK has undocumented behavior | Medium | High (P0 blocked) | Use gateway sandbox extensively; log all webhook payloads |
| Swiss Ephemeris Python binding (`pyswisseph`) has platform-specific build issues | Medium | High (P3 blocked) | Pin version; test in Docker; have fallback to `flatlib` |
| LLM output quality in Persian is poor | Medium | High (P3 quality) | Test with 10 diverse charts; iterate prompts; consider few-shot examples in prompt |
| `pgvector` similarity search is slow on large corpus | Low | Medium | Index with `ivfflat` or `hnsw`; limit corpus to 10k chunks initially |
| Jalali date edge cases cause chart errors | Medium | Medium | Comprehensive test suite for Esfand 29/30, century boundaries |
| Mobile keyboard covers input fields | High | Medium (UX) | Use `visualViewport` API or `scrollIntoView` on focus |

---

*End of MASTER_PLAN.md — Antigravity, Architect/Auditor*

*Hermes: execute phases in order. Report back with evidence for each acceptance criterion. I will audit.*