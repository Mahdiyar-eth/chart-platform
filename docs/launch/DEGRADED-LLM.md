# ZAYCHE — رفتار سیستم وقتی LLM در دسترس نیست (Degraded Mode)

> تاریخ: 2026-08-16 · قانون: نقد بازبینی خبره (ChatGPT) — هیچ خروجی جعلی/ساکت در حالت degraded
> این سند رفتار **واقعی** کد را شرح میدهد (هر ادعا با مسیر کد + تست).

## ۱) سطح‌ها و وضعیت‌ها

| وضعیت گزارش | معنی | چه زمانی ست می‌شود |
|---|---|---|
| `done` | کامل + R2 + بدون fallback | همهٔ بخش‌ها QA پاس شدند (`worker.py:260`) |
| `degraded` | تحویل‌شدنی ولی ناقص | هر یک از مسیرهای پایین |
| `failed` | غیرقابل تحویل | خطای غیرقابل بازیابی (`worker.py:262`) |
| `queued`/`running` | در صف/در حال تولید | ARQ |

## ۲) مسیرهای degraded

1. **LLM پایین/خطا (بعد از ۶ تلاش MAX_RETRIES):** بخش fail شده با intro صادقانهٔ fallback تولید می‌شود
   (`worker.py:138-151`) — نه تحلیل ساختگی؛ `metrics.fallback_domains` پر می‌شود و در `worker.py:255-258`
   گزارش `degraded` می‌شود با پیام فارسی: «بخش‌های ناقص (fallback): …».
2. **R2 (Cloudflare) برای آپلود در دسترس نیست (فقط prod):** `worker.py:249-253` — گزارش هرگز ساکت
   محلی تحویل داده نمی‌شود (دیسک لوکال ephemeral است): `degraded` با پیام آپلود ناموفق.
3. **Redis پایین:** rate-limit و سهمیهٔ روزانه چت به DB-count fallback می‌رود (`main.py:1481-1485`).
4. **هر dependency پایین (DB/Redis/LLM):** `GET /readiness` → `degraded` و بنر قرمز degری در تمام صفحات
   (`base.html:316-341` — `#degradedBar` poll هر ۳۰ ثانیه).

## ۳) چت (fail-closed)

وقتی پاسخ LLM در دسترس نیست: هیچ پاسخ ساختگی داده نمی‌شود (fail-closed، خطای فارسی واضح).
سهمیهٔ روزانه با DB-count fallback شمارش می‌شود تا کاربر نتواند با پایین بودن Redis محدودیت را دور بزند
و نباید بی‌دلیل بسته شود.

## ۴) Today / بینش روزانه

`/api/today` کاملاً deterministic است (بدون LLM) — در degraded همیشه کار می‌کند.
این عمدی است: بنر degraded هنگام قطع LLM نمایش داده می‌شود ولی امروز قطع نمی‌شود.

## ۵) Observability

- هر تلاش LLM در `llm_runs` ثبت می‌شود (ok/error/latency/cost) — مترینگ **هرگز** تولید را نمی‌شکند (`worker.py:82`).
- دلایل QA-reject به لاگ worker می‌رود (`worker.py:94-97`).
- ادمین: شمارندهٔ `degraded`/`failed` + DLQ + لاگ error + هزینهٔ LLM (KPI matrix A7 و llm-cost panel).
- Re-queue از ادمین روی degraded مجاز است (همان ردیف، بدون داپلیکیت — `admin.py` و تست A11).

## ۶) تست‌ها (`tests/test_degraded_llm_p12a11.py` — 3 تست)

1. `test_llm_down_report_becomes_degraded_not_done` — provider کاملاً down → degraded (نه done جعلی)،
   intro های fallback صادقانه، PDF هنوز ساخته می‌شود.
2. `test_llm_down_requeue_still_degrades_after_retry` — re-queue در حالت down → دوباره degraded (هرگز done).
3. `test_degraded_requeue_endpoint_allowed` — admin regenerate روی degraded → queued (همان ردیف، بدون داپ).
