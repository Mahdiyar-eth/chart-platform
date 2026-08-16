# RUNBOOK — ZAYCHE Deployment & Rollback Strategy (P0-6)

**تاریخ:** 2026-08-16 · مرجع نقد بیرونی #۵/#۶ (Untitled_8.md)

## 1) Deploy interruption — اندازهگیری واقعی (نه ادعا)

مطابق نقد بیرونی، «restart ~۲ ثانیه» به معنای zero-downtime نیست. اندازهگیری واقعی
(2026-08-16، 50 درخواست پشتسرهم همزمان با restart):

```
ok=44 total=50 → 5×HTTP 502 در بازهٔ ~۱.۲ ثانیه
```

**نتیجهٔ رسمی:** deploy روی chart-web = **قطعی ~۱.۲-۱.۵ ثانیه** (۵ درخواست 502).
این **Controlled restart است، نه zero-downtime.** انتظار UX: یک درخواست نادر
(از ~۱٪ در لحظهٔ restart) ممکن است 502 ببیند — کلاینت با retry روی لینکها
(دکمهٔ «دوباره تلاش کنید») مدیریت میشود. اندازهگیری در هر تغییر significant
در deploy (مثلاً افزودن کارگر دوم) تکرار شود.

اختیار (در صورت نیاز بعداً): nginx `proxy_next_upstream error timeout http_502`
روی upstream تکی فعلاً مؤثر نیست (یک instance). Blue/green = در صورت رشد،
نه الان (هزینهٔ زیرساخت فعلی یک سرور است).

## 2) Code rollback ≠ DB rollback

- **Code rollback:** `git checkout <commit> && bash scripts/deploy.sh` — تاریخچهٔ
  کامل و tag ها موجود است. این فقط کد را برمیگرداند.
- **Schema rollback:** alembic migrationها **downgrade واقعی دارند** (تأیید شد
  — مثال: `8d20fb4d4148` ستونها را drop میکند). تست:
  `alembic downgrade -1` روی DB تست قبل از هر release که migration دارد.
- **Data migrations:** تغییرات دادهبَر (backfill، rewrite) دستور کار
  **Expand → Migrate → Contract** است (نقد #۶) برای هر feature که ستون/داده
  جدید با transform دارد؛ در چنین موردی: ستون nullable → backfill →
  read-new → drop-old در ۲-۳ release جدا. تا زمانی که مشتری صفر است،
  migration های مستقیم با pre-deploy backup کافیاند؛ برای دادهٔ زنده این
  دستور کار الزامی است.

## 3) Pre-deploy backup (P0-5)

deploy.sh از الان (v15+) قبل از هر `--migrate` **بکاپ تازه** میگیرد و
شناسهاش را در `logs/deploy-backups.log` ثبت میکند:

```
== 1/5 pre-deploy backup (fresh, not the 03:15 daily) ==
```

- بکاپ 03:15 روزانه → disaster recovery (R2)
- بکاپ pre-deploy → deployment recovery (بازگشت به وضعیت دقیقِ قبل از migrate)

رولبک با داده: بکاپ pre-deploy + restore (scripts/restore-drill.sh — هفتگی
دریل میخورد).

## 4) Rules بعد از Launch (نقد #۱۰/#۳۱)

- AI/توسعهدهنده **هرگز مستقیم** prod را تغییر نمیدهد: هیچ SSH edit،
  تغییر مستقیم DB، تغییر پرامپت روی سرور، hot-patch بدون commit.
- مسیر: branch → test → commit → push (CI) → deploy.sh → smoke → monitor.
- پرامپتها: از پنل ادمین (نسخهبندی override) یا commit — قبل از change:
  AI regression، بعد: A/B در صورت نیاز، revert = تغییر version.

## 5) متریکهای Production (P0-3)

پنل ادمین → «Production Health»: web/worker/db/redis/backup-age/LLM keys/
budget/queue/last-drill. آستانههای واتچداگ: دیسک ≥85%، خطای 500،
worker down — همه به تلگرام (از قبل فعال).