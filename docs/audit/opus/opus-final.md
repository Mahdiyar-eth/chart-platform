# ZAYCHE — FINAL CONSOLIDATED AUDIT REPORT

---

## 1. CONSOLIDATED FINDINGS TABLE

Deduplicated, P0/P1 retained, P2 summarized. Findings are numbered globally.

| # | SEV | Dimension | Summary | File(s) | Status |
|---|-----|-----------|---------|---------|--------|
| F-01 | **P0** | Backend | `asyncio.run()` inside sync endpoints under uvicorn raises `RuntimeError` — crashes `/readiness`, `_enqueue_report`, `_enqueue_audio` | `app/main.py:~120,310,620` | OPEN |
| F-02 | **P0** | Backend | `readiness()` creates sync `redis.Redis` per call, never closes — FD leak under k8s probes | `app/main.py:~115` | OPEN |
| F-03 | **P0** | Backend | `_arq_pool()` global bound to throwaway loop via `readiness()` — all subsequent async ARQ calls fail ("attached to a different loop") | `app/main.py:~300` | OPEN |
| F-04 | **P0** | Backend | `_cache_get()`/`_cache_set()` leak Redis connections on exception (no `try/finally`) | `app/main.py:~380-400` | OPEN |
| F-05 | **P0** | Report/LLM | `OmniProvider.complete()` calls abstract `super().complete()` — crashes on every Gemini-routed call | `app/core/llm.py:~475` | OPEN |
| F-06 | **P0** | Report/LLM | `asyncio.run()` in `generate_sections` (sync wrapper) and `chat_answer` — crashes when called from async context (ARQ worker, FastAPI) | `app/report/generator.py:89`, `app/chat/service.py:42` | OPEN (dup of F-01 pattern) |
| F-07 | **P0** | Security | OTP dev mode has no prod guard — `OTP_DEV_MODE=true` in prod leaks codes in response + logs, full auth bypass | `app/auth.py:~36` | OPEN |
| F-08 | **P0** | UI/XSS | `{{ w.text|safe }}` on LLM-generated weekly text — stored XSS | `app/templates/account.html:~68` | OPEN |
| F-09 | **P0** | UI/XSS | Admin CMS: article titles/slugs interpolated into `innerHTML` via template literals — DOM XSS | `app/templates/admin.html:~95-120` | OPEN |
| F-10 | **P0** | Tests | `conftest.py` docstring says "temp SQLite" but code uses hardcoded Postgres credentials — misleading + credential leak | `tests/conftest.py:12` | OPEN |
| F-11 | **P1** | Backend | `seed_plans()` uses session `s` AFTER `with` block exits — `SessionError` on coupon seeding | `app/db.py:~80-95` | OPEN |
| F-12 | **P1** | Backend | Year validation in `_compute_and_save_chart` doesn't distinguish Jalali/Gregorian ranges (1300-2100 for both) | `app/main.py:~195` | OPEN |
| F-13 | **P1** | Backend | `_dedupe_update` uses `set.pop()` (arbitrary eviction) instead of FIFO — dedup window re-opens | `app/main.py:~730` | OPEN |
| F-14 | **P1** | Backend | `account_delete` missing FK cascade deletes for: `LLMRun` (by user_id), `Exploration`, `ConsentLog`, `NotificationPrefs`, `PushSubscription`, `CreditTransaction` — will 500 with `IntegrityError` | `app/main.py:~860-920` | OPEN |
| F-15 | **P1** | Backend | `get_current_user(request)` called twice — TOCTOU race + wasted DB lookup | `app/main.py:~215` | OPEN |
| F-16 | **P1** | Backend | `BirthProfile.tz_name` never set — defaults to `"Asia/Tehran"` for all cities | `app/main.py:~210` | OPEN |
| F-17 | **P1** | Backend | `api_payment_verify` exposes internal exception messages (hostnames, IPs) in `order.error` | `app/main.py:~530` | OPEN |
| F-18 | **P1** | Backend | `admin_page` does `select(ChatMessage.id).all()` — loads ALL IDs into memory; OOM at scale | `app/main.py:~1000` | OPEN |
| F-19 | **P1** | Backend | Credit pack orders allowed without authentication — credits granted to no user | `app/main.py:~430` | OPEN |
| F-20 | **P1** | Report/LLM | Data race on shared `metrics` dict under `asyncio.gather()` — lost cost/token counts | `app/report/worker.py:~107-110` | OPEN |
| F-21 | **P1** | Report/LLM | `build_section_router` cached with `@lru_cache(maxsize=None)` — unbounded memory, stale circuit breakers, shared mutable `in_flight` counters | `app/core/llm.py:~726` | OPEN |
| F-22 | **P1** | Report/LLM | Prompt injection via `personal_question` — user can inject `</پرسش_کاربر>` closing tag | `app/report/prompt_builder.py:~237` | OPEN |
| F-23 | **P1** | Report/LLM | `prompt_overrides.get_overrides()` replaces entire prompt — can break JSON output format, losing QA structure | `app/report/worker.py:~96-98` | OPEN |
| F-24 | **P1** | Report/LLM | Weekly delivery commits `WeeklyReflection` BEFORE `send_message` — on send failure, message is permanently lost (never retried) | `app/report/weekly.py:~120-127` | OPEN |
| F-25 | **P1** | Report/LLM | `validate_section` sign case mismatch: `sign_of()` returns title-case from chart JSON, `extract_claims` normalizes to lowercase — false hallucination flags | `app/report/claim_validation.py:~65,100` | OPEN |
| F-26 | **P1** | Report/LLM | `house_of()` computes whole-sign houses but chart stores Placidus — validation flags correct placements as hallucinations | `app/report/claim_validation.py:~178` | OPEN |
| F-27 | **P1** | Security | CSRF origin check allows bypass when `Origin` header absent (older browsers, privacy extensions) | `app/security.py:~138-143` | OPEN |
| F-28 | **P1** | Security | Phone number not validated in `request_otp` — OTP to arbitrary international numbers (cost leak), Redis key injection | `app/auth.py:~107` | OPEN |
| F-29 | **P1** | Security | `pay_order_with_balance` doesn't grant credits for credit-pack plans, doesn't handle `yearly` subscription | `app/payment/orders.py:~401-420` | OPEN |
| F-30 | **P1** | Security | Zarinpal verify: no assertion that `amount_rial` comes from DB order (caller responsibility undocumented) | `app/payment/zarinpal.py:~73` | OPEN |
| F-31 | **P1** | Security | Bot webhook secret not verified for Bale; Telegram `X-Telegram-Bot-Api-Secret-Token` not checked in handler | `app/bots/handler.py:~30` | OPEN |
| F-32 | **P1** | Security | `reveal_secret` has no access control or audit logging at function level | `app/secret_store.py:~195` | OPEN |
| F-33 | **P1** | UI | Admin withdrawal forms missing CSRF token — CSRF on financial action | `app/templates/admin.html:~410` | OPEN |
| F-34 | **P1** | UI | Dev OTP code rendered in production login template via `x-show="devCode"` | `app/templates/account_login.html:~22` | OPEN |
| F-35 | **P1** | UI | `access_token` leaked in Telegram share URL — anyone with the link gets full chart access | `app/templates/chart.html:~148` | OPEN |
| F-36 | **P1** | UI | `{{ banner_svg | safe }}` — SVG injection vector (can contain `<script>`, `onload`) | `app/templates/article.html:~10` | OPEN |
| F-37 | **P1** | UI | Subscription cancel two-step broken: `$el.dataset.confirm` checks button's own dataset but `cancel()` sets it on parent row — confirm button never appears | `app/templates/account.html:~130` | OPEN |
| F-38 | **P1** | Report/LLM | `render_share_card` runs Chromium with `--no-sandbox` in production | `app/share/card.py:~67` | OPEN |
| F-39 | **P1** | Tests | Hardcoded `/root/chart-platform` path in `test_content_sweep_v4.py` — fails everywhere else | `tests/test_content_sweep_v4.py:22` | OPEN |
| F-40 | **P1** | Tests | `_FakeZarinpal.request()` returns mismatched authority in URL vs first tuple element | `tests/conftest.py:~44` | OPEN |
| F-41 | **P1** | Tests | DB credentials embedded in subprocess `-c` command string — visible in `ps aux` | `tests/test_owasp_extra_s9.py:~168` | OPEN |

