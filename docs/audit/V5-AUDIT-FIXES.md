# گزارش فیکس ممیزی پنجم (V5-AUDIT) — پلتفرم زایچه

- **تاریخ:** پنجشنبه ۲۴ مرداد ۱۴۰۵ (2026-08-14)
- **منبع:** `ZAYCHE-Final-Audit.md` (ممیزی AI خارجی — امتیاز ۸.۰/۱۰)
- **نتیجهٔ راستی‌آزمایی:** ۱۰ ادعا از ۱۰ تأیید شد (این ممیز دقیق بود؛ شمارهٔ خطوط برخی موارد قدیمی بود ولی ماهیت همهٔ ادعاها درست)
- **کامیت:** `fix(v5-audit)` — push شده + دیپلوی prod ✅

## راستی‌آزمایی ادعاها (قبل از فیکس)

| ID | Severity | ادعا | راستی‌آزمایی |
|---|---|---|---|
| F-01 | P0 | برداشت بدون reserve → برداشت مکرر از یک موجودی | ✅ درست — `withdraw_request`/`resolve_withdrawal` هیچ‌کدام balance را تغییر نمی‌دادند |
| F-02 | P0 | race در پرداخت با موجودی (double-spend) | ✅ درست — read-check-subtract بدون lock اتمیک |
| F-03 | P1 | گزارش wallet-paid هرگز enqueue نمی‌شود | ✅ درست — فقط در مسیر زرین‌پال enqueue می‌شد؛ cron هم queued را برنمی‌دارد |
| F-04 | P1 | refund در `refunding` گیر می‌کند؛ repeat → refund_failed | ✅ درست — retry فقط از paid/refund_failed؛ خطای ۶۶/۶۷ → failed |
| F-05 | P1 | dedupe وب‌هوک process-local با ۲ worker + clear کل set | ✅ درست — `_seen_update_ids` set سراسری + `clear()` در ۱۰k |
| F-06 | P1 | fallback تهران برای مختصات جهانی → چارت غلط | ✅ درست — `tz_from_coords` همیشه Tehran برمی‌گرداند |
| F-07 | P1 | race ساخت گزارش → دو LLM job | ✅ درست — SELECT-then-INSERT بدون constraint/lock |
| F-08 | P1 | حذف حساب: audio و PDF محلی باقی می‌مانند | ✅ درست — فقط `r2_key` حذف می‌شد |
| F-09 | P1 | چت بدون system message — مرز trust ندارد | ✅ درست — policy + سؤال در یک user message |
| F-10 | P2 | referral با پرداخت wallet پاداش نمی‌گیرد | ✅ درست — reward فقط در مسیر زرین‌پال |

## فیکس‌ها

### P0 (blocker لانچ — مالی)
- **F-01:** `withdraw_request` مبلغ را **همان لحظه reserve** (debit) می‌کند؛ `resolve_withdrawal("rejected")` برمی‌گرداند؛ `"paid"` debit را نگه می‌دارد. یک pending همزمان + موجودی کسرشده ⇒ برداشت مکرر غیرممکن.
- **F-02:** debit اتمیک: `UPDATE users SET balance_rial = balance_rial - :amt WHERE id = :uid AND balance_rial >= :amt` — rowcount≠۱ ⇒ رد. دو درخواست همزمان دیگر نمی‌توانند double-spend کنند.

### P1
- **F-03:** بعد از پرداخت wallet، `_enqueue_report(order.report_id)` دقیقاً مثل مسیر زرین‌پال (fail → `failed` با پیام بازتولید).
- **F-04:** حالت `refunding` قابل retry شد؛ خطای gateway حاوی already/duplicate/66/67 → `refunded` (idempotent) + coupon/subscription هم بسته می‌شوند.
- **F-05:** dedupe با **Redis SET NX EX (TTL 300s)** مشترک بین worker ها؛ fallback محلی دیگر `clear()` نمی‌کند (پیرترین عضو را حذف می‌کند).
- **F-06:** `tz_from_coords` → `None` در خطا؛ `resolve_tz_safe` — تهران فقط داخل ایران (bounding box)؛ خارج → ۴۰۰ در وب / پیام شهر در ربات.
- **F-07:** `pg_advisory_xact_lock(hashtext('report:<chart_id>'))` قبل از select — دو POST همزمان سریال می‌شوند.
- **F-08:** حذف حساب: `audio_r2_key` + `pdf_path` محلی هم حذف می‌شوند؛ شکست R2 در audit log ثبت می‌شود.
- **F-09:** `CHAT_SYSTEM_PROMPT` (policy ثابت) به‌عنوان **system message** واقعی؛ user message فقط context + سؤال.

### P2
- **F-10:** `pay_order_with_balance` هم `reward_referral` را صدا می‌زند (try/except مثل مسیر زرین‌پال).

## تست‌ها
- **۹ تست جدید** در `tests/test_v5_audit_fixes.py` (reserve/reject، race دو-thread، enqueue wallet، refund idempotent، dedupe Redis، tz fail-closed، advisory lock، حذف audio/pdf، referral wallet) + آپدیت ۴ تست قدیمی به رفتار درست.
- سویییت کامل: **303 passed + 1 skipped** (از 294) — سه اجرای متوالی پایدار.
- `alembic check` پاک (بدون migration جدید — همه‌چیز در لایهٔ منطق/query).
- RUFF-OK.

## وضعیت پس از فیکس
- **هر ۱۰ یافته بسته شد.** P0 های مالی (برداشت بی‌نهایت، double-spend) رفع و با تست race اثبات شدند.
- دیپلوی prod ✅ + راستی‌آزمایی زنده (صفحات 200، admin 403، gate ها سر جای خود).

## باقی‌مانده (runtime — نیازمند طرف کاربر)
زرین‌پال واقعی، SMS واقعی، تست گوشی، اولین اجرای ترانزیت هفتگی (شنبه)، Web Push روی دستگاه — طبق بخش ۴ خود گزارش، از روی کد قابل اثبات نیستند.
