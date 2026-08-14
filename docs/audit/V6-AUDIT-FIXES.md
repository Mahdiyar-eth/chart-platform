# گزارش فیکس ممیزی ششم (V6-AUDIT) — پلتفرم زایچه

- **تاریخ:** پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **منبع:** `ZAYCHE-Final-Audit-v2.md` (ممیزی AI خارجی — امتیاز ۸.۷/۱۰)
- **نتیجهٔ راستیآزمایی:** ۴/۴ ادعا درست (۱×P0 + ۳×P1)
- **تستها:** 305 passed + 1 skipped (۴ اجرای متوالی پایدار)

---

## F-11 (P0) — race در ایجاد withdrawal ✅

**ادعا:** دو درخواست همزمان withdrawal هر دو check های اولیه را پاس میکنند و دو
`WithdrawalRequest` میسازند؛ reservation اتمیک نیست → مجموع برداشتها میتواند از
موجودی بگذرد (overdraw).

**راستیآزمایی:** ✅ درست. `withdraw_request()` قبلاً balance را با ORM میخواند،
pending را با SELECT ساده چک میکرد و سپس کم میکرد — دو session همزمان هر دو
شرط را پاس میکردند.

**فیکس (دو لایه):**
1. **Debit اتمیک:** `UPDATE users SET balance_rial = balance_rial - :amt
   WHERE id = :uid AND balance_rial >= :amt` — rowcount 0 ⇒ رد.
2. **Partial unique index** (migration `cec42d441b5c`):
   `UNIQUE (user_id) WHERE status = 'pending'` — دومین درخواست همزمان به
   IntegrityError میخورد و debit آن rollback میشود. ایندکس در `models.py`
   هم اعلام شد تا دروازهٔ `alembic check` سبز بماند.

**اثبات:** تست `test_concurrent_withdrawals_only_one_wins` — ۳ ترد همزمان روی
موجودی ۱M با مبلغ ۷۰۰k → دقیقاً یک برنده، موجودی نهایی ۳۰۰k (یکبار reserve).

## F-12 (P1) — failure isolation در referral ✅

**ادعا:** exception در `reward_referral()` میتواند `session.rollback()` را اجرا
کند و settlement پرداخت را برگرداند — در مسیر زرینپال پول درگاه رفته ولی order
محلی paid نمیشود (و گزارش هنوز تولید میشود = گزارش رایگان).

**راستیآزمایی:** ✅ درست. در هر دو مسیر (verify زرینپال و pay_order_with_balance)
referral داخل transaction پرداخت بود و rollback آن، claim/paid را هم undo میکرد.

**فیکس:** referral به **بعد از commit اصلی** منتقل شد (after-commit best-effort
و idempotent). failure در referral دیگر هیچوقت پرداخت را برنمیگرداند.

## F-13 (P1) — حذف artifact های R2 در حذف حساب ✅

**ادعا:** `delete_object()` exception را swallow میکرد و حساب همچنان حذف میشد —
artifact خصوصی orphan میماند.

**راستیآزمایی:** ✅ درست. `delete_object` best-effort بود (False بدون raise).

**فیکس:** تابع جدید `delete_object_checked()` (raise میکند) در مسیر حذف حساب؛
هر خطای R2 → **fail-closed**: کل حذف rollback + HTTP 502 با پیام «بعداً تلاش
کنید». حساب و artifact ها دستنخورده میمانند تا retry موفق.

**اثبات:** `test_account_delete_fails_closed_when_r2_delete_fails` — R2 down →
502، حساب و گزارش هنوز در DB.

## F-14 (P1) — تشخیص already-refunded ✅

**ادعا:** substring matching (`"66" in err.lower()`) میتواند پیام نامرتبط
(مثل timeout با «66 seconds») را اشتباهاً `refunded` کند.

**راستیآزمایی:** ✅ درست. `ZarinpalError` فقط متن داشت؛ `admin_refund` با
`any(k in err.lower() for k in (...))` تصمیم میگرفت.

**فیکس:** `ZarinpalError` حالا `gateway_code` ساختاریافته دارد (از `errors[0].code`
یا `data.code`). `admin_refund` فقط کدهای صریح **66/67** را success میکند —
هر چیز دیگر `refund_failed` (fail-closed).

---

## نقاط قوت تأییدشده (بخش ۳ ممیزی)

همهٔ ادعاهای ردشدهٔ ممیزی تأیید شدند (IDOR/ownership gate، guest token، dedupe
Redis بین-worker، double-spend اتمیک، system boundary چت، HNSW، stale recovery،
systemd hardening، degraded banner و…).

## Verdict جدید

- P0ها: **۰ باقیمانده** (F-01/F-02/F-11 بسته شدند)
- Payment از 7.5 → انتظار بهبود در ممیزی بعدی
- تستها: 294 → **305** (۱۲ تست جدید در دور پنجم و ششم)
- migrations: 14 → **15**