### Notable P2 findings (summarized, not individually listed):

- Synastry timezone fallback to `"Asia/Tehran"` for non-Iranian cities (`main.py:~500`)
- `_num()` Persian-to-ASCII digit translation incomplete for Arabic-Indic `٠١٢٣٧٨٩` (`claim_validation.py:161`)
- `_is_uncertain_moon` false-positive on "ماه" (month vs Moon) (`claim_validation.py:213`)
- `extract_claims` drops multi-planet claims before a sign (`claim_validation.py:130`)
- `GoProvider.stream()` yields duplicate results (`llm.py:159`)
- `qa_section` re-evaluates full rule engine per section per attempt (91× per report) (`qa.py:120`)
- `_client()` creates new boto3 S3 client per call (`storage.py:42`)
- Fernet key derivation uses raw SHA-256, no stretching (`secret_store.py:100`)
- In-memory secret cache has no TTL (`secret_store.py:137`)
- `font-display:optional` causes FOIT on slow Iranian connections (`base.html`)
- No SRI on third-party analytics script (`base.html:22`)
- Report polling has no timeout/max-retry (`chart.html`)
- Chat quota not decremented client-side after send (`chat.html`)
- Alpine store double-init on admin plan rows (`admin.html:~280`)
- `clearSecret` button text permanently corrupted after use (`admin.html`)
- No test isolation via transaction rollback — systemic flakiness risk
- `swe.set_ephe_path` hardcoded; `FLG_SWIEPH | FLG_MOSEPH` contradictory in tests

