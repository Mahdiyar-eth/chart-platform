# پیوست نهایی — دور سوم (۱۴ اوت ۲۰۲۶)

این پیوست نتیجهٔ نقد Production-Readiness بیرونی (سند «Untitled_3») و اجرای کامل پلن ۳ فازی تأییدشده است. هر ادعا ابتدا با کد/سیستم راستی‌آزمایی شد (قانون «ادعا به ادعا»).

## 🔴 باگ‌های امنیتی (هر دو تأیید و بسته شدند)

| ادعا | حکم | فیکس |
|---|---|---|
| چت بدون authorization (۴ endpoint) | ✅ درست (Critical) | `_owns_chart` روی صفحهٔ چت، access، history و POST — ۸ تست IDOR پاس |
| `/api/admin/stats` بدون auth | ✅ درست | `_is_admin` + 403 — ۲ تست |
| کوپن race (read-modify-write) | ✅ درست | `UPDATE … WHERE used_count<max_uses RETURNING` اتمیک — ۲ تست |
| سکرت تلگرام با `!=` | ✅ درست | `hmac.compare_digest` |
| `<b>` خام در ربات (باگ بولد) | ✅ درست | ۱۱ مورد → `**` — ۴ تست |
| injection در پرامپت سؤال شخصی | ✅ درست | دِلیمیتر `<پرسش_کاربر>` + برش ۶۰۰ کاراکتر |
| مسیر efemeris نسبی | ✅ درست | `SWISSEPH_EPHE_PATH` از env |

## 🟠 زیرساخت (همه انجام شد)

1. **Rate limit در-حافظه → Redis** (بین ورکرها shared) + fallback در-حافظه برای تست‌ها (`RATE_LIMIT_BACKEND`).
2. **User=root → کاربر `zayche`** + systemd hardening (NoNewPrivileges، ProtectSystem=strict، ProtectKernel*، RestrictAddressFamilies، CapabilityBoundingSet خالی، PrivateTmp) — رندر PDF به‌عنوان zayche تست شد (۳۰KB).
3. **dual-path create_all + Alembic**: `create_all` فقط با `CREATE_ALL_ON_BOOT=1` (تست)؛ پروداکشن فقط Alembic. `scripts/deploy.sh` جدید با `alembic upgrade head` + `alembic check`.
4. **Migration audit**: زنجیرهٔ ۴ مهاجرت (baseline → chat_messages → align → zodiac) بازسازی شد؛ `alembic check` = پاک (قبلاً ۱۵+ درفت واقعی بود). چک زنجیره در CI روی DB تازه.
5. **restore drill واقعی**: انجام شد (بکاپ → ریستور → تایید ۱۸ جدول)؛ هم‌زمان حادثهٔ ریستور اشتباه رخ داد و **دیتای واقعی از بکاپ ۱۷:۳۱ بازیابی شد** (۲ کاربر، ۱۸ چارت، ۵ سفارش، ۳ گزارش). گاردهای جدید: تارگت restore اجباری + `FORCE_PROD_RESTORE` + سانیتی‌بکاپ (بکاپ خالی را رد می‌کند) + `load_dotenv(override=True)`.
6. **master key drill**: سکرت تستی با کلید master داخل بکاپ decrypt شد — OK.
7. **CI امنیتی**: ruff (F/E9)، bandit (-lll)، pip-audit (حذف python-jose/ecdsa استفاده‌نشده → ۰ آسیب‌پذیری)، secret-scan، brand-scan، coverage ≥ ۶۰٪ (فعلی ۶۱٪+).
8. **تست race پرداخت**: ۵ کالبک هم‌زمان → دقیقاً ۱ پردازش (1 verify، 1 کوپن، 1 گزارش) — با قفل اتمیک `pending→paid RETURNING`.
9. **زودیاک**: تروپیکال پیش‌فرض + سایدریال لاهیری انتخابی (تحقیق رقبا: Astro-Seek/Co-Star/Time Nomad). ستون DB + migration + چیپ فرم وب + سیناستری + مرحلهٔ دکمه‌ای ربات + golden chart-7 (آیانامسا ۲۳.۷۸°) + فیکس متن homepage.
10. **R2 باکت جدا**: `zayche-storage` (۸ آبجکت منتقل شد + بکاپ‌های جدید).
11. **degraded status UI**: بنر polling از `/health` (باگ ترتیب DOM توسط تست مرورگر پیدا و فیکس شد — تأیید بصری روی نمونهٔ degraded).
12. **حافظه**: سقف‌های webui/voice-clone تنظیم شد (مجموع ۱۰.۲G < ۱۳.۶G).

## آمار نهایی

- تست‌ها: **۱۵۱ پاس + ۴ skip** (از ۱۲۳) — تست‌های جدید: IDOR چت (۸)، ادمین (۲)، کوپن (۲)، بولد (۴)، race پرداخت، زودیاک، health (۳)
- CI: ۶ گیت سبز
- بکاپ: زنجیرهٔ کامل migrations روی DB تازه = models (اثبات)

## باقی‌ماندهٔ سمت مالک (تغییری نکرده)

مرچنت واقعی زرین‌پال، کلید کاوه‌نگار، دامنهٔ zayche.io، تست موبایل واقعی، ثبت برند.
