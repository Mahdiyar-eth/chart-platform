# HARDENING PLAN — ZAYCHE (زایچه) — پس از Deep Review v3

> وضعیت: 2026-08-14 · پایه: کد فعلی main (دور ۴ کامل، 223 تست، CI OK)
> منبع: Deep_Research_Final_Review_Hermes_Plan_v3.md + راستیآزمایی مستقل در کد (هر ادعا با خط/تست ثابت شد)
> این سند مستقل است — قابل ارسال به هر متخصص/هوش مصنوعی برای بازبینی.

---

## خلاصهٔ راستیآزمایی (گزارش ≠ وحی)

هر ادعای گزارش با کد چک شد. نتیجه: **۴ ادعای کلیدی درستاند، ۳ ادعا نیاز به تصحیح دارند، ۱ باگ مهم گزارش نگفته بود.**

### ✅ تأییدشده در کد (خط دقیق)
| # | ادعا | شواهد |
|---|---|---|
| 1 | **Timezone هاردکد** | `app/main.py:306` — `tz_name="Asia/Tehran"` در ساخت چارت؛ سیناستری `:1009-1011` همین؛ `BirthProfile.tz_name` فیلد دارد ولی هیچجا از فرم پر نمیشود؛ دیتاست شهر فقط ایران (۷۰۰ شهر، بدون فیلد timezone)؛ lat/lon دستی هم تهران میگیرد → دقیقاً سناریوی «Istanbul با tz تهران» |
| 2 | **Golden Suite مستقیم engine است نه E2E** | `tests/test_golden_charts.py` — `compute_from_fields(**g["birth"])` مستقیم؛ birthهای golden فیلد tz ندارند → همه با پیشفرض تهران محاسبه میشوند؛ هیچ شهر خارجی/DST خارجی پوشش ندارد |
| 3 | **Unknown time: ماه بدون confidence** | `main.py:303` — `hour=12` جایگزین ساعت نامعلوم؛ خروجی moon sign قطعی است |
| 4 | **Worker stale recovery نیست** | `app/report/worker.py` — ARQ فقط `max_jobs=4, job_timeout=1800`؛ بدون max_tries/backoff/heartbeat/dead-letter؛ cron `retry_failed_reports.py` فقط status=failed را برمیگرداند — job گیرکرده در running هرگز آزاد نمیشود |
| 5 | **TTS همگام** | `app/main.py:1123-1181` — `api_report_audio` مستقیم `edge_tts` را در request اجرا میکند (R2 cache دارد ولی صف ندارد) |
| 6 | **چت context بریده میشود** | `app/chat/retrieval.py:61` — `json.dumps(ctx)[:3500]` — دقیقاً همان نگرانی گزارش |
| 7 | **Transits بدون tz chart** | `app/astrology/transits.py` — محاسبات با `datetime.now(timezone.utc)`؛ tz محلی چارت استفاده نمیشود |
| 8 | **Self-referral ممکن است** | `app/payment/orders.py:76-93` — فقط چک `not existing`؛ هیچ چک `referrer.user_id != new_user_id` |
| 9 | **Admin بدون 2FA/RBAC** | PIN/Secret فقط — همانطور که گزارش گفت |
| 10 | **LLMRun فیلدهای ناقص** | بدون prompt_version/cached_tokens/retry_count/user_id؛ داشبورد Gross Margin نیست |

### 🆕 باگ P0 که گزارش نگفت ولی بند ۱۵ به آن اشاره میکرد
> **حذف حساب کاربری که گزارشش RAG-index شده → خطای 500.**
> شبیهسازی روی DB واقعی: `delete report` وقتی `report_chunks` دارد → `IntegrityError (ForeignKeyViolation)`. گزارشها و چت حذف میشوند ولی `ReportChunk`ها نه (`app/models.py:298` FK بدون cascade؛ `app/main.py` بخش account_delete). یعنی **قبل از هر بتا باید فیکس شود** — دقیقاً همان «RAG Embeddings» در لیست بند ۱۵ گزارش.