---

## 2. PER-DIMENSION VERDICTS

### Architecture
**Rating: 🟡 CONDITIONAL**
The FastAPI + ARQ + Redis + Postgres stack is sound. The `asyncio.run()` anti-pattern (F-01, F-03, F-06) is systemic — it appears in readiness probes, report generation, chat, and audio. This is the single most pervasive architectural defect: the codebase straddles sync and async without a clean boundary. The ARQ pool global state binding (F-03) is a design flaw, not just a bug. Plan seeding has two sources of truth (main.py vs db.py). Account deletion cascade is incomplete by design omission (F-14).

### Backend Core
**Rating: 🔴 NOT READY**
Four P0 runtime crashes (F-01 through F-04), six missing FK cascade deletes (F-14), closed-session bug (F-11), and unauthenticated credit pack orders (F-19). The readiness probe — the thing k8s uses to decide if the pod is healthy — will crash on every invocation under uvicorn.

### Astrology Math
**Rating: 🟢 CORRECT**
Swiss Ephemeris usage is sound. Sidereal handling via manual ayanamsa subtraction avoids global state races. Element/modality counting is correct. DST handling via `zoneinfo` covers Iran's full history. Golden data test vectors are comprehensive. Moon phase calculation correctly cancels ayanamsa. The `_house_of` fallback to house 12 is a minor edge case (P2). The `tz_name` not being stored on `BirthProfile` (F-16) is a data integrity issue, not a math issue.

### Report / Chat / RAG Pipeline
**Rating: 🔴 NOT READY**
`OmniProvider` is completely broken (F-05) — if Gemini is the default or fallback model, no reports generate. The `asyncio.run()` pattern blocks sync paths (F-06). Claim validation has sign case mismatch (F-25) and whole-sign vs Placidus house mismatch (F-26), causing false hallucination flags that trigger unnecessary retries (wasting LLM budget). Prompt injection via XML tag escape (F-22) is partially mitigated but not closed. Weekly delivery commit-before-send (F-24) permanently loses messages on send failure.

