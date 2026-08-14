# گزارش فیکس ممیزی هفتم (V7-AUDIT) — پلتفرم زایچه

- **تاریخ:** پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **منبع:** `ZAYCHE-V6-Final-Audit.md` (ممیزی AI خارجی — امتیاز ۸.۷/۱۰)
- **نتیجهٔ راستیآزمایی:** ۲/۲ ادعا درست (۱×P0 + ۱×P2)
- **تستها:** 308 passed + 1 skipped (۳ اجرای متوالی پایدار)
- **تأیید:** F-11 تا F-14 از دید ممیز بستهشده اعلام شدند ✅

---

## F-15 (P0) — race در resolve برداشت توسط ادمین ✅

**ادعا:** دو درخواست همزمان admin میتوانند یک withdrawal را هر دو `paid` کنند
(چون transition اتمیک نیست) — یعنی برای یک payout واحد دو «پرداخت شد» صادر
میشود؛ در حالت `rejected` هم موجودی **دوبار** برگردانده میشود.

**راستیآزمایی:** ✅ درست. `resolve_withdrawal()`:
```python
wr = session.get(WithdrawalRequest, wid)
if not wr or wr.status != "pending": return False
wr.status = status        # read-check-write بدون CAS
if status == "rejected":
    u.balance_rial += wr.amount_rial   # در هر دو caller همزمان اجرا میشد
session.commit()
```

**فیکس (CAS اتمیک):**
```sql
UPDATE withdrawal_requests SET status=:status, note=:note, resolved_at=:now
WHERE id=:wid AND status='pending' RETURNING id
```
- فقط **یک caller** برندهٔ transition میشود؛ بازنده False میگیرد.
- refund حالت `rejected` در **همان transaction و فقط در برنده** اجرا میشود
  (`UPDATE users SET balance_rial = balance_rial + :amt`).

**اثبات (روی PostgreSQL واقعی):**
- `test_concurrent_admin_resolve_only_one_wins` — ۳ ترد همزمان resolve-paid →
  دقیقاً ۱ برنده، وضعیت `paid`، موجودی یکبار کم شده.
- `test_concurrent_admin_reject_refunds_exactly_once` — ۳ ترد reject همزمان →
  دقیقاً ۱ برنده، موجودی **دقیقاً یکبار** برگشت.

## F-16 (P2) — durability AuditLog ✅

**ادعا:** `audit()` تمام خطاها را swallow میکند — refund/withdrawal/secret change
میتواند بدون record دائمی بماند.

**راستیآزمایی:** ✅ درست. `except Exception: pass`.

**فیکس:** fallback **append-only** — وقتی DB fail میکند، رویداد به
`/tmp/zayche-audit-fallback.log` (قابل تنظیم با `AUDIT_FALLBACK_LOG`) بهصورت
JSON-line نوشته میشود؛ هیچ action حساسی بدون ردپا نمیماند.

**اثبات:** `test_audit_writes_fallback_when_db_fails` — engine خراب → خط به فایل
fallback با action/admin/entity کامل.

---

## وضعیت P0 ها در کل چرخهٔ ممیزی

| دور | یافته | وضعیت |
|---|---|---|
| v5 | F-01 برداشت بدون reserve | ✅ |
| v5 | F-02 double-spend پرداخت | ✅ |
| v6 | F-11 race ساخت withdrawal | ✅ (ایندکس partial + debit اتمیک) |
| v7 | **F-15 race resolve ادمین** | ✅ (CAS اتمیک) |

**P0 باقیمانده: صفر.**

## Verdict جدید

- امتیاز Payment از 7.4 بالا خواهد رفت (هر ۴ یافتهٔ مالی/کیف پول بسته شدند)
- تستها: 294 → **308** (+۱۴ در دورهای v5–v7)
- migrations: 15 (بدون تغییر — F-15 ایندکس جدید نمیخواهد)
- prod: دیپلوی شد، homepage 200، `alembic check` پاک

## موارد Runtime (سمت کاربر، پیش از لانچ)

طبق بخش ۴ ممیزی: مرچنت واقعی زرینپال، SMS کاوهنگار، تست موبایل واقعی،
دامنهٔ zayche.io، اولین اجرای کرون هفتگی — اینها به runtime و اکانتهای واقعی
نیاز دارند، نه کد.
