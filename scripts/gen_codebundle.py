#!/usr/bin/env python3
"""ZAYCHE full code bundle generator (module-organized, fresh pytest + git).
Adapted from project-documentation-snapshot template (2026-08-17)."""
import subprocess
from pathlib import Path

ROOT = Path("/root/chart-platform")
OUT = ROOT / "docs" / "audit" / "ZAYCHE-CODEBUNDLE.md"

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def code_block(rel: str, lang: str = "python") -> str:
    try:
        c = read(rel)
    except Exception as e:
        return f"### `{rel}`\n\n```\n(خطا در خواندن: {e})\n```\n"
    n = c.count("\n") + 1
    return f"### `{rel}` ({n} lines)\n\n```{lang}\n{c}\n```\n"

def section(title: str, rels: list[str], lang: str = "python") -> str:
    parts = [f"\n---\n\n## {title}\n"]
    for r in rels:
        parts.append(code_block(r, lang))
    return "\n".join(parts)

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
    if p.is_file() and p.suffix in (".service", ".example", ".txt", ".env", ".sh", ".py")
)
CI_FILES = py_files(".github/workflows/*.yml")

test_last = test_out.strip().splitlines()[-1] if test_out.strip() else "?"
header = f"""# ZAYCHE — Full Code Bundle (modular)

> Generated 2026-08-17 (final audit round) — up to commit `{head}`
> For deep code-level review by an external AI. Secrets are excluded; sensitive
> values appear only as env placeholders (get_secret / env pattern).
> Narrative companion: docs/audit/PLAIN-REPORT.md and reports/launch/FINAL-GO.md

## Current state
- Tests: {test_last}
- Commits: {commits} · head: {head}
- CI gates: pytest+coverage · ruff F/E9 · bandit -lll · pip-audit · secret-scan · brand-scan · alembic chain check
- Migrations: {len(MIGRATIONS)} Alembic
- Live stack: FastAPI + HTMX/Alpine (RTL PWA) · R2 presigned storage · Postgres 16 + pgvector (RAG) · OmniRoute LLM gateway (gemini flash-high default) with GO/zen fallback
"""

parts = [header]
def pick(prefix: str) -> list[str]:
    return sorted(f for f in APP_PY if f.startswith(prefix))

parts.append(section("۱) فایل اصلی اپلیکیشن (main.py — همه مسیرها)",
                     [f for f in APP_PY if f == "app/main.py"]))
parts.append(section("۲) هسته: مدل‌ها، دیتابیس، تنظیمات",
                     [f for f in APP_PY if f in ("app/models.py", "app/db.py", "app/config.py", "app/rotation.py")]))
parts.append(section("۳) امنیت و کلیدها",
                     [f for f in APP_PY if f in ("app/auth.py", "app/security.py", "app/secret_store.py", "app/storage.py", "app/rate_limiter.py")]))
parts.append(section("۴) موتور نجومی", pick("app/astrology/")))
parts.append(section("۵) موتور گزارش + QA", pick("app/report/")))
parts.append(section("۶) چت هوش مصنوعی", pick("app/chat/")))
parts.append(section("۷) پرداخت و سفارش", pick("app/payment/")))
parts.append(section("۸) ربات‌ها", pick("app/bots/")))
parts.append(section("۹) SEO و محتوا", pick("app/seo/")))
parts.append(section("۱۰) هستهٔ مشترک + اشتراک‌گذاری", pick("app/core/") + pick("app/share/")))
parts.append(section("۱۱) قالب‌های Jinja2 (فرانت‌اند)", TEMPLATES, "html"))
parts.append(section("۱۲) تست‌ها", TESTS))
parts.append(section("۱۳) زیرساخت و استقرار (اسکریپت‌ها)", SCRIPTS, "bash"))
parts.append(section("۱۴) میگریشن‌های Alembic", MIGRATIONS))
parts.append(section("۱۵) محتوای صفحات", ["app/content/pages.json"], "json"))
parts.append(section("۱۶) systemd units + CI + محیط نمونه",
                     DEPLOY + CI_FILES + ["requirements.txt", ".env.example"], "bash"))

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
print(f"WROTE: {OUT} | KB: {OUT.stat().st_size/1024:.0f} | files: {len(APP_PY)+len(TEMPLATES)+len(TESTS)}")