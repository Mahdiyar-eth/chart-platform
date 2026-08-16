# پلن جامع ZAYCHE — Multi-Provider LLM (چند API همزمان) + بستن مشکلات باقیمانده

> نسخه: 1.0 · تاریخ: 2026-08-16 · وضعیت: پیشنهادی (منتظر تأیید)
> این سند مستقل است — قابل ارسال مستقیم برای بازبینی AI دیگر.

---

## ۱) تشخیص — چرا AI Benchmark «فاجعه» بود و مشکلات واقعی چیست

### ۱.۱ ریشهٔ کندی (راستیآزماییشده با کد و اجرا)
| # | مشکل | شواهد |
|---|---|---|
| R1 | **تک API key** — کل سیستم فقط `GO_API_KEY` دارد (یک کلید = یک سهمیهٔ ۵ساعتهٔ GO) | app/core/llm.py:261 — `get_secret("go_api_key", "GO_API_KEY", "")` |
| R2 | **محدودیت GO واقعاً ۵ ساعت غلتان است** — بعد از سقف، درخواستها block میشوند | opencode.ai/docs/go: «The 5-hour limit resets on a rolling basis»؛ تست ما: HTTP 200 با **text خالی** (rate-limit خاموش) |
| R3 | **بازگشت روی کلید شکستخورده** — retry با backoff 12/24/36s روی همان کلید | scripts/ai_benchmark.py `_answer(retries=3)` — هر پاسخ خالی ~۱۴-۶۰s تلف میکند |
| R4 | **همزمانی پایین** — benchmark با CONC=2؛ worker گزارشها را **ترتیبی** تولید میکند (۱۳ بخش پشت سر هم، هر بخش ۵-۱۵s → ~۴۸s) | worker.py `for domain in prompts` (ترتیبی)؛ `max_jobs=4` فقط ۴ گزارش همزمان |
| R5 | timeout بلند ۱۲۰s + deadline ۱۵۰s → هر call ناموفق ~۲ دقیقه صبر میکند | llm.py:74-75 |
| R6 | fallback واقعی وجود ندارد — کلاس `DeepSeekProvider` هست (llm.py:150) ولی کلید در `.env` نیست | build_router → فقط GoProvider با کلید |

### ۱.۲ مشکلات باقیماندهٔ قبلی (از CHATGPT-REVIEW-v2 + موارد جدید)
| # | مشکل | نوع |
|---|---|---|
| B1-B5 | ۵ فعالسازی محیطی: مرچنت واقعی زرینپال / کلید کاوهنگار / گوشی فیزیکی / push واقعی / Search Console | بلوکر — نیازمند کاربر |
| P1 | کوپن تست prod `RACECOUP1786784851` باید حذف شود | پاکسازی (۲ دقیقه) |
| P2 | گزارش قدیمی qa5b chart3 (fallback career) در صف مانده | پاکسازی (۲ دقیقه) |
| P3 | LLM latency ~۴۸s برای گزارش کامل → UX ضعیف | برطرف میشود با M3 (موازیسازی) |
| P4 | GO روزها پاسخ خالی → گزارشها degraded میشوند | برطرف میشود با M1+M2 (پول کلید + fallback) |
| P5 | restore drill فقط روی scratch DB انجام شد — drill مستقل روی نمونهٔ real-like با دادهٔ جدید لازم است | تکمیل M7 |
| P6 | pyright 155 خطای type-only (gate نیست) | اختیاری/پایین |

---

## ۲) یافتههای تحقیق (وب + GitHub + مستندات رسمی)

### ۲.۱ واقعیتهای پلن GO (opencode.ai — منبع رسمی)
- GO = $۱۰/ماه، «aim to give you 6x that in usage».
- **سقف ۵ ساعت غلتان** (rolling 5-hour window) — بعد از سقف، درخواستها **بلاک** میشوند تا پنجره جابجا شود.
- گزینهٔ «Use balance» — بعد از سقف GO به Zen balance برگردد (اگر اعتبار دارد).
- **نکتهٔ کلیدی:** هر کلید API جداگانه، سهمیهٔ ۵ساعتهٔ **مستقل** دارد → با N کلید، توان همزمان ~N برابر میشود. (چند کلید = چند workspace/member در opencode.ai — از داشبورد zen قابل ساخت.)
- مدلها: deepseek-v4-pro / deepseek-v4-flash (و ۱۶ مدل دیگر در کاتالوگ zen).

