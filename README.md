# چارت تولد — پلتفرم فارسی خودشناسی مبتنی بر چارت تولد

> **آینهی خودشناسی، نه حکم دربارهی آینده.**

پلتفرم فارسیزبان AI-powered: محاسبهی دقیق چارت تولد (Swiss Ephemeris)، تفسیر فارسی
با سیستم Evidence، گزارش PDF/Word حرفهای، داشبورد شخصی، AI Chat، ترانزیت و سیناستری.
مرجع توسعه: `master-product-spec` + پلن نهایی v3.1 (`/root/astrology/plan/`).

## معماری (خلاصه)

```
دادهی تولد → [موتور نجومی: zoneinfo → pyswisseph] → Chart JSON (Canonical)
            → [Rule Engine: Factor/Weight/Evidence] → [LLM (نویسنده فقط)]
            → [QA خودکار] → [Renderer: PDF/Word/Dashboard]
```

**قانون سخت:** LLM هرگز محاسبه نمیکند — درجه/خانه/جنبه فقط از pyswisseph.

## استک

FastAPI + SQLModel + PostgreSQL 16 + Redis/ARQ + pyswisseph + WeasyPrint (PDF) +
HTMX/Alpine/Tailwind + R2 (فایل) + زرینپال (پرداخت) + Telegram/Bale bot

## وضعیت فعلی (فاز ۰ و ۱ — ۲۲ مرداد ۱۴۰۵)

| بخش | وضعیت |
|---|---|
| LLMProvider + Router (Gemini×9 کلید، DeepSeek/AvalAI آماده) | ✅ تستشده (۸ کلید سالم) |
| موتور نجومی (zoneinfo + pyswisseph + Chart JSON) | ✅ Golden Suite: ۲۱ تست پاس |
| Golden Charts (چارت مهدی = تطابق متخصص ۱′ قوس) | ✅ |
| دیتابیس شهرهای ایران (۳۳۷ شهر، ۴۵ مختصات دقیق) | ✅ |
| رندر SVG چرخ چارت | ✅ تأیید بصری Gemini (بدون تداخل) |

## اجرای تستها

```bash
source venv/bin/activate
pytest tests/ -v
```

## متغیرهای محیطی

```bash
cp .env.example .env   # سپس پر کنید
```

- `GEMINI_KEYS_PATH` — فایل کلیدهای Gemini (پیشفرض: `keys/gemini-keys.txt`)
- `DEEPSEEK_API_KEY` / `AVALAI_API_KEY` — برای فعالسازی پراوایدرهای پولی
- `DATABASE_URL` — PostgreSQL (پیشفرض dev: `postgresql://chart_app:CHANGE_ME@127.0.0.1:5432/chart_platform`)

## ساختار

```
app/
  core/llm.py          # LLMProvider/LM Router (abstraction + health)
  astrology/engine.py  # موتور محاسبه (Deterministic)
  astrology/golden_data.py  # ۸ چارت مرجع + Engine Config Snapshot
  astrology/svg_wheel.py    # رندر چرخ چارت SVG
  astrology/cities_ir.py    # شهرهای ایران (۳۳۷)
scripts/               # build_cities_seed.py و ...
tests/                 # pytest Golden Suite
```
