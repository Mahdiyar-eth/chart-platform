#!/usr/bin/env python3
"""Build ONE comprehensive handoff doc: narrative + ALL code + tests + git."""
import subprocess
from pathlib import Path

BASE = Path("/root/chart-platform")
OUT = BASE / "docs" / "FULL-REPORT.md"


def read(rel: str) -> str:
    return (BASE / rel).read_text(encoding="utf-8")


def code_section(rel: str, lang: str) -> str:
    try:
        c = read(rel)
    except Exception as e:
        return f"### {rel}\n\n```\n(خطا در خواندن: {e})\n```\n"
    n = c.count("\n") + 1
    return f"### `{rel}` ({n} lines)\n\n```{lang}\n{c}\n```\n"


def walk(glob: str) -> list:
    return sorted(str(p.relative_to(BASE)) for p in BASE.glob(glob)
                  if "__pycache__" not in str(p) and "venv" not in str(p))


# ── fresh test output ──
pytest = subprocess.run(
    ["venv/bin/python", "-m", "pytest", "tests/", "-q"],
    cwd=BASE, capture_output=True, text=True, timeout=300,
)
test_out = pytest.stdout + pytest.stderr

# ── git history ──
gitlog = subprocess.run(
    ["git", "log", "--oneline", "--date=short", "--pretty=format:%h %ad %s"],
    cwd=BASE, capture_output=True, text=True, timeout=30,
).stdout

gitstat = subprocess.run(
    ["git", "log", "--oneline"], cwd=BASE, capture_output=True, text=True, timeout=30,
).stdout
commit_count = len([l for l in gitstat.splitlines() if l.strip()])

py_files = walk("app/**/*.py") + walk("app/*.py")
html_files = walk("app/templates/*.html")

