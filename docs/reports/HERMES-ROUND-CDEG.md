# HERMES-ROUND-C — گزارش مرحلهٔ C/D/E/G (۲۰۲۶-۰۸-۲۲)

**برنچ:** `hermes/plan-v1-r1` · **شروع دور:** `3c70b46^` · **پایان:** `HEAD` (این کامیت)
**ممیزی نهایی:** ۱۶ صفحه × ۵ viewport × ۱۸ چک = **۰ تخلف** (`docs/qa/UI-AUDIT-2026-08-22.md`)

## خلاصه
تکمیل مراحل C تا G پلن HERMES-PLAN-v1: دیزاینسیستم، ممیزی UI سرتاسری، الگوهای UX،
دسترسپذیری/کارایی، nav واحد، سیاههٔ مسیرها/امنیت، و قیف رشد/SEO/برند.

## تغییرات
### C3 — ممیزی UI (۶۸ → ۰ تخلف)
- کنتراست دکمههای خرید (btn-accent ~۷:۱)، رنگ لینک سراسری (حذف آبی پیشفرض)،
  focus-visible سراسری، min-height لمسی ۴۰px+، aria-label/سمانتیک
- فیکس ۲۰ `status?\.` شکسته در today.html (SyntaxError کل Alpine) + گاردهای null در explore/today
- اسکریپت audit (`scripts/ui_audit.py`): ۱۸ چک × ۵ سایز، اندازهگیری CLS روی page تازه

### C4 — الگوهای UX
- progress واقعی گزارش (بخش N از ۱۳)، skeleton + empty-state طراحی شدهٔ /today
- بنر آنبوردینگ سهقدمی روی chart.html، **حالت روشن کامل** (توکن override + toggle ماندگار + ضدFLASH)

### C5 — کارایی/PWA
- maskable icon؛ CWV شش صفحه: CLS=0, LCP<250ms (لوکال)؛ تصمیم مستند font-display

### D — nav واحد
- `app/nav.py` رجیستری تنها منبع سه منو؛ state-aware (FAB فقط بدونچارت)؛ drawer گروهی
- تست `test_nav_d1.py` (۶ تست)؛ هندسهٔ RTL تأیید مرورگری

### E — مسیرها/امنیت
- `test_route_inventory_e2.py`: همهٔ href قالبها → مسیر واقعی (۰ لینک مرده؛ /signs/* با مسیر دینامیک پوشش دارد)
- AUTHORIZATION-MATRIX: ۳ مسیر گذر B3 اضافه شد (گیت سبز)
- هدرهای امنیتی همهٔ پاسخها + CSP report-only + `test_security_headers_e4.py`

### G — رشد
- **G1:** ۷ رویداد قیف وایر و تأیید fire واقعی در مرورگر (birth_form_start/chart_created/checkout_started/signup_*/share_clicked/report_started/chat_first_message)
- **G2:** بنر «این چارت را از دست نده» برای مهمان روی chart.html (بستن بزرگترین نشت قیف)
- **G3:** Subscriber model + `/gift-guide` (لید مگنت پشت تماس) + دانلود توکنی + unsubscribe — سرتاسر تست شد
- **G4:** چکلیست آنبوردینگ داشبورد (dismiss ماندگار localStorage)
- **G5:** کارت رفرال بعد پرداخت موفق + موجود در /account
- **G6:** Schema.org کامل (Organization/WebSite+SearchAction/Article/BreadcrumbList/FAQPage) — JSON معتبر
- **G7/G8:** `docs/BRAND.md` + `docs/GROWTH-CHANNELS.md`؛ نام در کد یکدست «زایچه»

## تستها
- سوئیت کامل chunk-by-chunk: **~۶۲۰ تست سبز، صفر شکست**
- تستهای جدید این دور: nav(۶) + route-inventory(۲) + security-headers(۵) + g2g3(۴)
- ممیزی UI پس از هر مرحله مجدد اجرا شد: **۰ تخلف**

## هزینه / زمان
فقط محاسبات لوکال + LLM خود ابزار؛ هیچ API پولی فراخوانی نشد.

## pending (خارج از scope این دور)
- G6 خوشههای SEO نیت واقعی («ماه در برج X» ۱۲×۱۲) — تولید محتوای یکتا، نیازمند تصمیم محتوایی
- GCS ثبت sitemap (BLOCKED روی مالک)
- پیامهای SMS آنبوردینگ (نیازمند سرویس SMS)

## rollback
```
git checkout <pre-round-sha>   # قبل از 3c70b46
```


## افزودنی ۲۰۲۶-۰۸-۲۲ (بعد از بازبینی)
- **خوشهٔ SEO «ماه در برج X»**: صفحهٔ ایندکس `/moon` + ۱۲ صفحهٔ یکتا `/moon-in/{slug}` (احساسات/عشق/کار/سایه/راه آرامش)، لینک‌چرخش بین صفحات، sitemap و ۶ تست رگرسیون — کامیت `088b756`.
- **فیکس لمسی:** لینک‌های breadcrumb حالا هدف لمسی ≥40px (قبلاً h=20px).
- **استقرار prod:** merge --ff-only به main (`f6def7e..088b756`) + restart chart-web/chart-worker؛ تأیید زنده: `/`, `/moon`, `/moon-in/hout`, `/sitemap.xml` (12 URL ماه)، `/gift-guide` همه 200.
