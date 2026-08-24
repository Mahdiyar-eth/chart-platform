"""F3 / R.7 / T2 — ZAYCHE astronomical glossary (واژه‌نامهٔ کوتاه).

Plan B-3/F3 required a glossary of 60+ linkable terms. Each entry carries:
  * term  — the Persian heading (link anchor id derived from it)
  * latin — the technical/English name (often the one users search)
  * def   — a one-or-two line plain-language definition (glossary must be simple)
  * link  — optional: a related page to deep-link (learn page / signs / article)

Planets / houses / signs reuse the existing `app.seo.content` slugs so the glossary
stays DRY and cross-linked into the already-published learning pages.
"""

# ── reuse existing content so links are real and consistent ──────────────────
from app.seo.content import HOUSES, SIGNS

_SIGN_SLUG = {s["slug"]: s["title"] for s in SIGNS.values()}


def _link(kind: str, key: str) -> str:
    if kind == "planet":
        return f"/learn/{key}"
    if kind == "house":
        return f"/learn/{key}"
    if kind == "sign":
        slug = next((s["slug"] for s in SIGNS.values() if s["kind"] == key or s["title"].startswith(key)), key)
        return f"/signs/{slug}"
    return ""


# Terms that map to an existing /learn page get a real link; the rest stand alone.
PLANET_TERMS = [
    {"term": "خورشید", "latin": "Sun", "link": "/learn/sun", "def": "هستهٔ هویت و اراده؛ برج خورشیدی یعنی خورشید در تولدت کجا بوده."},
    {"term": "ماه", "latin": "Moon", "link": "/learn/moon", "def": "احساسات، نیازهای درونی و واکنش‌های ناخودآگاه؛ ماهِ تولد، ماه عاطفی توست."},
    {"term": "عطارد", "latin": "Mercury", "link": "/learn/mercury", "def": "ذهن، گفتار، یادگیری و ارتباطات؛ شیوهٔ فکر کردن و بیان."},
    {"term": "ناهید", "latin": "Venus", "link": "/learn/venus", "def": "عشق، زیبایی، ارزش‌ها و جاذبه؛ زبانِ دل تو."},
    {"term": "مریخ", "latin": "Mars", "link": "/learn/mars", "def": "انرژی، اراده، شور و اقدام؛ چگونه وارد عمل می‌شوی."},
    {"term": "مشتری", "latin": "Jupiter", "link": "/learn/jupiter", "def": "رشد، خوش‌بینی، فراوانی و گسترش؛ جایی که بخت با توست."},
    {"term": "زحل", "latin": "Saturn", "link": "/learn/saturn", "def": "ساختار، مسئولیت و درس‌های بلندمدت؛ استادِ نظم."},
    {"term": "اورانوس", "latin": "Uranus", "link": "/learn/uranus", "def": "نوآوری، شورش و ناگهان‌ها؛ عامل تغییرهای عمومی."},
    {"term": "نپتون", "latin": "Neptune", "link": "/learn/neptune", "def": "خیال، شهود، وهم و معنویت؛ قلمروِ رؤیا و عدم قطعیت."},
    {"term": "پلوتون", "latin": "Pluto", "link": "/learn/pluto", "def": "قدرت، تحول و بازتولید؛ عمیق‌ترین لایهٔ دگرگونی."},
]

HOUSE_TERMS = [
    {"term": f"خانهٔ {n}", "latin": f"House {n}", "link": f"/learn/{n}", "def": h["title"].split("—")[0].strip()}
    for n, h in HOUSES.items()
]

SIGN_TERMS = [
    {"term": s["title"].split("—")[0].strip(), "latin": f"برج {s.get('element','')}", "link": f"/signs/{s['slug']}",
     "def": (s.get("personality") or s.get("challenge") or "")[:140]}
    for s in SIGNS.values()
]

ASPECT_TERMS = [
    {"term": "مقارنه", "latin": "Conjunction", "def": "دو سیاره نزدیکِ هم؛ انرژی‌ها در هم تنیده و قوی‌تر."},
    {"term": "تربیع", "latin": "Square", "def": "زاویهٔ ۹۰ درجه؛ تنشِ سازنده و دعوت به رشد."},
    {"term": "مثلث", "latin": "Trine", "def": "زاویهٔ ۱۲۰ درجه؛ جریانِ آسان و هماهنگی طبیعی."},
    {"term": "ششنقره", "latin": "Sextile", "def": "زاویهٔ ۶۰ درجه؛ فرصتِ ملایم که با تلاش فعال می‌شود."},
    {"term": "مقابله", "latin": "Opposition", "def": "زاویهٔ ۱۸۰ درجه؛ دو قطبِ مکمل و تنشِ تعادل‌طلب."},
]

