# ZAYCHE — CLOSURE MASTER PLAN (نقد چهارم → FINAL GO)
**نسخه 1.0 — 2026-08-16 · HEAD: 5856458 · تست: 532 passed**
سند مستقل — قابل ارسال به ChatGPT برای بازبینی.

---

## 0) وضعیت ورودی (با نقد چهارم موافقم — P0 بسته، Launch باز)

**✅ بسته شده:** KeyPool · failover · section routing · parallel sections · adaptive concurrency · telemetry · budget 4-لایه · hard AI gates · claim validation · prompt versioning · degraded (2 کلاس) · pre-deploy backup · health panel · CMS (4 جدول + CRUD + revisions + audit + R2 + DB-first + seed) · restore drill · rollback strategy · RUNBOOK · CI/security · 532 تست.

**🟡 نیمهباز (Implementer-side):** CMS Golden E2E · seed deep validation · Business Load نهایی · AI Benchmark 52 · Provider decision · Failure drill · Final Deployment Drill.

**🔴 باز (User-side — فقط اینها پیش کاربر میماند):** ZarinPal واقعی · Kavenegar واقعی · Android/iPhone واقعی · Push واقعی · Search Console · دامنهٔ نهایی · برند/لوگو.

**یافتهٔ کلیدی نقد که میپذیرم:** «تعداد تست ≠ اثبات واقعی» — تمام گیتهای باقی، اثباتِ business-level هستند (E2E زنده + load + benchmark + drill)، نه تست unit بیشتر. هیچ feature جدیدی ساخته نمیشود.

---

## R) گیتهای Implementer (ترتیب اجرا)

### R.1 — CMS Golden Path E2E + Seed Deep Validation (الان، بدون وابستگی)
**الف) Golden Path اتوماتیک (pytest، تست DB):** admin login → create article → draft → edit → publish → upload image (R2 mock) → public render → SEO meta/canonical درست → edit → revision v2 → restore v1 → audit rows → delete → sitemap update. (تست تستکنندهٔ خود ما نیست — تستِ مسیر واقعی کاربر است.)
**ب) Seed Deep Validation روی prod (اسکریپت):** count articles (== 50) · published/draft split · slug uniqueness (صفر تکراری) · هر 50 URL قدیمی → 200 · هر body render (بدون None/افتاده) · meta_title/meta_description/canonical/image URL غیرخالی · sitemap.xml شامل همهٔ 50 slug · مقایسهٔ شمارش JSON historical vs DB.
**ج) E2E زندهٔ prod (پاکسازی کامل بعدش):** یک مقالهٔ آزمایشی واقعی بسازم → publish → public render 200 → revision → restore → DELETE در انتها (هیچ data واقعی جا نمیماند).
**پذیرش:** a+b+c همه PASS → `CMS-E2E = PASS`.

### R.2 — Business Load نهایی (معیار: provider healthy → الان اجرا، نه ساعت)
سینیار: 10 users · 10 charts · 5 chats · 3 reports · R2 artifacts · QA · fallback · budget — با architecture فعلی.
**اگر provider الان ناسالم (K1/K2 weekly-limited):** اجرا میشود ولی حداقل subset اجرا میشود (charts/chats بدون AI) و گزارش وضعیت «BLOCKED_BY_PROVIDER یا partial» صادقانه ثبت میشود؛ اجرای کامل بهمحض healthy.
**پذیرش:** 10/10 charts · 5/5 chats · 3/3 reports · R2 3/3 · zero fake-done · zero unexpected degraded · cleanup 100% → `BUSINESS-LOAD = PASS`.

### R.3 — AI Benchmark نهایی (۵۲ چارت، v4، ۶ gate)
معیار اجرا = **provider healthy** (poll خودکار هر ۱۵ دقیقه بعد از ریست ~۰۸:۳۰ تهران؛ cron 09:00 بهعنوان backstop) — نه ساعت.
**گزارش جداگانه ۴ عدد:** Infrastructure (p95/retry/fail/unexpected) · Generation Success · AI Quality (det/rub/rep) · Hard Gates.
**پذیرش سخت (absolute):** critical hallucination=0 · grounding=0 · contradiction=0 · unsafe=0 · repeatability=100% · unexpected-degraded=0 · p95≤40s · retry≤30% · fail≤25% · **AI Quality ≥ 80 (secondary — هیچ gate را override نمیکند)** → `AI-BENCHMARK = PASS`.

### R.4 — Provider Decision (بعد از R.3 — با داده، نه حدس)
- GO pool: availability alto + latency good + quality ≥80 → **DeepSeek Direct خریداری نمیشود** (اقتصادی).
- GO bad → DeepSeek Direct اضافه شود با همان gates + budgetها (decision matrix در R.3 آماده میشود).
- خروجی: یک خط در config + جدول مقادیر measured.

