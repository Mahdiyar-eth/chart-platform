# ZAYCHE — دور ۹ (پاسخ به ممیزی نهایی Opus FINAL-AUDIT) — ۱۴۰۴/۰۶/۰۲

## نتیجه: هر دو باگ P1 (گزارش طلایی + گزارش مالی ادمین) و همهٔ موارد P2/P3 (Q3–Q7) رفع و راستی‌آزمایی شد.

## یافته‌های ممیزی نهایی (که ۸ دور بازبینی ندیده بودند)
- **P1-1**: `report_gold` (۱۴ اعتبار) فقط یک استحقاق `report` می‌ساخت ⇒ خریدار طلایی
  همان چیزی را می‌گرفت که خریدار `full` (۷ اعتبار) می‌گرفت، و برای «گذر ۱۲ماهه» دوباره پرداخت می‌کرد.
- **P1-2**: `admin_credit_report` از `p.key` (ناموجود) استفاده می‌کرد ⇒ همیشه ۵۰۰ — از روز نوشته‌شدن هرگز کار نکرده.

## فیکس‌ها

### Q1 (P1) — باندل طلایی واقعاً سه استحقاق
- `_MULTI_KIND_BY_ACTION = {"report_gold": ["report", "chat", "transit"]}` + `_kinds_for_action()`
  در `app/entitlements.py`؛ `grant_from_credits` اکنون برای هر kind یک استحقاق می‌سازد (chat=30روزه، transit=تحلیل ۱۲ماهه).
- انتقال `transit`: در `api_chart_forecast_analyze`، اگر کاربر استحقاق `transit` برای این چارت دارد،
  بدون کسر مجدد اعتبار تولید میشود (`entitlement: true`).
- گیت چت از قبل `ent_has(uid, "chat", chart_id)` را مصرف می‌کرد ⇒ با استحقاق جدید، چت ۳۰روزه باز میشود.
- تست: `test_gold_bundle_r9.py` (سه استحقاق، خریدار full بدون باندل، idempotent).

### Q2 (P1) — گزارش مالی ادمین ۲۰۰
- `app/routes/admin.py:441` → `p.action_key` به‌جای `p.key`.
- تست یکپارچگی `test_admin_credit_report_200` که اندپوینت را واقعاً صدا می‌زند (قبلاً صفر پوشش).

### Q3 (P2) — خطای درگاه → ۵۰۲ فارسی
- `ZarinpalError` اکنون زیرکلاس `RuntimeError` است (قبلاً `Exception` خام ⇒ ۵۰۰).
- `api_create_order` `except ZarinpalError → 502` با پیام «درگاه موقتاً در دسترس نیست؛ دوباره تلاش کنید».
- تست مسیر سازنده (بدون merchant id) `test_gateway_constructor_error_is_friendly_502`.

### Q4 (P2) — تصاویر مقالات همراه مخزن
- ۵۰ تصویر (۱۰۰ webp، ~۵.۶MB) از `app/static/articles/` رفع‌gitignore و کامیت شدند؛
  استقرار تازه دیگر ۵۰ `<img>` و ۵۰ `og:image` شکسته ندارد.
- تست `test_article_images_r9.py` (AC-4): هر image/thumb به فایل واقعی ارجاع میدهد + گیت «دیگر gitignored نیست».

### Q5 — برچسب دو ورودی فرم تولد
- `form.html`: ورودی «شهر» و «سؤال شخصی» → `<label for>` + `aria-label`.

### Q6 — `/api/credits/me` برای مهمان → ۲۰۰ `{balance:0}`
- به‌جای ۴۰۱ که روی هر صفحه یک خطای کنسول ثبت می‌کرد. تست به‌روز شد.

### Q7 — pin ابزارهای گیت
- `ruff==0.16.3 · bandit==1.9.4 · pip-audit==2.10.1 · pytest-cov==7.1.0` به `requirements.txt`
  اضافه و نصبِ بدون pin از `ci.yml` حذف شد (یک انتشار ناسازگار دیگر CI را نمی‌شکند).

## راستی‌آزمایی
- سوئیت: ~۷۵۷ تست سبز (۰ fail) · گیت‌های ci.sh (bash -n، compileall، ruff F/E9، drift، brand، bandit، secret، abs-path) ✅
- **CI از مخزن:** run #… → SUCCESS

## مدارک
- گزارش `docs/reports/HERMES-ROUND9.md` · تست‌های جدید (`test_gold_bundle_r9.py`, `test_article_images_r9.py`) +
  به‌روزرسانی‌ها (`test_admin_credit_a7.py`, `test_coupon_reservation.py`, `test_purchase_a4.py`) ·
  `app/entitlements.py` · `app/main.py` · `app/routes/admin.py` · `app/payment/zarinpal.py`

## درس از این ممیزی
دو باگ P1 در ۸ دور بازبینی کد دیده نشدند، ولی **ممیزی مستقل صفر-تا-صد با اجرای واقعی قیف و دفتر اعتبار** آن‌ها را لو داد.
این تأیید دوبارهٔ قانون: هر محصول پولی باید سرتاسری با عینک «مشتری چه می‌خرد و چه می‌گیرد» بررسی شود،
نه فقط با تست واحد.
