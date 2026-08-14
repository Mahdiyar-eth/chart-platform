# دور ۴ — گزارش فاز B: زیرساخت و عملیات (۹ مورد) ✅

تاریخ: ۱۴ مرداد ۱۴۰۵ (2026-08-14) — همه موارد با تست/اجرای واقعی تأیید شدند.

| # | بند پلن | وضعیت | شاهد |
|---|---------|--------|------|
| B1 | DLQ کرون خودکار + ادمین degraded | ✅ | `retry_failed_reports.py --limit 10` هر ۳۰ دقیقه (crontab) + KPI «گزارش ناموفق (DLQ)» در داشبورد ادمین |
| B2 | بکاپ age + جداسازی سکرت + drill | ✅ | بکاپها age-encrypted (کلید خصوصی `/root/.hermes/keys/chart-platform-age.txt`، PUB در .env)؛ ۶ بکاپ plaintext قدیمی از R2/دیسک حذف شد (با تأیید کاربر)؛ **drill بازیابی موفق**: decrypt→unzip→pg_restore→plans=5/users=2؛ drill مصون از شل کثیف (میخواند مستقیم از .env) |
| B3 | Presigned ۳۰ دقیقه + refresh | ✅ | TTL 604800→1800؛ هر دانلود URL تازه از API میگیرد (۳۰۲ per-request) |
| B4 | R2 fail-closed در prod | ✅ | بوت بدون کریدنشال R2 در prod = RuntimeError (تست در CI)؛ آپلود ناموفق → گزارش `degraded` با پیام شفاف (نه سکوت) |
| B5 | Rate limit چارت + Redis اجباری prod | ✅ | ساخت چارت ۲۰/min per client (429)؛ prod با backend=memory از بوت سرباز میزند (تست CI)؛ Redis outage در prod = fail-closed |
| B6 | Refund lifecycle | ✅ | ریفاند واقعی زرینپال (refund.json)؛ حالات refunding/refund_failed + تلاش مجدد ادمین؛ بستن اشتراک مبدأ (subscriptions.order_id)؛ برگشت کوپن؛ `orders.error`؛ مهاجرت alembic |
| B7 | Payment state machine verifying | ✅ | pending→verifying→paid|failed؛ خطای شبکه → بازگشت به pending (پول ممکن است رفته باشد!)؛ رفرش → verify مجدد (کد ۱۰۱ زرینپال) → paid؛ فیکس باگ ORM expire (raw-SQL claim) |
| B8 | Subscription renewal + UNIQUE | ✅ | (در A9 کامل شد) |
| B9 | LLM concurrency | ✅ | circuit breaker (LLM_CIRCUIT_THRESHOLD=3, COOLDOWN=60s)، per-call timeout (LLM_TIMEOUT=120)، deadline سراسری (LLM_DEADLINE=150)، fallback وقتی همه tripped |

## نکات مهم اجرا
- **کشف باگ تاریخی**: مهاجرت A9 قبلاً روی DB اشتباه (اسکرچ) رفته بود چون shell DATABASE_URL آلوده بود؛ schema پرود از create_all قدیمی بود و با مدل drift داشت → مهاجرت align (66bc97b51008) با IF EXISTS/IF NOT EXISTS + `compare_type=False` در alembic env → `alembic check` حالا همهجا تمیز است.
- shell DATABASE_URL پاکسازی شد (unset) تا خطای کلاس «stale shell env» تکرار نشود.

## وضعیت
- تستها: **193 passed, 4 skipped** (B فاز +10 تست)
- CI: `==> CI OK` (خروجی ۰) — همه گیتها (ruff, bandit, pip-audit, secret, brand, alembic chain, coverage≥60%, ۷ چک smoke پرود)
