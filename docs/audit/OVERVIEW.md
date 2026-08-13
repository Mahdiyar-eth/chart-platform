# چارت تولد — نمای صفر تا صد (OVERVIEW)

> سند مرجع «چه چیزی ساخته شده، چرا، و هر بخش چطور کار می‌کند» — برای تحلیل عمیق و برای توضیح به زبان ساده.

## ۰) محصول چیست

سرویس وب فارسی (RTL) که با داده‌ی دقیق تولد (تاریخ شمسی/میلادی، ساعت، شهر ایران) یک **چارت نجومی** محاسبه می‌کند و یک **گزارش تحلیلی عمیق** (PDF فارسی، ۱۳ حوزه + فصل فرهنگی-اسلامی) تولید می‌کند. مدل کسب‌وکار: فروش پلن (basic/full/gold)، سیناستری (سازگاری دو نفر)، اشتراک ماهانه، همه از طریق درگاه زرین‌پال.

**لایو:** https://chart.negar.io (nginx → uvicorn روی 127.0.0.1:8767، دیتابیس PostgreSQL 16، Redis برای صف، ARQ worker برای تولید گزارش، R2/Cloudflare برای فایل‌های PDF).

## ۱) منطق کل (جریان داده)

```
فرم تولد (RTL، تاریخ شمسی) → POST /api/charts → pyswisseph محاسبه (قطعی، بدون LLM)
→ ذخیره Chart + BirthProfile در DB → انتخاب پلن → سفارش (orders) → پرداخت زرین‌پال
→ گزارش: ARQ worker → 13/14 بخش با LLM (پرامپت‌ها از prompt_builder) → QA خودکار (qa.py)
→ تجمیع (generator) → رندر PDF (WeasyPrint RTL) → آپلود R2 (presigned 302) → دانلود
```

**قانون طلایی:** داده‌ی نجومی (سیارات، خانه‌ها، جنبه‌ها، ترانزیت‌ها) هرگز از LLM نمی‌گذرد — فقط محاسبه‌ی قطعی pyswisseph. LLM فقط برای نگارش متن تحلیل استفاده می‌شود.

## ۲) ماژول‌ها و وظایف (مرجع تحلیل)

| ماژول | کار | نکته‌ی کلیدی |
|---|---|---|
| `app/astrology/engine.py` | محاسبه‌ی چارت با pyswisseph + ephemeris محلی | ۳۳۷ شهر ایران در cities_ir.py؛ تبدیل شمسی→میلادی؛ timezone ایران |
| `app/astrology/big_three.py` | خورشید/ماه/طالع + کارت SVG | رایگان در پیش‌نمایش |
| `app/astrology/svg_wheel.py` | دایره‌ی زایچه SVG | RTL-safe، برند شخصی |
| `app/astrology/svg_widgets.py` | ۸+ ویجت SVG (شبکه جنبه‌ها، عناصر، خانه‌ها، KPI، ترانزیت سالانه) | بدون تصویر خارجی |
| `app/astrology/synastry.py` | تطبیق دو چارت (overlay + جنبه‌ها + امتیاز) | پولی (۴۹۹هزار) |
| `app/astrology/rectify.py` | Birth Time Finder (تست زمان‌های مختلف) | با معیارهای قطعی |
| `app/astrology/transits.py` | ترانزیت‌های روز/هفته/سال | digest هفتگی از کرون |
| `app/report/prompt_builder.py` | ساخت پرامپت هر بخش (۱۳ حوزه + اسلامی) | نسخه‌بندی شده (prompt_overrides) |
| `app/report/worker.py` | ARQ worker: حلقه‌ی تولید با retry | max_tokens 8192، retry=2 |
| `app/report/qa.py` | QA خودکار: JSON معتبر؟ حداقل طول؟ ارجاع به عوامل؟ | رد→بازتولید |
| `app/report/generator.py` | تجمیع بخش‌ها + متریک‌ها → ساختار گزارش نهایی | |
| `app/report/renderer.py` | WeasyPrint → PDF فارسی RTL + فصل ترانزیت | فونت وزیرمتن، جدول‌ها |
| `app/report/word.py` | خروجی Word (python-docx) | |
| `app/report/rules.py` | قانون‌های قطعی (بدون LLM) برای برخی تحلیلها | |
| `app/report/preview.py` | پیش‌نمایش رایگان ۳-۵ اینسایت (rule-engine قطعی، بدون LLM) | بازاریابی |
| `app/core/llm.py` | لایه‌ی LLM: GoProvider (DeepSeek V4 via opencode.ai) + Gemini فری + AvalAI؛ router با fallback | thinking disabled برای JSON؛ chat روی flash |
| `app/payment/orders.py` | سفارش/کوپن/ریفاند/فعال‌سازی اشتراک (هلپر مشترک) | idempotent |
| `app/payment/zarinpal.py` | اتصال زرین‌پال (سندباکس فعلاً) | callback verify |
| `app/bots/handler.py` | ربات تلگرام + بله (button-driven کامل) | webhook، callback `_` جداکننده |
| `app/bots/state.py` | جدول bot_chat_states | |
| `app/chat/service.py` + intents/retrieval | AI Chat روی گزارش (قفل تا خرید) | go-flash |
| `app/security.py` | امضای PDF، رفرال، audit log | |
| `app/auth.py` | OTP (SMS Kavenegar یا کد dev)، session cookie | |
| `app/db.py` + `models.py` | SQLModel: ۱۴+ جدول؛ seed پلن‌ها | auto-create، migration دستی |
| `app/main.py` | FastAPI: ~۴۰ route (API + صفحات) | CSP، سشن، ادمین |
| `app/templates/*` | Jinja2 RTL: index/form/chart/synastry/plans/account/admin/chat/rectify/transit/seo_* | Alpine.js + HTMX، tailwind_inline.css استاتیک |
| `scripts/` | ci.sh، send_transit_digests، migrate، backup | کرون سیستمی |
| `tests/` | ۶۶ تست pytest + ۲۱ golden (بررسی دقیق نجومی) | test DB جدا |

