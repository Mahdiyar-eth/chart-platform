# گزارش نهایی HARDENING — پلتفرم زایچه (chart-platform)

- **نسخه/تاریخ:** vH1-final — پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **برنچ:** `main` — آخرین کامیت `3800ba1` (h1.10)
- **وضعیت:** ✅ همهٔ ۱۶ آیتم H0+H1 انجام، تست و push شدهاند. H2 (بعد از بتا) باز میماند.

---

## ۱. خلاصه

این دور، کیفیت و استحکام پلتفرم را بهجای فیچر جدید نشانه گرفت (قانون: تا پایان H1 هیچ فیچر جدیدی اضافه نشد).
نتیجه: **سویییت از 223 تست به 292 تست + 1 skip** رسید (۳۰٪ رشد)، با ۱۶ کامیت پشتسرهم — هر کدام مستقل سبز و روی `main`.

| مرحله | عنوان | تستها | خروجی کلیدی |
|---|---|---|---|
| H0.1 | تایمزون واقعی | 246 | `timezonefinder` + دیتاست ۱۱۰۰ شهر جهانی؛ golden ۶ شهر خارجی؛ DST با offset واقعی |
| H0.2 | حذف حساب کامل | 247 | cascade حذف ReportChunk + WithdrawalRequest؛ flush صریح |
| H0.3 | ساعت نامعلوم | 253 | `moon_confidence` (۰۰:۰۰/۲۳:۵۹) + UI شیشهگام |
| H0.4 | بازیابی worker | 258 | `reports.updated_at` heartbeat + cron `recover_stale_reports` + ARQ max_tries |
| H0.5 | لایسنس Swiss Ephemeris | — | تصمیم مستند: AGPL (تحریمها خرید Professional را ناممکن کرده) |
| H1.1 | ترانزیت با tz چارت | 262 | «امروز» و رویدادها روزِ محلی چارت را دنبال میکنند؛ ورودی ephemeris UTC میماند |
| H1.2 | چت context ساختاریافته | 266 | حذف برش JSON خام؛ بلاکهای محدود (agents کامل، insights ۲۸۰ کاراکتر، RAG ≤۴ چانک) |
| H1.3 | سنجش هزینهٔ LLM | 269 | `llm_runs.user_id+kind` (migration)؛ داشبورد ۲۴h/7d/30d per model/user/kind + نرخ خطا |
| H1.4 | ضدسوءاستفاده referral | 273 | self-referral دو لایه (ساخت + reward)؛ کف برداشت ۵۰۰٬۰۰۰ ریال |
| H1.5 | TTS صفدار | 276 | edge-tts از مسیر inline خارج شد → ARQ job؛ وضعیت audio_status؛ دکمهٔ صوتی + پولینگ |
| H1.6 | سیناستری مهمان | 279 | Person B بدون حساب (BirthProfile با user_id=NULL) + capability token |
| H1.7 | لایهٔ اسلامی verified | 282 | `islamic_kb.json` (۳۰ مفهوم + ارجاع سوره/آیه) تنها منبع نقلقول؛ جعل ممنوع |
| H1.8 | ارزیابی انسانی | 285 | ۲۰ چارت × ۱۳ دامنه = ۲۶۰ prompt آفلاین؛ rubric ۸ معیاری (1-5)؛ LLM-judge |
| H1.9 | Refactor main.py | 289 | ۳۴ endpoint → `app/routes/{auth,wallet,push,seo,admin}.py`؛ 2242→1783 خط |
| H1.10 | سیاست حریم خصوصی | 292 | v1.1 دقیق: دادهها، طرفهای سوم نامبرده، کوکیها، نگهداری ۳۰ روزه، حقوق کاربر |

## ۲. پیشرفت تستها

```
223 → 236 → 246 → 247 → 253 → 258 → 262 → 266 → 269 → 273 → 276 → 279 → 282 → 285 → 289 → 292
(R4)  (H0.1) (H0.2)(H0.3)(H0.4)       (H1.1)(H1.2)(H1.3)(H1.4)(H1.5)(H1.6)(H1.7)(H1.8)(H1.9)(H1.10)
```

- ۳ اجرای متوالی کامل سویییت: **292 passed + 1 skipped** (پایدار).
- `ruff check --select F` (app/tests/scripts) — پاک.
- ۱۴ مهاجرت alembic؛ prod و test هر دو روی head (زنجیره تا `9d34ed9201c2`).

## ۳. نکات فنی مهم

- **H1.2:** `search_relevant` لیست `str` برمیگرداند؛ بلاک RAG هم `str` هم `dict` را پشتیبانی میکند.
- **H1.3:** DB/Redis تست بین اجراها persist دارند → تستهای aggregate نسبی + seed متمایز + teardown صریح.
- **H1.5:** درخواست صوتی هرگز inline تولید نمیکند؛ redis down → 503. سقف متن ۹K کاراکتر.
- **H1.6:** `_compute_and_save_chart(guest=True)` → user_id صریح None (بدون fallback به کاربر فعلی).
- **H1.9:** FastAPI جدید `include_router` را lazy نگه میدارد (`_IncludedRouter`) → روتها flatten به `app.router.routes` میشوند تا `app.routes` (تست ماتریس، middleware) کامل بماند.
- **H1.7:** فصل اسلامی فقط از KB نقلقول میکند؛ آزادی نقلقول LLM حذف شد.

## ۴. باقیمانده (سمت کاربر / بعد از بتا)

- مرچنت واقعی زرینپال + کلید کاوهنگار + دامنهٔ `zayche.io`.
- تست موبایل واقعی (شبیهساز ≠ گوشی واقعی — بدون تأیید کاربر، ادعای «درست شد» نمیدهیم).
- **H2 (بعد از بتا):** کش Redis برای صفحات عمومی، مقالات بیشتر، تصاویر اختصاصی، گزارشهای جامعتر.

## ۵. دستورهای مرتبط

```bash
cd /root/chart-platform
APP_ENV=test venv/bin/python -m pytest tests/ -q          # 292 passed, 1 skipped
venv/bin/ruff check --select F app/ tests/ scripts/       # clean
# بکاپ: /root/backups/chart-platform/chart_backup_*.zip.age (+ R2)
```
