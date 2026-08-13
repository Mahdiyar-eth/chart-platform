"""«آسمان امروز» — public today's-sky page (audit G-3).

Deterministic (pyswisseph) current planetary positions + moon phase + a weekly
reflective exercise. No LLM, no cost, no prediction — reflective self-knowledge.
"""
from __future__ import annotations

from datetime import datetime, timezone

import jdatetime
import swisseph as swe

from app.astrology.transits import SIGNS_FA, PLANET_NAMES, _lon

swe.set_ephe_path("ephe")
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


def _shamsi_today() -> str:
    j = jdatetime.datetime.fromgregorian(datetime=datetime.now())
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{j.day} {months[j.month - 1]} {j.year}"


def _moon_phase(jd: float) -> str:
    moon = _lon(swe.MOON, jd)
    sun = _lon(swe.SUN, jd)
    deg = swe.degnorm(moon - sun)
    if 180 - 8 <= deg <= 180 + 8:
        return "Full"
    if deg <= 8 or deg >= 352:
        return "New"
    return "Waxing" if deg < 180 else "Waning"


def weekly_reflection_prompt(when: datetime | None = None) -> str:
    now = when or datetime.now()
    return _REFLECTIONS[now.isocalendar()[1] % len(_REFLECTIONS)]


def sky_today(when: datetime | None = None) -> dict:
    """Current planetary positions + moon phase (public, no birth data)."""
    now = when or datetime.now(timezone.utc)
    jd = swe.julday(now.year, now.month, now.day,
                    now.hour + now.minute / 60 + now.second / 3600)

    planets = []
    for body, pname in PLANET_NAMES.items():
        if pname not in _PLANET_FA:
            continue
        lon = _lon(body, jd)
        speed = swe.calc_ut(jd, body)[0][3]
        planets.append({
            "name_fa": _PLANET_FA[pname],
            "glyph": _PLANET_GLYPH[pname],
            "sign_fa": SIGNS_FA[int(lon // 30) % 12],
            "retro": speed < 0,
        })

    return {
        "date_fa": _shamsi_today(),
        "moon_phase": _MOON_PHASE_FA[_moon_phase(jd)],
        "planets": planets,
        "reflection": weekly_reflection_prompt(now),
    }
