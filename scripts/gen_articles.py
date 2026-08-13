#!/usr/bin/env python3
"""SEO article batch generator — DeepSeek V4 Pro, thinking ON (quality), strict JSON."""
import asyncio, json, os, sys, time
from pathlib import Path
sys.path.insert(0, "/root/chart-platform")
os.chdir("/root/chart-platform")
from dotenv import load_dotenv
load_dotenv("/root/chart-platform/.env")
from app.core.llm import GoProvider

TOPICS = [
    ("چارت تولد چیست و چطور آن را بخوانیم؟", "آموزش نجوم", "چارت تولد,زایچه,آموزش نجوم"),
    ("طالع بینی چیست و چقدر دقیق است؟", "آموزش نجوم", "طالع بینی,دقت طالع بینی"),
    ("معنای ۱۲ برج در یک نگاه", "برج‌ها", "برج ها,طالع,۱۲ برج"),
    ("برج حمل: شخصیت و سازگاری", "برج‌ها", "برج حمل,شخصیت حمل"),
    ("برج ثور: شخصیت و سازگاری", "برج‌ها", "برج ثور,شخصیت ثور"),
    ("برج جوزا: شخصیت و سازگاری", "برج‌ها", "برج جوزا,شخصیت جوزا"),
    ("برج سرطان: شخصیت و سازگاری", "برج‌ها", "برج سرطان,شخصیت سرطان"),
    ("برج اسد: شخصیت و سازگاری", "برج‌ها", "برج اسد,شخصیت اسد"),
    ("برج سنبله: شخصیت و سازگاری", "برج‌ها", "برج سنبله,شخصیت سنبله"),
    ("برج میزان: شخصیت و سازگاری", "برج‌ها", "برج میزان,شخصیت میزان"),
    ("برج عقرب: شخصیت و سازگاری", "برج‌ها", "برج عقرب,شخصیت عقرب"),
    ("برج قوس: شخصیت و سازگاری", "برج‌ها", "برج قوس,شخصیت قوس"),
    ("برج جدی: شخصیت و سازگاری", "برج‌ها", "برج جدی,شخصیت جدی"),
    ("برج دلو: شخصیت و سازگاری", "برج‌ها", "برج دلو,شخصیت دلو"),
    ("برج حوت: شخصیت و سازگاری", "برج‌ها", "برج حوت,شخصیت حوت"),
    ("خورشید در چارت تولد یعنی چه؟", "سیارات", "خورشید,چارت تولد,هویت"),
    ("ماه در چارت تولد یعنی چه؟", "سیارات", "ماه,چارت تولد,احساسات"),
    ("عطارد در چارت تولد یعنی چه؟", "سیارات", "عطارد,چارت تولد,ذهن"),
    ("زهره در چارت تولد یعنی چه؟", "سیارات", "زهره,چارت تولد,عشق"),
    ("مریخ در چارت تولد یعنی چه؟", "سیارات", "مریخ,چارت تولد,انرژی"),
    ("خانه‌های نجومی به زبان ساده", "خانه‌ها", "خانه های نجومی,۱۲ خانه"),
    ("تأثیر مشتری و زحل بر زندگی", "سیارات", "مشتری,زحل,بخت,آموزش"),
    ("ترانزیت سیارات چیست؟", "ترانزیت", "ترانزیت,سیارات,پیش بینی"),
    ("سازگاری عاطفی برج‌ها", "سازگاری", "سازگاری برج ها,عشق,طالع"),
    ("شغل مناسب بر اساس چارت تولد", "شغل و موفقیت", "شغل,چارت تولد,مسیر شغلی"),
    ("ساعت تولد و اهمیت آن در طالع بینی", "آموزش نجوم", "ساعت تولد,طالع,خانه ها"),
    ("عنصرهای چهارگانه: آتش، خاک، هوا، آب", "آموزش نجوم", "عنصرها,آتش,خاک,هوا,آب"),
    ("ماه در هر برج چه احساسی می‌سازد؟", "ماه", "ماه در برج,احساسات,چارت تولد"),
    ("چرا دو نفر با یک برج متفاوت‌اند؟", "آموزش نجوم", "تفاوت برج ها,چارت تولد,ماه,طالع"),
    ("پیش‌بینی سالانه با ترانزیت‌ها", "ترانزیت", "پیش بینی سالانه,ترانزیت,چارت تولد"),
]

SYSTEM = """تو یک نویسنده ارشد محتوای فارسی (SEO) با ۱۰ سال تجربه در حوزه نجوم و طالع‌بینی هستی.
سبک: روان، انسانی، گرم، معتبر — مثل یک ستون‌نویس حرفه‌ای که با خواننده فارسی‌زبان حرف می‌زند.
اصول: عنوان جذاب، مقدمه گیرا، ساختار H2/H3، پاراگراف‌های کوتاه، جمع‌بندی و CTA ملایم به ساخت چارت.
هر مقاله: ۵۰۰-۷۰۰ کلمه فارسی. اطلاعات نجومی دقیق و استاندارد. بدون اغراق علمی‌نما؛ طالع‌بینی را «ابزار خودشناسی» معرفی کن نه «علم قطعی».
خروجی دقیقاً JSON با کلیدهای: slug (انگلیسی-خط تیره), title, category, excerpt (یک جمله), keywords (کاما), meta (حداکثر ۱۵۵ کاراکتر), body (آرایه‌ای از اشیاء {h2, p})."""

def prompt(title, cat, kw):
    return f"موضوع: «{title}» — دسته: {cat} — کلمات کلیدی: {kw}\n\nJSON معتبر بنویس (بدون فنس، بدون توضیح اضافه)."

def extract_json(txt: str) -> dict | None:
    """Robust: locate first { … last } — tolerant of surrounding prose/fences."""
    if not txt:
        return None
    s, e = txt.find("{"), txt.rfind("}")
    if s == -1 or e <= s:
        return None
    try:
        return json.loads(txt[s:e + 1])
    except Exception:
        return None


async def gen(provider, idx, item):
    t0 = time.monotonic()
    title, cat, kw = item
    art = None
    for attempt in (1, 2):
        res = await provider.complete(prompt(title, cat, kw), system=SYSTEM,
                                      max_tokens=6000, temperature=0.7)
        if res.ok:
            art = extract_json(res.text.strip())
            if art:
                break
        time.sleep(3)
    print(f"[{idx+1}/{len(TOPICS)}] {title[:30]} ok={res.ok} json={'✓' if art else '✗'} sec={int(time.monotonic()-t0)} err={(res.error or '')[:60]}", flush=True)
    return art

async def main():
    provider = GoProvider()  # pro, reasoning ON for quality
    provider.extra_payload = None
    provider.MODEL = "deepseek-v4-pro"
    existing = []
    p = Path("app/content/articles.json")
    if p.exists():
        existing = json.loads(p.read_text("utf-8"))
    seen = {a.get("slug") for a in existing}
    out = list(existing)
    for i, item in enumerate(TOPICS):
        art = await gen(provider, i, item)
        if art and art.get("slug") not in seen:
            art.setdefault("date_fa", "مرداد ۱۴۰۵")
            art.setdefault("image", "")
            out.append(art)
            seen.add(art["slug"])
            # atomic save: temp file + rename (crash-safe, no partial JSON)
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
            tmp.replace(p)
    missing = [t[0] for i, t in enumerate(TOPICS)
               if not any(a.get("title", "").startswith(t[0][:12]) for a in out)]
    print(f"TOTAL articles: {len(out)} | missing: {len(missing)}", flush=True)

asyncio.run(main())
