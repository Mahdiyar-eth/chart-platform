"""Big Three + interpretation keys — deterministic data only (LLM writes text later).

Each interpretation key maps to structured data the prompt builder will use.
This module contains NO LLM calls. Signs are 0-indexed (Aries=0 … Pisces=11).
"""
from __future__ import annotations

SIGNS_FA = ["حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله", "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت"]
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# Identity color per sign (plan v3.1 palette)
SIGN_COLORS = {
    "Aries": "#E4572E", "Taurus": "#C9A227", "Gemini": "#D4B84C", "Cancer": "#B76E79",
    "Leo": "#D4A017", "Virgo": "#7C9E5A", "Libra": "#5A8F7B", "Scorpio": "#6A5ACD",
    "Sagittarius": "#8B5CF6", "Capricorn": "#3B4A6B", "Aquarius": "#4A7BA6", "Pisces": "#2A9D8F",
}

# Element / modality (deterministic)
ELEMENTS = {
    "Aries": "آتش", "Leo": "آتش", "Sagittarius": "آتش",
    "Taurus": "خاک", "Virgo": "خاک", "Capricorn": "خاک",
    "Gemini": "هوا", "Libra": "هوا", "Aquarius": "هوا",
    "Cancer": "آب", "Scorpio": "آب", "Pisces": "آب",
}
MODALITIES = {
    "Aries": "کاردینال", "Cancer": "کاردینال", "Libra": "کاردینال", "Capricorn": "کاردینال",
    "Taurus": "ثابت", "Leo": "ثابت", "Scorpio": "ثابت", "Aquarius": "ثابت",
    "Gemini": "تغییرپذیر", "Virgo": "تغییرپذیر", "Sagittarius": "تغییرپذیر", "Pisces": "تغییرپذیر",
}

# Short interpretation seed per sign (used for the free Big Three box).
# Full report text comes from the LLM pipeline with Evidence — these are UI-level labels.
SIGN_KEYS = {
    "Aries": {"tone": "پیشگام و شجاع", "challenge": "شتابزدگی و بیصبری", "gift": "شروعکنندگی"},
    "Taurus": {"tone": "پایدار و حسی", "challenge": "لجاجت در تغییر", "gift": "ثبات و امنیت"},
    "Gemini": {"tone": "کنجکاو و ارتباطی", "challenge": "پراکندگی ذهنی", "gift": "انعطاف ذهنی"},
    "Cancer": {"tone": "مهربان و شهودی", "challenge": "حساسیت بیشازحد", "gift": "همدلی عمیق"},
    "Leo": {"tone": "درخشان و خلاق", "challenge": "نیاز به تأیید", "gift": "گرما و سخاوت"},
    "Virgo": {"tone": "دقیق و تحلیلگر", "challenge": "کمالگرایی سختگیر", "gift": "ساماندهی"},
    "Libra": {"tone": "متعادل و اجتماعی", "challenge": "مردد بودن", "gift": "دیپلماسی"},
    "Scorpio": {"tone": "عمیق و پرشور", "challenge": "کنترلگری", "gift": "بازسازی و تحول"},
    "Sagittarius": {"tone": "آزادیخواه و خوشبین", "challenge": "بیتعهدی", "gift": "چشمانداز وسیع"},
    "Capricorn": {"tone": "مسئول و استراتژیک", "challenge": "جدی بودن بیشازحد", "gift": "ساختن پایدار"},
    "Aquarius": {"tone": "نوآور و مستقل", "challenge": "فاصلهی عاطفی", "gift": "دید آیندهنگر"},
    "Pisces": {"tone": "رویاپرداز و شفقتورز", "challenge": "مرزهای محو", "gift": "شهود و تخیل"},
}


def sign_of_longitude(lon: float) -> str:
    return SIGNS_EN[int(lon // 30) % 12]


def big_three(chart_json: dict) -> dict:
    """Return Big Three (Sun/Moon/ASC sign + keys) from canonical chart JSON.
    When birth time is unknown, ASC is omitted (audit P0)."""
    planets = chart_json.get("planets") or {}
    if "Sun" not in planets or "Moon" not in planets:
        return {}
    sun_sign = sign_of_longitude(planets["Sun"]["longitude"])
    moon_sign = sign_of_longitude(planets["Moon"]["longitude"])
    out = {}
    for key, sign in (("Sun", sun_sign), ("Moon", moon_sign)):
        out[key] = {
            "sign_en": sign,
            "sign_fa": SIGNS_FA[["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"].index(sign)],
            "element": ELEMENTS[sign],
            "modality": MODALITIES[sign],
            "color": SIGN_COLORS[sign],
            **SIGN_KEYS[sign],
        }
    angles = chart_json.get("angles") or {}
    if "ASC" in angles:
        asc_sign = sign_of_longitude(angles["ASC"]["longitude"])
        out["ASC"] = {
            "sign_en": asc_sign,
            "sign_fa": SIGNS_FA[["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"].index(asc_sign)],
            "element": ELEMENTS[asc_sign],
            "modality": MODALITIES[asc_sign],
            "color": SIGN_COLORS[asc_sign],
            **SIGN_KEYS[asc_sign],
        }
    return out
