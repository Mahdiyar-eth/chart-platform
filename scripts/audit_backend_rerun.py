#!/usr/bin/env python3
"""Re-run the BACKEND dimension of the DeepSeek V4 Pro audit (it failed with
HTTP 500 in the original run) against the CURRENT code bundle."""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/chart-platform")
os.chdir("/root/chart-platform")

from dotenv import load_dotenv
load_dotenv("/root/chart-platform/.env")

from app.core.llm import GoProvider

OVERVIEW = Path("docs/audit/OVERVIEW.md").read_text()
BUNDLE = Path("docs/audit/CODEBUNDLE.md").read_text()
CHUNK = 40000
chunks = [BUNDLE[i:i + CHUNK] for i in range(0, len(BUNDLE), CHUNK)]
print(f"chunks: {len(chunks)}", flush=True)

SYSTEM = """تو یک معمار ارشد و مشاور فنی-محصولی با ۱۵ سال تجربه در محصولات SaaS فارسی هستی.
قرار است پروژه «چارت تولد» (سرویس نجومی فارسی) را از نظر بک‌اند تحلیل کنی.
سند OVERVIEW را همراه با کد دریافت می‌کنی. خروجی به فارسی روان، دقیق، عملی و با اولویت‌بندی (P0 بحرانی / P1 مهم / P2 بهبود) باشد.
اشکال واقعی را با ارجاع به فایل/خط گزارش کن؛ ادعای بدون مدرک ننویس. اگر جایی را نمی‌فهمی، بگو «نامشخص».
در پایان هر پاسخ یک بخش «جمع‌بندی این بُعد» بنویس."""

BACKEND_INSTR = """تحلیل بک‌اند: FastAPI، session/Depends، routeها، مدیریت خطا، race condition، صف ARQ، worker، retry، idempotency،
اتصال DB، تراکنش‌ها، حجم و کارایی queryها، لایه‌های middlewares، روت‌های API و صفحه‌ها، لاگ‌ها،
و هر اشکال منطقی/عملکردی/امنیتی در لایه بک‌اند که می‌بینی. هر یافته با ارجاع به فایل/تابع."""

async def main():
    provider = GoProvider()
    provider.extra_payload = None  # reasoning ENABLED
    provider.MODEL = "deepseek-v4-pro"
    t0 = time.monotonic()
    user = (f"# OVERVIEW (محصول)\n{OVERVIEW}\n\n"
            f"# کد (بخش مرتبط)\n{chunks[0]}\n\n"
            f"# مأموریت: بک‌اند\n{BACKEND_INSTR}")
    res = await provider.complete(user, system=SYSTEM, max_tokens=12000, temperature=0.3)
    Path("docs/audit/dim-backend.md").write_text(
        f"# بعد: بک‌اند\n\nپاسخ مدل: {res.provider}/{res.model}\n\n{res.text or ('ERROR: ' + (res.error or ''))}\n")
    print(f"dim backend: ok={res.ok} chars={len(res.text or '')} sec={int(time.monotonic()-t0)} err={(res.error or '')[:120]}", flush=True)
    if not res.ok:
        print("FAILED — inspect error above", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
