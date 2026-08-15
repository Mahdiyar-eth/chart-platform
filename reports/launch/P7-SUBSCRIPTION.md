# P7 — همراه (Subscription) — تکمیل شد

**تاریخ:** 2026-08-15 | **فاز:** H | **وضعیت:** ✅ DEPLOYED

## تغییرات
- پلن monthly = ۹۹٬۰۰۰ تومان (اصلاح از 399K) + پلن جدید yearly = ۸۹۰٬۰۰۰ (۲ ماه هدیه)
- `activate_subscription`: ۳۰/۳۶۵ روز بر اساس plan_key؛ تمدید از max(انقضا، حالا) — روزهای باقیمانده حفظ میشود
- گرنت ماهانه ۵ اعتبار: یک بار در هر ماهِ محلی (timezone ایران)؛ idempotent برای callback تکراری
- `grant_due_subscription_credits` — cron ماهانه برای اشتراکهای فعال
- `cancel_subscription` + `POST /api/subscriptions/{id}/cancel` (مالکیت chart→profile→user)
- `GET /api/subscriptions` — لیست اشتراکهای کاربر
- account.html: بخش «اشتراک همراه آسمان امروز» پویا (وضعیت/تمدید/لغو دو-مرحلهای بدون confirm())
- callback زرینپال: activate + گرنت ماه اول هنگام خرید
- migration `57a8681f0484` (subscriptions.last_credit_grant_at)

## تستها (۱۱ تست فاز H)
first activation ✓ renewal-extend ✓ failed renewal ✓ cancellation ✓ expiration ✓ overlapping ✓ duplicate callback ✓ monthly grant once-only + timezone ✓ due sweep ✓ entitlement بعد از restart/restore ✓ (435 passed, 1 skipped ×۳)

## شواهد prod
- شبیهسازی مسیر callback: sub monthly فعال، ۵۹ روز (۳۰ + ۲۹ تمدید)، گرنت تکراری در همان ماه رد شد، ledger `subscription +5` ✓
- order واقعی sandbox: payment_url StartPay ✓ (verify -12 rate-limit sandbox — مانند P6)
- مرورگر واقعی 420px: plans (ماهانه+سالانه) ✓ account (اشتراک همراه فعال + لغو + اعتبار) ✓
