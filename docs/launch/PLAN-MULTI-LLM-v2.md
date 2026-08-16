# پلن جامع ZAYCHE v2 — Multi-Provider LLM + کیفیت AI + زیرساخت

> نسخه: 2.0 · تاریخ: 2026-08-16 · جایگزین v1 · وضعیت: پیشنهادی (منتظر تأیید)
> این سند حاصل ادغام: پلن v1 Hermes + نقد ChatGPT (خطبهخط راستیآزماییشده) + تحقیق تکمیلی وب/GitHub.

---

## ۰) راستیآزمایی نقد ChatGPT (چه قبول شد، چه رد شد — با شواهد)

| ادعای ChatGPT | راستیآزمایی | حکم |
|---|---|---|
| «۱۹ empty response» | ✅ دقیقاً ۱۹ (از ۵۲ ردیف /tmp/ai_bench_results.jsonl: 33 ok با متن + 19 خالی) | قبول |
| «حتی با ۳۳ پاسخ واقعی، repeatability 40%» | ✅ از اجرای قبلی rubric — معتبر | قبول |
| «N keys = N quotas تضمینشده نیست» | ✅ مستندات رسمی صریح نیست؛ Reddit/GitHub: هر ورکاسپیس کلید خودش را دارد، سقف per-account محتمل است | قبول — **آزمایش تجربی M0** |
| «provider و quality باید جدا شوند» | ✅ درست — Benchmark A/B | قبول |
| «repeatability باید critical-fact باشد» | ✅ درست | قبول |
| «SectionRouter نیاز به A/B دارد» | ✅ درست (با حجم تعدیلشده: ۳۰ کیس کافی) | قبول |
| «fallback نباید quality gate را دور بزند» | ✅ درست — کد فعلی degraded از QA میگذرد؛ صریح میشود | قبول |
| «Telemetry + prompt_version» | ✅ درست — جدول prompt_versions از قبل هست | قبول |
| «M8 Prompt Engineering Audit» | ✅ درست — اضافه شد | قبول |
| «adaptive concurrency» | ✅ درست — نسخهٔ ساده | قبول |
| «استفاده از Zen balance بهجای چند کلید» | ⚠️ **نیمهدرست** | قبول مشروط — بهعنوان گزینهٔ M9 مقایسه میشود، نه جایگزین |
| «فعلاً کلید نده» | ⚠️ ناقص | **اصلاح: ۲ کلید (یکی از هر اکانت) لازم است برای M0** — همانهایی که داری؛ بدون آنها M0 ممکن نیست |

**نتیجه:** ۱۱ ادعا قبول، ۱ مشروط، ۱ اصلاح. هیچ ادعایی رد نشد — نقد ChatGPT دقیق و سازنده بود.

---

## ۱) کشف جدید مهم (بعد از v1)

اجرای cron شبانهٔ 04:00 (که فکر میکردیم ساعات کمبار GO است): **هر ۵۲ درخواست خالی برگردانده شد** (۱۹ مورد قبلی + ادامه، همه empty). یعنی:
- مشکل **فقط «ساعت روز» نیست** — GO در این دوره بهصورت گسترده پاسخ خالی میدهد (ظرفیت/سقف).
- **single-provider در شرایط فعلی غیرقابل اتکاست** — این دقیقاً استدلال اصلی برای M1+M9 است.

---

## ۲) معماری — M0 تا M9

### M0 — آزمایش تجربی سقف کلیدها (اولین قدم، ~۱۵ دقیقه)
قبل از هر تصمیم معماری، با **۲ کلید (یکی از هر اکانت)**:
1. ۱۰ درخواست همزمان با کلید A → ۱۰ درخواست همزمان با کلید B → همزمان A+B (۱۰+۱۰).
2. سنجش: empty-200، 429، latency، توزیع پاسخها بین دو کلید.
3. خروجی: «کلیدها مستقلاند» (pool چنداکانته با N سهمیه) یا «سقف مشترک» (سقف اشتراک، کلید اضافه بیفایده → معماری به fallback پولی Zen balance/DeepSeek تکیه میکند).
4. خروجی ثبت میشود در docs/launch/M0-QUOTA-RESULT.md — همین نتیجه تعیین میکند M1 با چند کلید چیده شود.

### M1 — KeyPool (چند کلید/چند اکانت)
- `.env` → `GO_API_KEYS=k1,k2` (کاما-جدا) + backward-compat `GO_API_KEY`.
- `KeySlot`: key, error_streak, tripped_until, in_flight, last_latency_ms.
- انتخاب: کمترین in_flight + سالم؛ هر کلید breaker مستقل (۳ خطا → cooldown ۶۰s منفرد).
- **empty-200 تشخیص داده میشود = خطا** (مهمترین فیکس — ریشهٔ کندی).
- مدیریت از پنل ادمین (secret `go_api_keys`) — کلیدها بدون رستارت اضافه/حذف.
- اگر M0 نشان دهد سقف مشترک است → M1 فقط «failover ترتیبی» میشود و وزن به M9 میرود.

