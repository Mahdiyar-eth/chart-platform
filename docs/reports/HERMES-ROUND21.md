# ZAYCHE — دور ۲.۱ (پاسخ به بازبینی Opus R2) — ۱۴۰۴/۰۶/۰۱

## نتیجه: Y1–Y12 اجرا شد؛ `scripts/ci.sh` برای اولین بار کاملاً سبز؛ prod لایو.

## راستیآزمایی Opus R2 (قبل از فیکس)
همهٔ یافتههایش (N1-N11) با کد/اجرای زنده تأیید شد — N1 حتی بازتولید شد:
خرید report_full → گزارش ساخته شد → PDF = 403. جزئیات در گفتگو.

## فیکسها (کامیت d2b053c)
| ID | فیکس |
|---|---|
| Y1/N1 | bind `ent.ref_id = rep.id` بعد ساخت گزارش + AC-1 E2E کامل بدون monkeypatch گیت: خرید→گزارش→PDF→DOCX همه 200، موجودی دقیق |
| Y2/N2 | plan_key از `CreditTransaction.reason` (از طریق ent.source_ref) — بدون مهاجرت؛ AC-2 پارامتریک: basic/full/gold هر سه درست |
| Y3/N3 | کش اول، spend بعد — ماه بعدِ کششده صفر اعتبار |
| Y4/N7 | مهاجرت c7f1a2b9d4e6 (uq_transit_chart_months) + c8d2e3f4a5b6 (همترازی اسکیمای مدلها: ایندکسهای funnel_events، nullable transit_alerts، حذف FK مدل-خارج transit_forecasts) — روی DB prod اعمال و تأیید شد |
| Y5/N5 | کلید idempotency rectify قطعی (بدون uuid4) — دابلکلیک یک بار خرج میکند (تست دارد) |
| Y6/N6 | سقف تجمعی refund ≤ cost تراکنش اصلی (تست ۳+۳ روی ۵) |
| Y7/N4 | سلکتور ۳ماه/۱۲ماه در UI گذرها + months پارامتری در analyze JS |
| Y8/N10 | yearly به گیتهای چت (هر ۳ تاپل) + _kind_for_plan اضافه شد — مشترک سالانه چت دارد (تست E2E دارد) |
| Y9/N11 | چک expires_at داخل consume() (ضد TOCTOU) |
| Y10 | os.environ.setdefault در ۱۲ فایل تست + حذف مسیر هاردکد eph |
| Y11 | assert جامانده r3 (نسخهٔ order-independent) + AC-2 جایگزین تست ضعیف x8 |
| Y12 | خروجی کامل CI: docs/qa/CI-ROUND21-2026-08-23.log |

## CI — اولین بار FULL GREEN
- alembic chain + drift check ✓
- pytest: **701 passed + 1 skipped**، پوشش **۸۲٪**
- boot smoke های prod-mode (fail-closed secrets/R2/rate-limit) ✓
- compileall ✓ · ruff F,E9 تمیز شد (۶۲ فیکس خودکار + F841های دستی) · bandit -lll تمیز (md5→sha256 در cache-buster)

## استقرار
main=d2b053c پوش شد؛ chart-web/chart-worker ریاستارت؛ /health سبز؛ صفحات کلیدی 200.

## مانده (Y13–Y17 کوچک/تصمیم مالک)
- Y13 داکسترینگ _chat_daily_limit (N12a)
- Y14 credit_cta در چت/سیناستری/کاوش (N12d)
- Y15 تصمیم مالک: rectify مهمان رایگان بماند؟ (N12e)
- Y16 R18/R25 (N12f)
- Y17 نکته merge روایتهای کهنه (N12b)
