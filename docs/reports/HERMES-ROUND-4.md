# گزارش هرمس — دور ۴ (هستهٔ درآمد: A2 + A3 + A4)

**مدل:** deepseek-v4-flash · **تاریخ:** 2026-08-21 · **برنچ کاری:** `hermes/plan-v1-r1`
**کامیتها:** A2=`e619fe8` · A3-module=`9185321` · A3-gates=`4376329` · A4-backend=`b39b643`
**سوئیت:** 604 passed, 1 skipped (سوئیت خام: از 18 failed + 9 error → 566 → 604)
**هزینهٔ LLM:** $0 (هیچ endpoint پولی در تستها شلیک نشد)

---

## خلاصه
این دور **هستهٔ درآمد (اعتبار)** پیاده شد: سرویس مرکزی اعتبار، لایهٔ استحقاق، بازنویسی گیتهای درآمد، و مسیر خرید یکپارچه. همهٔ `SET credits` به یک ماژول (`app/credits.py`) منتقل شد — الزام معماریِ پلن برقرار.

## تغییرات (A2 → A3 → A4)

### A2 — سرویس مرکزی اعتبار (`app/credits.py`)
- `spend(session, user_id, action_key, *, idempotency_key, chart_id=None)` → atomic `UPDATE ... WHERE credits >= :p RETURNING id`؛ در بزودی `ZAY-CRD-001`. Idempotency توسط کلید یکتا + تراکنش واحد (commit فقط بعد از add ledger؛ در تصادم کلید، تراکنش rollback و تراکنش برنده برگردانده میشود — هیچ خرج دوباره).
- `refund(session, tx_id, reason)` → atomic برگشت (`credits = credits + :c WHERE id = :uid`)؛ idempotent.
- `grant(session, user_id, amount, reason, *, idempotency_key, source_ref=None, commit=True)` → `commit=False` برای تراکنش بیرونی پرداخت (از partial-commit جلوگیری).
- `balance(session, user_id)` و `get_price(session, action_key)` (از DB، نه hardcode).
- استثناها: `CreditError` (پایه، code `ZAY-CRD-000`)، `InsufficientCredits` (ZAY-CRD-001)، `UnknownAction` (ZAY-CRD-002).
- **نکتهٔ فنی:** `session.exec(text("UPDATE..."))` بدون مصرف نتیجه (RETURNING) lazy اجرا میشود؛ به `session.execute` (بومی SQLAlchemy) مهاجرت شد — فوری اجرا و مطمئنتر.
- **مهاجرت callers:** `app/explore/service.py` (spend/refund/grant_free) و `app/payment/orders.py` (subscription/purchase/referral) به سرویس مرکزی delegate شدند؛ `grep -rn "SET credits" app/ | grep -v app/credits.py` → **خالی**.
- ۱۲ تست پذیرش.

### A3 — لایهٔ استحقاق + گیتها
- `app/entitlements.py`: `has(session, user_id, kind, *, chart_id=None, ref_id=None)`، `consume(session, ent, n)` (atomic)، `grant_from_credits(...)`، `grant_from_order(...)`.
- **تصمیم کاربر (per-report):** استحقاقِ گزارش به `ref_id=report.id` گره میخورد (فیکس F-17 ممیزی)، نه per-chart — بدون over-grant.
- **گیتها:** `_report_gate` (per-report + legacy order)، `api_chat_access` (پک گفتگو با سهمیه quantity)، `api_synastry_access` (استحقاق synastry + legacy). مسیر legacy (order پرداختشده) **دستنخورده** حفظ شد — مشتری فعلی چیزی از دست نمیدهد؛ مسیر entitlement **افزودنی** است.
- `grant_from_credits`: quantity از نگاشت اکشن (`chat_pack_20`→۲۰) + `ref_id`.
- ۱۰ تست پذیرش.

### A4 (پشتیبان) — مسیر خرید یکپارچه
- `POST /api/purchase` (`app/main.py`): `{action_key, chart_id?}`.
  - بدون لاگین → **401** `{login_required, next}`.
  - کمبود اعتبار → **402** `{needed, have, packs}` (پکهای اعتبار credit3/6/12 از DB).
  - موفق → **200** `{ok, entitlement_id, remaining}` (via `grant_from_credits`).
  - اکشن ناشناخته → **400**.
- پاسخها با `JSONResponse` در **سطح بالا** (نه `{"detail": ...}`) — مطابق قرارداد پلن.
- ۴ تست پذیرش.

## تستها
- **A2:** `tests/test_credits_service_a2.py` (12) — atomic، idempotency، refund، grant، concurrency (single-success)، accounting-invariant (50 عملیات)، negative-guard.
- **A3:** `tests/test_entitlements_a3.py` (10) — per-kind، per-chart، per-ref، expiry، exhausted، consume، grant_from_credits (idempotent + ref_id + quantity)، grant_from_order.
- **A4:** `tests/test_purchase_a4.py` (4) — 401/402+pack/200/400.
- **سوئیت کامل:** 604 passed, 1 skipped؛ `test_authz_matrix` با ردیف `POST /api/purchase` + `POST /api/track` و `GET /api/admin/funnel` همگام شد.

## هزینه
**$0** — هیچ فراخوانی LLM در تستها؛ فقط validation/DB/read-only.

## بلاکر / تصمیم بازگرفته
- **ref_id در `has()`:** وقتی استحقاقِ report با `ref_id=None` ساخته شود، فیلتر ref رد میشود → خریدِ یک گزارش به همهٔ گزارشها دسترسی میدهد (over-grant). مطرح شد و **کاربر per-report را تأیید کرد** (فیکس F-17). پیادهسازی: `grant_from_credits(ref_id=report.id)` بعد از تولید گزارش.
- **quantity پیشفرض:** `chat_pack_20` باید quantity=۲۰ داشته باشد، نه ۱ — با `_action_quantity` فیکس شد.

## بعدی
- **A4 UI** (بازنویسی `plans.html` + هدر اعتبار + `credit_cta`) — با تأیید بصری مرورگر موبایل.
- **A5** (اجبار حساب برای خرید + claim چارتهای ناشناس).
- **A6** (مهاجرت استحقاقها: backfill + dry-run).
- **A7** (پنل ادمین اقتصاد اعتبار).

## Rollback
هر مرحله گامبهگام: `git revert <commit>` (مثلاً `git revert b39b643` برای A4-backend). کل برنچ: `git checkout main && git merge hermes/plan-v1-r1` (بعد از بازبینی کلود).