### R.5 — Deployment Failure Recovery Drill (روی staging/آزمایشی، هرگز prod)
**سناریوی نقد:** backup created → migration INTENTIONALLY broken → deployment abort → restore → boot → healthy.
اجرا: ۱) pre-deploy backup واقعی · ۲) migration خراب (کلید fail) روی DB آزمایشی · ۳) abort خودکار deploy.sh بررسی · ۴) restore از backup · ۵) `alembic upgrade head` + sanity rows · ۶) boot + /health deep.
**پذیرش:** کل زنجیره بدون دخالت دستی کار میکند → `FAILURE-DRILL = PASS`.

### R.6 — Final Deployment Drill (پیش از FINAL GO)
ترتیب دقیق: Fresh backup → deploy → migration → deep health → smoke (همهٔ صفحات) → user flow (ایجاد چارت/چت/گزارش) → report flow → payment state (sandbox order) → **code rollback** (git revert) → **schema rollback** (downgrade) → boot.
**پذیرش:** هر ۱۲ گام سبز + rollback هر دو نوع ≤۵ دقیقه → `FINAL-DRILL = PASS`.

### R.7 — قانون دائمی Production (ثبت، یکبار برای همیشه)
**سه مسیر جدا:**
1. **محتوا** → Admin → Content → Edit → Publish (بدون deploy — CMS)
2. **کد** → branch → tests → CI → staging → **approval** → fresh backup → migration → deploy → health → monitor (هرگز AI مستقیم prod)
3. **Prompt** → Prompt version → benchmark/regression → publish
+ آمادهسازی GitHub Environments (protected `production` + approval rules) برای enforce مسیر ۲. + cronهای موجود (backup 03:15 · drill هفتگی · disk watchdog · error500).

---

## P1) گیتهای خارجی — دقیقاً چه چیزی از کاربر لازم است (هر کدام = یک فرم آماده)

| # | گیت | چه چیزی از MaHDi لازم است | بعد از دریافت, من |
|---|---|---|---|
| P1.1 | ZarinPal واقعی | مرچنت ID فعال (پنل زرینپال؛ دامنهٔ callback نهایی لازم است — **وابسته به P1.7**) | swap sandbox→prod، تست مبلغ کوچک واقعی، حذف order تست |
| P1.2 | Kavenegar واقعی | API key + خط (سرویس پیامک) | OTP واقعی روی گوشی خودش |
| P1.3/4 | Android + iPhone | گوشی فیزیکی (لنز ریموت = تست شبیهساز، نه کافی) | Golden path checklist چاپشده (ثبت/چارت/خرید/پوش) — گامبهگام با او |
| P1.5 | Push واقعی | گوشی + permission | subscribe واقعی + delivery + دکمهٔ تست در ادمین |
| P1.6 | Search Console | **دامنهٔ نهایی (P1.7) اول** + اکانت گوگل | verification (DNS TXT) + sitemap + inspection + coverage |
| P1.7 | **دامنهٔ نهایی** | **تصمیم: zayche.io یا chart.negar.io — قبل از P1.6 و P1.1** (تغییر بعداً = ریسک SEO/cookie/callback/CORS/push) | انتقال کامل (nginx/SSL/canonical/callback/sitemap) |
| P1.8 | برند/لوگو | لوگو + favicon + OG image + app icon (من میتوانم پیشنویس AI بدهم، تصمیم با او) | جایگذاری + meta/OG/sitemap برند |

**ترتیب وابستگی:** P1.7 (دامنه) → P1.6 (Search Console) و P1.1 (callback) → بعد بقیه.

---

## زمانبندی

| زمان | کار |
|---|---|
| **الان (امشب)** | R.1 کامل (Golden E2E + seed deep validation + E2E زنده + cleanup) · R.5 آمادهسازی (اسکریپت drill + تست روی staging) |
| **فردا ~۰۷:۴۵** (cron) | Business Load — اگر provider ریست شده باشد (میشود: ریست ۰۸:۳۰؟ → cron 07:45 ممکن است قبل از ریست باشد → اجرای partial + auto-poll) |
| **فردا ۰۹:۰۰** (cron backstop) | AI Benchmark 52 — poll ۱۵ دقیقهای از ۰۸:۳۰ |
| **بعد از R.3** | R.4 provider decision → deploy → R.6 final drill |
| **موازی** | کاربر آمادهسازی P1 (دامنه + مرچنت + کلید SMS + گوشی + لوگو) |
| **پایان** | Final Release Matrix: ALL REQUIRED GATES = PASS → **FINAL VERDICT: GO** |

## Rollback (برای کل پلن)
هر مرحله: fresh backup گرفتهشده → هر تغییر فقط از طریق git commit + deploy.sh → revert = git revert + alembic downgrade (Expand→Contract پابرجا). هیچ تغییر مستقیمی روی prod.

## عدم-شامل (تا FINAL GO ممنوع — طبق نقد)
هیچ feature جدیدی (جز blockerهای بالا) · هیچ تست unit تزئینی · هیچ کاری روی مسیر طولانی بدون dependency.

---
*امضا: Hermes — آمادهٔ اجرای R.1 امشب.*