parts = []
parts.append(f"""# چارت تولد — مستند کامل فنی (صفر تا صد، با کد)

> **هدف این سند:** یک فایل مستقل و جامع که یک هوش مصنوعی دیگر بدون دسترسی به مخزن، کل پروژه را بفهمد، تحلیل کند و ادامه بدهد.
> **تاریخ تولید:** ۲۲ مرداد ۱۴۰۵ (۱۳ اوت ۲۰۲۶) · **آخرین کامیت:** {gitlog.splitlines()[0] if gitlog else '?'}
> **حجم:** {len(py_files)} فایل پایتون + {len(html_files)} قالب HTML · {commit_count} کامیت · لایو: https://chart.negar.io

---

## ۱) محصول چیست

سرویس وب فارسی (RTL) که با داده‌ی دقیق تولد (تاریخ شمسی/میلادی، ساعت، شهر ایران) یک **چارت نجومی** محاسبه می‌کند و یک **گزارش تحلیلی عمیق** (PDF فارسی، ۱۳ حوزه + فصل فرهنگی-اسلامی) تولید می‌کند.

**مدل کسب‌وکار:**
- پلن گزارش: basic (~۱٬۴۹۰٬۰۰۰ ریال) / full (~۳٬۴۹۰٬۰۰۰) / gold (~۶٬۹۹۰٬۰۰۰)
- سیناستری (سازگاری دو نفر): ~۴۹۹٬۰۰۰
- اشتراک ماهانه: ~۳۹۹٬۰۰۰
- پرداخت: زرین‌پال (فعلاً sandbox) · کوپن WELCOME10 · رفرال · ریفاند ادمین

**زیرساخت لایو:** nginx → uvicorn (127.0.0.1:8767) · PostgreSQL 16 · Redis + ARQ worker · R2/Cloudflare برای PDF.

---

## ۲) جریان داده (قانون طلایی)

```
فرم تولد (RTL، تاریخ شمسی) → POST /api/charts → pyswisseph (قطعی، بدون LLM)
→ Chart + BirthProfile در DB → انتخاب پلن → سفارش (orders) → پرداخت زرین‌پال
→ گزارش: ARQ worker → 13/14 بخش با LLM → QA خودکار → تجمیع → PDF (WeasyPrint RTL)
→ آپلود R2 (presigned 302) → دانلود
```

**قانون طلایی:** داده‌ی نجومی (سیارات، خانه‌ها، جنبه‌ها، ترانزیت‌ها) هرگز از LLM نمی‌گذرد — فقط محاسبه‌ی قطعی pyswisseph با ephemeris محلی. LLM فقط برای نگارش متن تحلیل است.

---

## ۳) پشته فناوری

| لایه | تکنولوژی |
|---|---|
| بک‌اند | FastAPI + SQLModel (Python 3.11) |
| دیتابیس | PostgreSQL 16 (SQLModel، auto-create؛ migration دستی) |
| صف/worker | Redis + ARQ (`chart-worker` systemd) |
| موتور نجومی | pyswisseph + ephemeris محلی (Swiss Ephemeris) |
| LLM | روتر: go (deepseek-v4-pro/flash) → gemini (۲۴ کلید) → avalai → deepseek رسمی |
| فرانت | Jinja2 RTL + Alpine.js + HTMX + Tailwind (لوکال) |
| PDF | WeasyPrint + وزیرمتن (RTL) |
| Word | python-docx + bidi |
| صوت | edge-tts فارسی |
| پرداخت | زرین‌پال v4 (sandbox → مرچنت واقعی [منتظر کاربر]) |
| فایل‌ها | Cloudflare R2 (presigned 302) |
| OTP | Kavenegar SMS (کلید [منتظر کاربر]؛ dev-code فعال) |
| استقرار | Hetzner + systemd + nginx · PWA سبک · CI (scripts/ci.sh + GitHub Actions) |

---

## ۴) ساختار فایل‌ها

```
app/
├── astrology/      engine, big_three, svg_wheel, svg_widgets, synastry, rectify, transits, cities_ir, golden_data
├── report/         prompt_builder, worker, qa, generator, renderer, word, rules, preview, prompt_overrides
├── payment/        orders, zarinpal
├── bots/           handler (تلگرام + بله), state
├── chat/           service, intents, retrieval
├── core/           llm (روتر)
├── seo/            content, article_banner
├── share/          card
├── templates/      30+ قالب HTML
├── content/        pages.json, articles.json (۳۰ مقاله SEO)
├── main.py         ~۵۰ route
├── models.py       ۱۴+ جدول SQLModel
├── auth.py, db.py, security.py, storage.py, config.py
tests/              ۶۶ تست + ۲۱ golden chart
scripts/            ci.sh, weekly_transit, migrate, backup, gen_docs
docs/               PLAN-CHECKLIST (منبع حقیقت), PLAN-V4, RUNBOOK, audit/
```

---

## ۵) اندپوینت‌ها (کامل)

| مسیر | کار |
|---|---|
| GET / | لندینگ |
| GET /birth-form · POST /api/charts | ساخت چارت (رایگان، بدون ثبت‌نام) |
| GET /chart/{id} · /api/charts/{id} | نمایش چارت + پیش‌نمایش رایگان |
| GET /plans · /api/plans | پلن‌ها و قیمت |
| POST /api/orders · /api/payments/verify | سفارش + کالبک زرین‌پال |
| GET /payment/result | نتیجه پرداخت |
| GET /account · /account/login · /api/auth/otp/* | حساب کاربری + OTP |
| GET /synastry · /api/synastry/* | سیناستری (تیزر رایگان + پولی) |
| GET /rectify · /api/rectify | Birth Time Finder |
| GET /api/charts/{{id}}/transits · transit-year.svg | ترانزیت (on-demand) |
| GET /articles · /articles/{{slug}} · /learn/* · /signs/{{slug}} | محتوای SEO |
| GET /guide · /about · /faq · /privacy · /terms · /refund · /disclaimer · /contact | صفحات محتوا/قانونی |
| GET /admin · /admin/login · /api/admin/* | پنل ادمین (PIN) |
| POST /api/v1/telegram/webhook · /api/v1/bale/webhook/{{secret}} | ربات‌ها |
| GET /api/chat | AI Chat (قفل تا خرید) |

---

## ۶) ماژول‌ها و وظایف

| ماژول | کار | نکته |
|---|---|---|
| `astrology/engine.py` | محاسبه چارت pyswisseph | ۳۳۷ شهر ایران؛ شمسی→میلادی؛ tropical + sidereal/Lahiri |
| `astrology/big_three.py` | خورشید/ماه/طالع + کارت | رایگان |
| `astrology/svg_wheel.py` | دایره زایچه SVG | spidering شعاعی لیبل‌ها |
| `astrology/svg_widgets.py` | ۸+ ویجت SVG | ترانزیت سالانه |
| `astrology/synastry.py` | تطبیق دو چارت | پولی ۴۹۹k |
| `astrology/rectify.py` | Birth Time Finder | قوانین _EVENT_RULES + سقف ۳ رویداد |
| `astrology/transits.py` | ترانزیت روز/هفته/سال | compute_transits قطعی |
| `report/prompt_builder.py` | پرامپت هر بخش | ۱۳ حوزه + فصل اسلامی |
| `report/worker.py` | حلقه تولید ARQ | retry=2، max_tokens 8192 |
| `report/qa.py` | QA خودکار | JSON/طول/ارجاع + رد کلمات غیب/طلسم |
| `report/renderer.py` | PDF RTL | وزیرمتن |
| `report/preview.py` | پیش‌نمایش رایگان | rule-engine بدون LLM |
| `core/llm.py` | روتر LLM | go→gemini→avalai→deepseek |
| `payment/orders.py` | سفارش/کوپن/ریفاند/اشتراک | idempotent |
| `payment/zarinpal.py` | زرین‌پال | callback verify |
| `bots/handler.py` | ربات تلگرام+بله | button-driven، webhook |
| `chat/*` | AI Chat | retrieval روی گزارش |
| `auth.py` | OTP + session cookie | rate-limit ۵/min |
| `security.py` | امضای PDF، رفرال، audit | |
| `db.py`/`models.py` | SQLModel ۱۴+ جدول | seed_plans idempotent |

---

## ۷) مدل داده (خلاصه — کد کامل در app/models.py)

جدول‌ها: `users`, `birth_profiles`, `charts`, `reports`, `plans`, `orders`, `coupons`, `subscriptions`, `audit_logs`, `llm_runs`, `referral_events`, `bot_chat_states`, `prompt_versions`, `qa_runs`, `analytics_events`.

---

## ۸) کد کامل — بک‌اند (پایتون)

""")