### M2 — SectionRouter (هر بخش → کدام LLM) با A/B قبل از نهاییسازی
- جدول پیشنهادی (موقت): career/love/finance → pro؛ summary/energy/daily/... → flash؛ chat/preview → flash.
- **قبل از deploy نهایی، A/B روی ۳۰ چارت:** هر بخش با pro و flash تولید و rubric کیفیت (factual/hallucination/grounding/Persian/coherence) مقایسه میشود → جدول نهایی بر اساس شواهد، نه حدس.
- override از پنل ادمین: `sec_{name}_model/provider/pool`.

### M3 — تولید موازی بخشها + adaptive concurrency
- `asyncio.gather` + Semaphore اولیه ۴.
- **adaptive:** error_rate در پنجرهٔ ۵ دقیقه → healthy=4 · بالا=2 · بد=1 · down=fallback (M9).
- **اندازهگیری قبل/بعد:** LLM calls، tokens، cost، QA retries، provider errors، کیفیت — همه در M5 ثبت میشود (نه فقط latency).
- ترتیب خروجی حفظ میشود (PDF/UI بدون تغییر).

### M4 — Benchmark دوگانه (جدا کردن Infrastructure از Quality)
- **Benchmark A (Infrastructure):** availability، empty-200 rate، timeout، latency، retry count، key health، fallback hits، throughput — با چند کلید و CONC=6 → هدف: ۵۲ چارت < ۲۰ دقیقه.
- **Benchmark B (AI Quality):** فقط روی پاسخهای واقعی تولیدشده: ۱۰ معیار قبلی (factual/evidence/personalization/coherence/Persian/tone/safety/hallucination/contradiction/repeatability-critical).
- خروجی جداگانه: `INFRASTRUCTURE SCORE` · `AI QUALITY SCORE` · `FINAL VERDICT` (هر سه در گزارش).
- **بونوس فوری:** ۳۳ پاسخ ok در jsonl موجودند — Benchmark B روی آنها الان هم قابل اجراست (بدون کلید جدید).

### M5 — Telemetry کامل (llm_runs)
ستونهای جدید: `key_slot`, `section`, `pool`, `provider`, `model`, `prompt_version`, `attempt`, `error_code`, `fallback_used`, `qa_attempt`, `input_tokens`, `output_tokens`, `status`.
- هدف: هر regression کیفیت = قابل ردیابی به (provider + model + prompt_version).

### M6 — تستها (hermetic)
test_keypool · test_section_router · test_parallel_sections · test_adaptive_conc · test_benchmark_split · test_telemetry_cols · test_fallback_keeps_qa (fallback ≠ دور زدن gate) · test_critical_repeatability · test_prompt_audit — ~۲۰ تست جدید.

### M7 — Drill restore هفتگی (تکمیل A5)

### M8 — Prompt Engineering & Grounding Audit (جدید — از ChatGPT)
برای **همهٔ prompt های production** (۱۳ بخش گزارش + chat + preview + insights + weekly + transit + bot):
- input contract (چارت JSON همیشه داخل prompt؟) · evidence contract (هر ادعا ← از chart؟) · allowed/forbidden claims (بدون پیشگویی قطعی، بدون اعداد ساختگی) · uncertainty phrasing · output schema (JSON معتبر؟) · anti-hallucination (خروجی خارج از chart ممنوع) · prompt injection (ورودی کاربر از chart جدا؟) · retry correction (خطای قبلی به retry داده شود؟).
- خروجی: گزارش per-prompt با وضعیت PASS/FAIL + جدول prompt_versions (که در DB هست — نسخهبندی واقعی میشود).
- گیت: هر prompt FAIL → تعمیر قبل از deploy.

### M9 — Fallback اقتصادی (تصمیم بعد از M0)
دو گزینه (هر دو پولی ولی ارزان؛ فقط در لحظهٔ سقف GO فعال میشوند):
- **گزینهٔ ۱ — Zen balance (Use balance):** همان کلید GO؛ بعد از سقف، به اعتبار پیشپرداخت (از $۲۰، zero markup) برمیگردد — بدون کلید جدید، بدون provider جدید، ساده.
- **گزینهٔ ۲ — DeepSeek direct API:** کلید جدا + قیمت جدا (flash ارزان، peak/off-peak)؛ تنوع provider بیشتر ولی کلید/حساب دیگر.
- تصمیم: بعد از M0 + قیمت لحظهای؛ هر دو با **سقف هزینهٔ ماهانهٔ خودکار** (مثلاً $۵) در secret — بدون غافلگیری هزینه.
- **شرط (از ChatGPT):** fallback هرگز quality gate را دور نمیزند — خروجی fallback همان QA + safety + grounding را میگذراند؛ اگر پاس نکرد → degraded (همان fail-closed فعلی).

---
---

## ۳) معیارهای پذیرش (نهایی — شامل گیتهای ChatGPT)

