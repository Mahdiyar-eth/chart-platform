# RUNBOOK — پلتفرم چارت تولد (chart-platform)

آخرین بهروزرسانی: ۲۲ مرداد ۱۴۰۵ (v0.6.0)

## معماری
- **FastAPI** (uvicorn, پورت dev 8767) — `app/main.py`
- **Postgres 16** — دیتابیس `chart_platform` (کاربر `chart_app`) / تست: `chart_platform_test` (`chart_test`)
- **Redis + ARQ** — صف تولید گزارش (`venv/bin/arq app.report.worker.WorkerSettings`)
- **LLM**: روتر چندکلیدی Gemini (۲۴ کلید AQ؛ سهمیه ۲۰ تماس/روز/کلید ≈ ۴۸۰/روز) — `app/core/llm.py`
- **زرینپال** — سندباکس (حالا) → production (مرچنت واقعی لازم)
- **Ephemeris**: pyswisseph + فایلهای `ephe/` محلی

## Deployment (زنده — ۲۰۲۶-۰۸-۱۲)
- **دامنه**: https://chart.negar.io (A record → 91.107.183.171، Cloudflare proxied، SSL certbot)
- **nginx**: `/etc/nginx/sites-enabled/chart` → proxy به 127.0.0.1:8767 (گزیپ + کش استاتیک ۷ روز + CSP/HSTS/security headers)
- **سکرت‌ها**: `/root/chart-platform/.env` (توکن ربات‌ها، ZARINPAL، ADMIN_PIN — در git نیست؛ `app/config.py` لودش میکند)
- **پنل ادمین**: /admin با PIN رقمی (`ADMIN_PIN` در .env) — ورود: /admin/login؛ خروج: /admin/logout
- **دانلود PDF گیت‌شده**: فقط با سفارش paid همان چارت (403 در غیر این صورت)
- **ربات‌ها**: @Astrology_chartx_bot (تلگرام، webhook سکرتدار) + @astrologychartbot (بله، بدون سکرت)
  - webhook: `https://chart.negar.io/api/v1/telegram/webhook` + `/api/v1/bale/webhook`
  - ست/چک: `setWebhook` / `getWebhookInfo` (pending=0 و last_error=none = تأیید)
- **کارگر**: `systemctl status chart-worker` (systemd، Restart=always)

## اجرای محلی
```bash
cd /root/chart-platform
ZARINPAL_MERCHANT_ID=<uuid> ZARINPAL_SANDBOX=true PUBLIC_BASE_URL=http://127.0.0.1:8767 \
  venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8767 2>&1 | tail -30
# کارگر گزارش (پس از هر ریاستارت سرور)
venv/bin/arq app.report.worker.WorkerSettings
```

## تست
```bash
venv/bin/python -m pytest tests/ -q        # 55 پاس — هرگز prod را نمی‌زند (DB تست جدا)
```

## Endpoint های کلیدی
| مسیر | کارکرد |
|---|---|
| `/` | لندینگ + فرم ۵ مرحله |
| `/api/charts` | POST ساخت چارت |
| `/chart/{id}` | صفحه چارت + خرید + چت + گذرها |
| `/plans?chart={id}` | تعرفهها (۱۴۹/۳۴۹/۶۹۹ هزار تومان) |
| `/api/orders` POST | ایجاد سفارش → درگاه |
| `/api/payments/verify` | کالتبک زرینپال → پرداختشده → صف گزارش |
| `/api/charts/{id}/report` POST | صف تولید گزارش |
| `/api/reports/{id}/pdf` | دانلود PDF (گزارش تولیدشده) |
| `/chat/{id}` | گفتوگو با چارت (پس از خرید) |
| `/transit/{id}` | گذرهای کنونی |
| `/admin` | دشبورد (سفارشات + درآمد) |
| `/api/v1/{telegram,bale}/webhook` | رباتها (توکن از env) |
| `/api/share/{id}.png` | کارت اشتراک ۱۲۰۰×۶۳۰ |
| `/sitemap.xml` `/robots.txt` | سئو |

