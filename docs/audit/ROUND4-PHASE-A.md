# دور ۴ — گزارش فاز A: بلاکرهای لانچ (۱۱ مورد) ✅

تاریخ: ۱۴ مرداد ۱۴۰۵ (2026-08-14) — همه موارد با تست واقعی تأیید شدند.

| # | بند پلن | وضعیت | شاهد |
|---|---------|--------|------|
| A1 | چرخش Umami + پاکسازی تاریخچه | ✅ | رمز ۱۲رقمی جدید (لاگین 200/قدیم 401)؛ **۲۴ کلید GCP از تاریخچه حذف**؛ کلون ریموت تمیز (AQ=0)؛ سکرتها در /opt/umami.env (600) |
| A2 | APP_ENV → IS_PROD یکپارچه | ✅ | `prod` و `production` هر دو fail-closed؛ ۵ تست بوت |
| A3 | Transit IDOR | ✅ | `/api/charts/{id}/transits` + `/transit/{id}` → بدون مالکیت 403 |
| A4 | Synastry مالکیت | ✅ | `/api/synastry/full` + `/access` → مالکیت هر دو چارت لازم |
| A5 | Order مالکیت | ✅ | POST /api/orders → مالکیت چارت لازم |
| A6 | Bot capability token | ✅ | چارتهای بات `access_token` میگیرند؛ لینکها `?t=` سالم |
| A7 | Report idempotent | ✅ | تکراری → همان گزارش؛ `?regenerate=1` → جدید؛ failed → re-queue |
| A8 | سهمیه چت اتمیک per-account | ✅ | Redis INCR+TTL قبل از LLM؛ release در خطا؛ تست race ۱۰ ترد (دقیقاً ۳ برنده) |
| A9 | انقضای اشتراک ماهانه | ✅ | چت بعد از انقضا 403؛ تمدید از روز باقیمانده (`max(now,expiry)+30d`)؛ وب (chat_id=NULL) پشتیبانی؛ مهاجرت UNIQUE(chart,COALESCE(chat)) |
| A10 | Coupon reservation | ✅ | اسلات اتمیک هنگام ساخت؛ release در: خطای درگاه/شکست verify/ریفاند/stale؛ اسکریپت sweep هر ۳۰ دقیقه |
| A11 | CI prod smoke test | ✅ | بوت prod بدون سکرت → refuse؛ با سکرت → /health و مسیرهای حیاتی 200 |

**تعداد تست: 183 passed, 4 skipped** — CI کامل (alembic chain + coverage 65% + ruff + bandit + pip-audit 0 vuln + secret scan + brand scan + smoke) ✅

**مهاجرت alembic اعمالشده روی prod**: `3c92dac1a241 subscription_expiry_unique`

**کرون جدید**: `release_stale_coupons.py` هر ۳۰ دقیقه (آزادسازی رزرو کوپنهای pending>30د)

**درگیریهای قابل توجه حلشده**:
- تستهای اشتراکی Redis: باکت rate-limit مشترک + کانترهای ماندگار → کلیدهای یکتا per-run
- authority های time-based در فیکهای درگاه → UUID در authority (تداخل سفارشها در همان ثانیه)
- ناسازگاری tz در SQLite/Postgres → `app/timeutil.py` (ensure_utc/utcnow)