### Security
**Rating: 🔴 NOT READY**
**Strengths:** IDOR protections are thorough with `compare_digest`; payment state machine is well-designed; OTP uses hashed codes with TTL and attempt limits; HMAC cookies are properly signed; webhook auth uses `compare_digest`.
**Blockers:** OTP dev mode has no prod guard (F-07, P0); phone not validated (F-28); CSRF bypassable when Origin absent (F-27); credit-pack wallet-pay doesn't grant credits (F-29); bot webhook signatures not verified (F-31); `reveal_secret` has no access control (F-32); XSS via `|safe` on LLM output (F-08, P0) and admin CMS (F-09, P0).

### Payment
**Rating: 🟡 CONDITIONAL**
Atomic coupon reservation, advisory locks on payment verify, idempotent Zarinpal handling (101 status), and "never mark failed on network error" are all well-designed. **Blockers:** `pay_order_with_balance` doesn't grant credit packs or yearly subscriptions (F-29) — users pay but receive nothing. Zarinpal amount verification relies on caller discipline with no assertion (F-30).

### UI/UX (Mobile RTL)
**Rating: 🔴 NOT READY**
Three XSS vectors (F-08, F-09, F-36), missing CSRF on admin financial forms (F-33), broken subscription cancel flow (F-37), access token leaked in share URLs (F-35), dev OTP code renderable in production (F-34). SEO is good (proper robots directives, OG tags, structured data). RTL layout is mostly correct with minor direction issues.

### Bots
**Rating: 🟡 CONDITIONAL**
Webhook auth not verified (F-31). Bot user identity conflated with Telegram `chat_id` (not a real DB user) — creates orphan orders with fake `user_id`. `answer_callback` called twice in some paths (noise). Core bot flow (chart creation, subscription) works but lacks proper user identity management.

### SEO
**Rating: 🟢 GOOD**
Proper `noindex,nofollow` on private pages. JSON-LD WebSite schema present. OG tags complete. Canonical URLs set. Minor: duplicate `og:type` and `theme-color` meta tags.

### Tests / Deploy
**Rating: 🟡 CONDITIONAL**
Excellent coverage breadth (IDOR, OWASP, ownership, CSRF, rate limiting, budget gates, coupon atomicity, LLM circuit breakers, astrology cross-checks). **Issues:** Misleading conftest docstring (F-10, P0); hardcoded paths and credentials (F-39, F-41); no transaction-based test isolation (systemic flakiness); contradictory ephemeris flags in cross-checks.

### Cost
**Rating: 🟢 GOOD with caveats**
Chat quota is atomic (Redis INCR). Exploration refunds on failure. Preview caching prevents repeat LLM calls. Daily/monthly/per-report/per-user budget ceilings well-implemented. **Leaks:** QA re-evaluates rules 91× per report (P2); `metrics` race loses cost tracking data (F-20); streaming cost underreported (prompt tokens always 0); boto3 client created per call (P2); phone validation gap enables OTP cost abuse (F-28).

---

## 3. TOP 10 CRITICAL ISSUES (RANKED)

| Rank | Finding | Why Critical |
|------|---------|-------------|
| **1** | **F-05: OmniProvider crashes on every call** | If Gemini is default/fallback, **zero reports generate**. Complete feature outage. |
| **2** | **F-01/F-03: `asyncio.run()` in readiness probe** | k8s health check crashes → pod marked unhealthy → restart loop → **zero availability**. |
| **3** | **F-07: OTP dev mode no prod guard** | Single env var misconfiguration = **complete authentication bypass** for all users. |
| **4** | **F-08/F-09: Stored XSS via `\|safe`** | LLM-generated content rendered as raw HTML → **account takeover** via stored XSS on weekly text and admin CMS. |
| **5** | **F-14: Account deletion missing 6 FK cascades** | Every `account_delete` call **500s with IntegrityError** for any user with explorations, consent, notifications, push subs, or credit transactions. GDPR compliance failure. |
| **6** | **F-29: Wallet-pay doesn't grant credit packs** | Users pay real money from wallet balance, **receive nothing**. Revenue-destroying bug. |
| **7** | **F-11: `seed_plans()` uses closed session** | App startup **crashes on coupon seeding** — may prevent boot entirely. |
| **8** | **F-27/F-33: CSRF gaps** | Admin withdrawal approval (financial action) has no CSRF protection. Origin-absent bypass on all state-changing endpoints. |
| **9** | **F-35: Access token in share URL** | Every Telegram share leaks the **full-access capability token** to all recipients and Telegram's link preview servers. |
| **10** | **F-28: Phone number not validated** | Arbitrary international OTP sends = **unbounded Kavenegar cost**; Redis key injection possible. |

