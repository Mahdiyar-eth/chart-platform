# QA Report — Comprehensive Platform Verification (Zayche)

**Date:** 2026-08-21 · **Scope:** user + admin flows, item-by-item, real browser + vision
**Environment:** throwaway QA instance (127.0.0.1:8798) on **isolated** `chart_platform_qa` DB, `ENRICH_INSIGHTS=0` (NO paid LLM), `OTP_DEV_MODE=true`. Prod (`chart.negar.io`) NOT modified.
**Base:** full suite **563 passed, 1 skipped** (no regression).

---

## What was verified (user flows — deterministic, no LLM)

| # | Flow | Result |
|---|------|--------|
| 1 | OTP login (dev code) → `/api/auth/me` returns user | ✅ |
| 2 | Plans list (`basic/full/gold/credit3/credit6/synastry`) | ✅ |
| 3 | Create birth chart (anonymous) | ✅ |
| 4 | Chart page renders (`چارت تولد تو`) | ✅ |
| 5 | Chart preview + transit SVG | ✅ |
| 6 | Buy plan (mock Zarinpal) → order `pending` | ✅ |
| 7 | Verify payment → order `paid` + **Report created** | ✅ |
| 8 | Report state + PDF + audio-status endpoints | ✅ (PDF/audio need artifacts) |
| 9 | Subscriptions list | ✅ |
| 10 | Coupon check — invalid code correctly 404 | ✅ |
| 11 | Notification prefs (get + update) | ✅ |
| 12 | Explore cards catalog | ✅ |
| 13 | Today + transits + `/transit/{id}` | ✅ |
| 14 | Synastry (free teaser, birth-fields) | ✅ |
| 15 | Chat page + access | ✅ |
| 16 | Account / Dashboard / **Explore page** | ✅ (Explore was the bug) |
| 17 | Logout | ✅ |

### Extra user/mixed API
| Flow | Result |
|------|--------|
| City search (`/api/cities?q=تهران`) | ✅ |
| Consent + wallet surfaces | ✅ |
| Insight share (A8) create → guest `/si/{token}` render | ✅ |
| Explore history + invalid card → 404 (no LLM) | ✅ |
| Web-push VAPID public key | ✅ |
| Chart image share + chat history + synastry/access | ✅ |
| Rectify / today-reflection **validation only** (no LLM) | ✅ |

## Admin flows
| Flow | Result |
|------|--------|
| Admin login → dashboard → stats/KPI/health/llm-cost | ✅ |
| Prompt save (known key) | ✅ |
| Secrets whitelist: set + reveal (benign key) | ✅ |
| CMS articles: list/create/get/update/delete | ✅ |
| CMS media upload → delete | ✅ |
| CMS revisions + restore | ✅ |
| **Refund lifecycle** (paid → refunded via Zarinpal mock) | ✅ |
| Coupon CRUD | ✅ |

## SEO / public pages
`/`, `/birth-form`, `/plans`, `/about`, `/faq`, `/articles`, `/learn`, `/guide`, `/signs/asad`, `/sky`, `/deep-report`, `/self-discovery`, `/sky-today`, `/privacy`, `/terms`, `/refund`, `/disclaimer`, `/contact`, `/sitemap.xml`, `/robots.txt` — **all 200**.

---

## Real bugs found + fixed (test-first proof)

1. **`/explore` crashed with `TypeError` (500 for every user)** — `page_explore` called `_safe_json(..., ensure_ascii=False)` but `_safe_json(obj)` only accepted one arg. **Fixed** `main.py` `_safe_json(obj, ensure_ascii=False, **kw)`. Proven: E2E test + real browser render (HTTP 200, 0 console errors) + vision confirms clean layout.
2. **`/si/{token}` (insight share) crashed on non-ASCII token** — `hmac.compare_digest(str, str)` fails on non-ASCII. **Hardened** to `.encode()` both (`main.py:1066,1102`). Robustness, no user-facing path normally hit it.

*(The explore "truncated card" flagged by the vision model was a vision OCR misread — verified `cards.py:31` source is complete.)*

---

## NOT fired (intentionally, to avoid paid-LLM cost / gateway saturation)
- Chat message generation (`/api/chat`, `/api/chat/stream`)
- Exploration generation (`/api/explore/{card_key}`)
- Full synastry / rectify / today-reflection (LLM-dependent)
- Audio (TTS) + PDF artifact generation

These are **logic-gated and validated** (route reachable, input validation correct, no crash, no 500), but the LLM generation itself was **not run** in tests. A real end-to-end generation test would spend paid tokens.

---

## Still PENDING (not done)
- **P2: unified credit model + gamification** — the «همهچیز کردیتی» and streak/XP/badge/referral suggestions are **not implemented yet**.
- LLM-gated generation end-to-end (needs real tokens — user approval).

## Artifacts
- E2E test: `tests/test_e2e_full_flows.py` (5 tests, ~all flows)
- Browser/vision script: `scripts/qa_browser_vision.py`
- Screenshots: `/root/chart-qa-screens/*.png` (28, mobile+desktop)
- Commit: `9c90b2a`

## Rollback
Fixes are small + additive; `git revert 9c90b2a` reverts cleanly.
