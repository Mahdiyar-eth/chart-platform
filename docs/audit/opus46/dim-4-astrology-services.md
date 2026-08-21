# AUDIT — Personalized Services from Birth Chart

**Dimension:** Diverse personalized services derived from the birth chart
**Scope:** `app/astrology/*`, `app/report/*`, UI/report wiring, missing services
**Date:** 2025-01-XX

---

## 1. INVENTORY: What Exists

### 1.1 Astrology Engine Layer (`app/astrology/`)

| Module | Purpose | Status | Wired to UI/API? |
|---|---|---|---|
| `engine.py` | Natal chart computation (pyswisseph, Placidus, tropical+sidereal) | ✅ Solid, 14 golden charts | ✅ Yes — `/api/charts` |
| `big_three.py` | Sun/Moon/ASC sign + element/modality/color/keys | ✅ Complete | ✅ Yes — preview, PDF cover, chat |
| `transits.py` | Current transits to natal + `upcoming_transits()` 90-day scan | ✅ Functional | ⚠️ Partial — Gold PDF only (`renderer.py:127`), weekly delivery; **NOT exposed as standalone API/page** |
| `synastry.py` | Cross-chart aspects + 4-domain compatibility score | ✅ Functional | ❌ **Not wired** — no API endpoint, no UI page, no report section |
| `rectify.py` | Birth time finder (20-min step scan + event scoring) | ✅ Functional | ❌ **Not wired** — no API endpoint, no UI flow |
| `sky.py` | "Today's Sky" — public planetary positions, moon phase, aspects, reflections | ✅ Complete | ⚠️ Likely wired to a `/sky` page (imports `transits.py` helpers), but **not confirmed in provided routes** |
| `svg_wheel.py` | Chart wheel SVG renderer | ✅ Complete | ✅ Yes — chart page |
| `svg_widgets.py` | Aspect grid, element donut, house bar, KPI cards, transit timeline SVG | ✅ Complete | ⚠️ `transit_timeline_svg` used in Gold PDF only; other widgets likely on chart page but **not confirmed** |
| `cities_ir.py` | Iran city search + coordinates | ✅ Complete | ✅ Yes — birth form |
| `cities_world.py` | World city search + timezone resolution | ✅ Complete | ✅ Yes — birth form |
| `golden_data.py` | 14 reference charts for regression testing | ✅ Complete | N/A (test infra) |

### 1.2 Report Layer (`app/report/`)

| Module | Purpose | Status | Wired? |
|---|---|---|---|
| `rules.py` | Data-driven rule engine → 13 life domains, ~50 rules | ✅ Complete | ✅ Yes — drives prompt_builder |
| `prompt_builder.py` | Per-domain prompts + Islamic chapter + personal question | ✅ Complete | ✅ Yes — worker |
| `generator.py` | Sync orchestrator (legacy, superseded by worker) | ⚠️ Uses `asyncio.run()` inside sync — **dead code** in production | ❌ Not called in prod (worker.py is the real path) |
| `worker.py` | ARQ async worker — concurrent section generation, QA, PDF, audio | ✅ Production path | ✅ Yes |
| `qa.py` | Claim validation, forbidden patterns, evidence grounding | ✅ Thorough | ✅ Yes — worker |
| `claim_validation.py` | A2 — deterministic planet/sign/house/degree/aspect cross-check | ✅ Thorough | ⚠️ **Not called by worker.py or qa.py** — appears to be a standalone module; `validate_advanced()` is never invoked in the generation pipeline |
| `renderer.py` | WeasyPrint PDF (RTL Persian) | ✅ Complete | ✅ Yes |
| `preview.py` | Free insights (deterministic + optional LLM enrichment) | ✅ Complete | ✅ Yes — `/api/charts/{id}/preview` |
| `weekly.py` | Weekly transit reflection delivery (bot + web push) | ✅ Complete | ✅ Yes — scheduled job |
| `word.py` | Word (.docx) export | ✅ Complete | ⚠️ Likely wired but **not confirmed in routes** |
| `prompt_overrides.py` | Admin prompt versioning | ✅ Complete | ✅ Yes — worker |

### 1.3 Chat Layer (`app/chat/`)

| Module | Purpose | Wired? |
|---|---|---|
| `intents.py` | Keyword intent classifier (15 intents incl. "transit") | ✅ Yes |
| `retrieval.py` | Grounded context retrieval + system prompt | ✅ Yes |

---

## 2. CRITICAL FINDINGS

### F-01 [P0] `claim_validation.py` is DEAD CODE — never called in the pipeline