## ۳) پلن فروش و قیمت‌گذاری

- **basic** ~۱٬۴۹۰٬۰۰۰ ریال: ۵ بخش، PDF ~۱۰-۱۵ صفحه
- **full** ~۳٬۴۹۰٬۰۰۰: ۱۳ بخش، PDF ~۳۰-۴۰ صفحه
- **gold** ~۶٬۹۹۰٬۰۰۰: ۱۳ + فصل فرهنگی-اسلامی + ترانزیت ۳ساله + نمودار سالانه + چت
- **synastry** ~۴۹۹٬۰۰۰: سازگاری دو نفر
- **monthly** ~۳۹۹٬۰۰۰/ماه: اشتراک با digest هفتگی
- کوپن WELCOME10، رفرال دستی، ریفاند ادمین

## ۴) امنیت

PIN ادمین + کوکی امضا، OTP، CSP (`unsafe-inline/eval` برای Alpine — محدودیت مستند)، امضای PDF (mimetype بررسی)، سشن‌های HttpOnly، تزریق بررسی‌شده (SQLModel/ORM)، ریت‌لیمیت روی OTP، audit log، secrets فقط در .env (Fernet برای R2)، presigned URL کوتاه‌مدت.

## ۵) SEO/مارکتینگ (وضعیت فعلی)

sitemap ۳۱ URL (صفحات SEO برای شهرها/عنوان‌ها)، canonical، og tags، فونت وزیرمتن، PWA (sw.js + manifest)، سرعت (باندل لوکال، بدون CDN خارجی)، محتوای لندینگ فارسی.
**شکاف‌ها (معلوم):** صفحه‌ی راهنما/درباره ما/FAQ وجود ندارد؛ بخش مقالات نیست؛ دکمه‌های راهنما کنار گزینه‌ها نیست؛ فقط ۳۱ صفحه SEO (هدف: صدها مقاله).

## ۶) بستر اجرا

- سرور Hetzner (8GB/4vCPU)، systemd: chart-web (uvicorn)، chart-worker (arq)، nginx
- Redis برای صف، Postgres 16 محلی
- کرون سیستمی: backup 03:00، digest ترانزیت 07:00 (روزانه+هفتگی)، دیسک/uptime/500 watchdog
- CI: scripts/ci.sh (pytest + golden + import + syntax) + GitHub Actions
- گیت: ۳۰+ کامیت، گزارش فازها در reports/

## ۷) LLM (وضعیت پس از ارتقا)

- **روتر:** go (deepseek-v4-pro) → gemini (فری، ۲۴ کلید) → avalai → deepseek رسمی
- گزارش‌ها: v4-pro، thinking **disabled**، max_tokens 8192 (JSON کامل + عمق ۷۰۰-۱۱۰۰ کلمه/بخش)
- چت: v4-flash (سرعت)
- هزینه: اشتراک $10/ماه ثابت (سهمیه‌ی درخواست: pro=3450/5h، flash=126600/5h)
- json_mode: response_format json_object + parse فنساز (qa.py)

## ۸) تست‌ها

- ۶۶ pytest (پایه + پلن‌ها + فاز ۱۰) + ۲۱ golden chart (بررسی نجومی دقیق، ۳ اسکیپ بی‌خطر)
- تست E2E زنده: گزارش گلد واقعی ۱۴ بخش با V4 Pro → PDF 261KB (~۳.۵ برابر قبلی)
- CI سبز؛ اسموک: سایت/سوئیچ/ادمین/PWA همه 200
