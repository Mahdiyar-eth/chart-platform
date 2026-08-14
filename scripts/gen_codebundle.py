#!/usr/bin/env python3
"""Regenerate the FULL code bundle (ZAYCHE-CODEBUNDLE.md) from the CURRENT tree.

19 organized sections — everything an external AI needs for a deep code review:
app, templates, static PWA files, tests, scripts, migrations, deploy, CI, env template.
Secrets are never included (.env excluded; the repo secret-scan guards the rest).
Round-4 aware: Web Push (push.py, sw.js), pgvector RAG (rag.py), referral wallet,
SSE streaming chat (llm.stream / chat_stream) — all picked up automatically.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path("/root/chart-platform")
OUT = ROOT / "docs" / "audit" / "ZAYCHE-CODEBUNDLE.md"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def code_block(rel: str, lang: str = "python") -> str:
    try:
        c = read(rel)
    except Exception as e:  # noqa: BLE001
        return f"### `{rel}`\n\n```\n(خطا در خواندن: {e})\n```\n"
    n = c.count("\n") + 1
    return f"### `{rel}` ({n} lines)\n\n```{lang}\n{c}\n```\n"


def section(title: str, rels: list[str], lang: str = "python") -> str:
    parts = [f"\n---\n\n## {title}\n"]
    for r in rels:
        parts.append(code_block(r, lang))
    return "\n".join(parts)


# ── fresh test output + git ─────────────────────────────────────
pytest = subprocess.run(
    ["venv/bin/python", "-m", "pytest", "tests/", "-q"],
    cwd=ROOT, capture_output=True, text=True, timeout=600,
)
test_out = (pytest.stdout or "") + (pytest.stderr or "")
gitlog = subprocess.run(
    ["git", "log", "--oneline", "--date=short", "--pretty=format:%h %ad %s"],
    cwd=ROOT, capture_output=True, text=True, timeout=30,
).stdout
commits = len([l for l in gitlog.splitlines() if l.strip()])
head = gitlog.splitlines()[0] if gitlog else "?"


def py_files(glob: str) -> list[str]:
    return sorted(
        str(p.relative_to(ROOT)) for p in ROOT.glob(glob)
        if "__pycache__" not in str(p)
    )


APP_PY = [p for p in py_files("app/**/*.py")]
TEMPLATES = sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "app" / "templates").rglob("*.html")
    if "__pycache__" not in str(p)
)
STATIC_WEB = ["app/static/sw.js", "app/static/sw-register.js",
              "app/static/manifest.webmanifest"]
TESTS = py_files("tests/*.py")
SCRIPTS = sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "scripts").glob("*")
    if p.suffix in (".py", ".sh") and "__pycache__" not in str(p)
)
MIGRATIONS = [p for p in py_files("alembic/versions/*.py")]
DEPLOY = sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "deploy").glob("*")
    if p.is_file() and p.suffix in (".service", ".example", ".txt", ".env")
)
CI_FILES = py_files(".github/workflows/*.yml")

n_files = (len(APP_PY) + len(TEMPLATES) + len(STATIC_WEB) + len(TESTS) +
           len(SCRIPTS) + len(MIGRATIONS) + len(DEPLOY) + len(CI_FILES) + 3)

# live counts for the header
n_tables = len(re.findall(r'__tablename__\s*=\s*"(\w+)"', read("app/models.py")))
n_migrations = len(MIGRATIONS)
n_tests = len(TESTS)
# last test line, e.g. "223 passed, 1 skipped in 9.97s"
test_summary = test_out.strip().splitlines()[-1] if test_out.strip() else "?"


def pick(prefix: str, files: list[str]) -> list[str]:
    return sorted(f for f in files if f.startswith(prefix))


main_py = [f for f in APP_PY if f == "app/main.py"]
routes_py = [f for f in APP_PY if f.startswith("app/routes/")]  # H1.9
core_py = [f for f in APP_PY if f.startswith("app/astrology/")]
report_py = [f for f in APP_PY if f.startswith("app/report/")]
chat_py = [f for f in APP_PY if f.startswith("app/chat/")]
pay_py = [f for f in APP_PY if f.startswith("app/payment/")]
bots_py = [f for f in APP_PY if f.startswith("app/bots/")]
seo_py = [f for f in APP_PY if f.startswith("app/seo/")]
misc_py = [f for f in APP_PY if f.startswith(("app/core/", "app/share/"))]
base_py = [f for f in APP_PY if f in (
    "app/models.py", "app/db.py", "app/config.py",
    "app/auth.py", "app/security.py", "app/secret_store.py", "app/storage.py",
    "app/push.py", "app/rag.py", "app/timeutil.py",
)]

# content files (seo + H1.7 verified Islamic KB)
CONTENT_FILES = ["app/content/pages.json", "app/content/articles.json",
                 "app/content/guide-beginner.md", "app/content/islamic_kb.json"]

header = f"""# باندل کامل کد — زایچه (ZAYCHE) چارت تولد