## محیط (env)
`ZARINPAL_MERCHANT_ID`, `ZARINPAL_SANDBOX`, `PUBLIC_BASE_URL`,
`TELEGRAM_BOT_TOKEN`, `BALE_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`,
`GEMINI_KEYS_PATH` (کلیدها: `keys/gemini-keys.txt` / `~/.hermes/keys/gemini-3.6-keys.txt`)

## مدیریت رازها از پنل ادمین (برای انتقال سرور) 🔐
- همه کلیدها از پنل ادمین `/admin` → بخش «کلیدها و رازها» قابل ورود/ویرایش/پاککردناند
  (زرینپال، ربات تلگرام/بله، کلیدهای LLM، پیامک، R2).
- ذخیره: رمزنگاری Fernet (AES) در جدول `secrets` دیتابیس؛ کلید رمز از `SECRETS_MASTER_KEY` در `.env`
  (derived به Fernet-key با SHA256؛ هر رشته‌ای قبول میشود).
- اولویت خواندن: مقدار DB (اگر ست شده) → متغیر env → پیشفرض. «پاک کردن» یعنی بازگشت به env.
- بعد از ذخیره، **سرویس را ریاستارت کنید** (توکن ربات/کلیدهای module-level در import خوانده میشوند).
- **روی سرور جدید:** فقط اینها را در env بگذار و بقیه را خودت در پنل ادمین وارد کن:
  `SECRETS_MASTER_KEY` + `ADMIN_PIN`/`ADMIN_SECRET` + `DATABASE_URL` + `REDIS_URL` + `APP_ENV=prod`.
- ⚠️ `SECRETS_MASTER_KEY` بخشی از config است → باید در بکاپ باشد (همراه `.env`).
  اگر گم شود، رازهای ذخیرهشده در DB غیرقابل رمزگشایی میشوند.

## عملیات روزانه
- **سهمیه Gemini**: هر کلید ۲۰/روز. لاگ cooldown در استارتاپ روتر. کلیدهای جدید را به انتهای
  `keys/gemini-keys.txt` اضافه کن (هر خط یک کلید؛ خطوط `#` مجاز).
- **دیتابیس**: بکاپ خودکار ساعت ۰۳:۱۵ (cron سیستم → `scripts/backup-db.sh`). پایین را ببین.
- **کارگر**: اگر گزارشها queued ماندند → `systemctl status chart-worker` (سرویس systemd، پس از نصب).
- **دیسک**: واتچداگ هر ۳۰ دقیقه (هشدار ≥۸۵٪).

## داده — بکاپ، restore، Alembic، DLQ (فاز ۳)

### بکاپ (خودکار + دستی)
- `scripts/backup_db.py` → `pg_dump -Fc` از `chart_platform` + `.env` (شامل `SECRETS_MASTER_KEY`)
  → zip → آپلود به R2 زیر `backups/chart-platform/`. خروجی موفق = سکوت.
- کرون سیستم: `15 3 * * * /root/chart-platform/scripts/backup-db.sh` (روزانه ۰۳:۱۵).
- نگهداشت: لوکال ۷ روز، R2 ۳۰ روز. فایلها: `/root/backups/chart-platform/chart_backup_*.zip`.

### Restore (بازسازی از مستندات — تستشده ✅)
```bash
scripts/restore_db.sh /root/backups/chart-platform/chart_backup_<ts>.zip [target_db_url]
```
- بدون آرگومان دوم، به `DATABASE_URL` از `.env` ریاستور میکند.
- بعد از ریاستور، ۱۶ جدول core را verify میکند (اگر جدولی نبود → `FAIL`).
- تست تأیید: ریاستور به دیتابیس موقت → ۱۶ جدول حاضر (فاز ۳).

### Alembic (نسخهبندی اسکیمای دیتابیس)
- پیکربندی: `alembic.ini` + `alembic/env.py` (اتصال از `DATABASE_URL` در `.env`؛ متادیتا = `SQLModel.metadata`).
- بیسلاین: `alembic/versions/dfb85378c2bf_baseline_schema.py` (۱۶ جدول، شامل `reports.retry_count`).
- دیتابیس live با `alembic stamp head` علامتگذاری شده.
- **چرخه تغییر اسکیما:** مدل را عوض کن → `venv/bin/alembic revision --autogenerate -m "..."` → `venv/bin/alembic upgrade head`.
- ⚠️ autogenerate را فقط روی یک دیتابیس خالی بزن (وگرنه diff بهجای baseline میسازد).

