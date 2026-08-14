# گزارش فیکس ممیزی نهم (V9-AUDIT) — پلتفرم زایچه

- **تاریخ:** پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **منبع:** ممیزی مستقل V8 (AI خارجی — امتیاز ۸.۹/۱۰)
- **نتیجهٔ راستیآزمایی:** ۳/۳ ادعا درست بود (۲×P1 + ۱×P2)
- **تستها:** 312 passed + 1 skipped (۳ اجرای متوالی پایدار)
- **P0 باقیمانده: صفر | P1 باقیمانده: صفر**

---

## F-18 (P1) — Race در refund ادمین ✅

**ادعا:** دو ادمین همزمان میتوانستند یک order را هر دو `refunding` کنند
(transition با read/check/commit معمولی) و هر دو side-effects محلی
(`_release_coupon`، بستن اشتراک) را اجرا کنند — coupon used_count دوبار
کم میشد و در race با خرید جدید، سهمیهٔ کوپن خراب میشد.

**راستیآزمایی:** ✅ دقیقاً درست — `admin_refund` بدون CAS بود و
`_release_coupon()` فقط `used_count > 0` را decrement میکرد.

**فیکس (CAS دو مرحلهای):**
1. **Claim:** `UPDATE orders SET status='refunding' WHERE id=:oid AND
   status IN ('paid','refund_failed','refunding') RETURNING id` — هر caller
   میتواند به gateway برود (تکرارها 66/67 میگیرند) ولی…
2. **Finalize:** `UPDATE orders SET status='refunded' WHERE id=:oid AND
   status='refunding' RETURNING id` — **فقط برنده** coupon release و بستن
   اشتراک را اجرا میکند. Side-effects **دقیقاً یک بار**.
3. State غیرقابل ریفاند → 409 Conflict (بهجای 400).

**اثبات:** تست ۳ ترد همزمان + coupon + subscription — final state: refunded،
`used_count == 0` (یک بار کم شد)، subscription بسته. (تستهای قبلی 400→409
بهروز شدند — 409 سمانتیک درستتری است.)

## F-19 (P1) — orphan شدن دادهٔ Guest Synastry در failure پرداخت ✅

**ادعا:** اگر ساخت order برای Synastry بعد از ذخیرهٔ Chart A و Guest Person B
شکست بخورد، هر دو chart/profile — مخصوصاً Person B با user_id=NULL که هیچ
مسیر حذفی ندارد — در DB میماند.

**راستیآزمایی:** ✅ درست — فقط HTTP error برگردانده میشد، بدون cleanup.

**فیکس (failure compensation):** در except مسیر:
```
session.rollback()      # drop the uncommitted order (FK to chart A)
delete chart_a, chart_b → delete profile_a, profile_b → commit
```
نکتهٔ مهم: rollback اول لازم است چون order ساختهشدهٔ ناکام FK روی chart دارد
و delete بدون آن با ForeignKeyViolation شکست میخورد (در تست پیدا شد).

**اثبات:** تست با gateway-down: count charts/profiles قبل/بعد برابر — هیچ
orphan نمیماند.

## F-20 (P2) — کوپن reserve قبل از check موجودی در Wallet ✅

**ادعا:** در مسیر `x-pay-with-balance=1`، order + coupon reservation قبل از
بررسی موجودی ساخته میشد؛ موجودی ناکافی → pending order + reservation تا
sweep ساعتی باقی میماند.

**راستیآزمایی:** ✅ درست.

**فیکس (دو لایه):**
1. **Fail-fast:** قبل از `create_order`، اگر balance < قیمت plan → 400 فوری —
   هیچ order ای ساخته نمیشود.
2. **Fallback:** اگر بعد از ساخت (مثلاً با تخفیف) موجودی کافی نبود →
   order فوراً cancelled + coupon فوری release (نه تا sweep).

**اثبات:** تست: کاربر با 100k → 400، count orders بدون تغییر، coupon.used_count
دستنخورده.

---

## کارنامهٔ چرخه (V5 → V9)

| دسته | تعداد | وضعیت |
|---|---|---|
| P0 | ۶ مورد (F-01, F-02, F-11, F-15 + double-spendها) | ✅ صفر باقیمانده |
| P1 | ۱۱ مورد (F-03..F-09, F-12..F-14, F-17, F-18, F-19) | ✅ صفر باقیمانده |
| P2 | ۴ مورد (F-10, F-16, F-20 + v4 موارد) | ✅ |

تستها: 294 → **312** | migrations: 14 → **16** | prod: live 200/200