**Evidence:** `worker.py` calls `qa_section()` from `qa.py` (line ~130). `qa.py` does its own evidence checking but **never imports or calls** `validate_section()` or `validate_advanced()` from `claim_validation.py`. The advanced validator (house, degree, aspect, retrograde cross-checks) is the most thorough hallucination gate in the codebase, yet it sits unused.

**Impact:** The production QA pipeline lacks house-mismatch detection, degree-mismatch detection, aspect-mismatch detection, and retrograde-mismatch detection. Only planet→sign claims are partially checked by `qa.py`'s evidence loop.

**Acceptance criteria:**
- [ ] `worker.py` or `qa.py` calls `validate_advanced(domain, res.text, chart)` after `parse_section()` succeeds
- [ ] Any `critical_hallucination == True` result triggers a retry (same as current QA failures)
- [ ] Test: golden chart with a known Mercury-in-Virgo, inject "Mercury in Leo" → must fail

---

### F-02 [P0] Synastry is fully implemented but has ZERO UI/API surface

**Evidence:** `synastry.py` exports `synastry(chart_a, chart_b) → dict` with connections, domain scores, overall score, and verdict. No API endpoint imports it. No route file references it. No UI page exists.

**Impact:** A complete, tested compatibility service is invisible to users. This is the single highest-value missing personalized service.

**Acceptance criteria:**
- [ ] `POST /api/synastry` endpoint accepting two chart IDs, returning the synastry dict
- [ ] IDOR check: both charts must belong to the authenticated user (or be public)
- [ ] UI page with connection list, domain radar/bars, overall score, verdict
- [ ] Rate limit: ≤10 synastry computations per user per day

---

### F-03 [P0] Birth Time Rectification is fully implemented but has ZERO UI/API surface

**Evidence:** `rectify.py` exports `rectify_birth_time(...)` with scoring, top-3 candidates, and event details. No API endpoint imports it. No UI flow exists.

**Impact:** A unique differentiating service (birth time finder from life events) is invisible.

**Acceptance criteria:**
- [ ] `POST /api/rectify` endpoint accepting birth date + location + up to 3 life events
- [ ] Returns top-3 candidate times with scores and chart preview
- [ ] UI wizard: step 1 = birth date/location, step 2 = add life events, step 3 = results
- [ ] Auth required; rate limit ≤5 rectifications per user per day (CPU-intensive: 72 chart computations per call)

---

### F-04 [P1] Transits are Gold-PDF-only — no standalone personalized transit page/API

**Evidence:** `upcoming_transits()` is called in `renderer.py:127` (Gold PDF transit chapter) and `weekly.py` (weekly delivery). There is no `/api/transits` endpoint returning the user's personal transit events. The transit data is rich (planet, sign, natal target, aspect, orb, start date) but only surfaces in a static PDF table.

**Impact:** The core promise of "upcoming TRANSITS specific to that person, with clear full explanations" is not met for non-Gold users, and even Gold users only see it in a PDF — not as a live, updating page.

**Acceptance criteria:**
- [ ] `GET /api/charts/{id}/transits?days=90` returns `upcoming_transits()` output
- [ ] Auth + ownership check on chart ID
- [ ] UI page: timeline/calendar view of upcoming transits with Persian explanations
- [ ] Each transit event includes a 2-3 sentence LLM-generated reflection (via `build_router("preview")` — cheap model, cached per transit-key)
- [ ] Free tier: next 30 days; paid: 90 days

---

### F-05 [P1] `sky.py` "Today's Sky" — likely wired but not confirmed; missing personalization bridge

**Evidence:** `sky_today()` returns a rich public payload (planets, retrogrades, aspects, moon phase, reflection). However, it is **not personalized** — it shows the same sky for everyone. There is no function that overlays "today's sky vs YOUR chart" as a daily personal reading.

**Impact:** The gap between "public sky" and "personal transits" is the most valuable daily engagement feature. Users should see "Today, Jupiter at 15° Gemini is trining YOUR natal Sun at 14° Libra — a day of expansion in your identity."

