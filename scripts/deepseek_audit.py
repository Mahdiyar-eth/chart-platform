#!/usr/bin/env python3
"""DeepSeek V4 Pro full-stack audit (reasoning ENABLED) — 10 dimensions + synthesis."""
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

# split bundle into chunks ~40KB
CHUNK = 40000
chunks = [BUNDLE[i:i+CHUNK] for i in range(0, len(BUNDLE), CHUNK)]
print(f"chunks: {len(chunks)}", flush=True)

DIMS = {
    "ui-ux": ("UI/UX و تجربه کاربر", """تحلیل کامل UI/UX: ساختار صفحات، RTL، موبایل-فرست بودن، دسترس‌پذیری، جریان خرید، بازخورد کاربر، بهبودهای پیشنهادی با اولویت."""),
    "frontend": ("فرانت‌اند", """تحلیل فرانت: Jinja2/Alpine/HTMX، جاوااسکریپت، فرم‌ها، وضعیت‌ها، PWA/sw، اشکالات و ریسک‌ها."""),
    "backend": ("بک‌اند", """تحلیل بک‌اند: FastAPI، session/Depends، routeها، مدیریت خطا، race condition، صف ARQ، worker، retry، idempotency."""),
    "security": ("امنیت", """تحلیل امنیت: auth/OTP/session، CSP، تزریق، SSRF، امضای PDF، presigned URL، secrets، ریسک‌های باقی‌مانده."""),
    "seo": ("SEO", """تحلیل SEO: sitemap/canonical/og، ساختار URL، سرعت، محتوای فارسی، فرصت‌های رشد ارگانیک، استراتژی مقالات."""),
    "marketing": ("مارکتینگ و فروش", """تحلیل مارکتینگ: صفحات لندینگ، قیف فروش، قیمت‌گذاری، کوپن/رفرال، اشتراک، پیش‌نمایش رایگان، CTA، پیشنهادهای بهبود."""),
    "kpi-admin": ("KPI داشبورد و ادمین", """تحلیل پنل ادمین و KPI: متریک‌های موجود (درآمد/گزارش/LLM cost/کاربر/اشتراک)، چه KPI مهمی کم است، قابلیت‌های عملیاتی ادمین."""),
    "logic": ("منطق و سازوکارها", """تحلیل منطق محصول: موتور نجومی، QA، retry، پلن‌ها (basic/full/gold/synastry/monthly)، گیت‌های پرداخت، اشتراک، digest ترانزیت، پیش‌نمایش — اشکالات منطقی."""),
    "bots": ("ربات‌های تلگرام/بله", """تحلیل ربات‌ها: button-driven، callbackها، state، webhook، خطاهای احتمالی، ارتقا."""),
    "perf-cost": ("عملکرد و هزینه", """تحلیل عملکرد و هزینه: سرعت رندر، LLM cost (اشتراک $10/ماه)، حجم خروجی، کش، دیتابیس، بهینه‌سازی‌ها."""),
}

SYSTEM = """تو یک معمار ارشد و مشاور فنی-محصولی با ۱۵ سال تجربه در محصولات SaaS فارسی هستی. 
قرار است پروژه «چارت تولد» (سرویس نجومی فارسی) را از همه جهات تحلیل کنی.
سند OVERVIEW را همراه با کد دریافت می‌کنی. خروجی به فارسی روان، دقیق، عملی و با اولویت‌بندی (P0 بحرانی / P1 مهم / P2 بهبود) باشد.
اشکال واقعی را با ارجاع به فایل/خط گزارش کن؛ ادعای بدون مدرک ننویس. اگر جایی را نمی‌فهمی، بگو «نامشخص».
در پایان هر پاسخ یک بخش «جمع‌بندی این بُعد» بنویس."""

async def audit_dim(provider, name, title, instruction, chunk, out_dir):
    t0 = time.monotonic()
    user = f"# OVERVIEW (محصول)\n{OVERVIEW}\n\n# کد (بخش مرتبط)\n{chunk}\n\n# مأموریت: {title}\n{instruction}"
    res = await provider.complete(user, system=SYSTEM, max_tokens=12000, temperature=0.3)
    Path(out_dir, f"dim-{name}.md").write_text(
        f"# بعد: {title}\n\nپاسخ مدل: {res.provider}/{res.model}\n\n{res.text or ('ERROR: ' + (res.error or ''))}\n")
    print(f"dim {name}: ok={res.ok} chars={len(res.text or '')} sec={int(time.monotonic()-t0)} err={(res.error or '')[:80]}", flush=True)
    return res

async def main():
    provider = GoProvider()  # reasoning ENABLED (extra_payload=None below)
    provider.extra_payload = None  # let DeepSeek think — audit needs depth
    provider.MODEL = "deepseek-v4-pro"
    out_dir = "docs/audit"
    results = {}
    for name, (title, instr) in DIMS.items():
        res = await audit_dim(provider, name, title, instr, chunks[0], out_dir)
        results[name] = res
        if not res.ok:
            print(f"  !! dim {name} failed — continue", flush=True)
    # synthesis
    dim_texts = []
    for name in DIMS:
        p = Path(out_dir, f"dim-{name}.md")
        if p.exists():
            t = p.read_text()
            dim_texts.append(f"===== بعد: {name} =====\n{t[:14000]}")
    syn_user = ("دریافت: OVERVIEW + نتایج تحلیل ۱۰ بعد. "
                "یک گزارش نهایی جامع بنویس: ۱) خلاصه اجرایی ۲) یافته‌های اصلی به تفکیک بعد با اولویت P0/P1/P2 "
                "۳) ۱۰ توصیه‌ی برتر فوری (با تأثیر و هزینه) ۴) ریسک‌های پنهان ۵) نقشه‌ی راه پیشنهادی در ۴ فاز. "
                "به فارسی، عملی، دقیق.\n\n" + "\n".join(dim_texts[:90000]))
    syn = await provider.complete(syn_user, system=SYSTEM, max_tokens=12000, temperature=0.3)
    Path(out_dir, "deepseek-audit.md").write_text(
        f"# تحلیل جامع پروژه چارت تولد — DeepSeek V4 Pro (ریزنینگ روشن)\n\n{overview_note()}\n\n{syn.text or ('ERROR: ' + (syn.error or ''))}\n")
    print(f"SYNTHESIS: ok={syn.ok} chars={len(syn.text or '')}", flush=True)
    print("DONE", flush=True)

def overview_note():
    return "> این گزارش توسط DeepSeek V4 Pro (opencode.ai Go, reasoning enabled) بر اساس OVERVIEW + CODEBUNDLE تولید شد. ارجاع‌ها باید در کد راستی‌آزمایی شوند."

asyncio.run(main())