---

## 4. FINAL VERDICT

### **NO — NOT LAUNCH-READY**

**Exact blockers (must fix before any production traffic):**

1. **F-05** — `OmniProvider.complete()` calls abstract `super()`. Remove the call. (5-minute fix)
2. **F-01/F-03/F-06** — `asyncio.run()` pattern. Make readiness/enqueue endpoints `async`; remove `asyncio.run()` wrappers. (2-hour fix)
3. **F-07** — Add `if IS_PROD and _OTP_DEV_MODE: raise RuntimeError(...)`. (1-line fix)
4. **F-08** — Remove `|safe` from `{{ w.text|safe }}` in `account.html`. (1-line fix)
5. **F-09** — Escape admin CMS template literal interpolations with `textContent` or an `esc()` helper. (30-minute fix)
6. **F-14** — Add cascade deletes for `LLMRun`, `Exploration`, `ConsentLog`, `NotificationPrefs`, `PushSubscription`, `CreditTransaction` in `account_delete`. (1-hour fix)
7. **F-29** — Add credit-pack and yearly-subscription handling in `pay_order_with_balance`. (30-minute fix)
8. **F-11** — Move coupon seeding inside the `with Session` block. (5-minute fix)
9. **F-02/F-04** — Add `try/finally` with `r.close()`/`r.aclose()` on Redis connections. (15-minute fix)

**Estimated total fix time for blockers: ~5 hours of focused engineering.**

After these 9 blockers are resolved, the system is **CONDITIONAL** — the P1 issues (CSRF gaps, phone validation, webhook auth, access token in share URLs, prompt injection, claim validation mismatches) should be addressed within the first week post-launch with a security-focused sprint.

---

## 5. AI RECOMMENDATIONS

### Model Routing
- **Fix OmniProvider immediately** (F-05). Once fixed, use Gemini 2.0 Flash for high-volume section generation (cost-effective, fast) and reserve DeepSeek for complex domains (synastry, rectification) where reasoning depth matters.
- **Remove `@lru_cache` from `build_section_router`** (F-21). Build routers per-request — construction is cheap; stale circuit breaker state is expensive (cascading failures when a provider recovers but the cached breaker stays tripped).
- **Pre-compute QA rule evaluation once per report** and pass active factors to `qa_section` — eliminates 90 redundant evaluations per report (F-17 in dim-2), saving ~200ms latency and reducing CPU.

### Personalization
- **Store `tz_name` on `BirthProfile`** (F-16) — this unlocks timezone-aware "Today" features, transit timing, and localized daily horoscopes without re-resolving timezone on every request.
- **Fix claim validation case normalization** (F-25) and **house system alignment** (F-26) — these currently cause false hallucination flags that trigger unnecessary LLM retries, wasting ~15-30% of section generation budget on phantom QA failures.
- **Implement per-user model preference tracking**: log which model produced the highest user engagement (report shares, chat follow-ups, exploration completions) per domain, and use this signal to route future requests. The `LLMRun` table already captures provider/model — add a `user_rating` column and feed it back into router selection.

### Cost Control
- **Phone validation** (F-28) is also a cost control measure — without it, an attacker can drain the Kavenegar SMS budget by sending OTPs to premium international numbers.
- **Cap `GoProvider.stream()` duplicate yields** (P2) — the double-yield sends 2× tokens to SSE clients, doubling bandwidth for streaming responses.
- **Cache boto3 S3 client** — creating a new client per presigned URL call adds ~50ms latency and connection pool churn under load.