**Acceptance criteria:**
- [ ] New function `personal_sky_today(chart_json)` that merges `sky_today()` with `compute_transits(chart_json)`
- [ ] API endpoint `GET /api/charts/{id}/sky-today`
- [ ] UI card on dashboard: "Your sky today" with 2-3 personal transit highlights
- [ ] Cache per chart per day (transits don't change intra-day for slow planets)

---

### F-06 [P1] `generator.py` is dead code in production

**Evidence:** `generator.py:generate_sections()` uses `asyncio.run()` inside a sync function (line ~50: `await_complete` wraps `asyncio.run(router.complete(...))`). The actual production path is `worker.py:generate_sections_async()`. No route or worker imports `generator.py`.

**Impact:** Maintenance confusion; two divergent generation paths. The sync version lacks: concurrent section generation, per-section routing (M2), budget caps, focus-area reordering, personal question support, LLMRun logging.

**Acceptance criteria:**
- [ ] Delete `generator.py` or mark it explicitly as `# DEPRECATED — use worker.py`
- [ ] Ensure no import path reaches it

---

### F-07 [P2] Transit explanations are data-only — no "clear full explanations"

**Evidence:** `transits.py:upcoming_transits()` returns `{planet_fa, sign_fa, target, aspect, orb, start}` — raw astronomical data. The weekly delivery (`weekly.py`) adds template-based reflections (`ASPECT_REFLECTION` dict), but these are generic 1-liners, not "clear full explanations" of what a specific transit means for the person.

**Impact:** The audit dimension explicitly requires "clear full explanations." Current output is expert-level shorthand that a typical user cannot interpret.

**Acceptance criteria:**
- [ ] Each transit event in the API response includes a `explanation_fa` field: 3-5 sentences explaining what this transit means for the person, referencing their natal placement
- [ ] Generated via cheap LLM (preview router) with chart context, or via a deterministic template library keyed on (transit_planet, aspect, natal_target)
- [ ] Cached per (transit_planet, aspect_type, natal_sign) — ~350 combinations max

---

### F-08 [P2] No Solar Return / Profection Year / Progressions

**Evidence:** No module computes solar return charts, annual profections, or secondary progressions. These are standard personalized annual services in professional astrology platforms.

**Impact:** Missing service diversity. Solar return is the most requested "what does my year look like" service after transits.

---

### F-09 [P2] No Lunar Return / Void-of-Course Moon tracking

**Evidence:** `sky.py` tracks moon phase and sign but does not compute the user's personal lunar return (Moon returns to natal Moon position, ~monthly) or void-of-course periods.

---

### F-10 [P2] Synastry has no LLM interpretation layer

**Evidence:** `synastry.py` returns raw scores and connection lists. There is no prompt template or LLM pipeline to generate a human-readable compatibility report. The `prompt_builder.py` has no synastry domain.

**Acceptance criteria:**
- [ ] Add `build_synastry_prompt(chart_a, chart_b, synastry_result)` to prompt_builder
- [ ] QA pipeline validates synastry claims against both charts
- [ ] PDF/page rendering for synastry report

---

### F-11 [P3] `transits.py` ephemeris path is hardcoded relative

**Evidence:** `transits.py:10`: `swe.set_ephe_path("ephe")` — relative path. Compare with `engine.py:27`: `EPHE_PATH = os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")` which uses env var with absolute fallback. And `sky.py:18` uses the env var correctly.

**Impact:** If the worker's CWD is not the project root, `transits.py` will fail to find ephemeris files → `swe.calc_ut()` falls back to less accurate analytical ephemeris or crashes.

**Acceptance criteria:**
- [ ] `transits.py` uses `os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")` like `engine.py`

---

### F-12 [P3] `transits.py` calls `swe.set_sid_mode()` at module level — global state race

**Evidence:** `transits.py:11`: `swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)`. Same call in `engine.py:40` and `sky.py:19`. The `engine.py` comment (line 38-39) explicitly warns: "set_sid_mode is a GLOBAL swisseph state — setting it per-request races with concurrent requests." All three modules set the same mode (LAHIRI), so currently safe, but the triple-set is a maintenance trap.

**Acceptance criteria:**
- [ ] Single `swe.set_sid_mode()` call in one init module; others import from there
- [ ] Or: document that all three MUST stay identical

---

### F-13 [P3] `sky.py` duplicates sign/element/modality data from `big_three.py` and `engine.py`

**Evidence:** `sky.py` defines its own `_SIGN_BARE`, `_ELEMENT`, `_MODALITY` (lines 83-95) that duplicate `big_three.py:SIGNS_FA`, `ELEMENTS`, `MODALITIES` and `engine.py:SIGNS_FA`. Any sign name change must be updated in 3+ places.

**Acceptance criteria:**
- [ ] `sky.py` imports from `big_three.py` or a shared constants module

---

## 3. SECURITY & ROBUSTNESS

### S-01 [P1] Rectification endpoint (when built) needs CPU abuse protection

`rectify_birth_time()` computes 72 charts (24h × 60min / 20min steps) per call, each with full `swe.calc_ut()` for 13 bodies. With 3 events, that's 72 × 3 = 216 ephemeris lookups per event scan. An attacker could DoS the server.

**Acceptance criteria:**
- [ ] Rate limit: ≤5 per user per day
- [ ] Events capped at 3 (already done in code: `events = list(events)[:3]`)
- [ ] Timeout: 30s max per rectification call
- [ ] Run in ARQ worker, not in request path

### S-02 [P1] Synastry endpoint (when built) needs IDOR protection

Both chart IDs must belong to the authenticated user. Without this, any user could read another user's chart positions by requesting synastry between their chart and a victim's chart ID.

### S-03 [P2] `transits.py:upcoming_transits()` has unbounded `days` parameter

**Evidence:** `upcoming_transits(chart_json, days=90, step=1)` — if called with `days=3650`, it runs 3650 iterations of ephemeris calculations. The `weekly.py` calls it with `days=7`, `renderer.py` with `days=120`, but an API endpoint would need to cap this.

**Acceptance criteria:**
- [ ] API endpoint caps `days` at 365
- [ ] Function itself caps at 365: `days = min(days, 365)`

---

## 4. WHAT'S CORRECT

- **Engine accuracy:** `engine.py` is well-architected — proper IANA timezone handling via `zoneinfo`, Jalali conversion, sidereal support without global state mutation (manual ayanamsa subtraction), 14 golden charts covering DST edge cases, foreign cities, leap years, and house boundaries. This is production-grade.

- **Rule engine:** `rules.py` covers all 13 domains with ~50 rules, proper wildcard matching, priority/weight ordering. The fallback rules (sign-only when house is unavailable) correctly handle unknown birth times.

- **QA pipeline:** `qa.py` is thorough — forbidden pattern detection, evidence grounding, Persian→English normalization, cross-section repetition check. The F-27/F-31/F-32 runtime fixes show battle-tested iteration.

- **Weekly delivery:** `weekly.py` correctly handles web-only subscriptions (no chat_id), deduplicates per chart/week, and includes web push notification.

- **Unknown birth time handling:** Consistently implemented across engine (no ASC/houses), prompt_builder (warning injected), svg_widgets (notice instead of fake zeros), big_three (ASC omitted), and engine (moon sign confidence with possible_signs).

---

## 5. FEATURE LIST — Full Personalized Multi-Service Offering

### Currently Live (code-complete + wired)
1. ✅ **Natal Chart Computation** — tropical + sidereal, 13 bodies, Placidus houses
2. ✅ **Big Three Analysis** — Sun/Moon/ASC with element, modality, color, interpretation keys
3. ✅ **13-Domain Life Report** — LLM-written, QA-validated, PDF + audio
4. ✅ **Free Preview Insights** — deterministic + optional LLM enrichment
5. ✅ **Chart Wheel SVG** — interactive zodiac visualization
6. ✅ **Chart Widgets** — aspect grid, element donut, house bar, KPI cards
7. ✅ **Weekly Transit Reflection** — bot + web push delivery
8. ✅ **Personal Question** — user's question answered from chart context
9. ✅ **Islamic/Cultural Chapter** — Gold plan, verified KB citations
10. ✅ **AI Chat** — intent-routed, grounded in chart + report
11. ✅ **Today's Sky** (public) — planetary positions, moon phase, aspects

### Code-Complete but NOT Wired (dead features)
12. ⚠️ **Synastry / Compatibility** — `synastry.py` complete, no API/UI
13. ⚠️ **Birth Time Rectification** — `rectify.py` complete, no API/UI
14. ⚠️ **Transit Timeline SVG** — `svg_widgets.py:transit_timeline_svg()` only in Gold PDF
15. ⚠️ **Advanced Claim Validation** — `claim_validation.py` never called

### Missing (not implemented)
16. ❌ **Standalone Personal Transit Page** — live, updating, with explanations
17. ❌ **Personal Daily Sky** — today's sky overlaid on YOUR chart
18. ❌ **Solar Return Chart** — annual chart for birthday
19. ❌ **Annual Profections** — which house is activated this year
20. ❌ **Secondary Progressions** — progressed chart positions
21. ❌ **Lunar Return** — monthly emotional cycle chart
22. ❌ **Void-of-Course Moon** — timing guidance
23. ❌ **Transit Notifications** — push when a major transit enters orb
24. ❌ **Synastry LLM Report** — human-readable compatibility narrative
25. ❌ **Composite Chart** — midpoint chart for relationships
26. ❌ **Horary Chart** — chart for a specific question moment
27. ❌ **Electional Astrology** — best time to start something

---

## 6. BUILD ORDER (prioritized by user value × implementation effort)

### Phase 1 — Wire What's Already Built (1-2 weeks)

| # | Task | Effort | Depends on |
|---|---|---|---|
| 1.1 | Wire `claim_validation.validate_advanced()` into `worker.py` QA loop | 2h | — |
| 1.2 | Fix `transits.py` ephemeris path (F-11) | 15min | — |
| 1.3 | `POST /api/synastry` endpoint + IDOR check + rate limit | 4h | — |
| 1.4 | Synastry UI page (connection list, domain scores, verdict) | 8h | 1.3 |
| 1.5 | `POST /api/rectify` endpoint + rate limit + ARQ job | 4h | — |
| 1.6 | Rectification UI wizard (3-step flow) | 8h | 1.5 |
| 1.7 | Delete/deprecate `generator.py` | 15min | — |

### Phase 2 — Personal Transit Service (2-3 weeks)

| # | Task | Effort | Depends on |
|---|---|---|---|
| 2.1 | `GET /api/charts/{id}/transits` endpoint with auth + day cap | 3h | — |
| 2.2 | Transit explanation templates (deterministic, ~50 combos) | 8h | — |
| 2.3 | LLM-enriched transit explanations (preview router, cached) | 6h | 2.1, 2.2 |
| 2.4 | Transit timeline UI page (calendar/list view) | 12h | 2.1 |
| 2.5 | `GET /api/charts/{id}/sky-today` — personal daily sky | 4h | — |
| 2.6 | Dashboard "Your Sky Today" card | 6h | 2.5 |
| 2.7 | Transit push notifications (when major transit enters orb) | 8h | 2.1 |

### Phase 3 — Synastry Report + Solar Return (2-3 weeks)

| # | Task | Effort | Depends on |
|---|---|---|---|
| 3.1 | `build_synastry_prompt()` + QA for synastry claims | 6h | 1.3 |
| 3.2 | Synastry PDF renderer | 8h | 3.1 |
| 3.3 | Solar return chart computation (`engine.py` extension) | 6h | — |
| 3.4 | Solar return API + UI page | 8h | 3.3 |
| 3.5 | Annual profections (deterministic: age % 12 → house) | 3h | — |
| 3.6 | Profection year UI card on dashboard | 4h | 3.5 |

### Phase 4 — Advanced Services (3-4 weeks)

| # | Task | Effort | Depends on |
|---|---|---|---|
| 4.1 | Secondary progressions computation | 8h | — |
| 4.2 | Progressed chart API + UI | 8h | 4.1 |
| 4.3 | Lunar return computation + monthly cycle page | 6h | — |
| 4.4 | Void-of-course Moon tracking in sky.py | 4h | — |
| 4.5 | Composite chart (midpoint method) | 6h | — |
| 4.6 | Deduplicate shared constants (F-13) | 2h | — |

### Runtime Pattern Compliance

All new LLM-powered features (2.3, 3.1) MUST use the existing Omni gateway pattern:
```python
from app.core.llm import build_router
router = build_router("preview")  # cheap model for enrichment
# or
router = build_section_router(domain, section_model(domain))  # per-section routing
```

All new endpoints MUST:
- Use auth middleware (existing pattern)
- Log via `LLMRun` model (existing pattern in `worker.py`)
- Respect budget caps (`LLM_DAILY_BUDGET_USD`, `LLM_USER_DAILY_MAX_USD`)

---

## 7. SUMMARY VERDICT

| Dimension | Grade |
|---|---|
| Engine correctness | **A** — battle-tested, golden charts, DST edge cases handled |
| Service diversity (code) | **B+** — synastry, rectification, transits all implemented |
| Service diversity (wired to user) | **D** — only natal report + weekly + chat are live; synastry & rectify are dead code |
| Transit personalization | **C-** — data exists but no standalone page, no explanations, Gold-PDF-only |
| Hallucination prevention | **B-** — `claim_validation.py` is thorough but never called; `qa.py` covers basics |
| Code hygiene | **B** — some duplication, one dead module, ephemeris path inconsistency |

**Bottom line:** The astrology engine is strong. The report pipeline is production-hardened. But **3 of the 5 most valuable personalized services (synastry, rectification, personal transits page) are fully built and sitting unused.** Wiring them is the highest-ROI work — zero new computation code needed, just API endpoints + UI + auth.