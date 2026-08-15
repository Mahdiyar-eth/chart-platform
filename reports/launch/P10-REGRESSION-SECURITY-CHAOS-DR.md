# P10 — Regression ×3 + Security + Chaos + DR — تکمیل شد

**تاریخ:** 2026-08-15 | **وضعیت:** ✅ DONE

## Regression
- **442 passed, 1 skipped ×3 اجرا** (سبز پشتسرهم)
- ruff F,E9: All checks passed

## Security
- `pip-audit`: **No known vulnerabilities**
- `bandit`: **High=0**؛ Medium=4 (همه B108 `/tmp` — سرور تکمستاجری، قابل قبول)؛ Low=21 (assert در محاسبات + try-except-pass عمدی)
- authz: /api/coupons/check Public (بدون دادهٔ خصوصی)

## Chaos (روی prod واقعی)
- **Redis stop** → homepage/plans/sky 200 (graceful)؛ OTP با 429 (بدون crash)؛ restore → 200
- **Postgres read-only** → GET 200؛ POST order → 500 کنترلشده (خطای خوانا، بدون crash)؛ restore → 200
- **Restart سرویس** → 200 بلافاصله؛ verify با Authority جعلی → 404 (نه crash)
- نتیجه: هیچ سناریویی سایت را کرش نکرد — خطاها graceful

## DR (بازیابی از backup)
- restore-drill.sh (جدید، در repo): decrypt newest backup (age) → pg_restore → ownership fix → `alembic upgrade head` → sanity → drop
- **DRILL OK**: users=29, paid_orders=8, migrations=1 — برابر prod
- باگهایی که در drill پیدا/فیکس شد: mktemp 700 → postgres نمیخواند (chmod 755)؛ GRANT کافی نیست (ownership لازم)؛ extension vector باید superuser بسازد

## Performance
- ۸ صفحهٔ اصلی: **۳۴–۶۲ms** (TTR) — بدون کش، عالی
- (baseline عمیق گزارش ۱۳ بخشی: avg 48s/p95 57s از قبل ثبت شده — تغییری در کد گزارش رخ نداده)

## E2E زرینپال sandbox
- در این بازه verify سندباکس rate-limited ماند (-12) — E2E واقعی قبلاً با ref_id=435522808 اثبات شده؛ شبیهسازی callback روی prod برای P7 (فعالسازی ۳۰ روز + گرنت یکبار) تأیید شد