### ❌ تصحیح ادعاهای گزارش
| ادعا | حکم | دلیل |
|---|---|---|
| **Licensing P0 (بند ۲، ۴۲)** | ❌ **رد به عنوان کار فنی** | تصمیم مالک: مهم نیست (ایران/تحریم). حقایق: AGPL رایگان؛ Professional = 700 CHF یکبار (قیمت رسمی astro.com/swisseph/swephprice) — خرید از ایران عملاً ممکن نیست؛ ریسک عملی پیگیری برای استارتاپ ایرانی ≈ صفر. **فقط مستندسازی تصمیم کافی است** (یک پاراگراف در docs) |
| **معماری LLM «DeepSeek + Gemini + Fallback» (بند ۱۰/۱۱)** | ❌ **نادرست** | Gemini و AvalAI حذف شدهاند (تصمیم مالک 2026-08-13)؛ فعلی: Go (opencode) + DeepSeek. نکتهٔ health/quota/cost درست است و تا حدی هست |
| **Rule Engine نیاز به بازسازی (بند ۶)** | ❌ **قبلاً پیاده است** | `app/report/rules.py` — کلاس Rule با دقیقاً همان فیلدها (factor/condition/weight/domain/interpretation_key/evidence/priority) + evaluate/domain_coverage |
| **«اولین پلتفرم فارسی» (بند ۱۸)** | ❌ **در کد نیست** | هیچ template/seo از این عبارت استفاده نمیکند — هشدار محتاطانه، فعلاً بیاثر |
| **Data model (بند ۳۷)** | ✅ موجود | User→BirthProfile→Chart→Reports دقیقاً همین است |
| **Presigned 30 دقیقه (بند ۱۴)** | ✅ موجود | از دور ۴ B انجام شده |

---

## پلن اجرا

### فاز H0 — فوری (P0) — «اعداد درست شوند»

**H0.1 — Timezone واقعی شهرها** (گزارش بند ۱)
- `pip install timezonefinder` (آفلاین، `timezone_at(lng, lat)` → IANA؛ مرجع رسمی برای lat/lon→tz)
- فرم: اگر شهر از دیتاست پیدا شد → tz دیتاست؛ اگر lat/lon دستی → timezonefinder
- `main.py:306` و `:1009-1011` → `tz_name=profile.tz_name` (حذف هاردکد)
- دیتاست `cities_world.json` (~500 شهر پرطرفدار جهانی با lat/lon + tz_name) + `cities_ir` همه → `Asia/Tehran`
- DB: ستون `tz_name` در BirthProfile پر شود (migration پشتاری برای chartهای قبلی)
- **تست E2E جدید** `tests/test_timezone_e2e.py`: تهران/استانبول/دبی/نیویورک/لندن از مسیر واقعی (فرم → شهر → tz → UTC → engine → chart) + DST تابستان/زمستان هر شهر
- Golden Suite: birthها tz صریح بگیرند (تهران/استانبول/نیویورک/لندن) — پوشش DST

**H0.2 — فیکس حذف حساب با RAG chunk** (باگ یافتشده)
- در account_delete: حذف `ReportChunk`ها قبل از Report (به ترتیب FK)
- + migration: `ondelete="CASCADE"` برای آینده
- تست رگرسیون: حذف حساب کاربر با report ایندکسشده → 200، همه چیز پاک شد

**H0.3 — Unknown birth time: confidence** (گزارش بند ۵)
- engine: وقتی `time_known=False` → خروجی `moon_confidence: "low"|"high"` (مقایسهٔ درجهٔ ماه در ۲۴ ساعت: اگر sign عوض میشود → low + نشان دادن هر دو sign)
- JSON خروجی + گزارش (بخش ماه: «ماه در مرز دو برج — حدود»)
- تست: تاریخ مرزی (ماه در حال تعویض sign)

**H0.4 — Worker stale recovery** (گزارش بند ۳۰)
- `WorkerSettings`: `max_tries=3`, `retry_delay`, `keep_result`, `on_job_failure` → وضعیت `failed`
- heartbeat/stale: cron `recover_stale_reports.py` — jobهای running با `last_heartbeat > 30min` → requeue (مثل retry_failed_reports ولی برای running)
- تست: شبیهسازی job گیرکرده → recovery

