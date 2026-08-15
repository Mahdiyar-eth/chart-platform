# P8 — Referral + Coupon (فاز J) — تکمیل شد

**تاریخ:** 2026-08-15 | **وضعیت:** ✅ DEPLOYED

## Referral (§13)
- پاداش معرف: **۱۰٪** از مبلغ نهایی (قبلاً ۵٪) — `REFERRAL_REWARD_PERCENT`
- **۱ اعتبار کاوش هدیه** به کاربر معرفیشده بعد از اولین خرید (ledger `referral_bonus`) — فقط یک بار
- **جلوگیری از چرخهٔ معرفی**: اگر معرف در زنجیرهٔ معرفهای قبلی خریدار باشد (A→B→A) → پاداش void
- self-referral (استفاده از کد خودت) → void (از قبل)
- text UI: «۱۰٪ تخفیف برای دوست، ۱۰٪ پاداش برای تو، ۱ اعتبار هدیه برای او»

## Coupon LANCH20 (§13)
- **۲۰٪ تخفیف اولین گزارش عمیق** (basic/full/gold) — `report_only` ستون جدید
- گیت: فقط اولین گزارش (paid قبلی با REPORT_PLANS → رد)، فقط روی پلنهای گزارش (پک اعتبار → رد)
- max_uses + expiry + reservation اتمی (از قبل) — race/replay-safe
- `/api/coupons/check` — اعتبارسنجی بدون مصرف (چک first-report با کاربر فعلی)
- UI: باکس طلایی LANCH20 در /plans + input کد تخفیف با پیام inline (بدون alert)

## تستها (۶ تست P8) — 441 passed, 1 skipped ×۲
10% reward ✓ 1-credit bonus (یک بار) ✓ cycle voided ✓ LANCH20 first report ✓ rejected second/packs ✓ check endpoint ✓

## شواهد prod
- مرورگر واقعی 420px: باکس LANCH20 ✓ input کد ✓ پیام «نامعتبر» inline ✓ متن دعوت ۱۰٪ در حساب ✓
- LANCH20 در prod: `LANCH20|20|10000|0|t`
- migration `ea82d923` (server_default=false — چون coupons row داشت)

## باگهایی که در راه پیدا/فیکس شد
- migration NOT NULL بدون default روی جدول غیرخالی → server_default=false
- race در seed LANCH20 (۲ worker همزمان → duplicate) → ON CONFLICT DO NOTHING