ANGLE_TERMS = [
    {"term": "طالع", "latin": "Ascendant (ASC)", "link": "/learn/1", "def": "نقطهٔ برجِ بالارونده در لحظهٔ تولد؛ هویتِ بیرونی و پیش‌صحنهٔ زندگی."},
    {"term": "وسط‌آسمان", "latin": "Midheaven (MC)", "def": "سقفِ چارت؛ مسیر شغلی، جایگاه اجتماعی و تصویر عمومی."},
    {"term": "ته آسمان", "latin": "Imum Coeli (IC)", "def": "پایینِ چارت؛ ریشه‌ها، خانواده و زندگی خصوصی."},
    {"term": "نقطهٔ نزول", "latin": "Descendant (DSC)", "def": "برجِ غروب؛ شرکای زندگی، روابط و «دیگری»."},
    {"term": "گره‌ها", "latin": "Nodes", "def": "گرهٔ شمالی/جنوبی؛ مسیرِ رشد و الگوی کارما."},
]

GENERAL_TERMS = [
    {"term": "چارت تولد", "latin": "Birth chart", "link": "/learn/birth-chart", "def": "نقشهٔ آسمان در لحظه و مکان تولد؛ پایهٔ همهٔ تحلیل‌ها."},
    {"term": "زایچه", "latin": "Natal chart", "def": "نام دیگرِ چارت تولد — همان نقشهٔ شخصی آسمان."},
    {"term": "برج", "latin": "Zodiac sign", "def": "۱۲ تقسیمِ دایرهٔ بروج؛ رنگِ هر سیاره را تعیین می‌کند."},
    {"term": "خانه", "latin": "House", "link": "/learn/1", "def": "۱۲ حوزهٔ زندگی (خود، پول، ارتباطات، خانواده، …)."},
    {"term": "سیاره‌های شخصی", "latin": "Personal planets", "def": "خورشید، ماه، عطارد، ناهید و مریخ — ستونِ شخصیت."},
    {"term": "سیاره‌های اجتماعی", "latin": "Social planets", "def": "مشتری و زحل — پیوند با جامعه و ساختار."},
    {"term": "سیاره‌های بیرونی", "latin": "Outer planets", "def": "اورانوس، نپتون، پلوتون — نسلی و تحولی."},
    {"term": "کرهٔ برج", "latin": "Zodiac wheel", "def": "دایرهٔ ۳۶۰ درجه‌ای که برج‌ها و خانه‌ها روی آن‌اند."},
    {"term": "منظومهٔ شمسی", "latin": "Solar system", "def": "خورشید و سیارات؛ جسمِ مورد مطالعهٔ نجومِ چارت."},
    {"term": "زمین‌مرکز", "latin": "Geocentric", "def": "دید از زمین؛ ستاره‌شناسیِ چارت از دیدِ ناظرِ زمینی."},
    {"term": "خورشیدمرکز", "latin": "Heliocentric", "def": "دید از خورشید؛ گاه در تحلیل‌های پیشرفته."},
    {"term": "ساعتِ تولد", "latin": "Birth time", "link": "/learn/birth-chart", "def": "برای طالع و خانه‌ها ضروری؛ بدون آن چارت ناقص است."},
    {"term": "فاز ماه", "latin": "Moon phase", "link": "/moon", "def": "قمر در چرخهٔ ۲۹.۵ روزه؛ رنگِ عاطفی و لحنِ تولد."},
    {"term": "ماه نو", "latin": "New moon", "link": "/moon", "def": "شروع چرخه؛ انرژیِ تازه و تصمیم. (فاز ماه در تولد)"},
    {"term": "ماهِ کامل", "latin": "Full moon", "link": "/moon", "def": "اوج چرخه؛ روشنایی و نقطهٔ اوجِ نیمه‌چرخه."},
    {"term": "ترانزیت", "latin": "Transit", "link": "/learn/transit", "def": "جای فعلی سیارات در آسمان و نسبتش با چارت تولد."},
    {"term": "گذر", "latin": "Transit", "def": "همان ترانزیت؛ حرکت اکنونِ سیاره بر چارتِ تو."},
    {"term": "رتروگرید", "latin": "Retrograde", "def": "حرکتِ ظاهریِ سیاره به عقب؛ مرور، بازبینی و تأخیرِ سازنده."},
    {"term": "ردگام", "latin": "Retro", "def": "نشانِ غلطِ رایج برای رتروگرید؛ به معنی بازگشتِ سیاره."},
    {"term": "همنشینی", "latin": "Conjunction", "def": "هم‌نشینیِ نزدیکِ دو سیاره؛ ادغامِ انرژی."},
    {"term": "سیناستری", "latin": "Synastry", "link": "/synastry", "def": "برهم‌نهادنِ دو چارت؛ مقایسهٔ سازگاریِ دو نفر."},
    {"term": "سازگاری", "latin": "Compatibility", "link": "/synastry", "def": "میزان هماهنگیِ دو چارت؛ نه فقط برج."},
    {"term": "توزیع عنصری", "latin": "Element balance", "def": "سهمِ آتش/خاک/باد/آب در چارت؛ توازنِ انرژی."},
    {"term": "کیفیت‌ها", "latin": "Modalities", "def": "بنیادین/ثابت/متغیر؛ سبکِ پیشرفتِ هر سیاره."},
    {"term": "مثلثِ آب", "latin": "Water trine", "def": "هماهنگیِ سیاراتِ آبی؛ عاطفه و شهود."},
    {"term": "حوزهٔ شغلی", "latin": "Career area", "def": "خانه‌های ۱۰ و ۶ و وسط‌آسمان؛ مسیرِ کارِ تو."},
    {"term": "حوزهٔ روابط", "latin": "Relationship area", "def": "خانه‌های ۷ و ۵ و ۴؛ پیوندهای عاطفی."},
    {"term": "حوزهٔ پول", "latin": "Money houses", "def": "خانه‌های ۲ و ۸؛ درآمد و داراییِ مشترک."},
    {"term": "تثبیت", "latin": "Fixed", "def": "کیفیتِ ثابت؛ پایداری و مقاومت در برابر تغییر."},
    {"term": "بنیادین", "latin": "Cardinal", "def": "کیفیتِ بنیادین؛ آغازگر و پویا."},
    {"term": "متغیر", "latin": "Mutable", "def": "کیفیتِ متغیر؛ انعطاف، تغییر و سازگاری."},
    {"term": "دایرةالبروج", "latin": "Ecliptic", "def": "مسیرِ ظاهریِ خورشید در آسمان؛ دایرهٔ ۱۲ برج."},
    {"term": "Orb", "latin": "Orb / مجاز", "def": "میزانِ دقتِ زاویه؛ هر چقدر نزدیک‌تر، زاویه قوی‌تر."},
    {"term": "جنبهٔ اصلی", "latin": "Major aspect", "def": "مقارنه، تربیع، مثلث، مقابله و ششنقره."},
]


def build_glossary() -> list[dict]:
    """Return the full ordered glossary: planets → houses → signs → aspects →
    angles → general. Compact and linkable (anchor id = persian term). The `cat`
    field lets the template group them into sections."""
    out = []
    for _cat, terms in (("planet", PLANET_TERMS), ("house", HOUSE_TERMS), ("sign", SIGN_TERMS),
                        ("aspect", ASPECT_TERMS), ("angle", ANGLE_TERMS), ("general", GENERAL_TERMS)):
        for t in terms:
            out.append({"cat": _cat, **t})
    return out


if __name__ == "__main__":
    g = build_glossary()
    print(f"total terms: {len(g)}")
    nolink = sum(1 for t in g if not t.get("link"))
    print(f"linked: {len(g)-nolink} · standalone: {nolink}")
    # sanity: no empty defs, no dup terms
    seen = {}
    for t in g:
        assert t["term"] and t["def"], t
        seen[t["term"]] = seen.get(t["term"], 0) + 1
    dups = [t for t, c in seen.items() if c > 1]
    print(f"duplicate terms: {dups}")
    print("prefix:", [t["term"] for t in g[:6]])