**H0.5 — مستندسازی تصمیم Licensing**
- `docs/decisions/0001-swiss-ephemeris-licensing.md`: تصمیم مالک (AGPL، بدون خرید Professional — تحریم/هزینه)، تاریخ، امضا
- بدون تغییر کد

### فاز H1 — قبل از بتا (P1)

**H1.1 — Transits با tz چارت** (بند ۲۸): transits از `chart.chart_json["birth"]["tz_name"]` — روز شمسی محلی درست؛ تست استانبول/تهران تفاوت روز

**H1.2 — چت: context ساختاریافته** (بند ۷): بهجای `json.dumps[:3500]` → بخشهای مجزا: `relevant_factors` (خلاصهٔ rules)، `evidence`، `rag_chunks` (تا N، کوتاهشده) — بدون برش ناگهانی میدانی؛ تست: پرامپت شامل همهٔ فیلدهای حیاتی است

**H1.3 — LLMRun غنی + داشبورد هزینه** (بند ۱۲، ۲۵): فیلدهای `prompt_version, retry_count, user_id` + view ادمین: cost/report, tokens/report, calls/report, provider, model؛ (cached_tokens وقتی provider اعلام کند)

**H1.4 — Self-referral prevention** (بند ۳۱): `referrer.user_id != new_user_id` + چک user_id ادمین؟ (min withdrawal از قبل هست؟ — بررسی + تست)

**H1.5 — TTS صفدار** (بند ۱۶): job ARQ `tts` → worker → R2 → وضعیت؛ endpoint `POST /api/reports/{id}/audio/job` + polling؛ تست: job→ready→presigned

**H1.6 — Synastry Person B بدون اکانت** (بند ۱۷): حالت «پروفایل مهمان» (BirthProfile با user_id=NULL + توکن) — فقط در حد فرم دوم؛ privacy: فقط برای خود کاربر ذخیره

**H1.7 — Islamic verified layer** (بند ۹): فایل `app/content/islamic_kb.json` (~۳۰ مفهوم با ارجاع سوره/آیهٔ قطعی) → RAG یا جستجوی ساده → prompt «فقط از KB»؛ حذف آزادی نقلقول LLM

**H1.8 — Human evaluation** (بند ۲۲-۲۴): ۲۰ چارت × ۱۳ دامنه با معیار ۸تایی (1-5)؛ خروجی `docs/eval/`؛ معیار objective: genericness توسط LLM-judge + دستی

**H1.9 — Refactor main.py** (بند ۳۶): استخراج routes/ (auth, charts, reports, payments, chat, admin, seo, push, wallet) — بدون تغییر رفتار؛ 223 تست سند محافظ

**H1.10 — Privacy policy دقیق** (بند ۳۹): صفحهٔ privacy.html: جمعآوری/دلیل/مدت/حذف/بکاپ/سرویسدهندههای ثالث (Zarinpal, R2, OpenAI-compatible, edge-tts)

### فاز H2 — بعد از بتا (P2) — بر اساس رفتار واقعی کاربر
- Subscription کامل (داشبورد + insight روزانه + transit timeline + سهمیه چت + reading ماهانه + تخفیف سیناستری + صدا)
- Onboarding WOW (انیمیشن چارت → ۳ insight → big three → CTA)
- Astrocartography، Progressions، Solar Return، Vedic عمیق
- 2FA/RBAC ادمین · Public API · Community

---

## اولویت نهایی
```
H0 (اعداد/حساب/پایداری)  →  H1 (کیفیت/قابلاندازهگیری)  →  بتا  →  H2
```
قانون: **Feature جدید ممنوع** تا پایان H1 (طبق بند ۴۱). هر آیتم H0/H1 = تست + CI + گزارش.

## Definition of Done (بند ۴۶)
Backend ✓ Frontend ✓ DB/migration ✓ Error/Loading states ✓ Mobile+RTL ✓ Tests ✓ Security ✓ QA ✓ Acceptance criteria ✓