### ۲.۲ الگوهای صنعت (GitHub + docs)
| الگو | منبع | اصل کلیدی |
|---|---|---|
| **Credential Pool** (چند کلید برای همان provider، چرخش برای رد شدن از rate-limit) | گاید Hermes multi-model routing (fast.io) — «pools rotate multiple API keys for the same provider» | استاندارد صنعت برای resilience |
| **Key rotation + failover** — چرخش round-robin، 429-aware، circuit breaker per key | github.com/xiaozhe7772222/dsh-api-key-pool · github.com/genoshide/infinity-router | هر کلید health مستقل دارد؛ کلید بد = cooldown منفرد |
| **Load balancing + cooldown + fallback** (weighted routing، allowed_fails → cooldown TTL، retries) | docs.litellm.ai/docs/routing | همان منطق با تنظیم سبک برای پروژهٔ ما (لازم نیست کل litellm را بیاوریم — معماری فعلی httpx ساده است) |
| **Per-slot routing** — هر نوع تسک به provider/model/کلید مخصوص | Hermes auxiliary slots (۸ اسلات مستقل) | دقیقاً همان «هر بخش به کدام LLM» که خواستی |
| **Multi-worker async queue** — max_jobs/مقیاس همزمانی | arq (python-arq) | worker فعلی درست است؛ فقط بخشهای داخل گزارش باید موازی شوند |
| DeepSeek direct API (fallback پولی) — قیمت peak/off-peak، flash ارزان | api-docs.deepseek.com (2026) | گزینهٔ fallback واقعی خارج از GO |

**نتیجهٔ تحقیق:** راهحل ترکیبی استاندارد = (۱) **KeyPool** برای چند کلید GO، (۲) **SectionRouter** برای per-section routing، (۳) **موازیسازی بخشها** داخل گزارش، (۴) **fail-fast** + cooldown منفرد، (۵) fallback اختیاری DeepSeek. هیچکدام به لایبرری سنگین جدید نیاز ندارند — با همان لایهٔ httpx فعلی قابل پیادهسازی است (کد کمتر، تستپذیرتر).
---

## ۳) معماری پیشنهادی — ۶ ماژول (M1-M6) + ۱ دریل (M7)

### M1 — KeyPool (چند کلید GO همزمان) — هستهٔ اصلی
- `.env` → `GO_API_KEYS=k1,k2,k3` (کاما-جدا) با backward-compat `GO_API_KEY` (کلید اول).
- کلاس جدید `KeySlot`: {key, error_streak, tripped_until, in_flight, last_latency_ms}.
- **انتخاب کلید:** کمترین `in_flight` + سالم (وزندهی به latency) → درخواستهای همزمان روی کلیدهای مختلف توزیع میشوند.
- **هر کلید circuit breaker مستقل:** 429/empty/5xx → `error_streak++` → بعد از ۳ → cooldown ۶۰s فقط برای همان کلید (کلیدهای سالم ادامه میدهند — R3 حل میشود).
- **تشخیص «پاسخ خالی 200»:** بعد از complete، اگر `text.strip()==""` → همان رفتار error (این دقیقاً رفتار GO بود — R2 حل میشود).
- **مدیریت از پنل ادمین:** secret `go_api_keys` (ویرایش بدون رستارت — الگوی فعلی secret store) — کلیدها را از همان پنل ادمین اضافه/حذف میکنی.

### M2 — SectionRouter (هر بخش گزارش → کدام LLM)
جدول static + override از پنل ادمین (الگوی فعلی `{part}_llm_model` تعمیم مییابد):

| بخش گزارش | مدل پیشفرض | چرا |
|---|---|---|
| career · love · finance (کیفیت-حساس) | deepseek-v4-**pro** | عمق تحلیل = فروش |
| summary · intro · energy · daily · health · family · travel · spiritual (سبک) | deepseek-v4-**flash** | سرعت + هزینهٔ کمتر |
| chat · preview | deepseek-v4-flash | فعلی |
- فرمت secret: `sec_{name}_model` + `sec_{name}_provider` + `sec_{name}_pool` (مثلاً go-main / go-flash / deepseek).
- زنجیرهٔ fallback: کلید ۱ → کلید ۲ → … → DeepSeek (اگر کلید هست) → **degraded** (همان fail-closed فعلی — A11 حفظ میشود).
- کد: `LLMRouter` فعلی → `build_section_router(section)` — API بیرونی تغییر نمیکند (همان `router.complete`).

### M3 — تولید موازی بخشها (latency ~۴۸s → ~۱۵-۲۰s)
- `generate_sections_async`: ۱۳ بخش با `asyncio.gather` + `Semaphore(SECTION_CONC=4)` — بخشهای مستقل همزمان اجرا میشوند.
- ترتیب نهایی خروجی حفظ میشود (dict به همان ترتیب) → PDF/UI بدون تغییر.
- ARQ `max_jobs=4` میماند؛ توان کل با ۳ کلید ≈ ۴ گزارش × ۴ بخش موازی — بدون فشار به کلید (هر کلید حداکثر همزمانی تنظیمشده دارد).
- QA + fallback + degraded زنجیرهٔ فعلی دستنخورده.

### M4 — AI Benchmark سریع (همان ۱۰ معیار، سریعتر)
- تغییرات `scripts/ai_benchmark.py`: CONC=2→**۶** · timeout ۱۲۰s→**۶۰s** · **empty-response → فوراً کلید بعدی** (بدون backoff ۱۲/۲۴/۳۶) · resume موجود.
- تخمین: ۵۲ چارت × ۳ سؤال ÷ ۶ همزمان با ۲-۳ کلید ≈ **۱۰-۱۵ دقیقه** (قبلاً با ۱ کلید ساعتها).
- امتیازدهی/گیتها/rubric دستنخورده (استاندارد قبلی حفظ میشود).