### DLQ (گزارشهای failed)
- `scripts/retry_failed_reports.py` → گزارشهای `failed` با `retry_count < 5` را دوباره enqueue میکند.
  - `--dry-run` فقط لیست میکند؛ `--report <id>` یک گزارش خاص را.
- گزارشها بعد از ۵ بار retry دیگر خودکار retry نمیشوند (از حلقه جلوگیری).

## ریست سهمیه/اشکال
- «همه کلیدها cooldown» → صبر تا ساعت بعدی یا کلید جدید.
- گزارش failed → `scripts/retry_failed_reports.py --dry-run` بزن؛ ستون `error` ریشه را میگوید.
- 429 در verify → سهمیه؛ صبر یا کلید پولی.

## استقرار production (پیشنیازها)
1. دامنه نهایی + nginx reverse proxy به 127.0.0.1:8767 (الگوی vc.negar.io)
2. `PUBLIC_BASE_URL` دامنه نهایی؛ `ZARINPAL_SANDBOX=false` + مرچنت واقعی
3. توکن رباتها + ست webhook:
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<domain>/api/v1/telegram/webhook&secret_token=<SECRET>`
   `https://tapi.bale.ai/bot<TOKEN>/setWebhook?url=https://<domain>/api/v1/bale/webhook`
4. سرویس‌های systemd (deploy/): `chart-worker.service` (ARQ) + `chart-web.service` (uvicorn،
   auto-restart). گزینهٔ جایگزین: Docker — `docker compose up -d --build` (Dockerfile + compose،
   از Postgres/Redis هاست با network_mode:host استفاده می‌کند).
5. (اختیاری) کلید DeepSeek پولی برای تولید اصلی — `DEEPSEEK_API_KEY` env

## آنالیتیکس (Umami)
- داشبورد: `https://analytics.negar.io` — ورود `admin` / رمز در `deploy/umami-admin.txt` (عدد ۸ رقمی).
- شناسهٔ سایت (زایچه): `e8f58dc5-fee9-455d-8ee6-18e26ea23791`؛ اسکریپت ردیاب در `<head>` base.html.
- رویدادهای قیف: `form_submit`، `report_created`، `payment_success` (inline در قالب‌ها).
- سرور: کانتینر Docker `umami` (network host، پورت ۳۰۰۰) + دیتابیس Postgres `umami`؛
  env در `deploy/umami.env` (gitignored). nginx: `analytics.negar.io` → 127.0.0.1:3000.
- CSP چارت برای `analytics.negar.io` باز شده (script-src + connect-src).

## زرین‌پال — رفتن به live (پس از گرفتن مرچنت)
1. در پنل ادمین → «کلیدها و رازها» → مرچنت واقعی زرین‌پال را وارد کن (ذخیره در دیتابیس).
2. در `.env`: `ZARINPAL_SANDBOX=false` (یا در پنل ادمین sandbox را خاموش کن).
3. تست با یک پرداخت واقعی کم‌مبلغ + چک callback در `/api/payments/verify`.
4. اگر metadata.mobile خالی بود، خطای زرین‌پال -9 → کلید `mobile` را omit کن (بدون ثبت‌نام).

## لید مگنت
- راهنمای PDF رایگان: `app/content/guide-beginner.md` → `app/static/guides/zayche-guide.pdf`
  (ساخت دوباره: `/root/astrology/venv/bin/python scripts/md2pdf.py app/content/guide-beginner.md app/static/guides/zayche-guide.pdf`).
- دکمهٔ دانلود در هیروی صفحهٔ اصلی. اشتراک هفتگی: CTA در صفحهٔ حساب → ربات تلگرام.

## رولبک
هر فاز کامیت مستقل دارد: `git checkout v0.6.0` و غیره.
