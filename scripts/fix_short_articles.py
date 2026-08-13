#!/usr/bin/env python3
"""Regenerate broken/short articles (targeted)."""
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, "/root/chart-platform")
from app.core.llm import build_router  # noqa

FIX = {
    "برج-اسد-ویژگی-ها": ("ویژگی‌های کامل برج اسد: شخصیت، عشق و زندگی", "برج‌ها", ("اسد", "شخصیت اسد", "مشاغل اسد", "عشق اسد", "سازگاری اسد")),
    "سیارات-در-چارت-تولد": ("سیارات در چارت تولد: نقش هر سیاره در شخصیت شما", "آموزش نجوم", ("سیارات", "خورشید", "ماه", "عطارد", "زهره")),
    "chart-tavalod-chist": ("چارت تولد چیست و چرا باید آن را داشته باشید؟", "آموزش نجوم", ("چارت تولد", "طالع بینی", "زایچه", "نقشه آسمان")),
}
SYSTEM = "تو نویسنده‌ی وب‌سایت چارت تولد هستی. مقاله‌ی SEO فارسی با کیفیت بالا بنویس: حداقل 700 کلمه، 5-7 بخش h2، لحن گرم و ساده و غیرفنی، بدون کلیشه، با عناوین جذاب. خروجی: JSON خالص — {slug, title, category, excerpt, keywords, meta, body:[{h2,p:[]}]} — هیچ چیز دیگری."

def extract_json(txt):
    if not txt:
        return None
    s, e = txt.find("{"), txt.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(txt[s:e+1])
    except Exception:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.S)
        return json.loads(m.group(1)) if m else None

async def main():
    router = build_router()
    path = Path("/root/chart-platform/app/content/articles.json")
    arts = json.loads(path.read_text())
    kept, changed = [], 0
    for a in arts:
        if a["slug"] in FIX:
            title, cat, kw = FIX[a["slug"]]
            prompt = (f"موضوع: {title}\nکلمات کلیدی: {', '.join(kw)}\n"
                      "بنویس: 700+ کلمه، 5-7 بخش با h2، پاراگراف‌های 60-100 کلمه.")
            r = await router.complete(prompt, system=SYSTEM, max_tokens=6000)
            art = extract_json(r.text if hasattr(r, "text") else str(r))
            if art and art.get("body"):
                wc = sum(len(" ".join(s["p"]) .split()) if isinstance(s["p"], list) else len(s["p"].split()) for s in art["body"])
                if wc > 300:
                    art["slug"] = a["slug"]; art["date_fa"] = a.get("date_fa", "مرداد ۱۴۰۵")
                    art["image"] = a.get("image", "")
                    kept.append(art); changed += 1
                    print(f"✅ بازتولید شد: {a['slug']} ({wc} کلمه)")
                else:
                    kept.append(a)
                    print(f"❌ خیلی کوتاه ({wc}): {a['slug']}")
            else:
                kept.append(a)
                print(f"❌ بازتولید ناموفق، نگه داشته شد: {a['slug']}")
        else:
            kept.append(a)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=1))
    tmp.replace(path)
    print(f"تمام شد: {len(kept)} مقاله، {changed} بازتولید")

asyncio.run(main())