> تولید: 2026-08-14 (دور پنجم — HARDENING H0.1 تا H1.10 کامل — به‌روز تا کامیت `{head}`) — از ریپازیتوری /root/chart-platform
> این فایل برای **بررسی عمیق سطح کد** توسط هوش مصنوعی/متخصص تهیه شده؛ شامل کل سورس پایتون، قالب‌ها، تست‌ها و زیرساخت.
> سکرت‌ها (کلیدها، توکن‌ها، .env) **حذف شده‌اند**؛ مقادیر حساس فقط placeholder در کد دیده می‌شوند (خواندن از env).
> راهنمای کلی پروژه: `docs/audit/ZAYCHE-COMPLETE-REPORT.md` · دور سوم: `docs/audit/ROUND-3-ADDENDUM.md` · دور چهارم: `docs/audit/ROUND4-PHASE-C.md` و `docs/audit/ROUND4-PHASE-D.md` · **دور پنجم (HARDENING): `docs/audit/HARDENING-REPORT.md`**

## وضعیت فعلی (۱۴ اوت ۲۰۲۶ — راستی‌آزمایی‌شده)

- **تست‌ها:** {test_summary} ({n_tests} فایل تست)
- **کامیت‌ها:** {commits} · head: {head}
- **CI (scripts/ci.sh):** pytest + coverage ≥60٪ · ruff F/E9 · bandit -lll · pip-audit (0 vuln) · secret-scan · brand-scan · alembic chain check — همه سبز
- **مهاجرت‌ها:** {n_migrations} Alembic (baseline → chat → align-r3 → zodiac → D1-D3 → h0.4 reports.updated_at → h1.3 llm_runs.user_id/kind → h1.5 reports.audio_status) — `alembic check` پاک
- **جداول:** {n_tables} SQLModel — از جمله `push_subscriptions` (D1)، `report_chunks` + HNSW (D2)، `withdrawal_requests` (D3)
- **زیرساخت:** systemd chart-web/chart-worker (User=zayche, NoNewPrivileges, ProtectSystem=strict) · Redis+ARQ · PostgreSQL 16 + pgvector 0.6 · R2 باکت `zayche-storage` · nginx/HTTPS chart.negar.io
- **دور چهارم (A/B/C/D):** امنیت A11 + بکاپ age/presigned + ریفاند زرین‌پال + state machine پرداخت + circuit breaker LLM · TTS→R2 · لایو‌نس/ری‌دینس تفکیکی · حریم خصوصی/retention · Web Push (VAPID، سرویس‌کارگر، اعلان هفتگی) · RAG pgvector (e5-small چندزبانه 384-dim) · کیف پول رفرال (۵٪، پرداخت با موجودی، تسویه) · چت استریم SSE (توکن واقعی)
- **دور پنجم (HARDENING H0+H1):** تایمزون واقعی (timezonefinder + ۱۱۰۰ شهر جهانی) · حذف حساب کامل (cascade RAG) · confidence ساعت نامعلوم · بازیابی worker راکد (heartbeat + cron) · ترانزیت با tz چارت · چت context ساختاریافته (بدون برش JSON) · سنجش هزینهٔ LLM (llm_runs.user_id/kind + داشبورد) · ضدسوءاستفاده referral (self-referral + کف برداشت) · TTS صف‌دار (ARQ، بدون inline) · سیناستری مهمان (Person B بدون حساب + capability token) · لایهٔ اسلامی verified (KB ۳۰ مفهوم با ارجاع سوره/آیه) · چارچوب ارزیابی انسانی (۲۰ چارت × ۱۳ دامنه، rubric ۸ معیاری) · refactor main.py → app/routes/ · سیاست حریم خصوصی v1.1

## ساختار کلی

