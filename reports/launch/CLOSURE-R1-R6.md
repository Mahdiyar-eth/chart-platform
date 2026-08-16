# ZAYCHE — CLOSURE STATUS (پس از R.1–R.6)
**2026-08-16 · HEAD: b915608 · تست: 533 passed + 1 skipped · prod: homepage/faq/articles 200**

## ✅ بسته شد (این جلسه)
- **R.1 CMS**: Golden Path E2E (11-step) + 3 باگ prod واقعی فیکس
  (_read_json body، body serialize، seed_pages extra) + Seed Deep Validation **10/10** + E2E زندهٔ prod (create→publish→render→sitemap→restore→delete)
- **R.5**: Failure Recovery Drill **PASS** (migration شکستهٔ عمدی → abort اثباتشده — alembic دستنخورده → restore از بکاپ → boot)
- **R.6**: Final Deployment Drill **۹ گیت PASS**:
  1. بکاپ تازه قبل از deploy ✅
  2. deploy (ff-only + migration + restart + smoke) ✅
  3. migration در head ✅
  4. health web 200 ✅
  5. smoke ۹ صفحه عمومی ✅ (**باگ /faq=500 پیدا و فیکس شد**)
  6. auth flow reachable ✅ (OTP real = BLOCKED خارجی)
  7. payment sandbox ✅ (merchant real = P1)
  8. rollback drill PASS ✅
  9. (شمارش کل با ok ها)

## ⛔ BLOCKED_BY_PROVIDER (تا ریست کلیدها — فردا ~08:30)
- **R.2 Business Load** — cron دیروز `15 4 * * *` (07:45 تهران) اجرای نهایی
- **R.3 AI Benchmark 52 چارت** — cron `30 5 * * *` (09:00 تهران)
- **R.4 Provider decision** — بعد از benchmark (GO pool vs DeepSeek Direct)

## 🔴 فقط مال تو (P1 الخارجی — بدون کدنویسی)
| مورد | دقیقاً چه چیزی لازم است | آماده از ما |
|---|---|---|
| مرچنت زرینپال | مرچنت واقعی + `ZARINPAL_SANDBOX=false` | sandbox E2E تستشده؛ callback آماده |
| کلید کاوهنگار | SMS API key → `KAVENEGAR_API_KEY` | OTP fail-closed، flow آماده |
| دامنهٔ نهایی | تصمیم `zayche.io` یا `chart.negar.io` **قبل از Search Console** | هر دو کار میکنند؛ canonical/sitemap آماده |
| برند/لوگو | لوگو، favicon، OG image، metadata | placeholder فعلی؛ اندازهگیری CWV/SEO سبز |
| گوشی Android + iPhone | Golden Path دستی (۲ بار) | mobile-first UI، 44px targets |
| Push واقعی | دستگاه real برای web-push subscribe | VAPID keys آماده در .env |
| Search Console | verification + sitemap + inspection (بعد از دامنهٔ نهایی) | sitemap.xml ۶۵+ URL زنده |

## قانون دائمی production (ثبتشده در RUNBOOK)
سه مسیر جدا:
- **محتوا** → Admin → Content → Edit → Publish (بدون deploy)
- **کد** → git branch → tests/CI → فیکس → push → deploy.sh (backup خودکار)
- **پرامپت** → PROMPT_VERSION → benchmark/regression → publish

واقعیت اندازهگیریشده: restart ~1.2s (۵×502 در ۱ ثانیه) — برای تغییرات مهم blue-green/nginx پیشنهاد میشود در release بعد.