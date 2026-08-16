#!/usr/bin/env python3
"""Build ZAYCHE-FULL-BUNDLE.md — complete code + reports + structure in ONE file
for external AI review. Secrets (.env / keys / *.age) are NEVER included.
"""
from pathlib import Path

ROOT = Path("/root/chart-platform")
OUT = ROOT / "docs" / "audit" / "ZAYCHE-FULL-BUNDLE.md"

SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv", "data",
             "logs", ".hermes", "old"}
SKIP_SUFFIXES = {".pyc", ".age", ".pem", ".key", ".zip", ".pdf", ".mp3",
                 ".png", ".jpg", ".jpeg", ".svg", ".woff", ".woff2", ".ttf",
                 ".otf", ".ico", ".webmanifest"}
SKIP_NAMES = {".env", ".env.prod", ".env.test", "config.yaml", "config.yml"}


def include(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in SKIP_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in SKIP_NAMES or name.startswith(".env"):
        return False
    if any(name.endswith(s) for s in SKIP_SUFFIXES):
        return False
    return True


def collect(base: Path) -> list[Path]:
    files = []
    for f in sorted(base.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(ROOT).as_posix()
        if include(rel):
            files.append(f)
    return files


def heading(level: int, text: str) -> str:
    return f"\n{'#' * level} {text}\n"


sections = []

# ── 0. header + status ───────────────────────────────────────────────────────
sections.append("""# باندل کامل زایچه (ZAYCHE) — کد + گزارش‌ها + ساختار

> تولید: 2026-08-15 (پس از ۱۲ فاز Launch Plan v2.0 — P12 FINAL GO مشروط)
> یک فایل واحد برای بررسی کامل توسط هوش مصنوعی/متخصص.
> **سکرت‌ها حذف شده‌اند** (هیچ .env/کلید/توکن در این فایل نیست؛ کد فقط از env می‌خواند).

## وضعیت فعلی (راستی‌آزمایی‌شده 2026-08-15)

- **تست‌ها:** 451 passed, 1 skipped (۶۲+ فایل تست)
- **کیفیت:** ruff F/E9 پاک · bandit High=0 Medium=0 · pip-audit 0 آسیب‌پذیری · pyright type-only
- **پلن لانچ ۱۲ فاز:** P1-P12 کامل — verdict **FINAL GO (مشروط به ۳ فعال‌سازی کاربر: مرچنت زرین‌پال، کلید کاوه‌نگار، تست موبایل فیزیکی)**
- **زیرساخت:** systemd chart-web/chart-worker (User=zayche) · Redis+ARQ · PostgreSQL 16 + pgvector · R2 `zayche-storage` · nginx/HTTPS chart.negar.io · Umami analytics.negar.io
- **قیمت‌ها (تومان):** basic=149,000 · full=349,000 · gold=699,000 · credit3=180,000(3) · credit6=330,000(6) · credit12=600,000(12) · monthly=99,000 · yearly=890,000

## فهرست محتوا

1. ساختار کامل پروژه (درخت)
2. کد بک‌اند (app/**)
3. کد فرانت (templates + static)
4. تست‌ها (tests/**)
5. مهاجرت‌ها (alembic/**)
6. زیرساخت (deploy + scripts + CI)
7. مستندات (docs/** — راهنماها، AUTHORIZATION-MATRIX)
8. گزارش‌های ممیزی (docs/audit/**)
9. گزارش‌های لانچ (reports/launch/**)
10. وضعیت نهایی
""")

# ── 1. tree ──────────────────────────────────────────────────────────────────
sections.append(heading(1, "۱) ساختار کامل پروژه"))
tree = []
for f in collect(ROOT):
    rel = f.relative_to(ROOT).as_posix()
    depth = rel.count("/")
    tree.append("  " * depth + "└ " + rel.split("/")[-1])
sections.append("```\n" + "\n".join(tree) + "\n```\n")


def file_block(label: str, path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    txt = path.read_text(encoding="utf-8", errors="replace")
    lines = txt.count("\n") + 1
    return f"FILE: {rel}  ({lines} lines)\n{'=' * 70}\n{txt}\n"


# ── 2. backend ───────────────────────────────────────────────────────────────
sections.append(heading(1, "۲) کد بک‌اند (app/**)"))
backend = collect(ROOT / "app")
for f in backend:
    if f.suffix == ".py":
        sections.append(file_block("app", f))
sections.append("")

# ── 3. frontend ──────────────────────────────────────────────────────────────
sections.append(heading(1, "۳) کد فرانت (templates + static)"))
frontend = collect(ROOT / "app" / "templates") + collect(ROOT / "app" / "static")
for f in frontend:
    if f.suffix in (".html", ".js", ".css", ".json"):
        sections.append(file_block("front", f))
sections.append("")

# ── 4. tests ─────────────────────────────────────────────────────────────────
sections.append(heading(1, "۴) تست‌ها (tests/**)"))
for f in collect(ROOT / "tests"):
    sections.append(file_block("tests", f))
sections.append("")

# ── 5. migrations ────────────────────────────────────────────────────────────
sections.append(heading(1, "۵) مهاجرت‌ها (alembic/**)"))
for f in collect(ROOT / "alembic"):
    sections.append(file_block("alembic", f))
sections.append("")

# ── 6. infra ─────────────────────────────────────────────────────────────────
sections.append(heading(1, "۶) زیرساخت (deploy + scripts + CI)"))
for d in ("deploy", "scripts", ".github"):
    p = ROOT / d
    if p.exists():
        for f in collect(p):
            sections.append(file_block("infra", f))
sections.append("")

# ── 7. docs (non-audit) ──────────────────────────────────────────────────────
sections.append(heading(1, "۷) مستندات (docs/**)"))
for f in collect(ROOT / "docs"):
    if f.suffix == ".md" and "audit" not in f.relative_to(ROOT).as_posix():
        sections.append(file_block("docs", f))
sections.append("")

# ── 8. audit reports ─────────────────────────────────────────────────────────
sections.append(heading(1, "۸) گزارش‌های ممیزی (docs/audit/**)"))
# skip legacy code-bundles (code already in sections 2-5) and this file itself
SKIP_AUDIT = {"ZAYCHE-CODEBUNDLE.md", "CODEBUNDLE.md", "ZAYCHE-FULL-BUNDLE.md",
              "ZAYCHE-CODEBUNDLE-2.md"}
for f in collect(ROOT / "docs" / "audit"):
    if f.suffix == ".md" and f.name not in SKIP_AUDIT:
        sections.append(file_block("audit", f))
sections.append("")

# ── 9. launch reports ────────────────────────────────────────────────────────
sections.append(heading(1, "۹) گزارش‌های لانچ (reports/launch/**)"))
for f in collect(ROOT / "reports"):
    if f.suffix == ".md":
        sections.append(file_block("launch", f))
sections.append("")

# ── 10. final status ─────────────────────────────────────────────────────────
sections.append(heading(1, "۱۰) وضعیت نهایی"))
sections.append("""
## Verdict: ✅ FINAL GO (مشروط)

3 فعال‌سازی کاربر (هیچ‌کدام تغییر کد نمی‌خواهد):
1. مرچنت واقعی زرین‌پال → `ZARINPAL_SANDBOX=false`
2. کلید کاوه‌نگار → `OTP_SMS_API_KEY` (فعلاً OTP fail-closed)
3. تست موبایل فیزیکی (checklist در P12)

## گیت‌های §55 (همه بسته)

- security: bandit High=0/Medium=0 · pip-audit 0 · fail-closed SMS · کوکی HMAC · rate-limit Redis
- authz: AUTHORIZATION-MATRIX + تست مالکیت order→chart→profile→user
- payment: claim اتمی · کوپن اتمی · callback idempotent · refund · ledger
- privacy: referral بدون PII · backup age-encrypted · private-tmp (B108)
- data loss: backup روزانه 03:15 → R2 · DR drill OK (restore→migrate→sanity)
- report corruption: MAX_RETRIES=6 · degraded path · gold 13/13 صفر fallback
- AI safety: whitelist اتحادی · متن‌های ضداضطراب · بدون پیشگویی/درمان
- PWA/Push: FCM واقعی · proof decrypt دائمی (test_push_delivery_p12.py)
- OTP: 8 تست hardening + فیکس attempts>=MAX (brute force 5 تلاش)
- UX: 36/36 معیار landing · فانل رایگان→5 بینش→CTA
""")

out = "\n".join(sections)
OUT.write_text(out, encoding="utf-8")
n_app = len(collect(ROOT / "app"))
n_tests = len(collect(ROOT / "tests"))
print(f"files: app={n_app} tests={n_tests} | chars: {len(out)} | KB: {len(out)//1024} | MB: {len(out)/1024/1024:.1f}")