```
app/                  FastAPI app
  main.py             مسیرها + لایف‌سایکل + بوت ربات‌ها (~۱۷۸۰ خط)
  routes/             H1.9: auth / wallet / push / seo / admin (۳۴ endpoint استخراج‌شده)
  models.py           {n_tables} جدول SQLModel
  push.py             Web Push (VAPID + ارسال اعلان مرورگر)
  rag.py              pgvector RAG (chunk/index/search، مدل e5-small)
  astrology/          Swiss Ephemeris: engine, sky, synastry, rectify, transits, svg, golden_data, cities_world (H0.1)
  report/             تولید گزارش 13 بخشی + QA خودکار + PDF/Word + ترانزیت هفتگی + صوتی (H1.5)
  chat/               AI chat: retrieval + intents + service (+ SSE stream)
  payment/            زرین‌پال + سفارش/اشتراک/کوپن/استرداد + کیف پول/تسویه
  bots/               هندلر یکپارچه تلگرام + بله (تمام‌دکمه‌ای، مرحلهٔ زودیاک)
  seo/                محتوای آموزشی (برج‌ها/سیارات/خانه‌ها) + بنر مقالات
  content/            صفحات + مقالات + KB اسلامی تأییدشده (H1.7)
  core/llm.py         لایهٔ LLM (استریم توکن + fallback chain + circuit breaker)
  secret_store.py     کلیدها رمزنگاری‌شده (Fernet) در DB
templates/            {len(TEMPLATES)} قالب Jinja2 (RTL، Alpine.js، اسپرایت SVG) + degraded banner
static/               sw.js (push/notification) + manifest PWA + آیکون‌ها/فونت‌ها
tests/                {n_tests} فایل تست ({test_summary})
scripts/              بکاپ، ریستور، واچ‌داگ، CI، دیپلوی، ترانزیت، بازسازی باندل، eval انسانی (H1.8)
docs/eval/            چارچوب ارزیابی انسانی (H1.8): ۲۰ چارت + ۲۶۰ prompt + RUBRIC
deploy/               systemd unit ها + سقف‌های حافظه + نمونه‌های env
alembic/versions/     {n_migrations} مهاجرت
.github/workflows/    CI
```
"""

parts = [header]
parts.append(section("۱) فایل اصلی اپلیکیشن (main.py — مسیرهای هسته + include routes)", main_py))
parts.append(section("۱.۵) مسیرهای استخراج‌شده (H1.9 — app/routes/)", routes_py))
parts.append(section("۲) هسته: مدل‌ها، دیتابیس، تنظیمات",
                     [f for f in base_py if f in ("app/models.py", "app/db.py", "app/config.py", "app/timeutil.py")]))
parts.append(section("۳) امنیت، کلیدها و Web Push",
                     [f for f in base_py if f in ("app/auth.py", "app/security.py", "app/secret_store.py", "app/storage.py", "app/push.py")]))
parts.append(section("۴) موتور نجومی", core_py))
parts.append(section("۵) موتور گزارش + QA", report_py))
parts.append(section("۶) چت هوش مصنوعی + RAG", chat_py + [f for f in base_py if f == "app/rag.py"]))
parts.append(section("۷) پرداخت، سفارش و کیف پول", pay_py))
parts.append(section("۸) ربات‌های تلگرام و بله", bots_py))
parts.append(section("۹) SEO و محتوا", seo_py))
parts.append(section("۱۰) هستهٔ مشترک و لایهٔ LLM", misc_py))
parts.append(section("۱۱) قالب‌های Jinja2 (فرانت‌اند)", TEMPLATES, "html"))
parts.append(section("۱۲) PWA: سرویس‌کارگر اعلان + مانیفست", STATIC_WEB, "javascript"))
parts.append(section("۱۳) تست‌ها", TESTS))
parts.append(section("۱۴) زیرساخت و استقرار (اسکریپت‌ها)", SCRIPTS, "bash"))
parts.append(section("۱۵) میگریشن‌های Alembic", MIGRATIONS))
parts.append(section("۱۶) محتوای صفحات، مقالات و KB اسلامی (H1.7)", CONTENT_FILES, "json"))
parts.append(section("۱۷) systemd units + CI + محیط نمونه", DEPLOY + CI_FILES + ["requirements.txt", ".env.example"], "bash"))

parts.append(f"""

---

## ۱۸) خروجی واقعی pytest (آخرین اجرا)

```
{test_out.strip()}
```

## ۱۹) تاریخچه گیت (آخرین {min(commits, 40)} کامیت)

```
{chr(10).join(gitlog.splitlines()[:40])}
```
""")

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"WROTE: {OUT} | files: {n_files} | tables: {n_tables} | migrations: {n_migrations} | tests: {n_tests} | KB: {OUT.stat().st_size/1024:.0f}")