### M5 — Telemetry (قابل مشاهده در KPI)
- migration سبک: `llm_runs` + ستونهای `key_slot`, `section`, `pool` (nullable).
- `health_report()` → وضعیت per-key (healthy/cooldown/in_flight/latency/error_rate).
- پنل KPI: خطای per-key + توزیع مدل per-section.

### M6 — تستها (hermetic، بدون کلید واقعی)
- `test_keypool.py`: چرخش round-robin · انتخاب کمترین in_flight · cooldown منفرد بعد از ۳ خطا · کلید سالم از cooldown جدا · **empty-200 → retry کلید بعدی** · backward-compat GO_API_KEY.
- `test_section_router.py`: بخش career→pro، summary→flash · override admin · fallback زنجیره → degraded.
- `test_parallel_sections.py`: ۱۳ بخش mock با sleep → زمان ~max نه sum · ترتیب خروجی حفظ · Semaphore رعایت.
- `test_benchmark_speed.py`: ۵۲ چارت mock (latency ساختگی ۵s) → کل اجرا < ۳ دقیقه (گیت سرعت).

### M7 — Drill استقلالی restore (تکمیل A5)
- بکاپ تازه → restore به DB scratch → migration → boot → login → ساخت **چارت/گزارش جدید** → RAG chunk جدید → تأیید خواندن — بهعنوان cron هفتگی (یکشنبه ۰۴:۳۰).

---

## ۴) گامهای اجرا (به ترتیب)

| گام | ماژول | تحویل | تخمین |
|---|---|---|---|
| 1 | M1 | KeyPool + تستها | ~۳ ساعت |
| 2 | M2 | SectionRouter + تستها | ~۲ ساعت |
| 3 | M3 | بخشهای موازی + تست | ~۲ ساعت |
| 4 | M4 | benchmark سریع + اجرای کامل ۵۲ | ~۱ ساعت |
| 5 | M5 | migration telemetry + پنل | ~۱ ساعت |
| 6 | M6 | همهٔ تستها + رگرسیون کامل | ~۱ ساعت |
| 7 | M7 | drill هفتگی + cron | ~۱ ساعت |
| 8 | — | deploy + P15 report + ارسال به تلگرام | ~۳۰ دقیقه |

**مجموع: ~۱۱-۱۲ ساعت کار موثر** (بدون انتظار برای اجرای شبانه).

---

## ۵) چه چیزهایی از تو لازم است (بخش کاربر)

1. **حداقل ۲-۳ کلید GO** از داشبورد opencode.ai (zen workspace → چند member/workspace، هرکدام کلید مستقل با سهمیهٔ ۵ساعتهٔ جدا). اگر حساب اجازه نداد، با همان ۱ کلید هم کار میکند (فقط موازیسازی بخشها) ولی پول خیلی کمتر میشود. — این را قبل از گام ۱ میخواهم؛ بدون کلید دوم، M1/M4 نصف اثر دارند.
2. **(اختیاری) کلید DeepSeek API** (پلتفرم deepseek.com) بهعنوان fallback پولی — حدوداً ارزان (flash) — تصمیم با تو.
3. تایید این پلن (یا نسخهٔ اصلاحشده بعد از ادغام با پلن ChatGPT).

---

## ۶) معیارهای پذیرش

- ۵۲ چارت benchmark < ۲۰ دقیقه با ۲ کلید (گیت سرعت).
- گزارش کامل تولیدی: latency < ۲۵s (از ~۴۸s).
- صفر گزارش degraded در ۲۴ ساعت اول بعد از deploy (با ۲ کلید) — در KPI قابل مشاهده.
- همهٔ تستها سبز (۴۹۰+ تست فعلی + ~۱۵-۲۰ تست جدید).
- حفظ: fail-closed (A11)، ۱۰ معیار benchmark (A1)، circuit breaker (B9)، degraded banner — هیچکدام ضعیف نمیشوند.

---

## ۷) ریسکها و ملاحظات

- **چند کلید GO در یک حساب:** سقف ممکن است per-account باشد نه per-key (مستندات صریح نیست) — ریسک متوسط؛ با تست ۲ کلید در گام ۱ راستیآزمایی میشود؛ اگر سقف مشترک بود، گزینهٔ zen balance (Use balance) یا DeepSeek direct فعال میشود.
- **هزینهٔ DeepSeek direct:** fallback فقط — سقف ماهانهٔ خودکار (مثلاً $۵) در secret برای جلوگیری از غافلگیری.
- **موازیسازی بخشها:** ترتیب/کیفیت خروجی بدون تغییر (گارانتی با تست M3).
- **تغییر در llm.py:** API عمومی (`complete`/`stream`) ثابت میماند — مصرفکنندهها (worker/chat/explore/bot) تغییر نمیکنند.

---
**نکته:** منتظر پلن ChatGPT هستم — بعد از دریافت، این سند با آن ادغام میشود (افزودن/حذف موارد در صورت نیاز) و نسخهٔ نهایی برای اجرا ارسال میشود.
