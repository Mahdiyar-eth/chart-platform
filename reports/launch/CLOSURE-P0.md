# P0 Closure — گزارش اجرای ۶ اصلاح نهایی + CMS + زیرساخت deploy

**تاریخ:** 2026-08-16 · **HEAD:** 5856458 · **تست:** 532 passed + 1 skipped

## ۱) راستیآزمایی نقد بیرونی (Untitled_8.md) — نتیجه

| ادعا | راستیآزمایی من | وضعیت |
|---|---|---|
| «restart ≈ بدون قطعی» نادرست است | **اندازهگیری واقعی prod**: restart → ۵ درخواست 502 در ~۱.۲ ثانیه | ✅ حق با نقد — ثبت در RUNBOOK |
| «git checkout = rollback کامل نیست» | ۱۸ migration همگی downgrade واقعی دارند؛ ولی data migration استراتژی جدا میخواهد | ✅ حق با نقد — Expand→Migrate→Contract ثبت شد |
| «DeepSeek fallback را همین حالا فعال کن» | **کلید DeepSeek پولی موجود نیست** (zen free هم 429) — تناقض با نقد قبلی خودش | ⚠️ تصمیم با Benchmark فردا |
| «CMS قبل از launch» | ✅ ساخته شد (P0-4) | ✅ |

## ۲) کاری که انجام شد

### P0-1 — Pre-deploy backup
deploy.sh الان قبل از هر migrate بکاپ تازه میگیرد (نه فقط daily 03:15) + log ثبت (`logs/deploy-backups.log`). هر دو بکاپ (disaster + deployment) فعالاند.

### P0-2 — Budget چندلایه + فیکس باگ مهم
- daily $3 · monthly $30 · per-user $1/24h · per-report $0.5 (قابل تنظیم با env)
- ZERO LLM call وقتی سقفی رسیده (degraded صادقانه)
- **باگ واقعی که خودکار پیدا شد:** وقتی هر ۵ بخش fail بود، گزارش با status=done (خالی!) تحویل میشد → الان degraded با پیام صادقانه. این دقیقاً کلاس خطایی بود که نقد دربارهاش هشدار داد.

### P0-3 — Production Health panel
`/api/admin/health` + سکشن زنده در ادمین: web/worker/db/redis/backup-age/LLM-keys+budget/queue/last-drill.

### P0-4 — CMS کامل ⭐
- **۴ جدول Postgres:** cms_articles · cms_pages · cms_media · cms_versions (migration `10958fde8752`)
- **مقالات:** ایجاد/ویرایش/حذف/draft/publish/unpublish/slug/title/excerpt/body/کategory/keywords/meta title/meta description/canonical/تصویر شاخص/author/publish_at
- **صفحات:** ویرایش مستقیم درباره/راهنما/FAQ (+ هر landing page با key)
- **Revisions:** هر تغییر snapshot (v1, v2, v3…) + restore یک کلیک
- **Audit:** هر تغییر (admin/timestamp/object/field/old/new) در audit_logs — همان مسیر refund/secrets
- **Media:** آپلود/حذف به R2 با validation (نوع/حجم)
- **منبع حقیقت:** سایت از PostgreSQL میخواند (DB-first)؛ JSON فقط fallback تاریخی
- **Seed:** 50 مقاله + 3 صفحه از JSON → prod انجام شد — همهٔ صفحات 200
- ۸ تست + 14 route در AUTHORIZATION-MATRIX

### P0-5 — Benchmark
- Partial الان اجرا شد: **BLOCKED_BY_PROVIDER** (هر دو کلید GO weekly-limited + zen 429) → gates همه FAIL (رفتار درست — نه fake pass)
- Cron فردا `30 5 * * *` (09:00 تهران — بعد از ریست ~08:30) فعال و سالم

### P0-6 — RUNBOOK (docs/RUNBOOK.md)
- اندازهگیری واقعی interruption: ~1.2s (۵×502) — سقف پذیرش <5s ثبت
- استراتژی rollback: code (git) + schema (alembic downgrade) + data (Expand→Migrate→Contract) + backup (pre-deploy)

## ۳) وضعیت گیتها
- Commits: `29ab06b` (P0-closure-1) → `36f6435` (CMS) → `5856458` (seed fix)
- همه push + deploy → prod سالم (articles/guide/home = 200)
- 532 تست سبز + ruff پاک

## ۴) فردا (برنامهٔ خودکار)
- **07:45 تهران** — Business Load Test (10 users، provider سالم)
- **09:00 تهران** — AI Benchmark کامل ۵۲ چارت (v4، ۶ gate فعال)
- بعد از نتایج → تصمیم K3 / DeepSeek Direct با دادهٔ واقعی → P1 (نیازمند منابع تو)

## ۵) P1 — نیازمند کاربر (بلوکرهای لانچ)
Real ZarinPal · Real SMS (کاوهنگار) · گوشی واقعی Android/iPhone · Push واقعی · Search Console + sitemap · دامنهٔ نهایی (zayche.io؟) · لوگو/برند

## ۶) نکتهٔ صادقانه
این چرخه با پیدا شدن ۲ باگ واقعی (all-fallback→done و seed serialize) تمام شد — همانطور که نقد گفت: «تستهای زیاد != اثبات واقعی»؛ سیستمهای تحویل (deploy/seed) هم باید خودشان اثبات شوند.