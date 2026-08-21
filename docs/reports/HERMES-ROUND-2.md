# گزارش هرمس — دور ۲ (سختسازی سوئیت)

**مدل:** deepseek-v4-flash · **تاریخ:** 2026-08-21 · **برنچ کاری:** `hermes/plan-v1-r1` · **کامیت:** `2937356`

## 🎯 هدف
دور ۱ نشان داد که سوئیت روی **DB خام** ۱۸ failed + ۹ error میداد (ناشی از شکنندگیِ از پیش موجود، نه تغییرات هرمس — این روی کامیت پایهٔ `f6def7e` هم بازتولید شد). تصمیم کاربر: اول این تستها را سختسازی کن تا «پایهٔ مطمئن» داشته باشیم.

## 🔍 ۵ ریشهٔ اصلی + فیکس
| # | علت | فیکس | اثر |
|---|---|---|---|
| ۱ | `lifespan` پس از `commit()`، شیءهای ماژول `PLANS_SEED` را `expire` میکرد → دسترسی بعدی در تستها `DetachedInstanceError` (۱۷ بار) | `with Session(engine, expire_on_commit=False) as s` در `app/main.py` | رفع ~۱۷ خطا |
| ۲ | `db.seed_plans()` فقط ۶ پلن داشت؛ `credit3/6/12` (که `main.PLANS_SEED` دارد) را سید نمیکرد → `orders_plan_key_fkey` و `plan not found` | اضافهٔ پکهای اعتبار به `app/db.py` | رفع خطاهای plan |
| ۳ | `test_coupon_atomic` یک `INSERT INTO coupons` خام بدون ستون NOT NULL ی `report_only` | افزودن `report_only=false` به INSERT | رفع ۲ خطا |
| ۴ | `wallet_user` fixture با `phone` ثابت «09120000007» — تستِ قبلی Order برای آن میساخت و DELETE بعدی با FK تداخل میکرد | phone یکتا (`uuid`) در `test_audit_fixes.py` | رفع ۳ خطا |
| ۵ | `updated_at` ستون `reports` بهصورت naive ذخیره میشود ولی تست با aware مقایسه میکرد (TypeError) | مقایسه با naive-UTC در `test_stale_recovery.py` | رفع ۱ خطا |

## ✅ نتیجه
```
566 passed, 1 skipped in 30.77s   # روی DB کاملاً خام — exit=0
```
**یعنی سوئیت از ۱۸ failed + ۹ error به سبزِ کامل روی DB خام رسید.** این یک نقصِ واقعیِ نهفته را هم حل کرد (seed پلنها ناکامل بود و expire_on_commit شیءهای مشترک را میکشت).

## 📌 نکته
سختسازی فقط تست/کد بود؛ **schema و migration عوض نشد** (بنابراین اثبات «بدون drift» دور ۱ معتبر است).

## 🧭 وضعیت طرح کلان
- **دور ۱:** Z1 ✅ | E1 ✅ | A1 ✅ (مدل اعتبار)
- **دور ۲:** سختسازی سوئیت ✅ (اکنون ۵۶۶ سبز روی DB خام)
- **باقیماندهٔ مرحلهٔ ۰:** C1 (دیزاینسیستم) و G1 (رویدادهای قیف) — سپس مراحل ۱–۵.
- **مانع محیطی شناختهشده:** `alembic autogenerate` روی این DB تست (ساختهشده با `create_all`) کار نمیکند و `CREATE EXTENSION vector` برای DB تازه به ادمین نیاز دارد → migration ها دستی نوشته میشوند. این را باید حل کرد (پیشنهاد: یک `sa.Postgresql`/superuser برای تست یا `alembic stamp`).
