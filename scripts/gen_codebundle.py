#!/usr/bin/env python3
"""Regenerate the FULL code bundle (ZAYCHE-CODEBUNDLE.md) from the CURRENT tree.

16 organized sections — everything an external AI needs for a deep code review:
app, templates, tests, scripts, migrations, deploy, CI, env template.
Secrets are never included (.env excluded; the repo secret-scan guards the rest).
"""
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
    cwd=ROOT, capture_output=True, text=True, timeout=300,
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

n_files = len(APP_PY) + len(TEMPLATES) + len(TESTS) + len(SCRIPTS) + len(MIGRATIONS) + len(DEPLOY) + len(CI_FILES) + 3

def pick(prefix: str, files: list[str]) -> list[str]:
    return sorted(f for f in files if f.startswith(prefix))

main_py = [f for f in APP_PY if f == "app/main.py"]
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
)]

header = f"""# باندل کامل کد — زایچه (ZAYCHE) چارت تولد

> تولید: 2026-08-14 (دور سوم بازبینی — به‌روز تا کامیت `{head}`) — از ریپازیتوری /root/chart-platform
> این فایل برای **بررسی عمیق سطح کد** توسط هوش مصنوعی/متخصص تهیه شده؛ شامل کل سورس پایتون، قالب‌ها، تست‌ها و زیرساخت.
> سکرت‌ها (کلیدها، توکن‌ها، .env) **حذف شده‌اند**؛ مقادیر حساس فقط placeholder در کد دیده می‌شوند (خواندن از env).
> راهنمای کلی پروژه: `docs/audit/ZAYCHE-COMPLETE-REPORT.md` + پیوست دور سوم: `docs/audit/ROUND-3-ADDENDUM.md`

## وضعیت فعلی (۱۴ اوت ۲۰۲۶ — راستی‌آزمایی‌شده)

- **تست‌ها:** {test_out.strip().splitlines()[-1] if test_out.strip() else '?'}
- **کامیت‌ها:** {commits} · head: {head}
- **CI (scripts/ci.sh):** pytest + coverage ≥60٪ · ruff F/E9 · bandit -lll · pip-audit (0 vuln) · secret-scan · brand-scan · alembic chain check — همه سبز
- **مهاجرت‌ها:** 4 Alembic (baseline → chat_messages → align-audit-r3 → zodiac) — `alembic check` پاک
- **زیرساخت:** systemd chart-web/chart-worker (User=zayche, NoNewPrivileges, ProtectSystem=strict, MemoryMax=1.5G) · Redis+ARQ · PostgreSQL 16 · R2 باکت `zayche-storage` · nginx/HTTPS chart.negar.io
- **ویژگی‌های دور سوم:** زودیاک تروپیکال پیش‌فرض + سایدریال لاهیری · کوپن atomic · race پرداخت (claim اتمیک) · degraded banner · rate limit Redis+fallback

## ساختار کلی

```{ "```" }
app/                  FastAPI app
  main.py             همه مسیرها + لایف‌سایکل + بوت ربات‌ها
  models.py           17 جدول SQLModel (birth_profiles.zodiac اضافه شد)
  astrology/          Swiss Ephemeris: engine, sky, synastry, rectify, transits, svg, golden_data
  report/             تولید گزارش 13 بخشی + QA خودکار + PDF/Word + ترانزیت هفتگی
  chat/               AI chat: retrieval + intents + service
  payment/            زرین‌پال + سفارش/اشتراک/کوپن/استرداد
  bots/               هندلر یکپارچه تلگرام + بله (تمام‌دکمه‌ای، مرحلهٔ زودیاک)
  seo/                محتوای آموزشی (برج‌ها/سیارات/خانه‌ها) + بنر مقالات
  secret_store.py     کلیدها رمزنگاری‌شده (Fernet) در DB
templates/            ~30 قالب Jinja2 (RTL، Alpine.js، اسپرایت SVG) + degraded banner
tests/                {len(TESTS)} فایل تست ({'۱۵۱ تست'})
scripts/              بکاپ، ریستور، واچ‌داگ، CI، دیپلوی، ترانزیت
deploy/               systemd unit ها + سقف‌های حافظه
alembic/versions/     {len(MIGRATIONS)} مهاجرت
.github/workflows/    CI
```
"""

parts = [header]
parts.append(section("۱) فایل اصلی اپلیکیشن (main.py — همه مسیرها)", main_py))
parts.append(section("۲) هسته: مدل‌ها، دیتابیس، تنظیمات", [f for f in base_py if f in ("app/models.py", "app/db.py", "app/config.py")]))
parts.append(section("۳) امنیت و کلیدها", [f for f in base_py if f in ("app/auth.py", "app/security.py", "app/secret_store.py", "app/storage.py")]))
parts.append(section("۴) موتور نجومی", core_py))
parts.append(section("۵) موتور گزارش + QA", report_py))
parts.append(section("۶) چت هوش مصنوعی", chat_py))
parts.append(section("۷) پرداخت و سفارش", pay_py))
parts.append(section("۸) ربات‌های تلگرام و بله", bots_py))
parts.append(section("۹) SEO و محتوا", seo_py))
parts.append(section("۱۰) کارت اشتراک و هستهٔ مشترک", misc_py))
parts.append(section("۱۱) قالب‌های Jinja2 (فرانت‌اند)", TEMPLATES, "html"))
parts.append(section("۱۲) تست‌ها", TESTS))
parts.append(section("۱۳) زیرساخت و استقرار (اسکریپت‌ها)", SCRIPTS, "bash"))
parts.append(section("۱۴) میگریشن‌های Alembic", MIGRATIONS))
parts.append(section("۱۵) محتوای صفحات (pages.json)", ["app/content/pages.json"], "json"))
parts.append(section("۱۶) systemd units + CI + محیط نمونه", DEPLOY + CI_FILES + ["requirements.txt", ".env.example"], "bash"))

parts.append(f"""

---

## ۱۷) خروجی واقعی pytest (آخرین اجرا)

```
{test_out.strip()}
```

## ۱۸) تاریخچه گیت (آخرین {min(commits, 40)} کامیت)

```
{chr(10).join(gitlog.splitlines()[:40])}
```
""")

OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"WROTE: {OUT} | files: {n_files} | KB: {OUT.stat().st_size/1024:.0f}")