| دسته | گیت | آستانه |
|---|---|---|
| سرعت | Benchmark A کامل ۵۲ چارت | < ۲۰ دقیقه با ۲ کلید |
| سرعت | latency گزارش کامل تولیدی | < ۲۵s (از ~۴۸s) |
| زیرساخت | empty-200 / total در ۲۴h بعد از deploy | < ۱٪ (با pool فعال) |
| زیرساخت | degraded گزارش در ۲۴h اول | ۰ |
| کیفیت | **critical hallucination** | **۰** (هیچ سیاره/برج خارج از chart) |
| کیفیت | **critical contradiction** | **۰** (بین بخشها) |
| کیفیت | **critical grounding failure** | **۰** (هر ادعای کلیدی ← از chart) |
| کیفیت | **critical-fact repeatability** | **۱۰۰٪** (برج خورشید/ماه/ASC در ۲ پاسخ یکسان) |
| کیفیت | AI QUALITY SCORE | ≥ ۸۰/۱۰۰ (از ۷۸.۹ فعلی) |
| معماری | گزارش جداگانهٔ Provider vs AI quality | در P15 |
| امنیت | fallback ≠ دور زدن QA/safety | تست + کد |
| تست | کل suite | ۴۹۰ + ~۲۰ تست جدید سبز |

---

## ۴) گامهای اجرا (به ترتیب — با نقاط تصمیم)

| گام | ماژول | خروجی | وابسته به |
|---|---|---|---|
| 0 | M0 | نتیجهٔ آزمایش سقف ۲ کلید | **۲ کلید از تو** |
| 1 | M8 (بخش prompt inventory) | لیست ۲۰+ prompt با وضعیت فعلی | — |
| 2 | M1 | KeyPool + تستها | نتیجهٔ M0 (تعداد کلیدها) |
| 3 | M5 | migration telemetry + ثبت | — |
| 4 | M3 | موازیسازی + adaptive + اندازهگیری | M1 |
| 5 | M2 | A/B ۳۰ چارت → جدول نهایی بخشها | M1 (پول کلید) |
| 6 | M4 | Benchmark A/B اجرای کامل | M1+M2 |
| 7 | M8 (بخش تعمیر) | prompt ها PASS | — |
| 8 | M9 | fallback فعال (گزینهٔ تصمیمشده) | M0+قیمت |
| 9 | M6+M7 | تست کامل + drill | همه |
| 10 | — | deploy + P15 + ارسال | همه |

**مجموع: ~۱۳-۱۴ ساعت** (با M0 و A/B و M8 که در v1 نبودند).

---

## ۵) نیازمندی از کاربر (مهم — اصلاح نسبت به v1)

1. **۲ کلید GO** — یکی از هر اکانت (همان که داری؛ برای M0 لازم است، نه بیشتر). بدون اینها اولین قدم ممکن نیست. بعد از M0 مشخص میشود همین ۲ کافی است یا مسیر به Zen balance/DeepSeek میرود.
2. **(بعد از M0، در صورت نیاز)** تصمیم M9: شارژ $۲۰ Zen balance یا کلید DeepSeek — هر دو اختیاری و فقط اگر M0 نشان دهد pool بهتنهایی کافی نیست.
3. تأیید این پلن (بعد از ادغام با پلن قبلی ChatGPT — اگر هنوز لازم میدانی).

---

## ۶) ریسکها

- **GO در دورهٔ فعلی بد است** (۵۲/۵۲ خالی در شب) — حتی ۲ کلید ممکن است کافی نباشد؛ از این رو M9 (fallback پولی) از قبل در معماری است و در گام ۸ فعال میشود.
- **Zen balance "zero markup"** طبق منابع ثالث (toolradar) — باید با صورتوضعیت واقعی چک شود.
- A/B ۳۰ چارت = ~۱۰۰۰ درخواست LLM — روی GO pool انجام میشود؛ اگر GO خالی باشد، به شب موکول یا با fallback.
- همزمانی بیشتر ممکن است QA failures را زیاد کند → adaptive concurrency (M3) + متریکهای M5 دقیقاً برای همین است.

---

## ۷) جمعبندی

- v1 (زیرساخت) ✅ حفظ شد: KeyPool، fallback، SectionRouter، موازیسازی، telemetry، benchmark سریع.
- v2 افزود: M0 (آزمایش سقف)، Benchmark A/B جدا، M8 (Prompt/grounding audit)، critical gates، adaptive concurrency، Zen-balance گزینه، fallback-keeps-QA.
- نقد ChatGPT: ۱۱/۱۳ قبول — هیچ بخشی از v1 حذف نشد؛ فقط شفافتر و محکمتر شد.
- **قدم بعدی:** M0 با ۲ کلید → نتیجه در M0-QUOTA-RESULT.md → سپس اجرای گامهای ۱-۱۰.

---
*منتظر: (الف) ۲ کلید GO · (ب) تأیید یا ادغام با پلن قبلی ChatGPT · سپس شروع.*