for f in py_files:
    parts.append(code_section(f, "python"))

parts.append("\n\n---\n\n## ۹) کد کامل — فرانت (قالب‌های HTML)\n\n")
for f in html_files:
    parts.append(code_section(f, "html"))

parts.append(f"""

---

## ۱۰) نتایج تست (خروجی واقعی pytest)

```
{test_out.strip()}
```

---

## ۱۱) تاریخچه گیت (کامل — {commit_count} کامیت)

```
{gitlog.strip()}
```

---

## ۱۲) باگ‌های مهم پیدا و رفع‌شده (نمونه)

| باگ | ریشه | فیکس |
|---|---|---|
| دکمه «خرید پایه» کار نمی‌کرد | زرین‌پال `metadata.mobile` خالی را با خطای -9 رد می‌کرد (بدون ثبت‌نام → بدون شماره) | حذف `mobile` وقتی خالی است + جریان «بدون چارت → ساخت چارت → بازگشت به خرید» |
| ناخوانایی صفحه پلن‌ها | رنگ‌های حالت روشن (#3b2f80/#444) روی تم تیره | بازنویسی با رنگ‌های روشن WCAG |
| همپوشانی سیارات در چارت موبایل | فونت ریز + لیبل‌ها همه در یک شعاع | spidering شعاعی + فونت بزرگ‌تر |
| state سراسری sidereal (race) | حالت sidereal global | tropical + کسر دستی ayanamsa |
| _EVENT_RULES rectify استفاده نمی‌شد | تعریف‌شده ولی متصل نبود | اتصال + سقف ۳ رویداد |
| کالبک پرداخت غیر-idempotent | دوبار ارسال | verify سروربه‌سرور + idempotency |
| OTP dev-code در prod | ریسک امنیتی | fail-closed بدون کلید SMS |
| x-data روی والد صفحه چارت | پیش‌نمایش خارج از اسکوپ Alpine | جابه‌جایی x-data |

---

## ۱۳) شکاف‌های باز (مهم — از بازبینی ۲۰۲۶-۰۸-۱۳)

1. **اشتراک «ترانزیت هفتگی» نیمه‌کاره:** کرون `0 7 * * 6` در پلن [x] خورده ولی هرگز ساخته نشده؛ مشترک پول می‌دهد ولی هیچ چیزی خودکار دریافت نمی‌کند.
2. **لحن «فال/پیش‌بینی»:** FAQ و ۲۳ موضع در مقالات هنوز «پیش‌بینی» دارند؛ باید → «خودشناسی/تأمل/روند» (غیرمستقیم و الهی، بدون حس فال).
3. **شکاف رقبا:** صفحه عمومی «آسمان امروز» + تمرین تأمل هفتگی نداریم.

**منتظر کاربر:** نام برند · دامنه اختصاصی · مرچنت واقعی زرین‌پال · کلید Kavenegar · تست گوشی واقعی.

**پلن پیشنهادی v4:** `docs/PLAN-V4-COMPLETE.md` (۴ فاز: A اشتراک/ترانزیت، B پاکسازی لحن، C قابلیت‌های رقبا، D نهایی‌سازی).

---

## ۱۴) اجرای لوکال

```bash
cd /root/chart-platform
venv/bin/python -m pytest tests/ -q          # تست‌ها
venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8767 --proxy-headers --forwarded-allow-ips=127.0.0.1
# worker: systemctl status chart-worker (ARQ)
# اسکریپت‌های کرون: scripts/ (backup, weekly_transit, migrate, ci.sh)
```
""")

OUT.write_text("\n".join(parts), encoding="utf-8")
print("WROTE:", OUT, OUT.stat().st_size, "bytes")
