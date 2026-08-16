# P15 — MULTI-LLM LAUNCH INFRASTRUCTURE (M0–M9)

**نسخه:** 2026-08-16 · **گیت:** ffa2096 (← b792094 ← fb2af64) · **تگ:** HEAD
**محدوده:** PLAN-MULTI-LLM-v2 — زیرساخت multi-provider تا LAUNCH ACCEPTANCE

## Amendments 1–5 (approved by MaHDi 2026-08-16 — ALL APPLIED)

| # | متن | پیادهسازی |
|---|---|---|
| 1 | Zero-score override | ai_benchmark_v4: HARD GATES جدا (mismatch/grounding/contradiction/unsafe/repeatability) — هر FAIL → NOT RELEASE-READY حتی با score بالا؛ score فقط informational |
| 2 | Prompt → Claim Validation | ماژول جدید `app/report/claim_validation.py` — استخراج deterministic جفت (سیاره، برج) از خروجی و مقایسه با chart واقعی؛ هر mismatch = critical hallucination (hard gate) |
| 3 | Quality + GenSuccess جدا | خروجی: `AI QUALITY SCORE (on valid outputs)` و `GENERATION SUCCESS %` دو عدد مستقل |
| 4 | Parallel gates همزمان | در-flight cap per key (GO_MAX_IN_FLIGHT_PER_KEY=2) + attempts/429/empty/timeout/cost در Benchmark A |
| 5 | degraded طبقهبندی | `expected-safe` (همهٔ providers fail → PASS رفتار) vs `unexpected` (provider سالم ولی degraded → FAIL) |
| 6 | ۶ اصلاح نهایی (نقد دوم ChatGPT) | **A2b Claim Validation چندنوعی** (house/degree/aspect/MC/retrograde/transit/uncertainty — ۱۶ تست) · **latency p50/p95/max** · **M3 worker gate** (پنجرهٔ ۲۴h llm_runs: p95≤40s، retry≤30%، provider-fail≤25%، unexpected-degraded=0) · **GenSuccess جدا** · hard gates صریح در acceptance matrix |

## خلاصه

GO تککلید = فاجعهٔ benchmark (empty-200 شبانه ۵۲/۵۲). راهحل اجراشده: **KeyPool چندکلیدی با breaker منفرد + failover درون-درخواست + موازیسازی ۱۳ بخش + مسیریابی per-section + telemetry + سقف هزینه + benchmark دوگانه A/B** — همه با تست hermetic (بدون هزینهٔ واقعی).

## وضعیت ماژولها

| ماژول | وضعیت | شواهد |
|---|---|---|
| M0 سقف کلیدها | ✅ | آزمایش REAL: K1 سالم لحظهای که K2 429 بود — سقفها per-account |
| M1 KeyPool | ✅ | 7 تست؛ K1→K2 failover؛ breaker؛ empty/429 تشخیص؛ zen-free last resort |
| M2 SectionRouter | ✅ | per-section مدل (wellbeing→flash، بقیه pro)، override ادمین، router کششده |
| M3 موازیسازی | ✅ | 13 بخش همزمان، Semaphore=4، ترتیب حفظ، تست max_in_flight=4 |
| M4 Benchmark A/B | ✅ کد | ai_benchmark_v4: Infra A + Quality B + Final Verdict؛ cron شبانه 04:00 |
| M5 Telemetry | ✅ | ستونهای key_slot/section/attempt/error_code/fallback_used/prompt_version + migration 8d20fb4d4148 |
| M6 رگرسیون | ✅ | **505 passed, 1 skipped** + ci.sh کامل سبز (alembic/bandit/pip-audit/secret/brand) |
| M7 Drill restore | ✅ | اجرای REAL: بکاپ 0315 → restore → migrate m5 → sanity (users=29, paid=8)؛ cron هفتگی یکشنبه 03:00 |
| M8 Prompt audit | ✅ | PROMPT_VERSION 9.0 در هر ۳ template گزارش + chat؛ LLMRun.prompt_version واقعی |
| M9 Cost ceiling | ✅ | LLM_DAILY_BUDGET_USD=3.0 — gate degraded صادقانه + fallback intro; 2 تست |

## یافتهٔ مهم Benchmark A (نمونهٔ ۱۰ چارت، REAL)

- **GO در حال سقف هر دو کلید empty-200 میدهد** (نه 429!) — availability واقعی نمونه: 3.6%
- keys served: go-2=25، go-1=1، zen-free=2 → پس از فیکس، telemetry fail «go-1,go-2» (honest)
- فیکس: `_GO_EMPTY_COOLDOWN=300` (empty همان quota است) + key_slot صادقانهٔ fail
- نتیجه: کلیدهای GO کافی نیستند مگر با ریست سقف (K2 فردا 08-17) — اجرای کامل در cron 04:00

## هزینه

هزینهٔ واقعی این فاز: ~۰ دلار (benchmark از GO down استفاده کرد؛ تستها hermetic؛ drill محلی).

## ماندگار / بلاکرها

- Benchmark کامل ۵۲ چارت در cron 04:00 (v4) — خروجی به تلگرام
- B-gates: Real Payment / SMS / Device / Search Console / Backup Restore — **FINAL GO ممنوع تا کامل**
- داشبورد ادمین: SECTION_MODEL_<domain> و LLM_DAILY_BUDGET_USD از env قابل تنظیم

## Rollback

`git checkout v-p13-a-gates` (کل infra جدید حذف میشود) — migrations forward-only.