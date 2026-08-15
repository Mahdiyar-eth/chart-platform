# P11 — Final Production Preflight — کامل شد

**تاریخ:** 2026-08-15 | **وضعیت:** ✅ PASS (۲ مورد فعالسازی کاربر)

## Checklist (§54)

| مورد | وضعیت | شواهد |
|---|---|---|
| real merchant env | ⏳ **اقدام کاربر** | ZARINPAL_SANDBOX=true؛ با set ZARINPAL_SANDBOX=false + merchant ID فعال میشود (env-only) |
| live domain | ✅ | chart.negar.io |
| TLS | ✅ | HTTPS 200 (Let's Encrypt) |
| DNS | ✅ | A record + CF proxy |
| SMTP/SMS provider | ⏳ **اقدام کاربر** | OTP fail-closed در prod: «SMS provider not configured (OTP_SMS_API_KEY)» — تنظیم OTP_SMS_API_KEY کاوهنگار کافی است |
| secrets | ✅ | .env + backup age-encrypted (R2) |
| DB backup | ✅ | cron 03:15 + backup 22:29 امروز (age، روی R2) |
| R2 | ✅ | zayche-storage + backup bucket (age-encrypted) |
| Redis | ✅ | redis-server active |
| workers | ✅ | chart-worker.service active (ARQ) |
| queue | ✅ | ARQ |
| LLM credentials | ✅ | OmniRoute 127.0.0.1:20128 + keyها |
| Umami | ✅ | analytics.negar.io 200 + script در base.html + track events |
| robots/sitemap | ✅ | robots.txt 200 + sitemap.xml 200 |
| legal pages | ✅ | privacy/terms/refund/disclaimer/contact/guide/faq/about — همه 200 |
| payment | ✅ | sandbox E2E (ref_id=435522808) + شبیهسازی callback prod؛ merchant real = exception |
| subscription | ✅ | P7 (435→442 تست، prod تأیید) |
| referral | ✅ | P8 (10% + bonus credit + cycle void) |
| coupons | ✅ | P8 (LANCH20 در prod: `LANCH20|20|10000|0|t`) |
| push | ✅ | P2 FCM subscription واقعی (jmt17) — **توجه: subscription تستی user_id=NULL باید پاک شود** |
| monitoring | ✅ | disk/uptime/error500 watchdogs (cron سیستم) + backup cron |
| alerts | ✅ | همان watchdogs (هشدار از ۸۵٪ دیسک و غیره) |
| rollback | ✅ | git tag v-p11-preflight؛ rollback = git reset --hard <tag> + deploy.sh (merge --ff-only) |

## Performance
- ۸ صفحه: ۳۴–۶۲ms | baseline گزارش عمیق: avg 48s/p95 57s (ثبت شده، بدون تغییر)

## وضعیت نهایی
- ۲ مورد فعالسازی کاربر: **مرچنت واقعی زرینپال** (فقط env) + **کلید SMS کاوهنگار** (فقط env) — هر دو «استثنای فعالسازی» طبق §55
- بقیه: ساخته → تست → مستند → اثبات → آمادهٔ استفاده
