"""«آسمان امروز» — public today's-sky page (audit G-3).

Deterministic (pyswisseph) current planetary positions + moon phase + aspects +
retrogrades + upcoming moon events + a weekly reflective exercise.
No LLM, no cost, no prediction — reflective self-knowledge.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import jdatetime
import swisseph as swe

from app.astrology.transits import SIGNS_FA, PLANET_NAMES, _lon, _angular_diff

swe.set_ephe_path(os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe"))
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

_PLANET_FA = {
    "Sun": "خورشید", "Moon": "ماه", "Mercury": "تیر", "Venus": "ناهید",
    "Mars": "مریخ", "Jupiter": "مشتری", "Saturn": "کیوان",
    "Uranus": "اورانوس", "Neptune": "نپتون", "Pluto": "پلوتو",
}
_PLANET_GLYPH = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
}
_MOON_PHASE_FA = {
    "New": "ماه نو", "Waxing": "رو به رشد", "Full": "ماه کامل", "Waning": "رو به کاهش",
}
# plain-language meaning per phase (no prediction — reflection only)
_MOON_PHASE_MEANING = {
    "New": "فازِ ماهِ نو؛ وقتِ کاشتنِ نیت و شروعِ آرام. انرژی تازه در حال شکل‌گرفتن است.",
    "Waxing": "فازِ رشد؛ نیرو رو به زیاد شدن است. وقتِ عمل، ساختن و پیش‌بردن.",
    "Full": "فازِ ماهِ کامل؛ اوجِ روشنایی و شفاف‌شدنِ احساس‌ها. وقتِ دیدنِ نتیجه‌ها.",
    "Waning": "فازِ کاهنده؛ وقتِ جمع‌وجور کردن، رها کردنِ اضافه‌ها و سبک شدن.",
}

# one-line "domain" per planet — general layer (everyone understands)
_PLANET_THEME = {
    "خورشید": "هویت، اراده و مسیر زندگی",
    "ماه": "احساسات، نیازها و دنیای درون",
    "تیر": "فکر، گفت‌وگو و یادگیری",
    "ناهید": "عشق، زیبایی و ارزش‌ها",
    "مریخ": "انگیزه، انرژی و اقدام",
    "مشتری": "رشد، امید و معنا",
    "کیوان": "انضباط، مسئولیت و پختگی",
    "اورانوس": "تغییر، آزادی و نوآوری",
    "نپتون": "رؤیا، الهام و مرزگشایی",
    "پلوتو": "تحول عمیق و رهایی",
}
# what a retrograde invites us to REVIEW (not predict)
_PLANET_RETRO_REVIEW = {
    "تیر": "ارتباط‌ها، قرارها و تصمیم‌ها",
    "ناهید": "روابط و ارزش‌ها",
    "مریخ": "انگیزه و شیوه‌ی اقدام",
    "مشتری": "باورها و برنامه‌های بلندمدت",
    "کیوان": "مسئولیت‌ها و ساختارها",
    "اورانوس": "تغییرات و آزادی",
    "نپتون": "رؤیاها و مرزها",
    "پلوتو": "تحول‌های عمیق",
}

_SIGN_BARE = ["حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله", "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت"]
_ELEMENT = {
    "حمل": "آتش", "اسد": "آتش", "قوس": "آتش",
    "ثور": "خاک", "سنبله": "خاک", "جدی": "خاک",
    "جوزا": "هوا", "میزان": "هوا", "دلو": "هوا",
    "سرطان": "آب", "عقرب": "آب", "حوت": "آب",
}
_MODALITY = {
    "حمل": "بنیادین", "سرطان": "بنیادین", "میزان": "بنیادین", "جدی": "بنیادین",
    "ثور": "ثابت", "اسد": "ثابت", "عقرب": "ثابت", "دلو": "ثابت",
    "جوزا": "متغیر", "سنبله": "متغیر", "قوس": "متغیر", "حوت": "متغیر",
}

_ASPECTS = [
    {"key": "conj", "name": "هم‌نشینی", "base": 0, "orb": 8, "glyph": "☌",
     "meaning": "انرژیِ دو سیاره در هم می‌آمیزد؛ شدت و شروع."},
    {"key": "opp", "name": "مقابله", "base": 180, "orb": 6, "glyph": "☍",
     "meaning": "کششِ میانِ دو قطب؛ آگاهی و تعادل."},
    {"key": "tri", "name": "سه‌گانه", "base": 120, "orb": 6, "glyph": "△",
     "meaning": "جریانِ هماهنگ و روان؛ سهولت و استعداد."},
    {"key": "sqr", "name": "تربیع", "base": 90, "orb": 6, "glyph": "□",
     "meaning": "اصطکاکِ سازنده؛ چالشی که رشد می‌آورد."},
    {"key": "sxt", "name": "شش‌گانه", "base": 60, "orb": 4, "glyph": "⚹",
     "meaning": "فرصتی ملایم؛ همکاری و گشایش."},
]

# Weekly reflective prompts — rotate by ISO week number (no prediction, self-knowledge).
_REFLECTIONS = [
    "این هفته کدام بخش از زندگی‌ات را کمتر دیده‌ای و می‌خواهی بیشتر به آن توجه کنی؟",
    "چه الگویی در رفتار خودت را می‌خواهی با دقت بیشتری بشناسی؟",
    "در چه موقعیتی می‌توانی با صبر بیشتری واکنش نشان بدهی؟",
    "کدام رابطه یا ارزش برایت این روزها مهم‌تر شده است؟",
    "چه چیزی را می‌توانی ببخشی و سبک‌تر ادامه بدهی؟",
    "کجا می‌توانی شکرگزارتر باشی؟",
    "چه تصمیمی را مدام عقب انداخته‌ای و چرا؟",
    "در کدام رابطه به تعادل بیشتری نیاز داری؟",
]

_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
           "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def _shamsi_today() -> str:
    j = jdatetime.datetime.fromgregorian(datetime=datetime.now())
    return f"{j.day} {_MONTHS[j.month - 1]} {j.year}"


def _shamsi_from_jd(jd: float) -> str:
    # read the date in Tehran local time (UTC+3:30)
    y, m, d, _ = swe.revjul(jd + 3.5 / 24.0)
    j = jdatetime.date.fromgregorian(year=int(y), month=int(m), day=int(d))
    return f"{j.day} {_MONTHS[j.month - 1]} {j.year}"


def _moon_phase(jd: float) -> str:
    moon = _lon(swe.MOON, jd)
    sun = _lon(swe.SUN, jd)
    deg = swe.degnorm(moon - sun)
    if 180 - 8 <= deg <= 180 + 8:
        return "Full"
    if deg <= 8 or deg >= 352:
        return "New"
    return "Waxing" if deg < 180 else "Waning"


def _moon_elong(jd: float) -> float:
    return swe.degnorm(_lon(swe.MOON, jd) - _lon(swe.SUN, jd))


def _aspect_of(d: float) -> dict | None:
    """Return the tightest matching aspect {name, glyph, meaning, orb}."""
    best = None
    for a in _ASPECTS:
        diff = abs(d - a["base"])
        if diff <= a["orb"] and (best is None or diff < best[0]):
            best = (diff, a)
    if best is None:
        return None
    return {"name": best[1]["name"], "glyph": best[1]["glyph"],
            "meaning": best[1]["meaning"], "orb": round(best[0], 1)}


def _aspects_today(jd: float) -> list[dict]:
    """Real pairwise aspects among the 10 planets at this instant, tightest first."""
    bodies = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS,
              swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
    lons = {b: _lon(b, jd) for b in bodies}
    out: list[dict] = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            a, b = bodies[i], bodies[j]
            asp = _aspect_of(_angular_diff(lons[a], lons[b]))
            if not asp:
                continue
            a_name, b_name = PLANET_NAMES[a], PLANET_NAMES[b]
            out.append({
                "a_fa": _PLANET_FA[a_name], "b_fa": _PLANET_FA[b_name],
                "a_glyph": _PLANET_GLYPH[a_name], "b_glyph": _PLANET_GLYPH[b_name],
                "name": asp["name"], "glyph": asp["glyph"],
                "meaning": asp["meaning"], "orb": asp["orb"],
            })
    out.sort(key=lambda x: x["orb"])
    return out[:8]


def _next_moon_events(jd_now: float) -> list[dict]:
    """Next new moon and next full moon (deterministic 6h scan over 32 days)."""
    new_jd: float | None = None
    new_d = 1e9
    full_jd: float | None = None
    full_d = 1e9
    for h in range(6, 32 * 24 + 1, 6):
        jd = jd_now + h / 24.0
        e = _moon_elong(jd)
        d_new = min(e, 360 - e)
        d_full = abs(e - 180)
        if d_new < new_d:
            new_d, new_jd = d_new, jd
        if d_full < full_d:
            full_d, full_jd = d_full, jd
    raw: list[tuple[str, float]] = []
    if new_jd is not None:
        raw.append(("ماه نو", new_jd))
    if full_jd is not None:
        raw.append(("ماه کامل", full_jd))
    raw.sort(key=lambda r: r[1])
    events = []
    for label, jd in raw:
        sign_idx = int(_lon(swe.MOON, jd) // 30) % 12
        events.append({"label": label, "date_fa": _shamsi_from_jd(jd),
                       "sign_fa": SIGNS_FA[sign_idx]})
    return events


def weekly_reflection_prompt(when: datetime | None = None) -> str:
    now = when or datetime.now()
    return _REFLECTIONS[now.isocalendar()[1] % len(_REFLECTIONS)]


def sky_today(when: datetime | None = None) -> dict:
    """Current planetary positions + moon phase (public, no birth data)."""
    now = when or datetime.now(timezone.utc)
    jd = swe.julday(now.year, now.month, now.day,
                    now.hour + now.minute / 60 + now.second / 3600)

    planets = []
    retrogrades = []
    for body, pname in PLANET_NAMES.items():
        if pname not in _PLANET_FA:
            continue
        lon = _lon(body, jd)
        speed = swe.calc_ut(jd, body)[0][3]
        sign_idx = int(lon // 30) % 12
        sign_bare = _SIGN_BARE[sign_idx]
        fa = _PLANET_FA[pname]
        entry = {
            "name_fa": fa,
            "glyph": _PLANET_GLYPH[pname],
            "sign_fa": SIGNS_FA[sign_idx],
            "retro": speed < 0,
            "degree": round(lon - sign_idx * 30, 1),
            "element_fa": _ELEMENT[sign_bare],
            "modality_fa": _MODALITY[sign_bare],
            "theme": _PLANET_THEME[fa],
        }
        planets.append(entry)
        if speed < 0:
            retrogrades.append({
                "name_fa": fa,
                "glyph": _PLANET_GLYPH[pname],
                "sign_fa": SIGNS_FA[sign_idx],
                "review": _PLANET_RETRO_REVIEW.get(fa, "مرور و بازبینی"),
            })

    moon_lon = _lon(swe.MOON, jd)
    moon_sign_idx = int(moon_lon // 30) % 12
    phase_key = _moon_phase(jd)
    elong = _moon_elong(jd)
    illum = round((1 - math.cos(math.radians(elong))) / 2 * 100)

    return {
        "date_fa": _shamsi_today(),
        "moon_phase": _MOON_PHASE_FA[phase_key],
        "moon_phase_meaning": _MOON_PHASE_MEANING[phase_key],
        "moon_illumination": illum,
        "moon_sign_fa": SIGNS_FA[moon_sign_idx],
        "moon_degree": round(moon_lon - moon_sign_idx * 30, 1),
        "moon_events": _next_moon_events(jd),
        "planets": planets,
        "retrogrades": retrogrades,
        "aspects": _aspects_today(jd),
        "reflection": weekly_reflection_prompt(now),
    }
