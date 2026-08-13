FILE: app/__init__.py  (1 lines)
======================================================================


FILE: app/astrology/__init__.py  (1 lines)
======================================================================


FILE: app/astrology/big_three.py  (81 lines)
======================================================================
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
    planets = chart_json["planets"]
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


FILE: app/astrology/cities_ir.py  (72 lines)
======================================================================
"""Iran cities dataset — Persian names + coordinates (31 provinces, ~700 cities).
Source: github.com/pesarkhobeee/iran-states-and-cities-json-and-sql-including-area-coordinations
(MIT). Loaded at seed time into the cities_ir table (plan v3.1 §7).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "cities_seed.json"


def load_cities() -> list[dict]:
    """Return [{province_fa, city_fa, lat, lon}, ...] from the merged seed."""
    raw = json.loads(DATA_PATH.read_text())
    out = []
    for c in raw:
        name = c.get("city_fa", "").strip()
        if not name:
            continue
        out.append({
            "province_fa": c.get("province_fa", "").strip(),
            "city_fa": name,
            "lat": float(c["lat"]),
            "lon": float(c["lon"]),
        })
    return out


def ensure_data_file() -> None:
    """Copy the dataset into the repo if missing (self-contained deploy)."""
    if DATA_PATH.exists():
        return
    src = Path("/root/chart-platform/app/astrology/data/cities_seed.json")
    if src.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(src, DATA_PATH)


_CITIES_CACHE: list[dict] | None = None


def all_cities() -> list[dict]:
    global _CITIES_CACHE
    if _CITIES_CACHE is None:
        _CITIES_CACHE = load_cities()
    return _CITIES_CACHE


def search_cities(q: str, limit: int = 10) -> list[dict]:
    """Search by Persian city/province name (substring). Empty q → popular cities first."""
    q = (q or "").strip()
    cities = all_cities()
    if not q:
        popular = ["تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "کرج", "قم", "اهواز", "کرمانشاه", "رشت"]
        out = [c for c in cities if c["city_fa"] in popular]
        return out[:limit]
    # normalize Arabic yeh → Persian yeh for matching
    nq = q.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")
    out = [c for c in cities
           if nq in c["city_fa"].replace("\u064a", "\u06cc") or nq in c["province_fa"]]
    return out[:limit]


if __name__ == "__main__":
    ensure_data_file()
    cities = load_cities()
    print(f"cities loaded: {len(cities)}")
    teh = [c for c in cities if c["city_fa"] == "تهران"]
    print("Tehran entries:", teh[:2])


FILE: app/astrology/engine.py  (284 lines)
======================================================================
"""
Astrology engine — deterministic chart computation.

Rule (plan v3.1): LLM NEVER calculates. This module is the ONLY source of
planetary positions, houses, aspects. Output is canonical Chart JSON.

Timezone handling: zoneinfo (IANA tzdata, Asia/Tehran) — covers Iran's full
DST history (1978-1980, 1991-2005, 2008-2022) and the 1977-79 +4:00 base
change automatically. NO manual DST tables.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
import swisseph as swe

EPHE_PATH = "/root/chart-platform/ephe"
DEFAULT_CONFIG = {
    "house_system": "P",
    "zodiac": "tropical",
    "ayanamsa": None,
    "orb_rules": {"conjunction": 8.0, "sextile": 6.0, "square": 7.0,
                  "trine": 8.0, "opposition": 8.0},
    "node_type": "mean",       # MEAN_NODE
    "lilith": "mean",          # MEAN_APOG
    "chiron": True,
    "ephe": "sepl_18/semo_18/seas_18/sena_18",
    "swisseph_version": swe.version,
}

SIGNS_FA = ["حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله",
            "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت"]
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ASPECT_NAMES = {0: "conjunction", 60: "sextile", 90: "square", 120: "trine", 180: "opposition"}
ASPECT_FA = {0: "همنشینی", 60: "شش‌ضلعی", 90: "تربیع", 120: "سه‌ضلعی", 180: "مقابله"}

PLANET_DEFS = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY), ("Venus", swe.VENUS),
    ("Mars", swe.MARS), ("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN),
    ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE), ("Pluto", swe.PLUTO),
    ("Node", swe.MEAN_NODE), ("Lilith", swe.MEAN_APOG), ("Chiron", swe.CHIRON),
]


def ensure_ephe() -> None:
    swe.set_ephe_path(EPHE_PATH)


def jd_from_utc(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600)


def to_utc(local_dt: datetime, tz_name: str = "Asia/Tehran") -> datetime:
    """Local wall-clock → UTC using IANA tz (handles Iran DST history)."""
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(ZoneInfo("UTC"))


def gregorian_from_jalali(jy: int, jm: int, jd: int) -> datetime.date:
    return jdatetime.date(jy, jm, jd).togregorian()


def sign_of(lon: float) -> int:
    return int(swe.degnorm(lon) // 30)


def degree_in_sign(lon: float) -> tuple[int, float]:
    lon = swe.degnorm(lon)
    s = int(lon // 30)
    return s, lon - s * 30


def fmt_lon(lon: float, retro: bool = False) -> str:
    s, d = degree_in_sign(lon)
    deg = int(d)
    mi = int(round((d - deg) * 60))
    return f"{SIGNS_EN[s]} {deg}°{mi:02d}'{' R' if retro else ''}"


def _retro(speed: float) -> bool:
    return speed < 0


@dataclass
class BirthData:
    """Raw user input. date can be Gregorian (y,m,d) or Jalali (jy,jm,jd)."""
    lat: float
    lon: float
    year: int
    month: int
    day: int
    hour: int = 12
    minute: int = 0
    time_known: bool = True
    jalali: bool = False
    tz_name: str = "Asia/Tehran"

    def local_dt(self) -> datetime:
        if self.jalali:
            g = gregorian_from_jalali(self.year, self.month, self.day)
            return datetime(g.year, g.month, g.day, self.hour, self.minute)
        return datetime(self.year, self.month, self.day, self.hour, self.minute)


@dataclass
class ChartResult:
    chart_json: dict = field(default_factory=dict)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.chart_json, ensure_ascii=False, indent=indent)


def compute_chart(birth: BirthData, config: dict | None = None) -> ChartResult:
    """Compute full natal chart → canonical Chart JSON (deterministic)."""
    ensure_ephe()
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if cfg["zodiac"] == "sidereal":
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

    local = birth.local_dt()
    utc = to_utc(local, birth.tz_name)
    jd = jd_from_utc(utc)
    is_sidereal = cfg["zodiac"] == "sidereal"
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if is_sidereal else 0)

    planets = {}
    for name, pid in PLANET_DEFS:
        pos, _ = swe.calc_ut(jd, pid, flags)
        lon, speed = pos[0], pos[3]
        s, d = degree_in_sign(lon)
        planets[name] = {
            "longitude": round(lon, 6),
            "sign_index": s,
            "sign_en": SIGNS_EN[s],
            "sign_fa": SIGNS_FA[s],
            "degree": round(d, 6),
            "retrograde": _retro(speed),
            "speed": round(speed, 6),
        }

    # houses + angles (Placidus default; P = Placidus, W = Whole Sign, K = Koch...)
    # audit P0: when birth time is unknown, ASC/MC/houses are NOT reliable —
    # noon-based cusps would mislead users, so they are omitted entirely.
    cusps: list = []
    if birth.time_known:
        cusps, ascmc = swe.houses(jd, birth.lat, birth.lon, cfg["house_system"].encode())
        if is_sidereal:
            ayan = swe.get_ayanamsa_ut(jd)
            cusps = [(c - ayan) % 360 for c in cusps]
            ascmc = [(a - ayan) % 360 for a in ascmc]
        angles = {
            "ASC": {"longitude": round(ascmc[0], 6)},
            "MC": {"longitude": round(ascmc[1], 6)},
            "Vx": {"longitude": round(ascmc[3], 6)},
        }
        houses = {f"h{i+1}": round(cusps[i], 6) for i in range(12)}
        # house placement for planets + angles
        for name, p in planets.items():
            p["house"] = _house_of(p["longitude"], cusps)
        angles["ASC"]["house"] = 1
        angles["MC"]["house"] = 10
        # Part of Fortune (day formula; needs ASC)
        sun_lon = planets["Sun"]["longitude"]
        moon_lon = planets["Moon"]["longitude"]
        fortune = swe.degnorm(ascmc[0] + moon_lon - sun_lon)
    else:
        angles, houses = {}, {}
        for name, p in planets.items():
            p["house"] = None
        fortune = None
    sun_lon = planets["Sun"]["longitude"]
    moon_lon = planets["Moon"]["longitude"]
    if fortune is not None:
        planets["Fortune"] = {
            "longitude": round(fortune, 6), "sign_index": sign_of(fortune),
            "sign_en": SIGNS_EN[sign_of(fortune)], "sign_fa": SIGNS_FA[sign_of(fortune)],
            "degree": round(degree_in_sign(fortune)[1], 6), "retrograde": False,
            "speed": 0.0, "house": _house_of(fortune, cusps) if birth.time_known else None,
        }

    # aspects (major, orb rules from config)
    aspects = []
    all_points = {**planets, **angles}
    names = list(all_points.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            d = abs(all_points[a]["longitude"] - all_points[b]["longitude"])
            d = min(swe.degnorm(d), 360 - swe.degnorm(d))
            for ang, aname in ASPECT_NAMES.items():
                orb = cfg["orb_rules"][aname]
                if abs(d - ang) <= orb:
                    aspects.append({
                        "p1": a, "p2": b, "aspect": aname, "aspect_fa": ASPECT_FA[ang],
                        "angle": ang, "orb": round(abs(d - ang), 4), "exact_angle": round(d, 4),
                    })
                    break

    # elements & modalities
    counts = {"Fire": 0, "Earth": 0, "Air": 0, "Water": 0}
    modalities = {"Cardinal": 0, "Fixed": 0, "Mutable": 0}
    for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                 "Uranus", "Neptune", "Pluto"):
        s = planets[name]["sign_index"]
        counts[["Fire", "Earth", "Air", "Water"][s % 4]] += 1
        modalities[["Cardinal", "Fixed", "Mutable"][s % 3]] += 1

    # moon phase
    moon_phase = swe.degnorm(moon_lon - sun_lon)
    phase = "Full" if 180 - 8 <= moon_phase <= 180 + 8 else (
        "New" if moon_phase <= 8 or moon_phase >= 352 else "Waxing" if moon_phase < 180 else "Waning")

    chart = {
        "engine_config": cfg,
        "birth": {
            "local_time": local.strftime("%Y-%m-%d %H:%M"),
            "tz_name": birth.tz_name,
            "utc_time": utc.strftime("%Y-%m-%d %H:%M:%S"),
            "julian_day_ut": round(jd, 6),
            "lat": birth.lat, "lon": birth.lon,
            "time_known": birth.time_known,
        },
        "planets": planets,
        "angles": angles,
        "houses": houses,
        "aspects": aspects,
        "elements": counts,
        "modalities": modalities,
        "moon_phase": phase,
        "moon_phase_deg": round(moon_phase, 4),
    }
    return ChartResult(chart)


def _house_of(lon: float, cusps) -> int:
    """Placidus house index (1-12) for a longitude."""
    lon = swe.degnorm(lon)
    # cusps array: h1..h12 in zodiacal order (asc at cusp1)
    for i in range(12):
        c1, c2 = cusps[i], cusps[(i + 1) % 12]
        if _between(lon, c1, c2):
            return i + 1
    return 12


def _between(lon: float, c1: float, c2: float) -> bool:
    if c2 > c1:
        return c1 <= lon < c2
    return lon >= c1 or lon < c2  # wrap-around (c2 < c1)


# convenience: compute from raw fields
def validate_birth_fields(year: int, month: int, day: int) -> tuple[bool, str]:
    """Basic sanity check for birth date parts."""
    try:
        if not (1900 <= year <= 2026):
            return False, "سال تولد باید بین ۱۹۰۰ و ۲۰۲۶ باشد"
        if not (1 <= month <= 12):
            return False, "ماه نامعتبر است"
        import calendar
        maxd = calendar.monthrange(year, month)[1]
        if not (1 <= day <= maxd):
            return False, f"روز نامعتبر است (این ماه {maxd} روز دارد)"
        return True, ""
    except Exception:
        return False, "تاریخ نامعتبر است"


def compute_from_fields(lat: float, lon: float, year: int, month: int, day: int,
                        hour: int = 12, minute: int = 0, time_known: bool = True,
                        jalali: bool = False, tz_name: str = "Asia/Tehran",
                        zodiac: str = "tropical") -> ChartResult:
    return compute_chart(BirthData(lat=lat, lon=lon, year=year, month=month, day=day,
                                   hour=hour, minute=minute, time_known=time_known,
                                   jalali=jalali, tz_name=tz_name),
                         config={"zodiac": zodiac})


FILE: app/astrology/golden_data.py  (101 lines)
======================================================================
"""
Golden charts — reference charts with expected positions + engine config snapshot.
Every engine/prompt/renderer change must pass ALL golden charts (plan v3.1 §5.4).

Chart 1 = MaHDi's verified chart (expert agreement within 1 arc-minute,
cross-checked against manual DST-offset computation 2026-08-12).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

GOLDEN_CHARTS = [
    {
        "id": "chart-1-mahdi",
        "name": "چارت مرجع — مهدی (تطبیق با متخصص، تلرانس ۱ دقیقه قوس)",
        "birth": {
            "lat": 35.6892, "lon": 51.3890,
            "year": 1994, "month": 8, "day": 23, "hour": 6, "minute": 10,
            "time_known": True, "jalali": False, "tz_name": "Asia/Tehran",
        },
        "engine_config": {
            "house_system": "P", "zodiac": "tropical", "ayanamsa": None,
            "orb_rules": {"conjunction": 8.0, "sextile": 6.0, "square": 7.0,
                          "trine": 8.0, "opposition": 8.0},
            "node_type": "mean", "lilith": "mean", "chiron": True,
        },
        "expected": {  # degrees — tolerance 1 arc-minute (0.0167°)
            "Sun": 149.717, "Moon": 351.0, "ASC": 144.933, "MC": 49.967,
            "asc_deg": 24.933, "mc_deg": 19.967,
            "sun_sign": 4, "moon_sign": 11,
            "sun_house": 1, "moon_house": 8,
            "moon_phase": "Waning",
            "moon_phase_deg": 201.3,
            "saturn_retrograde": True, "saturn_house": 7,
        },
        "verify_utc": "1994-08-23 01:40:00",  # 06:10 +4:30 DST → UTC
    },
    {
        "id": "chart-2-no-time",
        "name": "بدون ساعت تولد (ساعت نامعلوم)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1994, "month": 8, "day": 23,
                  "hour": 12, "minute": 0, "time_known": False, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"sun_sign": 4, "sun_deg_min": 29.0, "sun_deg_max": 30.0},
    },
    {
        "id": "chart-3-no-dst-1400s",
        "name": "بعد از لغو DST (تولد ۱۴۰۲ — همیشه +3:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 2023, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "2023-08-23 02:40:00"},
    },
    {
        "id": "chart-4-pre-1977",
        "name": "قبل از آزمایش +4:00 (تولد ۱۳۵۵ — پایه +3:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1976, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "1976-08-23 02:40:00"},  # +3:30 base (pre-1977)
    },
    {
        "id": "chart-5-dst-era1",
        "name": "DST دوره اول (تولد ۱۳۵۸ تابستان — +4:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1979, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "1979-08-23 01:40:00"},  # DST May27-Sep19 1979
    },
    {
        "id": "chart-6-foreign-city",
        "name": "شهر خارجی (استانبول — UTC+3)",
        "birth": {"lat": 41.0082, "lon": 28.9784, "year": 1994, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Europe/Istanbul"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-08-23 03:10:00"},
    },
    {
        "id": "chart-7-leap-jalali",
        "name": "سال کبیسه شمسی (تولد ۱ اسفند ۱۳۹۹ — تبدیل جلالی)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1399, "month": 12, "day": 1,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": True,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "2021-02-19 02:40:00"},
    },
    {
        "id": "chart-8-house-boundary",
        "name": "مرز خانه (سیاره روی کاسپ) + رتروگرید",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 2020, "month": 5, "day": 15,
                  "hour": 14, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"has_retrograde": True},  # at least one retrograde planet
    },
]


FILE: app/astrology/rectify.py  (100 lines)
======================================================================
"""Birth Time Finder (plan §9.4) — deterministic rectification from life events.

Scans candidate birth times (20-min steps) and scores each against life events
using transit + house rulership evidence. Pure pyswisseph — no LLM.
"""
from dataclasses import dataclass, field

from app.astrology.engine import compute_from_fields, jd_from_utc, to_utc

# event category → what we look for
_EVENT_RULES: dict[str, list[str]] = {
    "marriage": ["Venus", "Jupiter", "Moon"],
    "child": ["Jupiter", "Moon"],
    "job_change": ["Saturn", "MC", "Sun"],
    "relocation": ["ASC", "Moon", "4"],
    "illness": ["Saturn", "Mars", "Moon"],
    "windfall": ["Jupiter", "Venus"],
    "fame": ["Sun", "MC", "Jupiter"],
    "loss": ["Saturn", "Pluto", "Moon"],
}

_TRANSIT_BODIES = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
_ASPECTS = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}
_ASPECT_WEIGHT = {"Conjunction": 3, "Opposition": 2, "Trine": 2, "Square": 2, "Sextile": 1}
_ORB = 2.5


def _transit_events(jd_event: float, planets_natal: dict, planets_event: dict) -> list[dict]:
    out = []
    for tb in _TRANSIT_BODIES:
        lon_t = planets_event[tb]["longitude"]
        for nat_name in ("Sun", "Moon", "ASC", "MC"):
            if nat_name not in planets_natal:
                continue
            lon_n = planets_natal[nat_name]["longitude"]
            diff = abs(lon_t - lon_n) % 360
            diff = min(diff, 360 - diff)
            for asp, ang in _ASPECTS.items():
                if abs(diff - ang) <= _ORB:
                    out.append({"transit": tb, "natal": nat_name, "aspect": asp,
                                "orb": round(abs(diff - ang), 2)})
    return out


@dataclass
class RectifyResult:
    best_time: str
    score: float
    chart_json: dict
    candidates: list = field(default_factory=list)
    events_used: int = 0
    details: list = field(default_factory=list)


def rectify_birth_time(lat: float, lon: float, year: int, month: int, day: int,
                       events: list[tuple[str, int, int, int]],  # (category, y, m, d)
                       tz_name: str = "Asia/Tehran", jalali: bool = False) -> RectifyResult:
    """Score every 20-min candidate; return best + top-3 details."""
    import swisseph as swe

    _BODY_IDS = {"Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Uranus": swe.URANUS,
                 "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO}
    best: dict | None = None
    candidates = []
    for minute in range(0, 24 * 60, 20):
        h, m = divmod(minute, 60)
        chart = compute_from_fields(lat, lon, year, month, day, h, m, True, jalali, tz_name)
        planets = chart.chart_json["planets"]
        natal_points = {**planets}
        if chart.chart_json.get("angles"):
            natal_points["ASC"] = {"longitude": chart.chart_json["angles"]["ASC"]["longitude"]}
            natal_points["MC"] = {"longitude": chart.chart_json["angles"]["MC"]["longitude"]}
        score = 0.0
        hits = []
        for cat, ey, em, ed in events:
            local = __import__("datetime").datetime(ey, em, ed, 12, 0)
            jd_e = jd_from_utc(to_utc(local, tz_name))
            # transit positions at event date (tropical)
            ev_planets = {}
            for name, pid in _BODY_IDS.items():
                pos, _ = swe.calc_ut(jd_e, pid, swe.FLG_SWIEPH)
                ev_planets[name] = {"longitude": pos[0]}
            evs = _transit_events(jd_e, natal_points, ev_planets)
            for e in evs:
                w = _ASPECT_WEIGHT[e["aspect"]]
                score += w * (1 - e["orb"] / _ORB)
                hits.append({"event": cat, **e})
        candidates.append({"time": f"{h:02d}:{m:02d}", "score": round(score, 2), "hits": len(hits)})
        if best is None or score > best["score"]:
            best = {"time": f"{h:02d}:{m:02d}", "score": score, "chart_json": chart.chart_json,
                    "details": hits}

    assert best is not None
    candidates.sort(key=lambda c: -c["score"])
    return RectifyResult(
        best_time=best["time"], score=round(best["score"], 2),
        chart_json=best["chart_json"], candidates=candidates[:3],
        events_used=len(events), details=best["details"][:8],
    )


FILE: app/astrology/svg_wheel.py  (154 lines)
======================================================================
"""
Chart wheel SVG renderer — deterministic, no external deps.

Layout (polar):
  - outer zodiac ring (12 signs, Persian labels)
  - house ring (Placidus cusps, numbered 1-12)
  - planet ring with glyphs + Persian names
  - ASC/MC markers
Returns a standalone <svg> string (RTL-friendly, uses current font stack).
"""
from __future__ import annotations

import math

from app.astrology.engine import SIGNS_FA, SIGNS_EN  # noqa: F401

SIGN_GLYPH = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
PLANET_GLYPH = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Node": "☊", "Lilith": "⚸", "Chiron": "⚷", "Fortune": "⊗", "ASC": "АС", "MC": "MC",
}
PLANET_FA = {
    "Sun": "خورشید", "Moon": "ماه", "Mercury": "عطارد", "Venus": "زهره", "Mars": "مریخ",
    "Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس", "Neptune": "نپتون",
    "Pluto": "پلوتو", "Node": "گره شمالی", "Lilith": "لیلیت", "Chiron": "کایرون",
    "Fortune": "بخت", "ASC": "طالع", "MC": "میلادی وسط",
}
# 12 zodiac colors (identity palette from plan v3.1)
SIGN_COLORS = [
    "#E4572E", "#C9A227", "#D4B84C", "#B76E79", "#D4A017", "#7C9E5A",
    "#5A8F7B", "#6A5ACD", "#8B5CF6", "#3B4A6B", "#4A7BA6", "#2A9D8F",
]

RAD = math.pi / 180.0


def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = (deg - 90) * RAD  # 0° at top, clockwise
    return cx + r * math.cos(a), cy + r * math.sin(a)


def render_chart_svg(chart: dict, size: int = 800) -> str:
    cx = cy = size / 2
    R = size / 2 - 8
    r_outer, r_sign, r_house, r_planet, r_inner = R, R * 0.84, R * 0.72, R * 0.55, R * 0.30

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
             f'width="100%" height="100%" font-family="Vazirmatn, Tahoma, sans-serif">']
    parts.append(f'<rect width="{size}" height="{size}" fill="#0b1026" rx="24"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="#2a3566" stroke-width="2"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="#10173a" stroke="#2a3566" stroke-width="1.5"/>')

    houses = chart.get("houses", {})
    cusps = [houses[f"h{i+1}"] for i in range(12)] if houses else []
    angles = chart.get("angles", {})
    planets = chart.get("planets", {})

    # ── zodiac segments (12 × 30°) ──
    for i in range(12):
        a0, a1 = i * 30, (i + 1) * 30
        x0, y0 = _polar(cx, cy, r_outer, a0)
        x1, y1 = _polar(cx, cy, r_outer, a1)
        x2, y2 = _polar(cx, cy, r_sign, a1)
        x3, y3 = _polar(cx, cy, r_sign, a0)
        col = SIGN_COLORS[i]
        parts.append(f'<path d="M{x0:.1f},{y0:.1f} A{r_outer:.1f},{r_outer:.1f} 0 0 1 {x1:.1f},{y1:.1f} '
                     f'L{x2:.1f},{y2:.1f} A{r_sign:.1f},{r_sign:.1f} 0 0 0 {x3:.1f},{y3:.1f} Z" '
                     f'fill="{col}" fill-opacity="0.10" stroke="{col}" stroke-opacity="0.5" stroke-width="1"/>')
        mx, my = _polar(cx, cy, (r_outer + r_sign) / 2, a0 + 15)
        parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" font-size="{size*0.026:.0f}" '
                     f'fill="{col}" text-anchor="middle" dominant-baseline="middle">{SIGNS_FA[i]}</text>')

    # ── house cusps (lines + numbers) — skipped when birth time unknown ──
    for i in range(len(cusps)):
        c = cusps[i]
        x0, y0 = _polar(cx, cy, r_inner, c)
        x1, y1 = _polar(cx, cy, r_outer, c)
        emph = i in (0, 9)  # ASC / MC lines
        parts.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                     f'stroke="{"#f5c518" if emph else "#3d4c8f"}" stroke-width="{"2" if emph else "1"}"/>')
        nx, ny = _polar(cx, cy, (r_inner + r_planet) / 2, c)
        parts.append(f'<text x="{nx:.1f}" y="{ny:.1f}" font-size="{size*0.02:.0f}" fill="#8fa3d8" '
                     f'text-anchor="middle" dominant-baseline="middle">{i + 1}</text>')

    # ── planets (labels spread to avoid overlap) ──
    items = [(name, p["longitude"]) for name, p in planets.items()
             if name != "Fortune"]
    items.sort(key=lambda t: t[1])
    SPREAD = 5.0   # degrees — planets closer than this share a cluster
    clusters: list[list[tuple[str, float]]] = []
    for it in items:
        if clusters and it[1] - clusters[-1][-1][1] < SPREAD:
            clusters[-1].append(it)
        else:
            clusters.append([it])
    for cluster in clusters:
        n = len(cluster)
        for i, (name, lon) in enumerate(cluster):
            if n == 1:
                glyph_r, label_r, a_off = r_planet, r_planet + size * 0.045, 0.0
            elif n == 2:
                # angular spread ±4.5° + alternating radii (robust even with unshaped text)
                a_off = 4.5 if i == 0 else -4.5
                glyph_r = r_planet
                label_r = (r_planet + size * 0.055) if i == 0 else (r_planet + size * 0.035)
            else:
                # spread members around the cluster center
                center = sum(x[1] for x in cluster) / n
                span = min(16.0, 4.0 * n)
                a_off = (i - (n - 1) / 2) * (span / max(n, 1))
                glyph_r = r_planet - size * 0.015
                label_r = r_planet + size * 0.050
            px, py = _polar(cx, cy, glyph_r, lon)
            glyph = PLANET_GLYPH.get(name, "•")
            col = "#f5c518" if name == "Sun" else "#e8ecff"
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{size*0.014:.0f}" '
                         f'fill="#10173a" stroke="{col}" stroke-width="1"/>')
            parts.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="{size*0.02:.0f}" fill="{col}" '
                         f'text-anchor="middle" dominant-baseline="middle">{glyph}</text>')
            lx, ly = _polar(cx, cy, label_r, lon + a_off)
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="{size*0.016:.0f}" fill="#aab8e0" '
                         f'text-anchor="middle" dominant-baseline="middle">{PLANET_FA.get(name, name)}</text>')

    # ── ASC / MC labels ──
    for key, label in (("ASC", "طالع"), ("MC", "MC")):
        if key in angles:
            lon = angles[key]["longitude"]
            px, py = _polar(cx, cy, r_inner - size * 0.03, lon)
            parts.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="{size*0.022:.0f}" fill="#f5c518" '
                         f'text-anchor="middle" dominant-baseline="middle" font-weight="bold">{label}</text>')

    parts.append("</svg>")
    return "".join(parts)


def save_chart_svg(chart: dict, path: str, size: int = 800) -> str:
    svg = render_chart_svg(chart, size=size)
    with open(path, "w") as f:
        f.write(svg)
    return path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from app.astrology.engine import compute_from_fields
    from app.astrology.golden_data import GOLDEN_CHARTS

    b = GOLDEN_CHARTS[0]["birth"]
    c = compute_from_fields(**b).chart_json
    save_chart_svg(c, "/tmp/chart_wheel.svg")
    print("SVG written → /tmp/chart_wheel.svg")


FILE: app/astrology/svg_widgets.py  (243 lines)
======================================================================
"""SVG widgets (plan §9.3) — aspect grid, element donut, house bar, KPI cards.

All deterministic, dark theme (#0b1026), Vazirmatn font, sized for inline
embedding on the web and in the PDF.
"""
from __future__ import annotations

SIGNS_ELEMENTS = {
    "حمل": "آتش", "اسد": "آتش", "قوس": "آتش",
    "ثور": "خاک", "سنبله": "خاک", "جد ی": "خاک",
    "جوزا": "هوا", "میزان": "هوا", "دلو": "هوا",
    "سرطان": "آب", "عقرب": "آب", "حوت": "آب",
}
ELEMENT_COLORS = {"آتش": "#f5c518", "خاک": "#4caf7d", "هوا": "#5ac8fa", "آب": "#7b6cf6"}
ASPECT_FA = {"Conjunction": "هم پیوند", "Opposition": "تقابل", "Trine": "سه گانه",
             "Square": "تربیع", "Sextile": "شش گانه", "Quincunx": "نیم شش گانه"}


def _svg_open(w: int, h: int) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" font-family="Vazirmatn, Tahoma, sans-serif">']


def _svg_close() -> list[str]:
    return ["</svg>"]


def aspect_grid_svg(planet_positions: dict) -> str:
    """Colored matrix of planet pairs (x = y planet). planets: {name: {"lon": float, "sign_fa": str}}."""
    names = [n for n in planet_positions if n not in ("ASC", "MC", "Part_of_Fortune", "Vertex")]
    if len(names) < 2:
        return ""
    n = len(names)
    cell, pad, header = 34, 0, 46
    w, h = n * cell + 80, n * cell + header + 10
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    p.append(f'<text x="24" y="30" fill="#cfd6ff" font-size="15" font-weight="700">ماتریس جنبه‌ها</text>')
    for i, name in enumerate(names):
        x = 70 + i * cell
        p.append(f'<text x="{x + cell // 2}" y="{header - 14}" fill="#8b96c9" font-size="11" text-anchor="middle">{name}</text>')
        p.append(f'<text x="{x + cell // 2}" y="{h - 8}" fill="#8b96c9" font-size="11" text-anchor="middle">{name}</text>')
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lon_i = planet_positions[names[i]]["longitude"]
            lon_j = planet_positions[names[j]]["longitude"]
            diff = abs(lon_i - lon_j) % 360
            diff = min(diff, 360 - diff)
            color, orb, asp = None, None, None
            for asp, (max_orb, c) in {
                "Conjunction": (8, "#f5c518"), "Opposition": (8, "#ff6b6b"),
                "Trine": (7, "#4caf7d"), "Square": (7, "#ff8a5c"),
                "Sextile": (5, "#5ac8fa"), "Quincunx": (3, "#c792ea"),
            }.items():
                if abs(diff - {"Conjunction": 0, "Opposition": 180, "Trine": 120,
                               "Square": 90, "Sextile": 60, "Quincunx": 150}[asp]) <= max_orb:
                    color, orb = c, round(abs(diff - {"Conjunction": 0, "Opposition": 180,
                                                      "Trine": 120, "Square": 90,
                                                      "Sextile": 60, "Quincunx": 150}[asp]), 1)
                    break
            x, y = 70 + j * cell, header + i * cell
            if color and asp:
                p.append(f'<circle cx="{x + cell // 2}" cy="{y + cell // 2}" r="9" fill="{color}" fill-opacity="0.85">'
                         f'<title>{names[i]} {ASPECT_FA.get(asp, asp)} {names[j]} (orb {orb}°)</title></circle>')
            else:
                p.append(f'<rect x="{x + 6}" y="{y + 6}" width="{cell - 12}" height="{cell - 12}" rx="6" '
                         f'fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.06)"/>')
    p.extend(_svg_close())
    return "".join(p)


def element_donut_svg(sign_counts: dict) -> str:
    """Donut of element distribution. sign_counts: {sign_fa: count}."""
    counts = {"آتش": 0, "خاک": 0, "هوا": 0, "آب": 0}
    for sign, cnt in sign_counts.items():
        el = SIGNS_ELEMENTS.get(sign)
        if el:
            counts[el] += cnt
    total = sum(counts.values()) or 1
    w, h, cx, cy, r = 320, 220, 130, 110, 80
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    p.append(f'<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">تعادل عناصر</text>')
    ang = -90
    for el, col in ELEMENT_COLORS.items():
        frac = counts[el] / total
        a1, a2 = ang, ang + frac * 360
        import math
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        x2, y2 = cx + r * math.cos(math.radians(a2)), cy + r * math.sin(math.radians(a2))
        large = 1 if (a2 - a1) > 180 else 0
        if frac > 0.001:
            p.append(f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" fill-opacity="0.8"/>')
        ang = a2
    p.append(f'<circle cx="{cx}" cy="{cy}" r="46" fill="#0b1026"/>')
    p.append(f'<text x="{cx}" y="{cy - 2}" fill="#fff" font-size="22" font-weight="800" text-anchor="middle">{total}</text>')
    p.append(f'<text x="{cx}" y="{cy + 18}" fill="#8b96c9" font-size="11" text-anchor="middle">سیاره</text>')
    ly = 40
    for el, col in ELEMENT_COLORS.items():
        p.append(f'<circle cx="212" cy="{ly}" r="6" fill="{col}"/>')
        p.append(f'<text x="226" y="{ly + 4}" fill="#cfd6ff" font-size="12">{el} — {counts[el]}</text>')
        ly += 26
    p.extend(_svg_close())
    return "".join(p)


def house_bar_svg(house_counts: dict) -> str:
    """Horizontal bar chart of planet counts per house (1-12).
    When birth time is unknown there are no houses — the widget renders a
    notice instead of fake zeros (audit P0)."""
    w, h = 320, 260
    p = _svg_open(w, h)
    p.append(f'<rect width="{w}" height="{h}" fill="#0b1026" rx="16"/>')
    if not house_counts:
        p.append(f'<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">توزیع خانه‌ها</text>')
        p.append(f'<text x="24" y="80" fill="#8b96c9" font-size="12">ساعت تولد نامعلوم است؛</text>')
        p.append(f'<text x="24" y="100" fill="#8b96c9" font-size="12">خانه‌ها محاسبه نشده‌اند.</text>')
        p.extend(_svg_close())
        return "".join(p)
    p.append(f'<text x="24" y="28" fill="#cfd6ff" font-size="15" font-weight="700">توزیع خانه‌ها</text>')
    maxv = max(house_counts.values()) if house_counts else 1
    for i in range(12):
        n = house_counts.get(i + 1, 0)
        bw = 120 * n / maxv
        y = 48 + i * 16
        p.append(f'<text x="24" y="{y + 10}" fill="#8b96c9" font-size="11">خانه {i + 1}</text>')
        p.append(f'<rect x="90" y="{y}" width="{max(bw, 4)}" height="10" rx="5" fill="#6a5acd" fill-opacity="{0.35 + 0.55 * n / maxv}"/>')
        if n:
            p.append(f'<text x="{98 + bw}" y="{y + 10}" fill="#fff" font-size="11">{n}</text>')
    p.extend(_svg_close())
    return "".join(p)


def kpi_svg(items: list[tuple[str, str]]) -> str:
    """KPI card row for PDF final page. items: [(label_fa, value_fa)] — max 4."""
    n = len(items)
    card_w, gap, h = 150, 12, 86
    w = n * card_w + (n - 1) * gap + 40
    p = _svg_open(w, h + 20)
    for i, (label, value) in enumerate(items[:4]):
        x = 20 + i * (card_w + gap)
        p.append(f'<rect x="{x}" y="12" width="{card_w}" height="{h}" rx="14" fill="#121a3f" '
                 f'stroke="rgba(255,255,255,0.09)"/>')
        p.append(f'<text x="{x + card_w // 2}" y="40" fill="#f5c518" font-size="17" font-weight="800" text-anchor="middle">{value}</text>')
        p.append(f'<text x="{x + card_w // 2}" y="62" fill="#8b96c9" font-size="11" text-anchor="middle">{label}</text>')
    p.extend(_svg_close())
    return "".join(p)


# ────────────────────────────── transit year timeline (plan §9.3 / §10) ──────────────────────────────

_SLOW_FA = {"Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس", "Neptune": "نپتون", "Pluto": "پلوتو"}
_ASPECT_ORBS = {"Conjunction": 5.0, "Opposition": 5.0, "Trine": 5.0, "Square": 4.5, "Sextile": 3.5}


def _natal_targets(chart_json: dict) -> dict:
    """Natal personal points to track: Sun, Moon, Mercury, Venus, Mars, ASC."""
    out: dict[str, float] = {}
    plan = chart_json.get("planets", {})
    for key, fa in (("Sun", "خورشید"), ("Moon", "ماه"), ("Mercury", "عطارد"),
                    ("Venus", "ناهید"), ("Mars", "مریخ")):
        lon = plan.get(key, {}).get("longitude")
        if lon is not None:
            out[key] = float(lon)
    asc = chart_json.get("houses", {}).get("ascendant")
    if asc is not None:
        out["ASC"] = float(asc)
    return out


def transit_timeline_svg(chart_json: dict, months: int = 12) -> str:
    """12-month overview: which slow transits hit the natal chart, month by month.

    Deterministic (pyswisseph), no LLM. Grid: rows = natal points, cols = months.
    A colored cell marks a conjunction/opposition/trine/square/sextile that month.
    """
    from datetime import datetime, timedelta, timezone
    import swisseph as swe

    targets = _natal_targets(chart_json)
    now = datetime.now(timezone.utc)
    rows = [("Sun", "خورشید"), ("Moon", "ماه"), ("Mercury", "عطارد"),
            ("Venus", "ناهید"), ("Mars", "مریخ"), ("ASC", "طالع")]
    rows = [(k, fa) for k, fa in rows if k in targets]

    # month snapshots: transit lon of slow planets at first of each month
    grid: dict[tuple[int, int], tuple[str, float]] = {}  # (row, col) -> (aspect, orb)
    month_labels: list[str] = []
    base = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for col in range(months):
        when = base + timedelta(days=31 * col)
        jd = swe.julday(when.year, when.month, when.day, 0)
        month_labels.append(f"{when.month:02d}/{when.year % 100:02d}")
        for key, swe_id in (("Jupiter", 5), ("Saturn", 6), ("Uranus", 7), ("Neptune", 8), ("Pluto", 10)):
            tlon = swe.calc_ut(jd, swe_id)[0][0]
            for r_idx, (rk, _fa) in enumerate(rows):
                diff = abs(tlon - targets[rk])
                diff = min(diff, 360 - diff)
                for asp, orb in _ASPECT_ORBS.items():
                    base_ang = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}[asp]
                    if abs(diff - base_ang) <= orb:
                        cell = grid.get((r_idx, col))
                        if cell is None or cell[1] > abs(diff - base_ang):
                            grid[(r_idx, col)] = (asp, round(abs(diff - base_ang), 1))
                        break

    # layout
    col_w, row_h, left, top = 46, 26, 92, 30
    h = top + len(rows) * row_h + 26
    w = left + months * col_w + 16
    p = _svg_open(w, h)
    p.append(f'<text x="8" y="20" fill="#e8ecff" font-size="13" font-weight="800">نقشهی گذرهای سال آینده</text>')
    for col, ml in enumerate(month_labels):
        x = left + col * col_w
        p.append(f'<text x="{x + col_w / 2}" y="18" fill="#8b96c9" font-size="9" text-anchor="middle">{ml}</text>')
    for r_idx, (rk, fa) in enumerate(rows):
        y = top + r_idx * row_h
        p.append(f'<text x="8" y="{y + 15}" fill="#c7cdf2" font-size="11">{fa}</text>')
        for col in range(months):
            x = left + col * col_w
            cell = grid.get((r_idx, col))
            if cell:
                asp, orb = cell
                color = {"Conjunction": "#f5c518", "Opposition": "#ff6b6b",
                         "Trine": "#4caf7d", "Square": "#ff8a5c", "Sextile": "#5ac8fa"}[asp]
                marker = {"Conjunction": "☌", "Opposition": "☍", "Trine": "△",
                          "Square": "□", "Sextile": "⚹"}[asp]
                p.append(f'<circle cx="{x + col_w / 2}" cy="{y + 13}" r="6" fill="{color}" opacity="0.85"/>')
                p.append(f'<text x="{x + col_w / 2}" y="{y + 17}" fill="#0b1026" font-size="8" font-weight="800" text-anchor="middle">{marker}</text>')
    # legend
    ly = h - 18
    lx = left
    for asp, fa in (("Conjunction", "☌ همپیوند"), ("Opposition", "☍ تقابل"), ("Trine", "△ سهگانه"),
                    ("Square", "□ تربیع"), ("Sextile", "⚹ ششگانه")):
        color = {"Conjunction": "#f5c518", "Opposition": "#ff6b6b", "Trine": "#4caf7d",
                 "Square": "#ff8a5c", "Sextile": "#5ac8fa"}[asp]
        p.append(f'<text x="{lx}" y="{ly}" fill="#8b96c9" font-size="9"><tspan fill="{color}">{fa}</tspan></text>')
        lx += 96
    p.extend(_svg_close())
    return "".join(p)


FILE: app/astrology/synastry.py  (86 lines)
======================================================================
"""Synastry (plan §8) — deterministic cross-chart aspects + compatibility score.

Given two chart JSONs, computes cross aspects (orb 5°), per-domain scores and
an overall compatibility index 0-100. Pure deterministic — LLM layer optional.
"""
from __future__ import annotations

_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
            "Uranus", "Neptune", "Pluto"]
_ASPECTS = {"Conjunction": 0, "Opposition": 180, "Trine": 120, "Square": 90, "Sextile": 60}
_ORB = 5.0

_ASPECT_FA = {"Conjunction": "همپیوندی", "Opposition": "مقابله", "Trine": "سهگانه",
              "Square": "تربیع", "Sextile": "ششگانه"}

# domain → planets of person A involved
_DOMAINS = {
    "love": ["Venus", "Moon", "Mars"],
    "mind": ["Mercury", "Moon"],
    "career": ["Sun", "Mars", "Saturn"],
    "spirit": ["Jupiter", "Sun"],
}


def synastry(chart_a: dict, chart_b: dict) -> dict:
    pa = chart_a.get("planets", {})
    pb = chart_b.get("planets", {})
    connections: list[dict] = []
    for n1 in _PLANETS:
        if n1 not in pa:
            continue
        for n2 in _PLANETS:
            if n2 not in pb or n1 == n2:
                continue
            lon1 = pa[n1]["longitude"]
            lon2 = pb[n2]["longitude"]
            diff = abs(lon1 - lon2) % 360
            diff = min(diff, 360 - diff)
            for asp, ang in _ASPECTS.items():
                if abs(diff - ang) <= _ORB:
                    connections.append({
                        "a": n1, "b": n2, "aspect": asp,
                        "aspect_fa": _ASPECT_FA[asp],
                        "orb": round(abs(diff - ang), 2),
                        "a_sign": pa[n1]["sign_fa"], "b_sign": pb[n2]["sign_fa"],
                    })

    # per-domain score: weighted positive/negative aspect balance
    def _domain_score(planets_a: list[str]) -> float:
        pos = neg = 0.0
        for c in connections:
            if c["a"] not in planets_a:
                continue
            w = 1.0 / (1.0 + c["orb"])
            if c["aspect"] in ("Conjunction", "Trine", "Sextile"):
                pos += w
            else:
                neg += w
        total = pos + neg
        if total == 0:
            return 50.0
        return round(50 + 50 * (pos - neg) / total, 1)

    domains = {k: _domain_score(v) for k, v in _DOMAINS.items()}
    overall = round(sum(domains.values()) / len(domains), 1)

    return {
        "connections_count": len(connections),
        "connections": sorted(connections, key=lambda c: -1.0 / (1.0 + c["orb"]))[:24],
        "domains": domains,
        "overall": overall,
        "verdict": _verdict(overall),
    }


def _verdict(score: float) -> str:
    if score >= 80:
        return "هماهنگی بسیار بالا — رابطه‌ای پر از حمایت متقابل"
    if score >= 65:
        return "هماهنگی خوب — تفاوت‌ها مکمل‌اند"
    if score >= 50:
        return "هماهنگی متوسط — نیاز به گفت‌وگو در برخی حوزه‌ها"
    if score >= 35:
        return "هماهنگی کم — چالش‌های قابل‌انتظار؛ با آگاهی قابل مدیریت"
    return "هماهنگی دشوار — نیاز به کار جدی روی ارتباط"


FILE: app/astrology/transits.py  (128 lines)
======================================================================
"""Transit engine — current sky vs natal chart (plan v3.1 §14).

Deterministic (pyswisseph); interpretation text stays in the LLM layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import swisseph as swe

swe.set_ephe_path("ephe")
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)


def _lon(body: int, jd: float) -> float:
    return swe.calc_ut(jd, body)[0][0]


PLANET_NAMES = {
    swe.SUN: "Sun", swe.MOON: "Moon", swe.MERCURY: "Mercury", swe.VENUS: "Venus",
    swe.MARS: "Mars", swe.JUPITER: "Jupiter", swe.SATURN: "Saturn",
    swe.URANUS: "Uranus", swe.NEPTUNE: "Neptune", swe.PLUTO: "Pluto",
    swe.MEAN_NODE: "Node", swe.CHIRON: "Chiron",
}


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _aspect(orb_deg: float) -> tuple[str, float] | None:
    for name, orb in (("هم‌نشینی", 8), ("تربیع", 6), ("سه‌گانه", 6), ("مقابله", 6), ("شش‌گانه", 4)):
        base = {"هم‌نشینی": 0, "تربیع": 90, "سه‌گانه": 120, "مقابله": 180, "شش‌گانه": 60}[name]
        d = abs(orb_deg - base)
        if d <= orb:
            return name, round(d, 1)
    return None


SIGNS_FA = ["برج حمل", "برج ثور", "برج جوزا", "برج سرطان", "برج اسد", "برج سنبله",
            "برج میزان", "برج عقرب", "برج قوس", "برج جدی", "برج دلو", "برج حوت"]


def compute_transits(chart_json: dict, when: datetime | None = None) -> list[dict]:
    """Transit events: {planet, sign_fa, natal_target, target_sign_fa, aspect, orb}."""
    now = when or datetime.now(timezone.utc)
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute / 60 + now.second / 3600)

    natal = chart_json.get("planets", {})
    angles = chart_json.get("angles", {})
    targets = {"Sun": natal.get("Sun"), "Moon": natal.get("Moon"), "ASC": angles.get("ASC")}

    events: list[dict] = []

    for body in (swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO, swe.MARS, swe.VENUS):
        lon = _lon(body, jd)
        sign_idx = int(lon // 30)
        sign_fa = SIGNS_FA[sign_idx]
        pname = PLANET_NAMES[body]
        for tname, t in targets.items():
            if not t:
                continue
            d = _angular_diff(lon, float(t.get("longitude", 0)))
            aspect = _aspect(d)
            if aspect:
                name, orb = aspect
                events.append({
                    "planet": pname, "planet_fa": _planet_fa(pname),
                    "sign_fa": sign_fa,
                    "target": tname, "target_sign_fa": t.get("sign_fa", ""),
                    "aspect": name, "orb": orb,
                })
    events.sort(key=lambda e: e["orb"])
    return events[:12]


def _planet_fa(name: str) -> str:
    return {"Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس", "Neptune": "نپتون",
            "Pluto": "پلوتو", "Mars": "مریخ", "Venus": "ناهید"}.get(name, name)


def upcoming_transits(chart_json: dict, days: int = 90, step: int = 1) -> list[dict]:
    """Upcoming transit EVENTS with start dates (plan §10 — gold transit chapter).

    Scans [now, now+days] at `step`-day resolution; a slow-planet aspect to a
    natal point becomes an event when it enters orb (2 consecutive in-orb
    samples → start), and stays one event until it leaves orb.

    Returns [{start: 'YYYY-MM-DD', planet_fa, sign_fa, aspect, orb}] sorted by start.
    """
    natal = chart_json.get("planets", {})
    angles = chart_json.get("angles", {})
    targets = {"Sun": natal.get("Sun"), "Moon": natal.get("Moon"),
               "ASC": angles.get("ASC"), "Venus": natal.get("Venus"),
               "Mars": natal.get("Mars"), "Mercury": natal.get("Mercury")}
    targets = {k: v for k, v in targets.items() if v}

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    events: list[dict] = []
    active: dict[tuple[int, str], tuple[str, float]] = {}

    for d in range(0, days + 1, step):
        when = now + timedelta(days=d)
        jd = swe.julday(when.year, when.month, when.day, 12)
        for body in (swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO):
            lon = _lon(body, jd)
            pname = PLANET_NAMES[body]
            for tname, t in targets.items():
                diff = _angular_diff(lon, float(t.get("longitude", 0)))
                aspect = _aspect(diff)
                if aspect:
                    name, orb = aspect
                    key = (body, tname)
                    if key not in active:
                        active[key] = (name, orb)
                        events.append({
                            "start": when.strftime("%Y-%m-%d"),
                            "planet_fa": _planet_fa(pname),
                            "sign_fa": SIGNS_FA[int(lon // 30)],
                            "target": tname,
                            "aspect": name, "orb": orb,
                        })
                else:
                    active.pop((body, tname), None)
    events.sort(key=lambda e: e["start"])
    return events


FILE: app/auth.py  (131 lines)
======================================================================
"""Lazy OTP auth (plan v3.1 §4 — Kavenegar first, dev-mode fallback).

Flow: chart form stays anonymous; OTP only when user wants dashboard/purchase.
- POST /api/auth/otp/request  {phone}   → 5-digit code (SMS via Kavenegar if
  OTP_SMS_API_KEY set, else server log — dev mode OTP_DEV_MODE=true returns hint).
- POST /api/auth/otp/verify   {phone, code} → session cookie (hmac of user id).
- GET  /api/auth/me                    → current user (or null)
- POST /api/auth/logout
Cookie: chart_user (httponly, samesite=lax, 30 days).
"""
import hashlib
import hmac as _hmac
import logging
import os
import random
import secrets
import time

from fastapi import Request
from sqlmodel import Session, select

import app.config  # noqa: F401
from app.db import engine
from app.models import User

log = logging.getLogger("chart.auth")

_AUTH_SECRET: str = os.getenv("AUTH_SECRET") or ""
if not _AUTH_SECRET:
    # fail-closed in production: a random per-boot secret would silently
    # invalidate every session on restart (audit P0)
    if os.getenv("APP_ENV", "dev") == "prod":
        raise RuntimeError("AUTH_SECRET is required (set APP_ENV=prod)")
    _AUTH_SECRET = secrets.token_hex(16)  # dev-only ephemeral
_OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "false").lower() == "true"
USER_COOKIE = "chart_user"
OTP_TTL = 300           # 5 minutes
OTP_MAX_ATTEMPTS = 5
_OTP_STORE: dict[str, dict] = {}   # phone -> {code, expires, attempts}


# ── session helpers ──────────────────────────────────────────────────────────

def _user_cookie_value(user_id: str) -> str:
    sig = _hmac.new(_AUTH_SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{sig}"


def get_current_user(request: Request) -> User | None:
    val = request.cookies.get(USER_COOKIE, "")
    if not val or "." not in val:
        return None
    uid, sig = val.rsplit(".", 1)
    if len(sig) != 64:
        return None
    expect = _hmac.new(_AUTH_SECRET.encode(), uid.encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expect, sig):
        return None
    with Session(engine) as s:
        return s.get(User, uid)


def set_user_cookie(request: Request, user_id: str):
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/account", status_code=303)
    resp.set_cookie(USER_COOKIE, _user_cookie_value(user_id), httponly=True,
                    max_age=30 * 24 * 3600, samesite="lax")
    return resp


# ── OTP ──────────────────────────────────────────────────────────────────────

def _send_sms(phone: str, code: str) -> None:
    """Kavenegar v2 if configured. Fail-closed in production (audit P0):
    never log the OTP itself outside explicit dev mode."""
    api_key = os.getenv("OTP_SMS_API_KEY", "")
    if api_key:
        try:
            import httpx
            url = f"https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"
            r = httpx.post(url, data={
                "receptor": phone, "token": code, "template": os.getenv("OTP_SMS_TEMPLATE", "chartotp"),
            }, timeout=10)
            r.raise_for_status()
            return
        except Exception as e:
            if os.getenv("APP_ENV", "dev") == "prod":
                raise RuntimeError(f"SMS delivery failed: {e}") from e
            log.warning("SMS send failed: %s — falling back to dev log", e)
    if _OTP_DEV_MODE:
        log.info("OTP DEV MODE: code for %s = %s", phone, code)
    else:
        raise RuntimeError("SMS provider not configured (OTP_SMS_API_KEY)")


def request_otp(phone: str) -> dict:
    phone = phone.strip()
    code = f"{random.randint(0, 99999):05d}"
    _OTP_STORE[phone] = {"code": code, "expires": time.time() + OTP_TTL, "attempts": 0}
    _send_sms(phone, code)
    out = {"ok": True, "expires_in": OTP_TTL}
    if _OTP_DEV_MODE:
        out["dev_code"] = code
    return out


def verify_otp(phone: str, code: str) -> User | None:
    phone = phone.strip()
    rec = _OTP_STORE.get(phone)
    if not rec:
        return None
    if time.time() > rec["expires"]:
        _OTP_STORE.pop(phone, None)
        return None
    rec["attempts"] += 1
    if rec["attempts"] > OTP_MAX_ATTEMPTS:
        _OTP_STORE.pop(phone, None)
        return None
    if not _hmac.compare_digest(rec["code"], code.strip()):
        return None
    _OTP_STORE.pop(phone, None)

    with Session(engine) as s:
        u = s.exec(select(User).where(User.phone == phone)).first()
        if not u:
            u = User(phone=phone)
            s.add(u)
            s.commit()
            s.refresh(u)
        return u


FILE: app/bots/handler.py  (331 lines)
======================================================================
"""Chart-platform bot handler — Telegram + Bale, fully button-driven.

Flow: /start → «ساخت چارت» → birth date → birth time (optional) → city →
chart computed → share card + chart link + action buttons.
Uses Bot API over httpx; tokens from env. parse_mode=HTML everywhere
(pitfall: Markdown breaks on _ in ids — none here, but stay safe).
"""
from __future__ import annotations

import html as _html
import logging
import os
import re
import traceback

import httpx

import app.config  # noqa: F401 — load .env FIRST
from app.astrology.big_three import big_three
from app.astrology.cities_ir import search_cities
from app.astrology.engine import compute_from_fields, validate_birth_fields
from app.bots.state import clear_chat_state, get_chat_state, set_chat_state
from sqlmodel import select

logger = logging.getLogger("chart.bots")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BALE_TOKEN = os.getenv("BALE_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}"


async def api_call(method: str, payload: dict, platform: str) -> dict:
    token = TELEGRAM_TOKEN if platform == "telegram" else BALE_TOKEN
    if not token:
        return {"ok": False, "description": "token not configured"}
    base = TELEGRAM_API if platform == "telegram" else BALE_API
    try:
        async with httpx.AsyncClient(timeout=30) as cl:
            r = await cl.post(f"{base}/{method}", json=payload)
            data = r.json()
            if not data.get("ok"):
                logger.warning("BotAPI %s/%s -> %s", platform, method, data.get("description"))
            return data
    except Exception as e:  # noqa: BLE001
        logger.error("BotAPI %s/%s error: %s", platform, method, e)
        return {"ok": False, "description": str(e)}


def _fmt_html(text: str) -> str:
    escaped = _html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


async def send_message(chat_id: int, text: str, platform: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": chat_id, "text": _fmt_html(text), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendMessage", payload, platform)


async def send_photo(chat_id: int, photo_url: str, caption: str, platform: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": _fmt_html(caption), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendPhoto", payload, platform)


async def answer_callback(cb_id: str, text: str = "", platform: str = "telegram") -> None:
    await api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text}, platform)


def cancel_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel"}]]}


def start_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "✨ ساخت چارت تولد من", "callback_data": "chart_start"}]]}


def chart_actions_keyboard(chart_id: str) -> dict:
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
    return {
        "inline_keyboard": [
            [{"text": "📄 مشاهده چارت", "url": f"{base}/chart/{chart_id}"}],
            [{"text": "✨ خرید گزارش کامل", "url": f"{base}/plans?chart={chart_id}"}],
            [{"text": "🌠 گذرهای کنونی", "url": f"{base}/transit/{chart_id}"}],
            [{"text": "☀️ اشتراک گذرهای روزانه", "callback_data": f"sub_{chart_id}"}],
        ]
    }


# ─────────────────────────── commands ───────────────────────────

async def _cmd_start(chat_id: int, platform: str) -> None:
    await send_message(
        chat_id,
        "🌟 به ربات چارت تولد خوش آمدی!\n\n"
        "با چند اطلاعات ساده، چارت نجومی دقیق تو را محاسبه می‌کنم و از آن یک گزارش اختصاصی می‌سازم.\n\n"
        "👇 شروع کنیم؟",
        platform, reply_markup=start_keyboard(),
    )


# ─────────────────────────── state routing ───────────────────────────

_DATE_RE = re.compile(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


async def _route_by_state(chat_id: int, platform: str, text: str) -> bool:
    st = get_chat_state(chat_id, platform)
    if not st:
        return False
    state, payload = st["state"], st["payload"]

    if state == "waiting_birth_date":
        m = _DATE_RE.match(text.strip())
        if not m:
            await send_message(chat_id, "⛔ قالب تاریخ درست نیست.\n📅 تاریخ را به شکل <b>روز/ماه/سال</b> بفرست؛ مثال: <b>23/08/1994</b>", platform)
            return True
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ok, err = validate_birth_fields(y, mo, d)
        if not ok:
            await send_message(chat_id, f"⛔ {err}", platform)
            return True
        set_chat_state(chat_id, platform, "waiting_birth_time", {**payload, "day": d, "month": mo, "year": y})
        await send_message(
            chat_id,
            "🕐 <b>ساعت تولد</b> را بفرست (مثال: 06:10).\n\n"
            "اگر ساعت دقیق را نمی‌دانی، فقط <b>صفر</b> یا <b>خالی</b> بفرست — نیمه‌شب در نظر گرفته می‌شود.",
            platform, reply_markup=cancel_keyboard(),
        )
        return True

    if state == "waiting_birth_time":
        t = text.strip()
        hour, minute = 12, 0
        if t and t not in ("0", "صفر"):
            m = _TIME_RE.match(t)
            if not m:
                await send_message(chat_id, "⛔ قالب ساعت درست نیست.\n🕐 ساعت را به شکل <b>ساعت:دقیقه</b> بفرست؛ مثال: <b>06:10</b>", platform)
                return True
            hour, minute = int(m.group(1)), int(m.group(2))
            if hour > 23 or minute > 59:
                await send_message(chat_id, "⛔ ساعت نامعتبر است. بین 00:00 تا 23:59", platform)
                return True
        set_chat_state(chat_id, platform, "waiting_birth_city", {**payload, "hour": hour, "minute": minute})
        await send_message(
            chat_id,
            "🏙️ <b>شهر تولد</b> را بفرست (مثال: تهران، شیراز، مشهد...)",
            platform, reply_markup=cancel_keyboard(),
        )
        return True

    if state == "waiting_birth_city":
        city = text.strip()
        hits = search_cities(city) if city else []
        if not hits:
            await send_message(
                chat_id,
                "⛔ شهری با این نام پیدا نکردم. نام شهر را دوباره بفرست (مثلاً: تهران، اصفهان، تبریز، کرج...)",
                platform,
            )
            return True
        best = hits[0]
        try:
            chart = compute_from_fields(best["lat"], best["lon"], payload["year"], payload["month"],
                                        payload["day"], payload["hour"], payload["minute"])
        except Exception as e:  # noqa: BLE001
            logger.error("compute failed: %s", e)
            await send_message(chat_id, "⛔ مشکلی در محاسبه پیش آمد؛ دوباره تلاش کن.", platform)
            return True
        clear_chat_state(chat_id, platform)

        from app.db import engine
        from sqlmodel import Session
        from app.models import Chart
        with Session(engine) as s:
            row = Chart(chart_json=chart.chart_json)
            s.add(row)
            s.commit()
            chart_id = row.id

        bt = big_three(chart.chart_json)
        base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
        caption = (
            f"🌟 <b>چارت تولد تو آماده شد!</b>\n\n"
            f"☀️ خورشید: <b>{bt.get('Sun', {}).get('sign_fa', '')}</b>\n"
            f"🌙 ماه: <b>{bt.get('Moon', {}).get('sign_fa', '')}</b>\n"
            f"⬆️ طالع: <b>{bt.get('ASC', {}).get('sign_fa', '')}</b>\n\n"
            f"برای مشاهده و خرید گزارش اختصاصی، دکمه‌های زیر را بزن:"
        )
        await send_photo(chat_id, f"{base}/api/share/{chart_id}.png", caption,
                         platform, reply_markup=chart_actions_keyboard(chart_id))
        return True

    return False


# ─────────────────────────── update dispatch ───────────────────────────

async def handle_update(update: dict, platform: str) -> dict:
    try:
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = msg.get("text") or ""
        entities = msg.get("entities") or []
        is_command = bool(entities and entities[0].get("type") == "bot_command") or text.startswith("/")

        if msg.get("photo") and chat_id:
            return await _route_photo(chat_id, platform, msg)

        if chat_id:
            if is_command and text.startswith("/start"):
                await _cmd_start(chat_id, platform)
                return {"ok": True}
            if is_command and text.startswith("/cancel_sub"):
                try:
                    from app.db import Session as _Session
                    from app.db import engine as _engine
                    from app.models import Subscription
                    with _Session(_engine) as s:
                        subs = s.exec(select(Subscription).where(
                            Subscription.chat_id == str(chat_id),
                            Subscription.active == True,
                        )).all()
                        for sub in subs:
                            sub.active = False
                        s.commit()
                    await send_message(chat_id, "اشتراک گذرها لغو شد. 😔\nهر وقت خواستی دوباره فعالش کن.", platform)
                except Exception as e:  # noqa: BLE001
                    logger.error("cancel_sub error: %s", e)
                    await send_message(chat_id, "مشکلی پیش آمد؛ دوباره تلاش کن.", platform)
                return {"ok": True}
            if not is_command and text:
                handled = await _route_by_state(chat_id, platform, text)
                if handled:
                    return {"ok": True}
                await send_message(chat_id, "برای شروع دکمه‌ی «✨ ساخت چارت تولد من» را بزن.", platform)
                return {"ok": True}

        cb = update.get("callback_query")
        if cb:
            await _handle_callback(cb, platform)
            return {"ok": True}

        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        logger.error("handle_update(%s) error: %s\n%s", platform, e, traceback.format_exc())
        return {"ok": True}


async def _route_photo(chat_id: int, platform: str, msg: dict) -> dict:
    """No photo flow in chart bot — but keep state machine sane."""
    st = get_chat_state(chat_id, platform)
    if st:
        await send_message(chat_id, "این بخش نیاز به متن دارد — لطفاً اطلاعات خواسته‌شده را بنویس.", platform)
    return {"ok": True}


async def _handle_callback(cb: dict, platform: str) -> None:
    cb_id = cb.get("id")
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    data = cb.get("data") or ""
    if not chat_id:
        if cb_id:
            await answer_callback(cb_id, platform=platform)
        return
    if data == "chart_start":
        set_chat_state(chat_id, platform, "waiting_birth_date", {})
        await send_message(
            chat_id,
            "📅 <b>تاریخ تولد</b> را بفرست؛ مثال: <b>23/08/1994</b>",
            platform, reply_markup=cancel_keyboard(),
        )
    elif data == "cancel":
        clear_chat_state(chat_id, platform)
        await send_message(chat_id, "لغو شد. هر وقت خواستی دوباره شروع کن 👇", platform, reply_markup=start_keyboard())
    elif data.startswith("sub_"):
        chart_id = data[4:]
        try:
            from app.db import Session as _Session
            from app.db import engine as _engine
            from app.models import Chart, Subscription
            with _Session(_engine) as s:
                chart = s.get(Chart, chart_id)
                if not chart:
                    await send_message(chat_id, "چارت پیدا نشد؛ اول یک چارت بساز.", platform)
                    return
                # existing active subscription → just show status
                sub = s.exec(select(Subscription).where(
                    Subscription.chat_id == str(chat_id),
                    Subscription.chart_id == chart_id, Subscription.active == True,
                )).first()
                if sub:
                    from datetime import datetime
                    expires = sub.expires_at.strftime("%Y-%m-%d") if sub.expires_at else "نامحدود"
                    await send_message(
                        chat_id,
                        f"☀️ اشتراک گذرها فعال است (تا {expires}).\nبرای لغو: /cancel_sub",
                        platform,
                    )
                    return
            # paid flow: monthly plan order → zarinpal link (plan v3.0 §7)
            from app.payment.orders import create_order
            with _Session(_engine) as s:
                order, pay_url = create_order(
                    s, "monthly", chart_id, chat_id=str(chat_id), platform=platform,
                    new_user_id=str(chat_id),
                )
            markup = {"inline_keyboard": [
                [{"text": "💳 پرداخت ۳۹۹ هزار تومان", "url": pay_url}],
            ]}
            await send_message(
                chat_id,
                "☀️ اشتراک گذرهای روزانه — ۳۹۹ هزار تومان در ماه\n\n"
                "هر روز صبح، مهم‌ترین گذرهای سیارهای چارتت را اینجا میفرستم.\n"
                "پس از پرداخت، اشتراک برای ۳۰ روز فعال میشود.",
                platform,
                reply_markup=markup,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("subscription error: %s", e)
            await send_message(chat_id, "مشکلی در ایجاد اشتراک پیش آمد؛ دوباره تلاش کن.", platform)
    if cb_id:
        await answer_callback(cb_id, platform=platform)


FILE: app/bots/state.py  (44 lines)
======================================================================
"""Bot per-chat state (v135 pattern) — state rows keyed by platform+chat_id."""
from __future__ import annotations

import json

from sqlmodel import Field, Session, select

from app.db import engine
from app.models import BotState


def get_chat_state(chat_id: int, platform: str) -> dict | None:
    """Return {"state": ..., "payload": {...}} or None."""
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if not row:
            return None
        return {"state": row.state, "payload": json.loads(row.payload or "{}")}


def set_chat_state(chat_id: int, platform: str, state: str, payload: dict | None = None) -> None:
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if not row:
            row = BotState(platform=platform, chat_id=chat_id)
            s.add(row)
        row.state = state
        row.payload = json.dumps(payload or {}, ensure_ascii=False)
        s.commit()


def clear_chat_state(chat_id: int, platform: str) -> None:
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if row:
            s.delete(row)
            s.commit()


FILE: app/chat/intents.py  (54 lines)
======================================================================
"""Intent detection (Persian) — Question → Intent (plan v3.1 §13 AI Chat).

Deterministic keyword classifier; no LLM call needed for routing.
"""
from __future__ import annotations

import re

INTENTS: dict[str, list[str]] = {
    "identity": ["شخصیت", "من کیستم", "هویت", "خودشناسی", "نفس", "طبع", "روحیات", "خلقیات", "روحیه", "خصوصیت"],
    "emotions": ["احساس", "هیجان", "عاطفه", "غم", "شادی", "ناراحت", "دلتنگی", "عصبی", "حس", "ماه"],
    "career": ["شغل", "کار", "حرفه", "مسیر شغلی", "موفقیت کاری", "درآمد شغلی", "ریاست", "مدیریت", "بیزینس", "کسب و کار", "استارتاپ"],
    "money": ["پول", "ثروت", "مالی", "درآمد", "پس‌انداز", "سرمایه", "بدهی", "خرج", "مادیات", "ریال", "تومان"],
    "relationships": ["ازدواج", "عشق", "عاشق", "رابطه", "همسر", "دوستی", "شریک", "نامزدی", "خواستگار", "طلاق", "مهر"],
    "family": ["خانواده", "پدر", "مادر", "فرزند", "بچه", "خواهر", "برادر", "خانه", "خانوادگی"],
    "wellbeing": ["سلامت", "انرژی", "خستگی", "ورزش", "بدن", "خواب", "استرس", "آرامش", "نشاط"],
    "education": ["تحصیل", "درس", "دانشگاه", "مدرسه", "یادگیری", "آموزش", "کتاب", "مدرک", "رشته"],
    "network": ["دوست", "رفیق", "شبکه", "ارتباطات", "آشنا", "همکار", "معاشرت", "محبوبیت"],
    "creativity": ["خلاقیت", "هنر", "نقاشی", "موسیقی", "نوشتن", "ایده", "ابتکار", "نوآوری"],
    "spirituality": ["معنویت", "روح", "عرفان", "دین", "مذهب", "مراقبه", "مدیتیشن", "انرژی معنوی", "دعا"],
    "karma": ["کارما", "سرنوشت", "تقدیر", "بدهی کارمایی", "زندگی قبلی", "درس زندگی", "مقصد روح"],
    "transit": ["امسال", "امسال", "آینده", "پیش رو", "گذر", "ترانزیت", "پیش‌بینی", "کی بهتر", "کی بدتر", "سال آینده", "ماه آینده", "موفقیت آینده"],
    "strength": ["نقطه قوت", "قوت", "توانایی", "استعداد", "مهارت", "چه کارایی بلدم", "قدرت"],
    "weakness": ["نقطه ضعف", "ضعف", "چالش", "مشکل", "عیب", "کمبود", "محدودیت"],
}

FALLBACK = "general"


def detect_intent(question: str) -> str:
    """Return best-matching intent key (or 'general')."""
    q = question.strip().lower()
    best, best_score = FALLBACK, 0
    for intent, kws in INTENTS.items():
        score = sum(1 for kw in kws if kw in q)
        if score > best_score:
            best, best_score = intent, score
    return best


def route_question(question: str, focus_areas: list[str] | None = None) -> dict:
    """Intent + domain list to fetch from the report/chart."""
    intent = detect_intent(question)
    domain_map = {
        "identity": ["identity"], "emotions": ["emotions"], "career": ["career"],
        "money": ["money"], "relationships": ["relationships"], "family": ["family"],
        "wellbeing": ["wellbeing"], "education": ["education"], "network": ["network"],
        "creativity": ["creativity"], "spirituality": ["spirituality"],
        "karma": ["karma"], "transit": ["career", "money", "wellbeing"],
        "strength": ["identity", "wellbeing", "career"], "weakness": ["identity", "karma"],
        "general": list((focus_areas or ["identity", "emotions", "career", "money", "relationships"])),
    }
    return {"intent": intent, "domains": domain_map[intent]}


FILE: app/chat/retrieval.py  (56 lines)
======================================================================
"""Retrieval layer — pull grounded context (chart factors + report sections) for chat.

Plan v3.1 §13: Question → Intent → Domains → Factors → Evidence → Prompt → LLM.
Only retrieved, relevant context is sent to the LLM (never the whole chart).
"""
from __future__ import annotations

import json

from app.report.prompt_builder import factors_block
from app.report.rules import DOMAINS, evaluate


def retrieve_context(chart_json: dict, report_sections: dict | None,
                     domains: list[str]) -> dict:
    """Assemble the retrieval payload for one chat turn."""
    active = evaluate(chart_json)
    ctx: dict = {"chart_summary": _chart_summary(chart_json), "domains": {}}

    for d in domains:
        sec = (report_sections or {}).get(d)
        block: dict = {"factors": factors_block(chart_json, d, active.get(d, []))}
        if sec and sec.get("insights"):
            block["insights"] = [
                {"title": i.get("insight", "")[:120],
                 "strengths": i.get("strengths", [])[:3],
                 "challenges": i.get("challenges", [])[:3]}
                for i in sec["insights"][:2]
            ]
        ctx["domains"][d] = block
    return ctx


def _chart_summary(chart_json: dict) -> str:
    """One-line deterministic summary of the chart (identity anchors)."""
    p = chart_json.get("planets", {})
    ang = chart_json.get("angles", {})
    sun = p.get("Sun", {}); moon = p.get("Moon", {}); asc = ang.get("ASC", {})
    parts = []
    for label, d in (("خورشید", sun), ("ماه", moon), ("طالع", asc)):
        if d.get("sign_fa"):
            parts.append(f"{label} در {d['sign_fa']}" + (f" (خانه {d['house']})" if d.get("house") else ""))
    return "، ".join(parts) or "چارت محاسبه شده است"


def build_chat_prompt(question: str, ctx: dict) -> str:
    """Final grounded prompt for the LLM (Persian, compassionate, no girl-topic)."""
    import json as _j
    return (
        "تو یک منجم انسانی و دلسوز هستی که بر اساس چارت تولد محاسبه‌شده‌ی دقیق پاسخ می‌دهی.\n"
        "فقط از اطلاعات داده‌شده استفاده کن؛ هرگز چیزی اختراع نکن و از ادعای قطعی درباره آینده بپرهیز.\n"
        "پاسخ کوتاه، صمیمی و در ۳ تا ۶ جمله باشد.\n\n"
        "اطلاعات چارت:\n" + _j.dumps(ctx, ensure_ascii=False, indent=1)[:3500] +
        "\n\nسؤال کاربر:\n" + question
    )


FILE: app/chat/service.py  (31 lines)
======================================================================
"""Chat service — one grounded turn: intent → retrieve → LLM → answer."""
from __future__ import annotations

import asyncio

from app.chat.intents import route_question
from app.chat.retrieval import build_chat_prompt, retrieve_context


def chat_answer(question: str, chart_json: dict, report_sections: dict | None = None,
                focus_areas: list[str] | None = None, router=None) -> dict:
    """Sync entry (dev/tests): returns {answer, intent, domains, cost, tokens}."""
    route = route_question(question, focus_areas)
    ctx = retrieve_context(chart_json, report_sections, route["domains"])
    prompt = build_chat_prompt(question, ctx)

    from app.core.llm import build_chat_router
    rtr = router or build_chat_router()
    res = asyncio.run(rtr.complete(prompt, max_tokens=1024, temperature=0.7))
    answer = res.text or ""
    if not answer:
        answer = "در حال حاضر سرویس پاسخ‌گویی در دسترس نیست (محدودیت سهمیه). لطفاً چند ساعت بعد تلاش کنید."
    return {
        "answer": answer,
        "intent": route["intent"],
        "domains": route["domains"],
        "ok": res.ok,
        "cost_usd": res.cost,
        "tokens": res.usage.total,
    }


FILE: app/config.py  (11 lines)
======================================================================
"""Env loader — must be imported FIRST (before app.db / any env reads).

Loads /root/chart-platform/.env (secrets: bot tokens, zarinpal, keys path).
"""
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=False)


FILE: app/core/__init__.py  (1 lines)
======================================================================


FILE: app/core/llm.py  (362 lines)
======================================================================
"""
LLM Provider layer — deterministic chart data NEVER goes through LLM.

Architecture (plan v3.1 section 6.1):
    LLMProvider (abstract: health/quota/latency/error_rate/cost)
      ├── GeminiProvider   (direct REST, AQ free-tier keys, rotation)  ✅ tested
      ├── DeepSeekProvider (OpenAI-compatible API)                     ⏳ needs key
      └── AvalAIProvider   (OpenAI-compatible Iranian gateway)          ⏳ needs key
    LLMRouter picks the best provider by health + quota + cost.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger("chart.llm")


# ─────────────────────────── dataclasses ───────────────────────────

@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    usage: LLMUsage = field(default_factory=LLMUsage)
    cost: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ProviderHealth:
    provider: str
    healthy: bool = True
    last_error: str | None = None
    error_streak: int = 0
    last_latency_ms: int = 0
    cost_usd: float = 0.0


# ─────────────────────────── abstract provider ───────────────────────────

class LLMProvider(ABC):
    """All providers expose the same interface so nothing is locked to one vendor."""

    name: str = "base"

    def __init__(self) -> None:
        self.health = ProviderHealth(provider=self.name)

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7) -> LLMResult:
        """Single completion. Returns structured result — never raises for API errors."""

    def report_success(self, latency_ms: int, usage: LLMUsage) -> None:
        self.health.last_latency_ms = latency_ms
        self.health.error_streak = 0
        self.health.cost_usd += self.estimate_cost(usage)

    def report_error(self, err: str) -> None:
        self.health.error_streak += 1
        self.health.last_error = err
        self.health.healthy = self.health.error_streak < 5

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        """Override per provider pricing. DeepSeek official: in $0.14/1M (miss), out $0.28/1M."""
        return (usage.prompt_tokens * 0.14 + usage.completion_tokens * 0.28) / 1_000_000


# ─────────────────────────── Gemini (direct REST, free-tier AQ keys) ───────────────────────────

class GeminiProvider(LLMProvider):
    """Gemini 3.6 Flash via native generateContent?key= — PROVEN working from this server (2026-08-12)."""

    name = "gemini"
    MODEL = "gemini-3.6-flash"

    def __init__(self, keys: list[str], api_base: str = "https://generativelanguage.googleapis.com/v1beta") -> None:
        super().__init__()
        self.keys = keys
        self.api_base = api_base
        self._idx = 0
        self._exhausted: dict[str, float] = {}  # key -> cooldown-until (monotonic)
        self._daily_quota = 20  # free tier: 20 req/day/project/model
        self._daily: dict[str, int] = {}
        self._daily_reset = int(time.time()) // 86400

    def _next_key(self) -> str:
        """Round-robin over keys, skipping cooldown + daily-quota-exhausted keys."""
        today = int(time.time()) // 86400
        if today != self._daily_reset:
            self._daily.clear()
            self._daily_reset = today
        for _ in range(len(self.keys)):
            key = self.keys[self._idx % len(self.keys)]
            self._idx += 1
            if self._exhausted.get(key, 0) <= time.monotonic() and self._daily.get(key, 0) < self._daily_quota:
                self._daily[key] = self._daily.get(key, 0) + 1
                return key
        # everything cooling down / quota-exhausted — try the next key anyway (retry > nothing)
        key = self.keys[self._idx % len(self.keys)]
        self._idx += 1
        return key

    def _mark_exhausted(self, key: str, cooldown_s: float) -> None:
        self._exhausted[key] = time.monotonic() + cooldown_s
        logger.warning("Gemini key %s… cooldown %.0fs (remaining healthy keys: %d)",
                       key[-6:], cooldown_s, sum(1 for k in self.keys if self._exhausted.get(k, 0) <= time.monotonic()))

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        t0 = time.monotonic()
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        # try up to len(keys) times — skip exhausted keys automatically
        for attempt in range(max(len(self.keys), 1)):
            key = self._next_key()
            url = f"{self.api_base}/models/{self.MODEL}:generateContent?key={key}"
            try:
                async with httpx.AsyncClient(timeout=120) as cl:
                    r = await cl.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    text = "".join(p.get("text", "") for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
                    usage = data.get("usageMetadata", {})
                    u = LLMUsage(prompt_tokens=usage.get("promptTokenCount", 0),
                                 completion_tokens=usage.get("candidatesTokenCount", 0))
                    lat = int((time.monotonic() - t0) * 1000)
                    self.report_success(lat, u)
                    return LLMResult(text=text, provider=self.name, model=self.MODEL,
                                     latency_ms=lat, usage=u, cost=self.estimate_cost(u))
                err = r.text[:200]
                if r.status_code == 429:
                    if "quota" in r.text.lower() or "billing" in r.text.lower():
                        self._mark_exhausted(key, 3600)
                    else:
                        self._mark_exhausted(key, 30)
                elif r.status_code >= 500:
                    self._mark_exhausted(key, 30)
                if attempt == len(self.keys) - 1:
                    self.report_error(err)
                    return LLMResult(text="", provider=self.name, model=self.MODEL, error=f"HTTP {r.status_code}: {err}")
            except Exception as e:  # network etc.
                if attempt == len(self.keys) - 1:
                    self.report_error(str(e))
                    return LLMResult(text="", provider=self.name, model=self.MODEL, error=str(e))
        return LLMResult(text="", provider=self.name, model=self.MODEL, error="no keys available")

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        return 0.0  # free-tier keys


# ─────────────────────────── DeepSeek (OpenAI-compatible) ───────────────────────────

class DeepSeekProvider(LLMProvider):
    """DeepSeek V4 Flash via official OpenAI-compatible API. Needs DEEPSEEK_API_KEY env."""

    name = "deepseek"
    MODEL = "deepseek-v4-flash"

    def __init__(self, api_key: str | None = None, api_base: str = "https://api.deepseek.com") -> None:
        super().__init__()
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.api_base = api_base
        self.user_agent = "chart-platform/1.0"
        self.extra_payload: dict | None = None

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        if not self.api_key:
            return LLMResult(text="", provider=self.name, model=self.MODEL, error="DEEPSEEK_API_KEY not set")
        t0 = time.monotonic()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict = {"model": self.MODEL, "messages": messages,
                         "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "User-Agent": self.user_agent}
        if self.extra_payload:
            payload.update(self.extra_payload)
        try:
            async with httpx.AsyncClient(timeout=300) as cl:
                r = await cl.post(f"{self.api_base}/chat/completions",
                                  headers=headers,
                                  json=payload)
            if r.status_code != 200:
                err = r.text[:200]
                self.report_error(err)
                return LLMResult(text="", provider=self.name, model=self.MODEL, error=f"HTTP {r.status_code}: {err}")
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            u = LLMUsage(prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                         completion_tokens=data.get("usage", {}).get("completion_tokens", 0))
            lat = int((time.monotonic() - t0) * 1000)
            self.report_success(lat, u)
            return LLMResult(text=text, provider=self.name, model=self.MODEL,
                             latency_ms=lat, usage=u, cost=self.estimate_cost(u))
        except Exception as e:
            self.report_error(str(e))
            return LLMResult(text="", provider=self.name, model=self.MODEL, error=str(e))


# ─────────────────────────── Go (opencode.ai subscription, OpenAI-compatible) ───────────────────────────

class GoProvider(DeepSeekProvider):
    """OpenCode Go subscription (opencode.ai/zen/go/v1) — DeepSeek V4 via OpenAI-compatible API.
    Flat $10/mo with per-model request quotas — cost per call recorded as 0 (billed via subscription).
    KEY: reasoning models burn max_tokens on thinking → MUST send thinking: disabled (verified 2026-08-12).
    NOTE: gateway sits behind Cloudflare — sends browser UA to avoid 403 (error code 1010)."""

    name = "go"
    MODEL = os.getenv("GO_MODEL", "deepseek-v4-pro")

    def __init__(self, api_key: str | None = None, api_base: str | None = None,
                 model: str | None = None) -> None:
        super().__init__(api_key=api_key or os.getenv("GO_API_KEY", ""),
                         api_base=api_base or os.getenv("GO_API_BASE", "https://opencode.ai/zen/go/v1"))
        if model:
            self.MODEL = model
        self.extra_payload = {"thinking": {"type": "disabled"}}
        self.user_agent = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "Chrome/126.0 Safari/537.36")

    @staticmethod
    def estimate_cost(usage: LLMUsage) -> float:
        return 0.0  # flat subscription — not per-token


# ─────────────────────────── AvalAI (Iranian gateway, OpenAI-compatible) ───────────────────────────

class AvalAIProvider(DeepSeekProvider):
    """AvalAI (avalai.ir) — OpenAI-compatible Iranian gateway with riyal billing.
    Set AVALAI_API_KEY. Optional paid fallback; interface identical to DeepSeek."""

    name = "avalai"
    MODEL = "deepseek-chat"  # their default DeepSeek model

    def __init__(self, api_key: str | None = None, api_base: str = "https://api.avalai.ir/v1") -> None:
        super().__init__(api_key=api_key or os.getenv("AVALAI_API_KEY", ""), api_base=api_base)


# ─────────────────────────── Router ───────────────────────────

class LLMRouter:
    """Picks the best provider: healthy + cheapest + lowest error streak.
    Priority order can be overridden via LLM_ORDER env (comma-separated provider names)."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        self.providers = {p.name: p for p in providers}
        env_order = os.getenv("LLM_ORDER", "")
        self.order = [n.strip() for n in env_order.split(",") if n.strip()] or list(self.providers)

    def _rank(self) -> list[LLMProvider]:
        def key(p: LLMProvider) -> tuple:
            return (not p.health.healthy, p.health.error_streak, p.health.cost_usd)
        return sorted((self.providers[n] for n in self.order if n in self.providers), key=key)

    async def complete(self, prompt: str, system: str | None = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       json_mode: bool = False) -> LLMResult:
        last: LLMResult | None = None
        for p in self._rank():
            last = await p.complete(prompt, system=system, max_tokens=max_tokens,
                                    temperature=temperature, json_mode=json_mode)
            if last.ok:
                return last
            logger.warning("LLM provider %s failed: %s — trying next", p.name, last.error)
        return last or LLMResult(text="", provider="none", model="", error="all providers failed")

    def health_report(self) -> list[dict]:
        return [
            {"provider": p.name, "healthy": p.health.healthy, "error_streak": p.health.error_streak,
             "last_latency_ms": p.health.last_latency_ms, "last_error": p.health.last_error,
             "cost_usd": round(p.health.cost_usd, 6)}
            for p in self.providers.values()
        ]


# ─────────────────────────── factory ───────────────────────────

def load_gemini_keys(path: str | None = None) -> list[str]:
    """Load Gemini keys: platform .env path → platform keys/ → hermes fallback."""
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates += [
        Path(os.getenv("GEMINI_KEYS_PATH", "keys/gemini-keys.txt")),
        Path("/root/chart-platform/keys/gemini-keys.txt"),
        Path("/root/.hermes/keys/gemini-3.6-keys.txt"),
    ]
    for cand in candidates:
        if cand.exists():
            keys = [l.strip() for l in cand.read_text().splitlines()
                    if l.strip().startswith("AQ.")]
            if keys:
                return keys
    return []


def build_router() -> LLMRouter:
    providers: list[LLMProvider] = []
    go = GoProvider()
    if go.api_key:
        providers.append(go)
    gkeys = load_gemini_keys()
    if gkeys:
        providers.append(GeminiProvider(gkeys))
    providers.append(DeepSeekProvider())
    providers.append(AvalAIProvider())
    return LLMRouter(providers)


def build_chat_router() -> LLMRouter:
    """Chat/preview router — fast + quota-cheap: go-flash → gemini → avalai."""
    providers: list[LLMProvider] = []
    go = GoProvider(model="deepseek-v4-flash")
    if go.api_key:
        providers.append(go)
    gkeys = load_gemini_keys()
    if gkeys:
        providers.append(GeminiProvider(gkeys))
    providers.append(AvalAIProvider())
    return LLMRouter(providers)


FILE: app/db.py  (64 lines)
======================================================================
"""DB session + init (Postgres). For tests: override engine with temp SQLite."""
import os

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

_DEV_DEFAULT = "postgresql://chart_app:chart_dev_2026@127.0.0.1:5432/chart_platform"
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("APP_ENV", "dev") == "prod":
        raise RuntimeError("DATABASE_URL is required (set APP_ENV=prod)")
    DATABASE_URL = _DEV_DEFAULT

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db() -> None:
    # import models so they register on metadata
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    seed_plans()


def seed_plans() -> None:
    """Idempotent plan catalog (plan v3.0 §12 — prices in toman; price_rial = ×10)."""
    from sqlmodel import select
    from app.models import Plan

    catalog: list[dict] = [
        dict(key="basic", name_fa="پایه", subtitle_fa="آغاز شناخت", price_toman=149_000,
             features=["چارت تولد تعاملی + SVG", "سه‌گانه‌ی اصلی (خورشید، ماه، طالع)",
                       "۵ بخش اصلی گزارش", "دانلود PDF"], sort=1),
        dict(key="full", name_fa="کامل", subtitle_fa="شناخت عمیق", price_toman=349_000,
             features=["همه‌ی امکانات پایه", "هر ۱۳ حوزه‌ی تفسیر با شواهد نجومی",
                       "گزارش PDF + Word", "نمودارهای SVG اختصاصی", "استعلام سیناستری"], sort=2),
        dict(key="gold", name_fa="طلایی", subtitle_fa="مشاوره‌ی اختصاصی", price_toman=699_000,
             features=["همه‌ی امکانات کامل", "فصل فرهنگی-اسلامی", "نقشه‌ی گذرهای ۴ ماه آینده",
                       "هوش مصنوعی چت سوال‌پاسخ", "اولویت تولید"], sort=3),
        dict(key="synastry", name_fa="سیناستری", subtitle_fa="سازگاری دو چارت", price_toman=499_000,
             features=["نمره‌ی سازگاری ۴ حوزه‌ای", "۲۵+ ارتباط سیاره‌ای", "تفسیر اختصاصی"],
             sort=4),
        dict(key="monthly", name_fa="اشتراک ماهانه", subtitle_fa="گذرهای روزانه", price_toman=399_000,
             features=["گذرهای روزانه در ربات تلگرام/بله", "خلاصه‌ی هفتگی", "تمدید خودکار ۳۰ روزه"],
             sort=5),
    ]
    with Session(engine) as s:
        for item in catalog:
            existing = s.exec(select(Plan).where(Plan.key == item["key"])).first()
            if existing:
                # only update display fields, never overwrite runtime price edits
                existing.name_fa = item["name_fa"]
                existing.subtitle_fa = item["subtitle_fa"]
                existing.features = item["features"]
                existing.sort = item["sort"]
                s.add(existing)
            else:
                s.add(Plan(**item))
        s.commit()


def get_session():
    with Session(engine) as s:
        yield s


FILE: app/main.py  (1316 lines)
======================================================================
"""Chart Platform — FastAPI app (Phase 2: free product).

Routes: landing, birth form, chart compute (sync), chart page, city search.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

import app.config  # noqa: F401 — load .env FIRST
from app.auth import get_current_user, request_otp, set_user_cookie, verify_otp
from app.security import security_guard
from app.astrology.big_three import big_three
from app.astrology.cities_ir import search_cities
from app.astrology.engine import compute_from_fields
from app.astrology.svg_wheel import render_chart_svg
from app.bots.handler import TELEGRAM_WEBHOOK_SECRET, handle_update
from app.chat.service import chat_answer
from app.db import engine, get_session, init_db
from app.models import (AuditLog, BirthProfile, Chart, Coupon, LLMRun, Order, Plan,
                        PromptVersion, ReferralEvent, Report, Subscription, User)

BALE_WEBHOOK_SECRET = os.getenv("BALE_WEBHOOK_SECRET", "")
from datetime import datetime, timezone
from app.payment.zarinpal import ZarinpalClient, ZarinpalError

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

PLANS_SEED = [
    Plan(key="basic", name_fa="پایه", subtitle_fa="آغاز شناخت",
         price_toman=149_000, sort=1, active=True,
         features=["چارت تولد تعاملی + SVG", "سهگانهی اصلی (خورشید، ماه، طالع)",
                   "۵ بخش اصلی گزارش", "دانلود PDF"]),
    Plan(key="full", name_fa="کامل", subtitle_fa="گزارش ۱۳ بخشی اختصاصی",
         price_toman=349_000, sort=2, active=True,
         features=["همهی امکانات پایه", "گزارش کامل ۱۳ حوزهی زندگی",
                   "تحلیل جنبهها و خانهها", "دانلود PDF ۲۵+ صفحهای"]),
    Plan(key="gold", name_fa="طلایی", subtitle_fa="شناخت عمیق + پشتیبانی",
         price_toman=699_000, sort=3, active=True,
         features=["همهی امکانات کامل", "مشاورهی هوشمند (AI Chat)",
                   "بهروزرسانیهای آینده رایگان", "اولویت در صف تولید"]),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as s:
        for p in PLANS_SEED:
            if s.get(Plan, p.key) is None:
                s.add(p)
        s.commit()
    yield
    await _close_arq_pool()


app = FastAPI(title="چارت تولد", lifespan=lifespan)
app.middleware("http")(security_guard)   # security.py: CSRF origin check + rate limits
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/sw.js")
def sw_file():
    """Service worker at ROOT scope (PWA — plan §13.9)."""
    from fastapi.responses import FileResponse
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


# ─────────────────────────── pages ───────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing(request: Request, ref: str = ""):
    resp = templates.TemplateResponse(request, "index.html", {"title": "چارت تولد — آینهی خودشناسی", "ref": ref})
    if ref and len(ref) <= 20:
        resp.set_cookie("chart_ref", ref, max_age=7 * 86400, httponly=True, samesite="lax")
    return resp


@app.get("/birth-form", response_class=HTMLResponse)
def birth_form_page(request: Request):
    return templates.TemplateResponse(request, "form.html", {"title": "فرم تولد"})


@app.get("/chart/{chart_id}", response_class=HTMLResponse)
def chart_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    bt = big_three(chart.chart_json)
    svg = render_chart_svg(chart.chart_json)
    from app.astrology.svg_widgets import aspect_grid_svg, element_donut_svg, house_bar_svg
    planets = chart.chart_json.get("planets", {})
    houses = {}
    sign_counts = {}
    for _p in planets.values():
        _h = _p.get("house")
        if _h:
            houses[_h] = houses.get(_h, 0) + 1
        _s = _p.get("sign_fa", "")
        if _s:
            sign_counts[_s] = sign_counts.get(_s, 0) + 1   # audit P1-6: real counts per sign
    return templates.TemplateResponse(request, "chart.html", {
        "title": "چارت تولد", "chart": chart, "big_three": bt, "svg": svg,
        "aspect_grid": aspect_grid_svg(planets),
        "element_donut": element_donut_svg(sign_counts),
        "house_bar": house_bar_svg(houses),
    })


# ─────────────────────────── api ───────────────────────────

@app.get("/api/cities")
def api_cities(q: str = Query(default="", max_length=50), limit: int = 10):
    return {"results": search_cities(q, limit)}


@app.post("/api/charts")
def api_create_chart(
    request: Request,
    session: Session = Depends(get_session),
    calendar: str = Form("jalali"),
    year: int = Form(...),
    month: int = Form(...),
    day: int = Form(...),
    time_known: bool = Form(False),
    hour: int | None = Form(None),
    minute: int | None = Form(None),
    city_fa: str | None = Form(None),
    province_fa: str | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    name: str = Form(""),
    zodiac: str = Form("tropical"),  # tropical | sidereal (Vedic / Lahiri)
    focus_areas: str | None = Form(None),  # comma-separated
):
    """Compute chart (sync, fast) + cache. Returns chart_id."""
    chart, profile = _compute_and_save_chart(
        session, request,
        calendar=calendar, year=year, month=month, day=day,
        time_known=time_known, hour=hour, minute=minute,
        city_fa=city_fa, province_fa=province_fa, lat=lat, lon=lon,
        name=name, zodiac=zodiac, focus_areas=focus_areas,
    )
    session.add(chart)
    session.commit()
    session.refresh(chart)
    return JSONResponse({
        "chart_id": chart.id,
        "profile_id": profile.id,
        "utc": chart.chart_json["birth"]["utc_time"],
        "engine_config": chart.chart_json["engine_config"],
    })


def _compute_and_save_chart(
    session: Session, request: Request,
    calendar: str, year: int, month: int, day: int,
    time_known: bool, hour: int | None, minute: int | None,
    city_fa: str | None, province_fa: str | None,
    lat: float | None, lon: float | None,
    name: str, zodiac: str, focus_areas: str | None = None,
    user_id: str | None = None,
) -> tuple[Chart, BirthProfile]:
    """Shared chart computation + persistence (charts API, synastry orders, bots)."""
    if calendar not in ("jalali", "gregorian"):
        raise HTTPException(400, "calendar must be jalali|gregorian")
    if zodiac not in ("tropical", "sidereal"):
        raise HTTPException(400, "zodiac must be tropical|sidereal")
    if year < 1300 or year > 2100:
        raise HTTPException(400, "year out of range")
    # audit P1-9: sanitize free-text inputs that flow into the LLM prompt
    name = (name or "").strip()[:60]
    focus_areas = (focus_areas or "").strip()[:120]

    if lat is None or lon is None:
        city = search_cities(city_fa or "", 1)
        if not city:
            raise HTTPException(400, "city not found")
        lat, lon = city[0]["lat"], city[0]["lon"]
        province_fa = province_fa or city[0]["province_fa"]

    profile = BirthProfile(
        calendar_system=calendar,
        raw_year=year, raw_month=month, raw_day=day,
        time_known=time_known, hour=hour, minute=minute,
        city_fa=city_fa, province_fa=province_fa, lat=lat, lon=lon,
        name=name,
        focus_areas=[a.strip() for a in (focus_areas or "").split(",") if a.strip()],
        user_id=user_id or (get_current_user(request).id if get_current_user(request) else None),
    )
    assert lat is not None and lon is not None
    try:
        result = compute_from_fields(
            lat=lat, lon=lon, year=year, month=month, day=day,
            hour=hour if time_known else 12,
            minute=minute if time_known else 0,
            time_known=time_known, jalali=(calendar == "jalali"),
            tz_name="Asia/Tehran", zodiac=zodiac,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    from datetime import datetime as _dt
    profile.utc_datetime = _dt.strptime(result.chart_json["birth"]["utc_time"], "%Y-%m-%d %H:%M:%S")
    session.add(profile)
    session.flush()
    chart = Chart(profile_id=profile.id, chart_json=result.chart_json,
                  engine_config=result.chart_json["engine_config"])
    return chart, profile


# ─────────────────────────── report (Phase 3) ───────────────────────────

def _report_gate(rep, session, request) -> bool:
    """Paid-order gate + ownership (audit P0-3): a registered user may only
    download reports of charts linked to their own birth profile."""
    paid = session.exec(
        select(Order).where(Order.chart_id == rep.chart_id, Order.status == "paid")
    ).first()
    if not paid:
        return False
    chart = session.get(Chart, rep.chart_id)
    if chart and chart.profile_id:
        prof = session.get(BirthProfile, chart.profile_id)
        if prof and prof.user_id:
            u = get_current_user(request)
            if not u or u.id != prof.user_id:
                return False
    return True


_REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_ARQ_POOL = None  # shared ARQ pool (created lazily on first enqueue)


async def _arq_pool():
    """Shared ARQ pool (audit P1: pool-per-request was wasteful)."""
    global _ARQ_POOL
    if _ARQ_POOL is None:
        from arq import create_pool
        from arq.connections import RedisSettings
        _ARQ_POOL = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
    return _ARQ_POOL


async def _close_arq_pool():
    global _ARQ_POOL
    if _ARQ_POOL is not None:
        try:
            await _ARQ_POOL.aclose()
        except Exception:  # noqa: BLE001
            pass
        _ARQ_POOL = None


def _enqueue_report(report_id: str) -> bool:
    """Enqueue ARQ job via the shared pool; False if Redis/worker unavailable."""
    try:
        import asyncio
        asyncio.run(_enqueue_async(report_id))
        return True
    except Exception:  # noqa: BLE001
        return False


async def _enqueue_async(report_id: str) -> None:
    pool = await _arq_pool()
    await pool.enqueue_job("generate_report", report_id)


@app.post("/api/charts/{chart_id}/report")
def api_create_report(chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    # plan v3.0 §8/§12: report generation happens AFTER payment — plan_key drives section set
    paid = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    if not paid:
        raise HTTPException(403, "برای تولید گزارش، ابتدا پلن را خریداری کنید")
    rep = Report(chart_id=chart_id, status="queued", plan_key=paid.plan_key or "full")
    session.add(rep)
    session.commit()
    session.refresh(rep)
    ok = _enqueue_report(rep.id)
    if not ok:
        rep.status = "failed"
        rep.error = "queue unavailable (worker not running)"
        session.commit()
    return {"report_id": rep.id, "status": rep.status, "queued": ok, "plan_key": rep.plan_key}


@app.get("/api/charts/{chart_id}/preview")
def api_chart_preview(chart_id: str, session: Session = Depends(get_session)):
    """Free 3-5 rule-based insights (plan v3.0 §8) — no LLM, no payment."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.report.preview import free_insights
    return free_insights(chart.chart_json)


@app.get("/api/charts/{chart_id}/transit-year.svg")
def api_transit_year_svg(chart_id: str, session: Session = Depends(get_session)):
    """Annual transit timeline widget (plan §9.3) — deterministic, no LLM."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.astrology.svg_widgets import transit_timeline_svg
    from fastapi.responses import Response
    return Response(transit_timeline_svg(chart.chart_json), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/charts/{chart_id}/report")
def api_report_status(chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    rep = session.exec(
        select(Report).where(Report.chart_id == chart_id).order_by(Report.created_at.desc())
    ).first()
    if not rep:
        return {"report_id": None, "status": "none"}
    return {
        "report_id": rep.id,
        "status": rep.status,
        "error": rep.error,
        "metrics": rep.metrics,
        "sections_count": len(rep.sections or {}),
        "pdf_url": f"/api/reports/{rep.id}/pdf" if rep.status == "done" else None,
    }


@app.get("/api/reports/{report_id}.docx")
def api_report_docx(report_id: str, request: Request,
                    session: Session = Depends(get_session)):
    rep = session.get(Report, report_id)
    if not rep or rep.status != "done":
        raise HTTPException(404, "report not ready")
    # gate: paid order + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "برای دانلود گزارش، ابتدا خرید کنید")
    from app.report.word import report_to_docx
    title = "گزارش اختصاصی چارت تولد"
    sections = {k: {"title": (v or {}).get("title", k), "content": (v or {}).get("content", "")}
                for k, v in (rep.sections or {}).items()}
    data = report_to_docx({"title": title, "intro": "گزارش اختصاصی چارت تولد — تولید شده توسط موتور نجومی Swiss Ephemeris", "sections": sections})
    from fastapi.responses import Response
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=chart-report-{report_id[:8]}.docx"})


@app.get("/api/reports/{report_id}/pdf")
def api_report_pdf(report_id: str, request: Request,
                   session: Session = Depends(get_session)):
    rep = session.get(Report, report_id)
    if not rep or rep.status != "done" or not rep.pdf_path:
        raise HTTPException(404, "report not ready")
    # gate: paid order on this chart + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "برای دانلود گزارش، ابتدا خرید کنید")
    from app.storage import presigned_url
    r2_url = presigned_url(rep.r2_key) if rep.r2_key else None
    if r2_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(r2_url, status_code=302)
    from fastapi.responses import FileResponse
    return FileResponse(rep.pdf_path, media_type="application/pdf",
                        filename=f"report-{report_id[:8]}.pdf")


# ─────────────────────────── commercial (Phase 4) ───────────────────────────

@app.get("/plans", response_class=HTMLResponse)
def plans_page(request: Request, session: Session = Depends(get_session)):
    plans = session.exec(select(Plan).where(Plan.active).order_by(Plan.sort)).all()
    return templates.TemplateResponse(request, "plans.html", {
        "title": "تعرفهها", "plans": plans,
    })


@app.get("/payment/result", response_class=HTMLResponse)
def payment_result_page(request: Request, order_id: str,
                        session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    plan = session.get(Plan, order.plan_key) if order.plan_key else None
    return templates.TemplateResponse(request, "payment_result.html", {
        "title": "نتیجهی پرداخت", "order": order, "plan": plan,
    })


@app.get("/api/plans")
def api_plans(session: Session = Depends(get_session)):
    plans = session.exec(select(Plan).where(Plan.active).order_by(Plan.sort)).all()
    return [{"key": p.key, "name_fa": p.name_fa, "subtitle_fa": p.subtitle_fa,
             "price_toman": p.price_toman, "features": p.features} for p in plans]


@app.post("/api/orders")
def api_create_order(
    request: Request,
    plan_key: str = Form(...),
    chart_id: str = Form(...),
    coupon: str | None = Form(None),
    secondary_chart_id: str | None = Form(None),
    chat_id: str | None = Form(None),
    platform: str | None = Form(None),
    session: Session = Depends(get_session),
):
    """Create order + payment URL (shared helper — also used by bots)."""
    from app.payment.orders import create_order
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    user = get_current_user(request)
    try:
        order, pay_url = create_order(
            session, plan_key, chart_id,
            secondary_chart_id=secondary_chart_id, chat_id=chat_id, platform=platform,
            coupon=coupon, ref_code=request.cookies.get("chart_ref", ""),
            new_user_id=user.id if user else None,
        )
    except LookupError:
        raise HTTPException(404, "plan not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"order_id": order.id, "payment_url": pay_url, "authority": order.authority}


@app.get("/api/orders/{order_id}")
def api_order_status(order_id: str, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    return {"order_id": order.id, "status": order.status, "ref_id": order.ref_id,
            "report_id": order.report_id}


@app.get("/api/payments/verify")
def api_payment_verify(
    request: Request,
    Authority: str = Query(default=""),
    Status: str = Query(default=""),
    session: Session = Depends(get_session),
):
    """Zarinpal callback — verify + mark order paid, then redirect to result page."""
    order = session.exec(select(Order).where(Order.authority == Authority)).first()
    if not order:
        raise HTTPException(404, "order not found for authority")

    # idempotency (audit P0-1): duplicate callback / refresh must NOT re-verify,
    # re-extend subscription or re-consume coupon — already-paid orders just redirect.
    if order.status == "paid":
        return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)

    if Status == "OK":
        client = ZarinpalClient()
        try:
            v = client.verify(Authority, order.amount_rial)
            order.status = "paid"
            order.ref_id = v["ref_id"]
            order.card_pan = v.get("card_pan")
            from datetime import datetime, timezone
            order.paid_at = datetime.now(timezone.utc)
            # consume coupon (idempotent — only once per order)
            if order.coupon_id:
                c = session.get(Coupon, order.coupon_id)
                if c and c.used_count < c.max_uses:
                    c.used_count += 1
            # monthly subscription: activate + extend 30 days (plan §7)
            from app.payment.orders import REPORT_PLANS, activate_subscription
            if order.plan_key == "monthly":
                activate_subscription(session, order)
            # auto-generate report for report plans (basic/full/gold — NOT synastry/sub)
            if order.plan_key in REPORT_PLANS and order.chart_id and not order.report_id:
                rep = Report(chart_id=order.chart_id, status="queued",
                             plan_key=order.plan_key)
                session.add(rep)
                session.flush()
                order.report_id = rep.id
            session.commit()
            # enqueue AFTER commit (audit P0-2): worker must see the committed row;
            # if queue is unavailable, mark failed so admin "regenerate" can retry.
            if order.report_id:
                rep = session.get(Report, order.report_id)
                if rep and rep.status == "queued":
                    if not _enqueue_report(rep.id):
                        rep.status = "failed"
                        rep.error = "queue unavailable at payment time — از ادمین بازتولید کنید"
                        session.add(rep)
                        session.commit()
        except ZarinpalError:
            order.status = "failed"
            session.commit()
    else:
        order.status = "failed"
        session.commit()

    return RedirectResponse(f"/payment/result?order_id={order.id}", status_code=303)


@app.get("/sitemap.xml")
def sitemap_xml():
    import os
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
    urls = ["/", "/plans", "/birth-form", "/synastry", "/rectify", "/learn", "/privacy",
            "/guide", "/about", "/faq", "/articles",
            "/learn/birth-chart", "/learn/big-three", "/learn/transit",
            "/learn/sun", "/learn/moon", "/learn/venus", "/learn/mars",
            "/learn/jupiter", "/learn/saturn", "/learn/1", "/learn/7", "/learn/10"]
    urls += [f"/signs/{s}" for s in ("hamal", "sowr", "jowza", "sartan", "asad", "sowza",
                                      "mizan", "aghrab", "ghows", "jadi", "dalv", "hout")]
    try:
        urls += [f"/articles/{a['slug']}" for a in _load_articles()]
    except Exception:
        pass
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        body += f'  <url><loc>{base}{u}</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>\n'
    body += "</urlset>\n"
    from fastapi.responses import Response
    return Response(content=body, media_type="application/xml")


@app.get("/robots.txt")
def robots_txt():
    import os
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.example.com").rstrip("/")
    from fastapi.responses import Response
    return Response(content=f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n",
                    media_type="text/plain")


@app.get("/api/share/{chart_id}.png")
def api_share_card(chart_id: str, request: Request,
                   session: Session = Depends(get_session)):
    if not _rate_limit(f"share:{_rl_client(request)}", 15, 60):
        raise HTTPException(429, "درخواست زیاد است")
    """OG share card (1200×630) — rendered + cached on first request."""
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.share.card import render_share_card
    from fastapi.responses import FileResponse
    path = render_share_card(chart.chart_json, chart_id)
    return FileResponse(path, media_type="image/png")


@app.post("/api/admin/coupons")
def admin_coupon_create(request: Request, session: Session = Depends(get_session),
                        code: str = Form(...), percent: int = Form(...), max_uses: int = Form(1)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if not (0 < percent <= 100):
        raise HTTPException(400, "percent must be 1-100")
    c = Coupon(code=code.strip().upper(), percent=percent, max_uses=max_uses)
    session.add(c)
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "coupon.create", c.code, f"{percent}%")
    return {"ok": True, "id": c.id, "code": c.code}


# ── prompt overrides (plan v3.0 §8 — مدیریت پرامپتها) ─────────────────────────
PROMPT_KEYS = ["identity", "mind", "emotions", "career", "money", "love", "health",
               "family", "social", "spirit", "life_path", "strength", "karma", "cultural"]


@app.get("/api/admin/prompts")
def admin_prompts_list(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from app.report.prompt_overrides import get_overrides
    active = get_overrides()
    rows = session.exec(select(PromptVersion).order_by(
        PromptVersion.prompt_key, PromptVersion.version.desc())).all()
    seen: set[str] = set()
    out = []
    for r in rows:  # latest version per key (rows are desc by version)
        if r.prompt_key in seen:
            continue
        seen.add(r.prompt_key)
        out.append({"key": r.prompt_key, "version": r.version,
                    "is_active": r.is_active,
                    "content": r.content if r.is_active else None})
    # keys without any override yet
    missing = [k for k in PROMPT_KEYS if k not in seen]
    return {"keys": [o["key"] for o in out] + missing,
            "overrides": out, "active": active}


@app.post("/api/admin/prompts/{prompt_key}")
def admin_prompt_save(request: Request, prompt_key: str, session: Session = Depends(get_session),
                      content: str = Form(...)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    if prompt_key not in PROMPT_KEYS:
        raise HTTPException(400, "unknown prompt key")
    from app.report.prompt_overrides import set_override
    row = set_override(session, prompt_key, content)
    from app.security import audit
    audit(session.bind, "admin", "prompt.update", prompt_key, f"v{row.version} ({len(content)} chars)")
    return {"ok": True, "key": prompt_key, "version": row.version}


@app.post("/api/admin/orders/{order_id}/refund")
def admin_refund(order_id: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if order.status != "paid":
        raise HTTPException(400, "فقط سفارش پرداخت‌شده ریفاند می‌شود")
    order.status = "refunded"
    if order.coupon_id:
        c = session.get(Coupon, order.coupon_id)
        if c and c.used_count > 0:
            c.used_count -= 1
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "order.refund", order.id, order.ref_id or "")
    return {"ok": True, "status": "refunded"}


@app.post("/api/admin/orders/{order_id}/regenerate")
def admin_regenerate(order_id: str, request: Request, session: Session = Depends(get_session)):
    """Re-run a failed report from admin (plan v3.0 §8 — بازتولید گزارش)."""
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    if order.status != "paid":
        raise HTTPException(400, "فقط سفارش پرداخت‌شده بازتولید می‌شود")
    chart = session.get(Chart, order.chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    rep = session.exec(select(Report).where(Report.chart_id == order.chart_id).order_by(
        Report.created_at.desc())).first()
    if not rep:
        raise HTTPException(404, "report not found")
    if rep.status == "done":
        raise HTTPException(400, "گزارش آماده است — برای اجرای مجدد اول حذفش کنید")
    rep.status = "queued"
    rep.error = None
    session.add(rep)
    session.commit()
    ok = _enqueue_report(rep.id)
    if not ok:
        rep.status = "failed"
        rep.error = "queue unavailable (worker not running)"
        session.commit()
        raise HTTPException(503, "worker در دسترس نیست — بعداً دوباره تلاش کنید")
    from app.security import audit
    audit(session.bind, "admin", "report.regenerate", rep.id, f"order={order.id} chart={chart.id}")
    return {"ok": True, "report_id": rep.id, "status": "queued"}


@app.get("/api/admin/coupons", response_class=JSONResponse)
def admin_coupons(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    return [{"id": c.id, "code": c.code, "percent": c.percent, "max_uses": c.max_uses,
             "used_count": c.used_count, "active": c.active} for c in session.exec(select(Coupon)).all()]


# ─────────────────────────── synastry / rectify / audio (Phases 8-9) ───────────────

@app.get("/synastry", response_class=HTMLResponse)
def synastry_page(request: Request):
    return templates.TemplateResponse(request, "synastry.html", {"title": "سازگاری دو چارت"})


@app.post("/api/synastry")
def api_synastry(request: Request, session: Session = Depends(get_session),
                 name_a: str = Form(""), year_a: int = Form(...), month_a: int = Form(...),
                 day_a: int = Form(...), hour_a: int = Form(12), minute_a: int = Form(0),
                 city_a: str = Form(None), calendar_a: str = Form("jalali"),
                 name_b: str = Form(""), year_b: int = Form(...), month_b: int = Form(...),
                 day_b: int = Form(...), hour_b: int = Form(12), minute_b: int = Form(0),
                 city_b: str = Form(None), calendar_b: str = Form("jalali")):
    if not _rate_limit(f"synastry:{_rl_client(request)}", 10, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    """Free teaser (plan §8): score + verdict only. Full analysis is a paid product."""
    from app.astrology.synastry import synastry
    city_a = search_cities(city_a or "", 1)
    city_b = search_cities(city_b or "", 1)
    if not city_a or not city_b:
        raise HTTPException(400, "شهرها را انتخاب کنید")
    ca = compute_from_fields(city_a[0]["lat"], city_a[0]["lon"], year_a, month_a, day_a,
                             hour_a, minute_a, True, calendar_a == "jalali", "Asia/Tehran")
    cb = compute_from_fields(city_b[0]["lat"], city_b[0]["lon"], year_b, month_b, day_b,
                             hour_b, minute_b, True, calendar_b == "jalali", "Asia/Tehran")
    r = synastry(ca.chart_json, cb.chart_json)
    return {
        "a": name_a or "شخص اول", "b": name_b or "شخص دوم",
        "score": r["overall"], "verdict": r["verdict"], "free": True, "full_locked": True,
    }


@app.post("/api/synastry/order")
def api_synastry_order(request: Request, session: Session = Depends(get_session),
                       name_a: str = Form(""), year_a: int = Form(...), month_a: int = Form(...),
                       day_a: int = Form(...), hour_a: int = Form(12), minute_a: int = Form(0),
                       city_a: str = Form(None), calendar_a: str = Form("jalali"),
                       name_b: str = Form(""), year_b: int = Form(...), month_b: int = Form(...),
                       day_b: int = Form(...), hour_b: int = Form(12), minute_b: int = Form(0),
                       city_b: str = Form(None), calendar_b: str = Form("jalali")):
    """Save both charts + create the paid synastry order (plan §8, ~499k toman)."""
    from app.payment.orders import create_order
    chart_a, _ = _compute_and_save_chart(
        session, request, calendar=calendar_a, year=year_a, month=month_a, day=day_a,
        time_known=True, hour=hour_a, minute=minute_a, city_fa=city_a,
        province_fa=None, lat=None, lon=None, name=name_a, zodiac="tropical")
    chart_b, _ = _compute_and_save_chart(
        session, request, calendar=calendar_b, year=year_b, month=month_b, day=day_b,
        time_known=True, hour=hour_b, minute=minute_b, city_fa=city_b,
        province_fa=None, lat=None, lon=None, name=name_b, zodiac="tropical")
    session.add(chart_a); session.add(chart_b)
    session.commit(); session.refresh(chart_a); session.refresh(chart_b)
    user = get_current_user(request)
    try:
        order, pay_url = create_order(
            session, "synastry", chart_a.id, secondary_chart_id=chart_b.id,
            coupon=None, ref_code="", new_user_id=user.id if user else None,
        )
    except (LookupError, ValueError) as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"order_id": order.id, "payment_url": pay_url,
            "chart_a": chart_a.id, "chart_b": chart_b.id}


@app.post("/api/synastry/full")
def api_synastry_full(chart_a: str = Form(...), chart_b: str = Form(...),
                      session: Session = Depends(get_session)):
    """Full synastry report — requires a paid synastry order for the pair."""
    from app.astrology.synastry import synastry
    ca = session.get(Chart, chart_a)
    cb = session.get(Chart, chart_b)
    if not ca or not cb:
        raise HTTPException(404, "chart not found")
    paid = session.exec(
        select(Order).where(
            Order.plan_key == "synastry", Order.status == "paid",
            Order.chart_id == chart_a, Order.secondary_chart_id == chart_b,
        )
    ).first()
    if not paid:
        raise HTTPException(403, "برای مشاهدهی تحلیل کامل، ابتدا سیناستری را خریداری کنید")
    return synastry(ca.chart_json, cb.chart_json)


@app.get("/api/synastry/access")
def api_synastry_access(chart_a: str, chart_b: str, session: Session = Depends(get_session)):
    paid = session.exec(
        select(Order).where(
            Order.plan_key == "synastry", Order.status == "paid",
            Order.chart_id == chart_a, Order.secondary_chart_id == chart_b,
        )
    ).first()
    return {"full": bool(paid)}


@app.get("/rectify", response_class=HTMLResponse)
def rectify_page(request: Request):
    return templates.TemplateResponse(request, "rectify.html", {"title": "یافتن ساعت تولد"})


@app.post("/api/rectify")
def api_rectify(request: Request, city_fa: str = Form(...), year: int = Form(...), month: int = Form(...),
                day: int = Form(...), calendar: str = Form("jalali"),
                events_json: str = Form(...)):  # [["marriage",2019,6,12], ...]
    if not _rate_limit(f"rectify:{_rl_client(request)}", 6, 300):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    import json as _json
    from app.astrology.rectify import rectify_birth_time
    city = search_cities(city_fa, 1)
    if not city:
        raise HTTPException(400, "شهر پیدا نشد")
    try:
        events = [_json.loads(x) if isinstance(x, str) else x for x in _json.loads(events_json)]
        events = [(e[0], int(e[1]), int(e[2]), int(e[3])) for e in events if len(e) >= 4]
    except Exception:
        raise HTTPException(400, "فرمت رویدادها نامعتبر است")
    if not events:
        raise HTTPException(400, "حداقل یک رویداد لازم است")
    r = rectify_birth_time(city[0]["lat"], city[0]["lon"], year, month, day, events,
                           jalali=calendar == "jalali")
    return {"best_time": r.best_time, "score": r.score, "candidates": r.candidates,
            "events_used": r.events_used, "details": r.details}


@app.get("/api/reports/{report_id}/audio")
def api_report_audio(report_id: str, request: Request,
                     session: Session = Depends(get_session)):
    rep = session.get(Report, report_id)
    if not rep or rep.status != "done":
        raise HTTPException(404, "report not ready")
    # gate: paid order + ownership (audit P0-3)
    if not _report_gate(rep, session, request):
        raise HTTPException(403, "برای دریافت فایل صوتی، ابتدا خرید کنید")
    import asyncio
    import time as _time
    from pathlib import Path as _P
    # audit P1: /tmp hygiene — drop audio cache files older than 24h
    try:
        _cut = _time.time() - 86400
        for _f in _P("/tmp").glob("report-audio-*.mp3"):
            if _f.stat().st_mtime < _cut:
                _f.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    out = _P("/tmp") / f"report-audio-{report_id[:8]}.mp3"
    if not out.exists():
        text = "گزارش اختصاصی چارت تولد. "
        for k, v in (rep.sections or {}).items():
            t = (v or {}).get("title", k)
            c = (v or {}).get("content", "")
            text += f"بخش {t}. {' '.join(str(c).split())[:800]} "
            if len(text) > 9000:
                break
        try:
            import edge_tts
            async def _gen():
                tts = edge_tts.Communicate(text, "fa-IR-DilaraNeural", rate="+0%")
                await tts.save(str(out))
            asyncio.run(_gen())
        except Exception as e:
            raise HTTPException(502, f"تولید صوت ممکن نیست: {e}")
    from fastapi.responses import FileResponse
    return FileResponse(str(out), media_type="audio/mpeg",
                        filename=f"chart-report-{report_id[:8]}.mp3")


@app.get("/learn", response_class=HTMLResponse)
def learn_index(request: Request):
    from app.seo.content import GUIDES, PLANETS, HOUSES
    return templates.TemplateResponse(request, "seo_index.html", {
        "title": "آموزش چارت تولد — مقالات نجومی",
        "guides": GUIDES, "planets": PLANETS, "houses": HOUSES,
    })


@app.get("/learn/{slug}", response_class=HTMLResponse)
def learn_page(request: Request, slug: str):
    from app.seo.content import GUIDES, PLANETS, HOUSES, SIGNS
    page = GUIDES.get(slug) or PLANETS.get(slug) or HOUSES.get(slug) or (
        next((s for s in SIGNS.values() if s["slug"] == slug), None))
    if not page:
        raise HTTPException(404, "not found")
    return templates.TemplateResponse(request, "seo_page.html", {
        "title": page["title"], "page": page, "slug": slug,
        "meta_description": (page.get("keywords") or page.get("title")),
    })


@app.get("/signs/{slug}", response_class=HTMLResponse)
def sign_page(request: Request, slug: str):
    from app.seo.content import SIGNS
    sign = next((s for s in SIGNS.values() if s["slug"] == slug), None)
    if not sign:
        raise HTTPException(404, "not found")
    return templates.TemplateResponse(request, "seo_page.html", {
        "title": sign["title"], "page": sign, "slug": slug,
        "meta_description": sign["keywords"],
    })


# ─────────────────────────── SEO (Phase 8) ───────────────────────────


@app.get("/chat/{chart_id}", response_class=HTMLResponse)
def chat_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    return templates.TemplateResponse(request, "chat.html", {
        "title": "گفت‌وگو با چارت", "chart_id": chart_id,
    })


@app.get("/api/chat/access/{chart_id}")
def api_chat_access(chart_id: str, session: Session = Depends(get_session)):
    # audit P0-4: AI chat is a GOLD/monthly feature (plan §7) — basic/full don't include it
    order = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    allowed = bool(order and order.plan_key in ("gold", "monthly"))
    return {"allowed": allowed}


@app.post("/api/chat")
def api_chat(
    request: Request,
    chart_id: str = Form(...),
    question: str = Form(..., max_length=500),
    session: Session = Depends(get_session),
):
    if not _rate_limit(f"chat:{_rl_client(request)}", 20, 60):
        raise HTTPException(429, "درخواست زیاد است؛ کمی بعد دوباره تلاش کن")
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    # paid check: chat requires GOLD/monthly (audit P0-4 — plan §7)
    order = session.exec(
        select(Order).where(Order.chart_id == chart_id, Order.status == "paid")
    ).first()
    if not order or order.plan_key not in ("gold", "monthly"):
        raise HTTPException(403, "گفت‌وگو با هوش مصنوعی مخصوص پلن طلایی است")

    profile = session.get(BirthProfile, chart.profile_id) if chart.profile_id else None
    report = session.exec(
        select(Report).where(Report.chart_id == chart_id).order_by(Report.created_at.desc())
    ).first()

    result = chat_answer(
        question, chart.chart_json,
        report_sections=(report.sections if report and report.sections else None),
        focus_areas=(profile.focus_areas if profile else None),
    )
    return result


@app.get("/api/charts/{chart_id}/transits")
def api_chart_transits(chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.astrology.transits import compute_transits
    return {"events": compute_transits(chart.chart_json)}


@app.get("/transit/{chart_id}", response_class=HTMLResponse)
def transit_page(request: Request, chart_id: str, session: Session = Depends(get_session)):
    chart = session.get(Chart, chart_id)
    if not chart:
        raise HTTPException(404, "chart not found")
    from app.astrology.transits import compute_transits
    return templates.TemplateResponse(request, "transit.html", {
        "title": "گذرهای کنونی", "chart_id": chart_id,
        "events": compute_transits(chart.chart_json),
    })


# ─────────────────────────── bots (Phase 6) ───────────────────────────

_seen_update_ids: set = set()
_MAX_SEEN = 10_000

# ── audit P1-8: lightweight per-IP rate limit for expensive endpoints ──
_RL: dict = {}


def _rate_limit(key: str, limit: int, window: float = 60.0) -> bool:
    import time as _t
    now = _t.time()
    w = _RL.get(key)
    if not w or now - w[0] > window:
        _RL[key] = [now, 1]
        return True
    if w[1] >= limit:
        return False
    w[1] += 1
    return True


def _rl_client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _dedupe_update(update: dict) -> bool:
    """audit P0-5: return True if this update_id was already processed (retry)."""
    uid = update.get("update_id")
    if uid is None:
        return False
    if uid in _seen_update_ids:
        return True
    _seen_update_ids.add(uid)
    if len(_seen_update_ids) > _MAX_SEEN:      # bounded memory
        _seen_update_ids.clear()
    return False


@app.post("/api/v1/telegram/webhook")
async def telegram_webhook(request: Request):
    # audit P0: fail-closed — without a configured secret the route refuses
    if not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403, "telegram webhook not configured (fail-closed)")
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403, "bad secret")
    update = await request.json()
    if _dedupe_update(update):
        return {"ok": True}
    try:
        await handle_update(update, "telegram")
    except Exception:  # noqa: BLE001 — a bot error must never cause endless TG retries
        pass
    return {"ok": True}


@app.post("/api/v1/bale/webhook/{secret}")
async def bale_webhook(secret: str, request: Request):
    # audit P0: Bale has no secret_token header support (v140 pitfall), so the
    # shared secret lives in the URL path — the webhook must be registered as
    # https://chart.negar.io/api/v1/bale/webhook/<BALE_WEBHOOK_SECRET>
    if not BALE_WEBHOOK_SECRET or not _hmac.compare_digest(secret, BALE_WEBHOOK_SECRET):
        raise HTTPException(403, "bad webhook secret")
    update = await request.json()
    if _dedupe_update(update):
        return {"ok": True}
    try:
        await handle_update(update, "bale")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ─────────────────────────── auth (lazy OTP — plan §4) ───────────────────────────

@app.post("/api/auth/otp/request")
def auth_otp_request(phone: str = Form(...)):
    if not phone or len(phone) < 10:
        raise HTTPException(400, "شماره موبایل معتبر نیست")
    try:
        return request_otp(phone)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/auth/otp/verify")
def auth_otp_verify(request: Request, phone: str = Form(...), code: str = Form(...)):
    u = verify_otp(phone, code)
    if not u:
        raise HTTPException(401, "کد نادرست یا منقضی شده")
    return set_user_cookie(request, u.id)


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = get_current_user(request)
    if not u:
        return {"user": None}
    return {"user": {"id": u.id, "phone": u.phone, "role": u.role}}


@app.post("/api/auth/logout")
def auth_logout():
    from fastapi.responses import RedirectResponse
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request, session: Session = Depends(get_session)):
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login", status_code=303)
    profiles = session.exec(select(BirthProfile).where(BirthProfile.user_id == u.id)).all()
    profile_ids = [p.id for p in profiles]
    charts = session.exec(
        select(Chart).where(Chart.profile_id.in_(profile_ids)).order_by(Chart.created_at.desc())
    ).all() if profile_ids else []
    chart_ids = [c.id for c in charts]
    reports = session.exec(
        select(Report).where(Report.chart_id.in_(chart_ids)).order_by(Report.created_at.desc())
    ).all() if chart_ids else []
    orders = session.exec(
        select(Order).where(Order.profile_id.in_(profile_ids)).order_by(Order.created_at.desc())
    ).all() if profile_ids else []
    return templates.TemplateResponse(request, "account.html", {
        "title": "حساب کاربری", "user": u, "profiles": profiles,
        "charts": charts, "reports": reports, "orders": orders,
        "ref_url": f"{os.getenv('PUBLIC_BASE_URL', 'https://chart.negar.io')}/?ref={u.phone}",
    })


@app.get("/account/login", response_class=HTMLResponse)
def account_login_page(request: Request):
    return templates.TemplateResponse(request, "account_login.html", {"title": "ورود"})


@app.post("/account/delete", response_class=HTMLResponse)
def account_delete(request: Request, session: Session = Depends(get_session)):
    u = get_current_user(request)
    if not u:
        return RedirectResponse("/account/login", status_code=303)
    from app.security import audit
    audit(session.bind, u.phone or u.id, "account.delete", u.id)
    for p in session.exec(select(BirthProfile).where(BirthProfile.user_id == u.id)).all():
        for c in session.exec(select(Chart).where(Chart.profile_id == p.id)).all():
            session.delete(c)
        session.delete(p)
    session.delete(u)
    session.commit()
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("chart_user")
    return resp


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {"title": "حریم خصوصی"})


# ─── content pages (guide / about / faq) + articles ───

def _load_pages() -> dict:
    import json as _json
    from pathlib import Path as _P
    return _json.loads(_P("/root/chart-platform/app/content/pages.json").read_text("utf-8"))


def _load_articles() -> list[dict]:
    import json as _json
    from pathlib import Path as _P
    p = _P("/root/chart-platform/app/content/articles.json")
    return _json.loads(p.read_text("utf-8")) if p.exists() else []


@app.get("/guide", response_class=HTMLResponse)
def page_guide(request: Request):
    data = _load_pages()["guide"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@app.get("/about", response_class=HTMLResponse)
def page_about(request: Request):
    data = _load_pages()["about"]
    return templates.TemplateResponse(request, "page.html", {
        "title": data["title"], "meta": data.get("meta", ""),
        "sections": data["sections"], "hero": data["title"],
    })


@app.get("/faq", response_class=HTMLResponse)
def page_faq(request: Request):
    data = _load_pages()["faq"]
    return templates.TemplateResponse(request, "faq.html", {
        "title": data["title"], "meta": data.get("meta", ""), "items": data["items"],
    })


@app.get("/articles", response_class=HTMLResponse)
def page_articles(request: Request):
    arts = _load_articles()
    return templates.TemplateResponse(request, "articles_index.html", {
        "title": "مقالات نجوم و چارت تولد",
        "meta": "مجموعه مقالات آموزشی نجوم، چارت تولد، سیارات، برج‌ها و تحلیل شخصیت — به زبان ساده",
        "articles": arts,
    })


@app.get("/articles/{slug}", response_class=HTMLResponse)
def page_article(slug: str, request: Request):
    arts = _load_articles()
    art = next((a for a in arts if a["slug"] == slug), None)
    if not art:
        raise HTTPException(404, "article not found")
    from app.seo.article_banner import article_banner_svg
    return templates.TemplateResponse(request, "article.html", {
        "title": art["title"], "meta": art.get("meta", ""), "art": art,
        "banner_svg": article_banner_svg(art.get("category", ""), art["title"]),
        "others": [a for a in arts if a["slug"] != slug][:6],
    })


# ─────────────────────────── admin dashboard (Phase 5) ───────────────────────────

import hashlib
import hmac as _hmac
import secrets as _secrets

_ADMIN_PIN: str = os.getenv("ADMIN_PIN") or ""
if not _ADMIN_PIN:
    raise RuntimeError("ADMIN_PIN is required (audit P0: no default admin PIN)")
_ADMIN_COOKIE = "chart_admin"
_ADMIN_SECRET: str = os.getenv("ADMIN_SECRET") or ""
if not _ADMIN_SECRET:
    if os.getenv("APP_ENV", "dev") == "prod":
        raise RuntimeError("ADMIN_SECRET is required (set APP_ENV=prod)")
    _ADMIN_SECRET = _secrets.token_hex(16)


def _admin_cookie_value() -> str:
    return _hmac.new(_ADMIN_SECRET.encode(), _ADMIN_PIN.encode(), hashlib.sha256).hexdigest()


def _is_admin(request: Request) -> bool:
    return _hmac.compare_digest(request.cookies.get(_ADMIN_COOKIE, ""), _admin_cookie_value())


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"title": "ورود مدیریت"})


@app.post("/admin/login")
def admin_login(request: Request, pin: str = Form(...), session: Session = Depends(get_session)):
    # audit P1: brute-force throttle — 5 tries / 5 min per IP
    if not _rate_limit(f"admin-login:{_rl_client(request)}", 5, 300):
        return templates.TemplateResponse(request, "admin_login.html", {
            "title": "ورود مدیریت", "error": "تلاش‌های زیاد؛ ۵ دقیقه بعد دوباره امتحان کنید",
        }, status_code=429)
    if not _hmac.compare_digest(pin, _ADMIN_PIN):
        return templates.TemplateResponse(request, "admin_login.html", {
            "title": "ورود مدیریت", "error": "رمز نادرست است",
        }, status_code=401)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(_ADMIN_COOKIE, _admin_cookie_value(), httponly=True, max_age=12 * 3600,
                    samesite="lax")
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(_ADMIN_COOKIE)
    return resp


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    orders = session.exec(select(Order).order_by(Order.created_at.desc()).limit(100)).all()
    reports = session.exec(select(Report).order_by(Report.created_at.desc()).limit(20)).all()
    users = session.exec(select(User).order_by(User.created_at.desc()).limit(50)).all()
    plans = session.exec(select(Plan).order_by(Plan.sort)).all()
    audit = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(30)).all()
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    llm = session.exec(select(LLMRun).where(LLMRun.created_at >= week_ago)).all()
    llm_cost = round(sum(r.cost_usd for r in llm), 4)
    paid = [o for o in orders if o.status == "paid"]
    revenue = sum(o.amount_rial for o in paid) / 10  # toman
    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1
    return templates.TemplateResponse(request, "admin.html", {
        "title": "دشبورد مدیریت", "orders": orders, "reports": reports,
        "revenue_toman": revenue, "by_status": by_status,
        "users": users, "plans": plans, "audit": audit,
        "llm_cost_7d": llm_cost, "llm_runs_7d": len(llm),
        "prompt_keys": PROMPT_KEYS,
        "prompt_overrides": [{"key": o["key"], "version": o["version"],
                              "is_active": o["is_active"], "content": o["content"]}
                             for o in admin_prompts_list(request, session)["overrides"]],
    })


@app.put("/api/admin/plans/{plan_key}")
def api_admin_plan_update(plan_key: str, request: Request, session: Session = Depends(get_session),
                          price_toman: int | None = Form(None), active: bool | None = Form(None)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    plan = session.get(Plan, plan_key)
    if not plan:
        raise HTTPException(404, "plan not found")
    if price_toman is not None and price_toman > 0:
        plan.price_toman = price_toman
    if active is not None:
        plan.active = active
    session.add(plan)
    session.commit()
    from app.security import audit
    audit(session.bind, "admin", "plan.update", plan.key, f"{plan.price_toman} toman active={plan.active}")
    return {"ok": True}


@app.get("/api/admin/llm-cost")
def api_admin_llm_cost(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403, "admin only")
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    rows = session.exec(select(LLMRun).where(LLMRun.created_at >= week_ago)).all()
    by_provider: dict[str, float] = {}
    for r in rows:
        by_provider[r.provider] = by_provider.get(r.provider, 0) + r.cost_usd
    return {"cost_usd_7d": round(sum(r.cost_usd for r in rows), 4),
            "runs_7d": len(rows), "by_provider": {k: round(v, 4) for k, v in by_provider.items()}}


@app.get("/api/admin/stats")
def api_admin_stats(session: Session = Depends(get_session)):
    orders = session.exec(select(Order)).all()
    paid = [o for o in orders if o.status == "paid"]
    return {
        "orders_total": len(orders),
        "orders_paid": len(paid),
        "revenue_toman": sum(o.amount_rial for o in paid) / 10,
        "reports_done": len(session.exec(select(Report).where(Report.status == "done")).all()),
    }


FILE: app/models.py  (209 lines)
======================================================================
"""Database models (plan v3.1 §7) — users → birth_profiles → charts.

Gender is OPTIONAL (Claude review #6): NULL-safe, never affects computation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=_uuid, primary_key=True)
    phone: str | None = Field(default=None, unique=True, index=True)  # OTP login (lazy)
    email: str | None = Field(default=None, unique=True)
    password_hash: str | None = Field(default=None)
    role: str = Field(default="user")  # user | admin
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BirthProfile(SQLModel, table=True):
    """One person per profile — user can have many (self/mother/spouse/friend → synastry)."""
    __tablename__ = "birth_profiles"
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    name: str = Field(default="")
    gender: str | None = Field(default=None)  # OPTIONAL — never used in computation
    # raw input (auditable)
    calendar_system: str = Field(default="jalali")  # jalali | gregorian
    raw_year: int
    raw_month: int
    raw_day: int
    time_known: bool = Field(default=False)
    hour: int | None = Field(default=None)
    minute: int | None = Field(default=None)
    # location
    city_fa: str | None = Field(default=None)
    province_fa: str | None = Field(default=None)
    lat: float | None = Field(default=None)
    lon: float | None = Field(default=None)
    tz_name: str = Field(default="Asia/Tehran")
    utc_datetime: datetime | None = Field(default=None)  # computed
    focus_areas: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    personal_question: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chart(SQLModel, table=True):
    """Canonical Chart JSON (deterministic, cached) + engine config snapshot."""
    __tablename__ = "charts"
    id: str = Field(default_factory=_uuid, primary_key=True)
    profile_id: str | None = Field(default=None, foreign_key="birth_profiles.id", index=True)
    chart_json: dict = Field(sa_column=Column(JSONB))          # canonical output
    engine_config: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # snapshot
    svg_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMRun(SQLModel, table=True):
    """Cost/usage metering per report call (Claude review #7)."""
    __tablename__ = "llm_runs"
    id: str = Field(default_factory=_uuid, primary_key=True)
    report_id: str | None = Field(default=None, index=True)
    provider: str
    model: str
    gateway: str | None = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    latency_ms: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    ok: bool = Field(default=True)
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Report(SQLModel, table=True):
    """Generated 13-section report (sections + metrics + PDF artifact)."""
    __tablename__ = "reports"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chart_id: str = Field(default=None, foreign_key="charts.id", index=True)
    status: str = Field(default="queued")  # queued | running | done | failed
    plan_key: str | None = Field(default=None)   # section set: basic|full|gold (plan v3.0 §10.3)
    sections: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    pdf_path: str | None = Field(default=None)
    r2_key: str | None = Field(default=None)   # R2 object key (reports/<id>.pdf) when uploaded
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Plan(SQLModel, table=True):
    """Sellable report plans (Phase 4 — commercial)."""
    __tablename__ = "plans"
    key: str = Field(primary_key=True)  # basic | full | gold
    name_fa: str
    subtitle_fa: str = Field(default="")
    price_toman: int  # e.g. 149_000 (تومان) — stored for display
    features: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    sort: int = Field(default=0)
    active: bool = Field(default=True)

    @property
    def price_rial(self) -> int:
        """Zarinpal v4 amount unit = Rial (ریال)."""
        return self.price_toman * 10


class Order(SQLModel, table=True):
    """Payment order — one per (profile, plan) purchase."""
    __tablename__ = "orders"
    id: str = Field(default_factory=_uuid, primary_key=True)
    profile_id: str | None = Field(default=None, foreign_key="birth_profiles.id", index=True)
    chart_id: str | None = Field(default=None, foreign_key="charts.id", index=True)
    plan_key: str = Field(default=None, foreign_key="plans.key", index=True)
    amount_rial: int
    status: str = Field(default="pending")  # pending | paid | failed | expired
    coupon_id: str | None = Field(default=None, foreign_key="coupons.id")
    authority: str | None = Field(default=None, index=True)
    ref_id: str | None = Field(default=None)
    card_pan: str | None = Field(default=None)
    report_id: str | None = Field(default=None, index=True)  # linked once generated
    secondary_chart_id: str | None = Field(default=None, index=True)  # synastry pair (plan §8)
    chat_id: str | None = Field(default=None, index=True)             # bot subscription (plan §7)
    platform: str | None = Field(default=None)                        # telegram | bale
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: datetime | None = Field(default=None)


class Coupon(SQLModel, table=True):
    __tablename__ = "coupons"
    id: str = Field(default_factory=_uuid, primary_key=True)
    code: str = Field(unique=True, index=True)
    percent: int = Field(default=0)          # discount percent (0-100)
    max_uses: int = Field(default=1)
    used_count: int = Field(default=0)
    expires_at: datetime | None = Field(default=None)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_id: str = Field(index=True)
    platform: str = Field(default="telegram")   # telegram | bale
    chart_id: str = Field(index=True)
    freq: str = Field(default="daily")          # daily | weekly
    plan_key: str = Field(default="monthly")    # paid monthly plan (plan v3.0 §12)
    active: bool = Field(default=True)
    expires_at: datetime | None = Field(default=None)
    last_sent_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReferralEvent(SQLModel, table=True):
    __tablename__ = "referral_events"
    id: str = Field(default_factory=_uuid, primary_key=True)
    code: str = Field(index=True)            # referrer's phone
    referrer_user_id: str | None = Field(default=None)
    new_user_id: str | None = Field(default=None)
    order_id: str | None = Field(default=None, index=True)
    amount_rial: int = Field(default=0)
    reward_rial: int = Field(default=0)
    status: str = Field(default="pending")   # pending | rewarded
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PromptVersion(SQLModel, table=True):
    """Admin-editable prompt overrides (plan v3.0 §8 — مدیریت پرامپتها).
    One active row per prompt_key; save() bumps version."""
    __tablename__ = "prompt_versions"
    id: str = Field(default_factory=_uuid, primary_key=True)
    prompt_key: str = Field(index=True)      # domain key (identity..karma) or "cultural"
    version: int = Field(default=1)
    content: str
    is_active: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    id: int | None = Field(default=None, primary_key=True)
    admin: str = ""
    action: str = ""
    entity: str = ""
    details: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BotState(SQLModel, table=True):
    """Per-chat bot state machine row (v135 pattern)."""
    __tablename__ = "bot_chat_states"
    __table_args__ = (UniqueConstraint("platform", "chat_id", name="uq_botstate_platform_chat"),)
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    platform: str = Field(index=True)  # telegram | bale
    chat_id: int = Field(index=True)
    state: str = ""
    payload: str | None = None  # JSON
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


FILE: app/payment/orders.py  (118 lines)
======================================================================
"""Shared order creation + subscription activation (plan v3.0 §7/§8/§12).

Used by BOTH the web API and the Telegram/Bale bots so pricing, coupon,
referral and payment flows stay in one place.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import Coupon, Order, Plan, ReferralEvent, Report, Subscription, User


def create_order(
    session: Session,
    plan_key: str,
    chart_id: str,
    secondary_chart_id: str | None = None,
    chat_id: str | None = None,
    platform: str | None = None,
    coupon: str | None = None,
    ref_code: str = "",
    new_user_id: str | None = None,
) -> tuple[Order, str]:
    """Create a pending order + request Zarinpal authority. Returns (order, pay_url)."""
    from app.payment.zarinpal import ZarinpalClient, ZarinpalError

    plan = session.get(Plan, plan_key)
    if not plan or not plan.active:
        raise LookupError("plan not found")

    amount = plan.price_rial
    coupon_row = None
    if coupon:
        coupon_row = session.exec(
            select(Coupon).where(Coupon.code == coupon.strip().upper())
        ).first()
        if not coupon_row or not coupon_row.active:
            raise ValueError("کد تخفیف نامعتبر است")
        if coupon_row.expires_at and coupon_row.expires_at < datetime.now(timezone.utc):
            raise ValueError("کد تخفیف منقضی شده")
        if coupon_row.used_count >= coupon_row.max_uses:
            raise ValueError("کد تخفیف مصرف شده")
        amount = max(1, int(amount * (100 - coupon_row.percent) / 100))

    referral_event = None
    if ref_code and not coupon_row:
        existing = session.exec(
            select(Order).where(Order.chart_id == chart_id, Order.status != "failed")
        ).first()
        referrer = session.exec(select(User).where(User.phone == ref_code)).first()
        if not existing and referrer:
            amount = max(1, int(amount * 0.9))
            referral_event = ReferralEvent(
                code=ref_code, referrer_user_id=referrer.id, new_user_id=new_user_id,
                amount_rial=amount, reward_rial=int(amount * 0.05), status="pending",
            )
            session.add(referral_event)
            session.flush()

    order = Order(chart_id=chart_id, profile_id=None, plan_key=plan.key,
                  amount_rial=amount, status="pending",
                  coupon_id=coupon_row.id if coupon_row else None,
                  secondary_chart_id=secondary_chart_id,
                  chat_id=chat_id, platform=platform)
    session.add(order)
    session.flush()
    if referral_event:
        referral_event.order_id = order.id

    public_base = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8767")
    callback_url = f"{public_base}/api/payments/verify"

    client = ZarinpalClient()
    try:
        authority, pay_url = client.request(
            order.amount_rial, callback_url,
            f"خرید {plan.name_fa}",
            {"mobile": new_user_id or ""},
        )
    except ZarinpalError as e:
        order.status = "failed"
        session.commit()
        raise RuntimeError(f"درگاه پرداخت در دسترس نیست: {e}") from e

    order.authority = authority
    session.commit()
    return order, pay_url


def activate_subscription(session: Session, order: Order) -> None:
    """After a paid monthly order: activate/refresh the chat subscription."""
    if not order.chat_id or not order.chart_id:
        return
    sub = session.exec(
        select(Subscription).where(
            Subscription.chat_id == order.chat_id,
            Subscription.chart_id == order.chart_id,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if sub:
        sub.active = True
        sub.expires_at = now + timedelta(days=30)
        sub.plan_key = order.plan_key
        sub.platform = order.platform or sub.platform
    else:
        session.add(Subscription(
            chat_id=order.chat_id, platform=order.platform or "telegram",
            chart_id=order.chart_id, freq="daily", plan_key=order.plan_key,
            active=True, expires_at=now + timedelta(days=30),
        ))


REPORT_PLANS = {"basic", "full", "gold"}


FILE: app/payment/zarinpal.py  (81 lines)
======================================================================
"""Zarinpal v4 payment client — sandbox + production.

Docs: https://www.zarinpal.com/docs/paymentGateway/connectToGateway
Sandbox: any UUID works as merchant_id; authorities start with "S".
Amount unit: Rial (ریال) — multiply Toman prices by 10.
"""
from __future__ import annotations

import logging
import os
import uuid

import httpx

log = logging.getLogger("zarinpal")

SANDBOX_BASE = "https://sandbox.zarinpal.com/pg/v4"
PROD_BASE = "https://payment.zarinpal.com/pg/v4"
SANDBOX_PAY = "https://sandbox.zarinpal.com/pg/StartPay"
PROD_PAY = "https://payment.zarinpal.com/pg/StartPay"


class ZarinpalError(Exception):
    pass


class ZarinpalClient:
    def __init__(self, merchant_id: str | None = None, sandbox: bool | None = None):
        self.merchant_id = merchant_id or os.getenv("ZARINPAL_MERCHANT_ID", "")
        if not self.merchant_id:
            raise ZarinpalError("ZARINPAL_MERCHANT_ID is not set")
        self.sandbox = sandbox if sandbox is not None else os.getenv("ZARINPAL_SANDBOX", "true").lower() == "true"
        self.base = SANDBOX_BASE if self.sandbox else PROD_BASE
        self.pay_base = SANDBOX_PAY if self.sandbox else PROD_PAY
        self.timeout = float(os.getenv("ZARINPAL_TIMEOUT", "15"))

    def request(self, amount_rial: int, callback_url: str, description: str,
                metadata: dict | None = None) -> tuple[str, str]:
        """Create a transaction. Returns (authority, payment_url)."""
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_rial,
            "callback_url": callback_url,
            "description": description,
            "metadata": metadata or {},
        }
        r = httpx.post(f"{self.base}/payment/request.json", json=payload,
                       headers={"Accept": "application/json"}, timeout=self.timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        errs = data.get("errors") or []
        if errs:
            raise ZarinpalError(f"request failed: {errs}")
        d = data.get("data") or {}
        if d.get("code") != 100:
            raise ZarinpalError(f"request code {d.get('code')}: {d.get('message')}")
        authority = d["authority"]
        return authority, f"{self.pay_base}/{authority}"

    def verify(self, authority: str, amount_rial: int) -> dict:
        """Verify a payment after callback. Returns {ref_id, card_pan} on success."""
        payload = {
            "merchant_id": self.merchant_id,
            "authority": authority,
            "amount": amount_rial,
        }
        r = httpx.post(f"{self.base}/payment/verify.json", json=payload,
                       headers={"Accept": "application/json"}, timeout=self.timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        errs = data.get("errors") or []
        if errs:
            raise ZarinpalError(f"verify failed: {errs}")
        d = data.get("data") or {}
        code = d.get("code")
        if code not in (100, 101):  # 101 = already verified (idempotent retry)
            raise ZarinpalError(f"verify code {code}: {d.get('message')}")
        return {"ref_id": d.get("ref_id", ""), "card_pan": d.get("card_pan", "")}


def fake_authority() -> str:
    return "S" + uuid.uuid4().hex[:32].upper()


FILE: app/report/generator.py  (106 lines)
======================================================================
"""
Report generator — orchestrates the full pipeline (plan v3.1 §6):

Chart JSON → Rule Engine → Prompts → LLM (LLMRouter) → JSON → QA → sections
→ PDF render. Logs cost/tokens/calls per report (Claude review #7).

Phase 3: synchronous worker (ARQ queue comes in the same phase, see worker.py).
"""
from __future__ import annotations

import json
import logging
import time

from app.core.llm import build_router
from app.report.prompt_builder import build_all_prompts, build_prompts_for_plan
from app.report.qa import parse_section, qa_repetition, qa_section

log = logging.getLogger("report")

MAX_RETRIES = 2


def generate_sections(chart: dict, max_tokens: int = 4096, router=None,
                      plan_key: str = "full") -> tuple[dict[str, dict], dict]:
    """Run the plan's section set through the LLM + QA (plan v3.0 §10.3)."""
    router = router or build_router()
    prompts = build_prompts_for_plan(chart, plan_key)
    sections: dict[str, dict] = {}
    metrics = {
        "calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
        "qa_failures": 0, "provider": set(),
    }

    for domain, (prompt, ctx) in prompts.items():
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            res = await_complete(router, prompt, max_tokens)
            metrics["calls"] += 1
            metrics["total_tokens"] += res.usage.total
            metrics["cost_usd"] += res.cost
            metrics["provider"].add(res.provider)
            if not res.ok:
                metrics["retries"] += 1
                continue

            section = parse_section(res.text)
            if section is not None:
                errors = qa_section(section, chart, domain)
            else:
                errors = ["خروجی JSON نامعتبر است"]
            if not errors:
                sections[domain] = section
                ok = True
                break
            metrics["qa_failures"] += 1
            log.warning("QA fail %s (attempt %d): %s", domain, attempt, errors[:2])
            if attempt < MAX_RETRIES:
                metrics["retries"] += 1

        if not ok:
            # last resort: minimal deterministic fallback (never empty section)
            sections[domain] = {
                "section": domain,
                "title_fa": ctx["domain_title"],
                "intro": "بر اساس عوامل محاسبهشده، این حوزه از زندگی اهمیت ویژهای دارد.",
                "insights": [{
                    "insight": "نقشهی نجومی این حوزه را میتوان با دقت بیشتری در گزارش تکمیلی بررسی کرد. "
                               "عوامل فعال: " + (ctx["factors"].replace("\n", " — ")[:200]),
                    "evidence": [],
                    "strengths": [], "challenges": [],
                    "practical_advice": "برای تفسیر دقیقتر، به گزارش کامل مراجعه کنید.",
                }],
            }

    # cross-section repetition check (informational — does not fail the report)
    rep = qa_repetition(sections)
    if rep:
        log.info("repetition warnings: %s", rep[:3])

    metrics["provider"] = sorted(metrics["provider"])
    return sections, metrics


def await_complete(router, prompt: str, max_tokens: int):
    """Sync wrapper over the async LLMRouter (worker will be async later)."""
    import asyncio
    return asyncio.run(router.complete(prompt, max_tokens=max_tokens, temperature=0.6, json_mode=True))


def build_report_json(chart: dict, sections: dict[str, dict], metrics: dict) -> dict:
    """Assemble the final structured report (stored + rendered)."""
    return {
        "chart": chart,
        "sections": sections,
        "metrics": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "calls": metrics.get("calls", 0),
            "retries": metrics.get("retries", 0),
            "total_tokens": metrics.get("total_tokens", 0),
            "cost_usd": round(metrics.get("cost_usd", 0.0), 6),
            "providers": sorted(metrics.get("provider", [])) if isinstance(metrics.get("provider"), (set, list)) else [],
            "qa_failures": metrics.get("qa_failures", 0),
        },
    }


FILE: app/report/preview.py  (79 lines)
======================================================================
"""Free insights preview (plan v3.0 §8) — deterministic rule-engine teaser.

3-5 short insights derived from the ACTIVE RULES (no LLM, no cost, instant).
Powers POST /api/charts/{id}/preview and the chart page "اینسایتهای رایگان".
"""
from __future__ import annotations

from app.astrology.big_three import big_three
from app.astrology.svg_wheel import PLANET_FA
from app.report.rules import DOMAINS, evaluate

_TITLE = {
    "identity": "هویت و شخصیت",
    "mind": "ذهن و منطق",
    "emotions": "عواطف و شهود",
    "money": "پول و ثروت",
    "career": "شغل و مسیر حرفهای",
    "relationships": "روابط و ازدواج",
    "family": "خانواده و ریشهها",
    "wellbeing": "انرژی و تندرستی",
    "creativity": "فرزند و خلاقیت",
    "education": "آموزش و مهاجرت",
    "network": "شبکهها و دوستان",
    "spirituality": "معنویت",
    "karma": "الگوهای رشد و کارما",
}

_PRIORITY = ["identity", "mind", "emotions", "career", "money"]


def _insight_text(domain: str, rec: dict) -> str:
    """Human-readable one-liner from the active rule record (deterministic)."""
    detail = rec.get("detail") or {}
    factor = PLANET_FA.get(rec.get("factor", ""), rec.get("factor", ""))
    sign = detail.get("sign_fa") or ""
    house = detail.get("house")
    aspect = detail.get("aspect")
    if aspect and isinstance(aspect, str):
        return f"{factor} — جنبهی «{aspect}» با عامل مهمی در «{_TITLE.get(domain, domain)}» فعال است."
    if sign and house:
        return f"{factor} در برج {sign} و خانهی {house} — عامل اصلی حوزهی «{_TITLE.get(domain, domain)}»."
    if sign:
        return f"{factor} در برج {sign} — تأثیرگذار بر حوزهی «{_TITLE.get(domain, domain)}»."
    return f"عامل «{factor}» در حوزهی «{_TITLE.get(domain, domain)}» فعال است."


def free_insights(chart: dict, limit: int = 5) -> dict:
    """Top N domains by active-rule count (priority tiebreak) → 1-line insight each."""
    active = evaluate(chart)
    ranked = sorted(
        active.items(),
        key=lambda kv: (len(kv[1]) if kv[1] else 0,
                        -_PRIORITY.index(kv[0]) if kv[0] in _PRIORITY else 99),
        reverse=True,
    )
    bt = big_three(chart)
    teaser = {
        "sun": bt.get("Sun", {}).get("sign_fa", ""),
        "moon": bt.get("Moon", {}).get("sign_fa", ""),
        "asc": bt.get("ASC", {}).get("sign_fa", ""),
    }
    out = []
    for domain, rules in ranked:
        if not rules or len(out) >= limit:
            continue
        rec = rules[0]
        out.append({
            "domain": domain,
            "domain_title": _TITLE.get(domain, domain),
            "rule_id": rec.get("rule_id", ""),
            "factor": rec.get("factor", ""),
            "insight": _insight_text(domain, rec),
        })
    return {
        "big_three": teaser,
        "insights": out,
        "full_report_teaser": "گزارش کامل، هر ۱۳ حوزهی زندگی را با تحلیل عمیق و راهکارهای عملی پوشش میدهد.",
    }


FILE: app/report/prompt_builder.py  (170 lines)
======================================================================
"""Prompt Builder — sends ONLY relevant factors (not the whole chart) to the LLM.
(Claude review #4: retrieval-based, cost + quality.)

Per domain: active rules → compact factor block → Persian writing instruction.
The LLM is the WRITER; every position it cites comes from this block.
"""
from __future__ import annotations

from app.astrology.big_three import big_three
from app.report.rules import DOMAINS, evaluate

SECTION_TEMPLATE = """تو نویسندهی حرفهای گزارش چارت تولد به زبان فارسی هستی.

# قوانین طلایی
- فقط از اطلاعات بخش «عوامل محاسبهشده» استفاده کن. هرگز درجه/خانه/برج/جنبه را حدس نزن یا جعل نکن.
- لحن: دلسوز، دقیق، غیرقضاوتی. «آینهی خودشناسی» — هرگز ادعای قطعی دربارهی آینده، مرگ، بیماری یا غیب نکن.
- از عبارات مطلق (حتماً، قطعاً، همیشه) پرهیز کن. بهجای آن: «به احتمال»، «ممکن است»، «در مسیر رشد».
- هر بینش باید با حداقل یک «شاهد» از عوامل محاسبهشده همراه باشد: (سیاره، برج، خانه) یا (جنبه، اورب).
- ادعای پزشکی ممنوع: تشخیص، درمان، دارو. «انرژی و تندرستی» فقط سبک زندگی است.
- پاسخ فقط JSON معتبر — بدون مقدمه و بدون مارک‌داون.

# عوامل محاسبهشده (فقط اینها را استفاده کن)
{factors_block}

# اطلاعات مکمل
- فاز ماه: {moon_phase}
- Big Three: {big_three}

# خروجی JSON برای بخش «{domain_title}»
{{
  "section": "{domain_key}",
  "title_fa": "{domain_title}",
  "intro": "2-3 جمله معرفی بخش با توجه به عوامل فعال",
  "insights": [
    {{
      "insight": "تحلیل عمیق 4-6 جمله‌ای با ارجاع صریح به عوامل",
      "evidence": [{{"factor": "Venus", "sign": "Libra", "house": 2}}],
      "strengths": ["نقطه قوت 1", "نقطه قوت 2"],
      "challenges": ["چالش 1", "چالش 2"],
      "practical_advice": "یک پیشنهاد عملی مشخص"
    }}
  ]
}}
بخش باید 4 تا 6 insight داشته باشد و جمعاً 700-1000 کلمه فارسی عمیق و خوانا.
هر insight: ابتدا تحلیل 5-7 جمله‌ای با ارجاع صریح به عوامل، سپس نقاط قوت/چالش و یک پیشنهاد عملی مشخص.
نثر روان، ادبی و انسانی باشد — نه فهرستی و نه تکراری.
"""


def factors_block(chart: dict, domain: str, active: list[dict]) -> str:
    """Compact, human-readable factor block for one domain."""
    lines = []
    for r in active:
        d = r.get("detail") or {}
        parts = []
        if d.get("sign_fa"):
            parts.append(f"برج {d['sign_fa']}")
        if d.get("house"):
            parts.append(f"خانه {d['house']}")
        if d.get("degree") is not None:
            parts.append(f"{d['degree']} درجه")
        if d.get("retrograde"):
            parts.append("رتروگرید")
        if d.get("phase"):
            parts.append(f"فاز {d['phase']}")
        line = f"- {r['factor']}: " + ("، ".join(parts) if parts else "فعال")
        lines.append(line)
    # aspects involving this domain's factors
    planets = chart.get("planets", {})
    aspects = chart.get("aspects", [])
    for a in aspects:
        if a["p1"] in {r["factor"] for r in active} or a["p2"] in {r["factor"] for r in active}:
            lines.append(f"- جنبه: {a['p1']} {a['aspect_fa']} {a['p2']} (اورب {a['orb']}°)")
    return "\n".join(lines) if lines else "- (عامل فعال خاصی ثبت نشده — بر اساس Big Three بنویس)"


def build_prompt(chart: dict, domain: str) -> tuple[str, dict]:
    """Return (prompt, context_dict) for one domain section."""
    active = evaluate(chart).get(domain, [])
    bt = big_three(chart)
    context = {
        "domain": domain,
        "domain_title": DOMAINS[domain],
        "active_rules": [r["rule_id"] for r in active],
        "factors": factors_block(chart, domain, active),
        "moon_phase": chart.get("moon_phase", ""),
        "big_three": bt,
        "time_unknown": not (chart.get("birth") or {}).get("time_known", True),
    }
    note = ""
    if context["time_unknown"]:
        # audit P0: no ASC/houses — the LLM must not infer them
        note = ("\n⚠️ ساعت تولد کاربر نامعلوم است؛ بنابراین طالع (ASC)، MC و خانه‌ها "
                "محاسبه نشده‌اند و در عوامل بالا وجود ندارند. هرگز در مورد طالع یا "
                "خانه‌ها چیزی ننویس و نگو «نمی‌توان گفت» — صرفاً از خورشید/ماه/سیارات "
                "استفاده کن. اگر بخش به خانه وابسته است، به جای آن از جنبه‌ها و "
                "برج‌های سیارات استفاده کن.")
    prompt = SECTION_TEMPLATE.format(
        factors_block=context["factors"],
        moon_phase=context["moon_phase"],
        big_three=context["big_three"],
        domain_title=context["domain_title"],
        domain_key=domain,
    ) + note
    return prompt, context


# ─── plan-based section sets (plan v3.0 §10.3/§12) ───────────────────────
CORE_DOMAINS = ["identity", "mind", "emotions", "career", "money"]

PLAN_SECTIONS = {
    "basic": CORE_DOMAINS,
    "full": list(DOMAINS),
    "gold": list(DOMAINS) + ["islamic"],
}

ISLAMIC_TEMPLATE = """تو نویسندهی فصل «فرهنگ و باورها» در یک گزارش خودشناسی به زبان فارسی هستی.

# قوانین طلایی این فصل (مهم‌ترین‌ها)
- این فصل **فرهنگی-معنوی** است، نه نجومی و نه فقهی. هیچ ادعایی درباره‌ی غیب، تقدیر قطعی، یا نظر شرعی قطعی نکن.
- «آینه‌ی خودشناسی»: از مفاهیم قرآن و سنت (شکر، توکل، صبر، توبه، عدل، مسئولیت) فقط به‌عنوان **چهارچوب رشد اخلاقی** استفاده کن — هرگز به‌عنوان حکم یا پیش‌گویی.
- احترام کامل: برای هر کس با هر باوری قابل‌خواندن باشد. مؤمن و غیرمؤمن هر دو باید آن را مفید بدانند.
- هیچ آیه‌ای را جعل نکن؛ اگر از آیه استفاده می‌کنی، مفاهیم مشهور و قطعی (مثل اهمیت توکل و صبر) را بدون نقل‌قول تحت‌اللفظی بیاور، یا بنویس «در سنت ما بر توکل و صبر تأکید شده است».
- ادعای پزشکی ممنوع. وعده‌ی مالی/شفای قطعی ممنوع.
- پاسخ فقط JSON معتبر — بدون مقدمه و بدون مارک‌داون.

# اطلاعات مکمل (برای شخصی‌سازی لحن — نه برای حدس زدن)
- Big Three: {big_three}
- فاز ماه: {moon_phase}

# خروجی JSON برای فصل «فرهنگ و باورها»
{{
  "section": "islamic",
  "title_fa": "فرهنگ و باورها — از منظر خودشناسی",
  "intro": "2-3 جمله: چرا این فصل جدا از تحلیل نجومی، با نگاه فرهنگی-معنوی نوشته شده است",
  "insights": [
    {{
      "insight": "4-6 جمله: پیوند ارزش‌های اخلاقی (توکل/صبر/شکر/مسئولیت) با الگوهای شخصیتی چارت — بدون ادعای غیب",
      "evidence": [{{"factor": "ارزش اخلاقی", "sign": "", "house": 0}}],
      "strengths": ["نقطه قوت اخلاقی 1", "نقطه قوت اخلاقی 2"],
      "challenges": ["چالش 1", "چالش 2"],
      "practical_advice": "یک اقدام عملی مشخص (مثلاً عادت شکرگزاری روزانه)"
    }}
  ]
}}
فصل باید 3 تا 5 insight داشته باشد و جمعاً 600-900 کلمه فارسی عمیق و انسانی — نه فهرستی و نه تکراری.
"""


def build_islamic_prompt(chart: dict) -> tuple[str, dict]:
    bt = big_three(chart)
    context = {"domain": "islamic", "domain_title": "فرهنگ و باورها — از منظر خودشناسی",
               "factors": "", "moon_phase": chart.get("moon_phase", ""), "big_three": bt}
    prompt = ISLAMIC_TEMPLATE.format(big_three=bt, moon_phase=context["moon_phase"])
    return prompt, context


def build_prompts_for_plan(chart: dict, plan_key: str | None = None) -> dict[str, tuple[str, dict]]:
    """Prompts for the plan's section set (plan v3.0 §10.3)."""
    domains = PLAN_SECTIONS.get(plan_key or "full", list(DOMAINS))
    prompts = {d: build_prompt(chart, d) for d in domains if d in DOMAINS}
    if "islamic" in domains:
        prompts["islamic"] = build_islamic_prompt(chart)
    return prompts


def build_all_prompts(chart: dict) -> dict[str, tuple[str, dict]]:
    """All 13 domain prompts (for queue processing)."""
    return build_prompts_for_plan(chart, "full")


FILE: app/report/prompt_overrides.py  (40 lines)
======================================================================
"""Admin prompt overrides (plan v3.0 §8 — مدیریت پرامپتها).

Worker merges active overrides into generated prompts at report time;
admin UI saves new versions. Never raises: generation must not break
if the table is missing or DB is down.
"""
from app.db import Session, engine
from app.models import PromptVersion
from sqlmodel import select


def get_overrides() -> dict[str, str]:
    """Active overrides: {prompt_key: content}. Empty dict on any failure."""
    try:
        with Session(engine) as s:
            rows = s.exec(select(PromptVersion).where(PromptVersion.is_active == True)).all()  # noqa: E712
            return {r.prompt_key: r.content for r in rows}
    except Exception:  # noqa: BLE001 — overrides are an enhancement, never a blocker
        return {}


def set_override(session, prompt_key: str, content: str) -> PromptVersion:
    """Bump version: deactivate old active row, insert new one. Returns new row."""
    from datetime import datetime, timezone

    old = session.exec(select(PromptVersion).where(
        PromptVersion.prompt_key == prompt_key,
        PromptVersion.is_active == True)).first()  # noqa: E712
    next_version = (old.version + 1) if old else 1
    if old:
        old.is_active = False
        session.add(old)
    row = PromptVersion(prompt_key=prompt_key, version=next_version,
                        content=content, is_active=True,
                        updated_at=datetime.now(timezone.utc))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


FILE: app/report/qa.py  (151 lines)
======================================================================
"""
Auto QA — every section must pass before it enters the report (plan v3.1 §6.4).

Checks: valid JSON, evidence grounded in Chart JSON, no invented factors,
no medical/fortune absolutes, min length, no boilerplate repetition.
"""
from __future__ import annotations

import json
import re

FORBIDDEN_PATTERNS = [
    # medical claims (تشخیص/بستری are common Persian verbs — too blunt to ban)
    r"درمان", r"دارو", r"بیماری", r"مرگ", r"فوت",
    # absolute fortune claims (حتما/همیشه/هرگز are common Persian adverbs)
    r"قطعاً", r"قطعی", r"یقیناً", r"مطمئناً", r"پیشگویی",
    # divination claims (غیب alone = "the unseen", poetic — ban only گویی/گو)
    r"غیبگویی", r"غیبگو", r"طلسم", r"جادو",
]

VALID_PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                 "Uranus", "Neptune", "Pluto", "Node", "Lilith", "Chiron",
                 "ASC", "MC", "Fortune", "Vertex", "Vx"}

ASPECT_NAMES = {"Conjunction", "Sextile", "Square", "Trine", "Opposition",
                "Quincunx", "SemiSquare", "Sesquiquadrate", "Trigon", "Parallel"}


def parse_section(raw: str) -> dict | None:
    """Robust JSON extraction (strip code fences, find first { ... })."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # find balanced JSON object
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def qa_section(section: dict | None, chart: dict, domain: str) -> list[str]:
    """Return list of QA failures (empty = pass)."""
    errors: list[str] = []
    if section is None:
        return ["خروجی JSON نامعتبر است"]

    insights = section.get("insights", [])
    if not isinstance(insights, list) or len(insights) < 2:
        errors.append(f"{domain}: تعداد insight کافی نیست ({len(insights)})")
    is_cultural = domain == "islamic"  # cultural chapter: evidence = values, not planets

    total_words = 0
    for ins in insights:
        text = ins.get("insight", "")
        if not isinstance(text, str) or len(text.split()) < 40:
            errors.append(f"{domain}: insight کوتاه است")
        total_words += len(text.split())

        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, text):
                errors.append(f"{domain}: عبارت ممنوع «{pat}» در متن")
                break

        # evidence groundedness
        for ev in ins.get("evidence", []):
            if is_cultural:
                if not ev:
                    errors.append(f"{domain}: evidence بدون عامل")
                continue
            if isinstance(ev, str):  # model wrote "Pluto Conjunction Node"
                f = ev.split()[0] if ev.split() else ""
            elif isinstance(ev, dict) and ev.get("aspect"):  # {"aspect": "Sun Conjunct ASC"}
                aparts = str(ev["aspect"]).split()
                f = aparts[0] if aparts else ""
                if len(aparts) >= 3 and aparts[0].title() in VALID_PLANETS and aparts[-1].title() in VALID_PLANETS \
                        and (aparts[-1].title() in chart.get("planets", {}) or aparts[-1].title() in chart.get("angles", {})):
                    pass  # valid aspect dict — both endpoints grounded
                elif len(aparts) < 3:
                    pass  # {"aspect": "Conjunction"} — supplementary, skip endpoint check
                else:
                    errors.append(f"{domain}: جنبه ناشناخته در evidence: {ev.get('aspect')}")
            else:
                f = ev.get("factor", "") if isinstance(ev, dict) else ""
            f = f.title() if isinstance(f, str) and f else f
            if not f:
                errors.append(f"{domain}: evidence بدون عامل")
            elif f == "Moon Phase" or f == "Phase":
                pass  # moon phase evidence — grounded in chart["moon_phase"]
            elif f not in VALID_PLANETS:
                # aspect-style string evidence: "Pluto Conjunction Node" or bare "Sextile"
                parts = f.split()
                if len(parts) >= 3 and parts[0] in VALID_PLANETS and parts[2] in VALID_PLANETS:
                    pass  # valid aspect string
                elif len(parts) == 1 and parts[0] in ASPECT_NAMES:
                    pass  # bare aspect name — supplementary evidence
                elif isinstance(ev, dict) and ev.get("p1") in VALID_PLANETS and ev.get("p2") in VALID_PLANETS:
                    pass  # valid aspect dict
                else:
                    errors.append(f"{domain}: عامل جعلی در evidence: {f}")
            elif f not in chart.get("planets", {}) and f not in chart.get("angles", {}):
                errors.append(f"{domain}: عامل {f} در چارت وجود ندارد")
            else:
                # verify sign/house if present
                src = chart["planets"].get(f) or chart["angles"].get(f)
                if isinstance(ev, dict) and "sign" in ev and ev["sign"] is not None:
                    if str(ev.get("sign")).lower() not in (
                            str(src.get("sign_en", "")).lower(),
                            str(src.get("sign_fa", "")).lower(),
                            str(src.get("sign_index", ""))):
                        errors.append(f"{domain}: برج نادرست در evidence برای {f}: {ev.get('sign')}")

    if total_words < 150:
        errors.append(f"{domain}: کل بخش کوتاه است ({total_words} کلمه)")

    return errors


def qa_repetition(sections: dict[str, dict]) -> list[str]:
    """Boilerplate check: identical sentences across sections."""
    errors = []
    sentences = {}
    for dom, sec in sections.items():
        if not sec:
            continue
        for ins in sec.get("insights", []):
            text = ins.get("insight", "")
            for s in re.split(r"[.؟!]", text):
                s = s.strip()
                if len(s) > 25:
                    sentences.setdefault(s, []).append(dom)
    for s, doms in sentences.items():
        if len(set(doms)) >= 3:
            errors.append(f"جمله تکراری در {len(set(doms))} بخش: «{s[:40]}…»")
    return errors


FILE: app/report/renderer.py  (152 lines)
======================================================================
"""
PDF renderer — WeasyPrint + Vazirmatn (RTL Persian report, plan v3.1 §6.5).

Deterministic: same report JSON → same PDF. No JS, no network fonts.
"""
from __future__ import annotations

import html
from pathlib import Path

from weasyprint import HTML

from app.astrology.big_three import big_three
from app.astrology.engine import fmt_lon
from app.report.rules import DOMAINS

FONT_DIR = Path(__file__).parent.parent / "static" / "fonts"

CSS = """
@page {
  size: A4;
  margin: 2cm 1.8cm;
  @bottom-center { content: counter(page) " / " counter(pages); font-family: Vazirmatn; font-size: 8pt; color: #999; }
}
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Regular.ttf"); font-weight: 400; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Medium.ttf"); font-weight: 500; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Bold.ttf"); font-weight: 700; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-ExtraBold.ttf"); font-weight: 800; }
* { box-sizing: border-box; }
body { font-family: Vazirmatn; font-size: 10.5pt; line-height: 2; color: #1a1a2e; direction: rtl; }
.cover { text-align: center; padding-top: 38%; }
.cover .title { font-size: 30pt; font-weight: 800; color: #3b2f80; margin-bottom: 8px; }
.cover .sub { font-size: 13pt; color: #666; margin-bottom: 30px; }
.cover .badge { display: inline-block; background: #efeaff; color: #2b2170; border-radius: 99px; padding: 4px 18px; font-size: 10pt; margin: 4px; font-weight: 600; }
h1.section { font-size: 17pt; font-weight: 800; color: #3b2f80; border-bottom: 2px solid #d5c9ff; padding-bottom: 6px; margin: 28px 0 12px; page-break-after: avoid; }
h2.insight { font-size: 12.5pt; font-weight: 700; color: #2a9d8f; margin: 16px 0 4px; page-break-after: avoid; }
.block { page-break-inside: avoid; margin: 8px 0; }
p { margin: 6px 0; text-align: justify; orphans: 3; widows: 3; }
.evidence { font-size: 8.5pt; color: #888; background: #f6f6fb; border-radius: 8px; padding: 4px 10px; margin: 4px 0; }
ul { margin: 4px 0; padding-right: 18px; list-style-position: inside; }
li { margin: 2px 0; }
li::marker { unicode-bidi: plaintext; }
.advice { background: #eefaf5; border-right: 4px solid #2a9d8f; padding: 8px 12px; border-radius: 8px; margin: 8px 0; }
table.transit { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9.5pt; }
table.transit th { background: #2a3555; color: #fff; padding: 6px 8px; text-align: right; }
table.transit td { border-bottom: 1px solid #e3e6f0; padding: 6px 8px; }
.bigthree { text-align: center; margin: 18px 0; }
.bigthree .bt { display: inline-block; background: #f0edff; border-radius: 14px; padding: 10px 22px; margin: 6px; }
.bigthree .bt .k { font-size: 9pt; color: #888; }
.bigthree .bt .v { font-size: 12.5pt; font-weight: 700; color: #3b2f80; }
.meta { font-size: 9pt; color: #777; text-align: center; margin-top: 10px; }
.footer-note { margin-top: 30px; font-size: 8.5pt; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }
"""


def _esc(s: str) -> str:
    return html.escape(str(s or ""))


def render_report_pdf(report: dict, out_path: str | Path, plan_key: str | None = None) -> Path:
    """report JSON (build_report_json output) → PDF file."""
    chart = report["chart"]
    sections = report["sections"]
    metrics = report.get("metrics", {})
    bt = big_three(chart)
    birth = chart["birth"]

    parts = [f'<div class="cover">',
             f'<div class="title">گزارش چارت تولد</div>',
             f'<div class="sub">آینهی خودشناسی — تفسیر اختصاصی بر اساس محاسبهی نجومی دقیق</div>',
             f'<div class="badge">تاریخ و ساعت تولد: {_esc(birth.get("local_time", ""))}</div>',
             f'<div class="badge">مکان: {_esc(birth.get("city_fa", "")) or "—"}</div>',
             "</div>"]

    # Big Three box
    parts.append('<div class="bigthree">')
    for key, label in (("sun", "خورشید"), ("moon", "ماه"), ("asc", "طالع")):
        v = bt.get(key, {})
        parts.append(f'<div class="bt"><div class="k">{label}</div><div class="v">'
                     f'{_esc(v.get("sign_fa", ""))}</div></div>')
    parts.append("</div>")
    asc = chart.get("angles", {}).get("ASC", {})
    parts.append(f'<p class="meta">فاز ماه: {_esc(chart.get("moon_phase", ""))} — '
                 f'طالع {_esc(bt.get("asc", {}).get("sign_fa", asc.get("sign_fa", "")))}</p>')

    # Sections (iterate actual generated sections — plan-based subsets + islamic)
    for domain_key, sec in sections.items():
        title_fa = DOMAINS.get(domain_key, "فرهنگ و باورها — از منظر خودشناسی")
        parts.append(f'<h1 class="section">{_esc(sec.get("title_fa", title_fa))}</h1>')
        if sec.get("intro"):
            parts.append(f"<p>{_esc(sec['intro'])}</p>")
        for ins in sec.get("insights", []):
            parts.append('<div class="block">')
            title = ins.get("insight", "")[:70]
            parts.append(f'<h2 class="insight">◈ {_esc(title)}{"…" if len(ins.get("insight", "")) > 70 else ""}</h2>')
            body = ins.get("insight", "")
            parts.append(f"<p>{_esc(body)}</p>")
            evs = ins.get("evidence", [])
            if evs:
                ev_txt = "شواهد نجومی: " + " | ".join(
                    f"{_esc(e.get('factor'))} در {_esc(e.get('sign', ''))} {_esc(e.get('house', ''))}".strip()
                    for e in evs)
                parts.append(f'<div class="evidence">{ev_txt}</div>')
            strengths = ins.get("strengths", [])
            if strengths:
                parts.append("<ul>" + "".join(f"<li>✔ {_esc(s)}</li>" for s in strengths) + "</ul>")
            challenges = ins.get("challenges", [])
            if challenges:
                parts.append("<ul>" + "".join(f"<li>• {_esc(c)}</li>" for c in challenges) + "</ul>")
            if ins.get("practical_advice"):
                parts.append(f'<div class="advice">💡 پیشنهاد عملی: {_esc(ins["practical_advice"])}</div>')
            parts.append("</div>")

    # ── Gold bonus: upcoming-transit chapter (plan §10 — deterministic, no LLM) ──
    if plan_key == "gold":
        try:
            from app.astrology.svg_widgets import transit_timeline_svg
            from app.astrology.transits import upcoming_transits
            events = upcoming_transits(chart, days=120)[:10]
            parts.append('<h1 class="section">گذرهای پیشِ رو — نقشهی ۴ ماه آینده</h1>')
            if events:
                parts.append('<table class="transit">')
                parts.append('<tr><th>از تاریخ</th><th>سیارهی گذرنده</th><th>با</th><th>نوع</th></tr>')
                for e in events:
                    tgt = {"Sun": "خورشید", "Moon": "ماه", "ASC": "طالع", "Venus": "ناهید",
                           "Mars": "مریخ", "Mercury": "عطارد"}.get(e["target"], e["target"])
                    parts.append(f"<tr><td>{_esc(e['start'])}</td><td>{_esc(e['planet_fa'])} "
                                 f"({_esc(e['sign_fa'])})</td><td>{_esc(tgt)}</td>"
                                 f"<td>{_esc(e['aspect'])} (اورب {e['orb']}°)</td></tr>")
                parts.append("</table>")
            parts.append(f'<div class="advice">🌠 این جدول از روی محاسبهی مستقیم نجومی ساخته شده '
                         f'و نشان میدهد کدام گذرهای مهم روی چارت تو فعال میشوند.</div>')
            try:
                svg = transit_timeline_svg(chart, months=12).replace('width="100%"', 'width="680"')
                parts.append(f'<div style="page-break-inside:avoid;">{svg}</div>')
            except Exception:  # noqa: BLE001 — widget must never break the PDF
                pass
        except Exception:  # noqa: BLE001
            pass

    parts.append(f'<div class="footer-note">این گزارش با محاسبهی دقیق نجومی (Swiss Ephemeris) و '
                 f'هوش مصنوعی تهیه شده و جنبهی خودشناسی و سرگرمی دارد. '
                 f'تولید: {metrics.get("generated_at", "")}</div>')

    html_doc = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
    <style>{CSS}</style></head><body>{"".join(parts)}</body></html>"""

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc, base_url=str(FONT_DIR)).write_pdf(str(out))
    return out


FILE: app/report/rules.py  (212 lines)
======================================================================
"""
Rule Engine — data-driven, NOT if/else (Claude review #3).

Each rule: factor, condition, domain, weight, interpretation_key, priority, evidence.
Evaluates canonical Chart JSON → active factors per domain. The LLM never
calculates — this module decides WHAT to tell the writer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 13 life domains (plan v3.1 §8)
DOMAINS = {
    "identity": "هویت و شخصیت",
    "mind": "ذهن و منطق",
    "emotions": "عواطف و شهود",
    "money": "پول و ثروت",
    "career": "شغل و مسیر حرفهای",
    "relationships": "روابط و ازدواج",
    "family": "خانواده و ریشهها",
    "wellbeing": "انرژی و تندرستی",
    "creativity": "فرزند و خلاقیت",
    "education": "آموزش و مهاجرت",
    "network": "شبکهها و دوستان",
    "spirituality": "معنویت",
    "karma": "الگوهای رشد و کارما",
}


@dataclass
class Rule:
    id: str
    domain: str
    factor: str          # planet/angle: Venus, Moon, ASC, MC, 7th_house_cusp...
    condition: dict      # e.g. {"sign": "Libra"}, {"house": 7}, {"aspect": ("Moon", "trine", 6.0)}
    weight: float        # 0..1 — importance
    interpretation_key: str  # i18n key for prompt builder
    priority: int = 1    # higher = always included
    evidence: bool = True


RULES: list[Rule] = [
    # ── identity ──
    Rule("sun_sign", "identity", "Sun", {"sign": "*"}, 1.0, "sun_in_sign", 5),
    Rule("sun_house", "identity", "Sun", {"house": "*"}, 0.9, "sun_in_house", 4),
    Rule("asc_sign", "identity", "ASC", {"sign": "*"}, 1.0, "asc_in_sign", 5),
    Rule("mc_sign", "identity", "MC", {"sign": "*"}, 0.85, "mc_in_sign", 3),
    # ── mind ──
    Rule("mercury_sign", "mind", "Mercury", {"sign": "*"}, 1.0, "mercury_in_sign", 5),
    Rule("mercury_house", "mind", "Mercury", {"house": "*"}, 0.8, "mercury_in_house", 3),
    Rule("mercury_retro", "mind", "Mercury", {"retrograde": True}, 0.75, "mercury_retrograde", 3),
    # ── emotions ──
    Rule("moon_sign", "emotions", "Moon", {"sign": "*"}, 1.0, "moon_in_sign", 5),
    Rule("moon_house", "emotions", "Moon", {"house": "*"}, 0.9, "moon_in_house", 4),
    Rule("moon_phase", "emotions", "Moon", {"phase": "*"}, 0.7, "moon_phase", 3),
    # ── money ──
    Rule("venus_sign", "money", "Venus", {"sign": "*"}, 0.75, "venus_in_sign_money", 2),
    Rule("venus_house", "money", "Venus", {"house": "*"}, 0.85, "venus_in_house", 3),
    Rule("jupiter_sign", "money", "Jupiter", {"sign": "*"}, 0.8, "jupiter_in_sign", 3),
    Rule("jupiter_house", "money", "Jupiter", {"house": "*"}, 0.9, "jupiter_in_house", 4),
    Rule("saturn_sign", "money", "Saturn", {"sign": "*"}, 0.7, "saturn_in_sign", 2),
    Rule("saturn_house", "money", "Saturn", {"house": "*"}, 0.85, "saturn_in_house", 3),
    # ── career ──
    Rule("mc_sign_career", "career", "MC", {"sign": "*"}, 1.0, "mc_career", 5),
    Rule("sun_house_career", "career", "Sun", {"house": 10}, 0.9, "sun_in_10th", 4),
    Rule("saturn_house_career", "career", "Saturn", {"house": 10}, 0.85, "saturn_in_10th", 3),
    Rule("jupiter_house_career", "career", "Jupiter", {"house": 10}, 0.8, "jupiter_in_10th", 2),
    Rule("mars_house", "career", "Mars", {"house": 10}, 0.8, "mars_in_10th", 2),
    Rule("mars_sign", "career", "Mars", {"sign": "*"}, 0.8, "mars_in_sign", 3),
    # ── relationships ──
    Rule("venus_house_rel", "relationships", "Venus", {"house": 7}, 0.95, "venus_in_7th", 5),
    Rule("venus_sign_rel", "relationships", "Venus", {"sign": "*"}, 0.9, "venus_in_sign_rel", 4),
    Rule("moon_house_rel", "relationships", "Moon", {"house": 7}, 0.9, "moon_in_7th", 4),
    Rule("mars_house_rel", "relationships", "Mars", {"house": 7}, 0.85, "mars_in_7th", 3),
    Rule("saturn_house_rel", "relationships", "Saturn", {"house": 7}, 0.95, "saturn_in_7th", 5),
    Rule("saturn_retro_rel", "relationships", "Saturn", {"retrograde": True}, 0.7, "saturn_retrograde_rel", 2),
    # ── family (fallbacks: always cover) ──
    Rule("moon_house_fam", "family", "Moon", {"house": 4}, 0.9, "moon_in_4th", 4),
    Rule("sun_house_fam", "family", "Sun", {"house": 4}, 0.85, "sun_in_4th", 3),
    Rule("saturn_house_fam", "family", "Saturn", {"house": 4}, 0.8, "saturn_in_4th", 3),
    Rule("moon_sign_fam", "family", "Moon", {"sign": "*"}, 0.6, "moon_family_style", 1),
    Rule("saturn_sign_fam", "family", "Saturn", {"sign": "*"}, 0.55, "saturn_family_duty", 1),
    # ── wellbeing ──
    Rule("sun_sign_energy", "wellbeing", "Sun", {"sign": "*"}, 0.75, "sun_energy", 2),
    Rule("mars_sign_energy", "wellbeing", "Mars", {"sign": "*"}, 0.85, "mars_energy", 3),
    Rule("moon_phase_energy", "wellbeing", "Moon", {"phase": "*"}, 0.7, "moon_energy_rhythm", 2),
    # ── creativity (fallbacks) ──
    Rule("sun_house_crea", "creativity", "Sun", {"house": 5}, 0.9, "sun_in_5th", 4),
    Rule("venus_house_crea", "creativity", "Venus", {"house": 5}, 0.8, "venus_in_5th", 3),
    Rule("moon_house_crea", "creativity", "Moon", {"house": 5}, 0.8, "moon_in_5th", 3),
    Rule("mercury_house_crea", "creativity", "Mercury", {"house": 5}, 0.7, "mercury_in_5th", 2),
    Rule("sun_sign_crea", "creativity", "Sun", {"sign": "*"}, 0.6, "sun_creativity", 1),
    Rule("venus_sign_crea", "creativity", "Venus", {"sign": "*"}, 0.6, "venus_aesthetics", 1),
    # ── education (fallbacks) ──
    Rule("mercury_house_edu", "education", "Mercury", {"house": 3}, 0.85, "mercury_in_3rd", 3),
    Rule("mercury_house_edu9", "education", "Mercury", {"house": 9}, 0.9, "mercury_in_9th", 4),
    Rule("jupiter_house_edu9", "education", "Jupiter", {"house": 9}, 0.95, "jupiter_in_9th", 4),
    Rule("moon_house_edu4", "education", "Moon", {"house": 9}, 0.8, "moon_in_9th", 2),
    Rule("mercury_sign_edu", "education", "Mercury", {"sign": "*"}, 0.6, "mercury_learning", 1),
    Rule("jupiter_sign_edu", "education", "Jupiter", {"sign": "*"}, 0.6, "jupiter_growth", 1),
    Rule("moon_sign_edu", "education", "Moon", {"sign": "*"}, 0.5, "moon_learning_style", 1),
    # ── network (fallbacks) ──
    Rule("mercury_house_net", "network", "Mercury", {"house": 11}, 0.8, "mercury_in_11th", 3),
    Rule("jupiter_house_net", "network", "Jupiter", {"house": 11}, 0.9, "jupiter_in_11th", 4),
    Rule("sun_house_net", "network", "Sun", {"house": 11}, 0.8, "sun_in_11th", 3),
    Rule("mercury_sign_net", "network", "Mercury", {"sign": "*"}, 0.55, "mercury_network", 1),
    Rule("jupiter_sign_net", "network", "Jupiter", {"sign": "*"}, 0.6, "jupiter_social", 1),
    # ── spirituality ──
    Rule("neptune_sign", "spirituality", "Neptune", {"sign": "*"}, 0.9, "neptune_in_sign", 4),
    Rule("neptune_house", "spirituality", "Neptune", {"house": 12}, 0.95, "neptune_in_12th", 5),
    Rule("moon_house_spir", "spirituality", "Moon", {"house": 12}, 0.85, "moon_in_12th", 4),
    Rule("jupiter_house_spir", "spirituality", "Jupiter", {"house": 12}, 0.85, "jupiter_in_12th", 3),
    # ── karma ──
    Rule("north_node_sign", "karma", "Node", {"sign": "*"}, 0.9, "node_in_sign", 4),
    Rule("saturn_house_karma", "karma", "Saturn", {"house": "*"}, 0.85, "saturn_karma", 3),
    Rule("pluto_house", "karma", "Pluto", {"house": "*"}, 0.9, "pluto_in_house", 4),
    Rule("pluto_sign", "karma", "Pluto", {"sign": "*"}, 0.8, "pluto_in_sign", 3),
]


def evaluate(chart: dict) -> dict[str, list[dict]]:
    """Chart JSON → {domain: [active rule records with matched factor data]}."""
    planets = chart.get("planets", {})
    angles = chart.get("angles", {})
    houses = chart.get("houses", {})
    aspects = chart.get("aspects", [])
    moon_phase = chart.get("moon_phase", "")

    # fast lookup: planet name → position dict
    pos = {}
    for name, p in planets.items():
        d = {"sign": p.get("sign_index"), "house": p.get("house"),
             "retrograde": p.get("retrograde", False), "longitude": p.get("longitude"),
             "degree": p.get("degree_in_sign"), "sign_fa": p.get("sign_fa")}
        pos[name] = d
    for name, p in angles.items():
        pos[name] = {"sign": p.get("sign_index"), "house": None, "retrograde": False,
                     "longitude": p.get("longitude"), "degree": p.get("degree_in_sign"),
                     "sign_fa": p.get("sign_fa")}

    # aspect lookup: (a, b) → aspect dict
    aspect_map = {}
    for a in aspects:
        key = tuple(sorted([a["p1"], a["p2"]]))
        aspect_map[key] = a

    out: dict[str, list[dict]] = {}
    for rule in RULES:
        cond = rule.condition
        matched = True
        detail = None

        if "sign" in cond:
            target = pos.get(rule.factor)
            if target is None:
                matched = False
            elif cond["sign"] == "*":
                detail = target
            elif target["sign"] == cond["sign"]:
                detail = target
            else:
                matched = False
        if matched and "house" in cond:
            target = pos.get(rule.factor)
            if target is None or target.get("house") is None:
                matched = False
            elif cond["house"] == "*":
                detail = target
            elif target["house"] == cond["house"]:
                detail = detail or target
            else:
                matched = False
        if matched and "retrograde" in cond:
            target = pos.get(rule.factor)
            if target is None or target.get("retrograde") != cond["retrograde"]:
                matched = False
            else:
                detail = detail or target
        if matched and "phase" in cond:
            if cond["phase"] != "*" and moon_phase != cond["phase"]:
                matched = False
            else:
                detail = detail or {"phase": moon_phase}
        if matched and "aspect" in cond:
            p1, aname, orb = cond["aspect"]
            key = tuple(sorted([p1, rule.factor]))
            if key not in aspect_map or aspect_map[key]["aspect"] != aname:
                matched = False
            else:
                detail = detail or aspect_map[key]

        if matched:
            out.setdefault(rule.domain, []).append({
                "rule_id": rule.id,
                "factor": rule.factor,
                "weight": rule.weight,
                "interpretation_key": rule.interpretation_key,
                "priority": rule.priority,
                "evidence": rule.evidence,
                "detail": detail,
            })

    # order by priority desc then weight desc
    for dom in out:
        out[dom].sort(key=lambda r: (-r["priority"], -r["weight"]))
    return out


def domain_coverage(chart: dict) -> dict[str, int]:
    """Count of active rules per domain (for QA: no empty sections)."""
    return {d: len(r) for d, r in evaluate(chart).items()}


FILE: app/report/word.py  (53 lines)
======================================================================
"""Word export (plan §10) — RTL Persian .docx from a done Report.

Uses python-docx; paragraphs are right-aligned, text set to Vazirmatn when
available on the client machine (falls back to Tahoma), font size 11pt.
"""
import io
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


def _rtl(paragraph) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    bidi = pPr.makeelement(qn("w:bidi"), {})
    bidi.set(qn("w:val"), "1")
    pPr.append(bidi)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def report_to_docx(rep: dict[str, Any]) -> bytes:
    """rep: {"title", "intro", "sections": {key: {title, content}}}"""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Vazirmatn"
    style.font.size = Pt(11)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Vazirmatn")

    h = doc.add_heading(rep.get("title", "گزارش چارت تولد"), level=0)
    _rtl(h)
    for run in h.runs:
        run.font.name = "Vazirmatn"

    intro = doc.add_paragraph(rep.get("intro", ""))
    _rtl(intro)

    for key, sec in (rep.get("sections") or {}).items():
        title = sec.get("title", key)
        content = sec.get("content", "")
        h2 = doc.add_heading(title, level=1)
        _rtl(h2)
        for run in h2.runs:
            run.font.name = "Vazirmatn"
        for para in str(content).split("\n\n"):
            p = doc.add_paragraph(para)
            _rtl(p)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


FILE: app/report/worker.py  (170 lines)
======================================================================
"""
ARQ worker — async report generation queue (plan v3.1 §6.4, Redis required).

Run: venv/bin/arq app.report.worker.WorkerSettings
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from arq.connections import RedisSettings
from sqlmodel import Session

import app.config  # noqa: F401 — load .env FIRST
from app.core.llm import build_router
from app.db import engine as db_engine
from app.models import Chart, LLMRun, Report
from app.report.generator import build_report_json
from app.report.prompt_builder import build_all_prompts, build_prompts_for_plan
from app.report.qa import parse_section, qa_repetition, qa_section
from app.report.renderer import render_report_pdf

log = logging.getLogger("report.worker")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
MAX_RETRIES = 2


async def generate_sections_async(router, chart: dict, max_tokens: int = 8192,
                                   report_id: str | None = None, plan_key: str = "full") -> tuple[dict, dict]:
    """Plan-aware section generation (plan v3.0 §10.3): basic=5, full=13, gold=13+islamic."""
    prompts = build_prompts_for_plan(chart, plan_key)
    # admin prompt overrides (plan v3.0 §8) — swap content, keep meta
    from app.report.prompt_overrides import get_overrides
    for key, content in get_overrides().items():
        if key in prompts:
            prompts[key] = (content, prompts[key][1])
    sections: dict[str, dict] = {}
    metrics = {"calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
               "qa_failures": 0, "provider": set()}

    for domain, (prompt, ctx_info) in prompts.items():
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            res = await router.complete(prompt, max_tokens=max_tokens, temperature=0.6, json_mode=True)
            metrics["calls"] += 1
            metrics["total_tokens"] += res.usage.total
            metrics["cost_usd"] += res.cost
            metrics["provider"].add(res.provider)
            try:
                with Session(db_engine) as _s:
                    _s.add(LLMRun(report_id=report_id, provider=res.provider,
                                  model=res.model, gateway="gemini",
                                  prompt_tokens=res.usage.prompt_tokens,
                                  completion_tokens=res.usage.completion_tokens,
                                  cost_usd=res.cost, ok=res.ok,
                                  error=(res.error or "")[:300]))
                    _s.commit()
            except Exception:  # noqa: BLE001 — metering must never break generation
                pass
            if not res.ok:
                metrics["retries"] += 1
                continue
            section = parse_section(res.text)
            errors = qa_section(section, chart, domain) if section else ["invalid JSON"]
            if not errors:
                sections[domain] = section
                ok = True
                break
            metrics["qa_failures"] += 1
            if attempt < MAX_RETRIES:
                metrics["retries"] += 1

        if not ok:
            sections[domain] = {
                "section": domain,
                "title_fa": ctx_info["domain_title"],
                "intro": "بر اساس عوامل محاسبهشده، این حوزه از زندگی اهمیت ویژهای دارد.",
                "insights": [{
                    "insight": "نقشهی نجومی این حوزه را میتوان با دقت بیشتری در گزارش تکمیلی بررسی کرد. "
                               "عوامل فعال: " + (ctx_info["factors"].replace("\n", " — ")[:200]),
                    "evidence": [],
                    "strengths": [], "challenges": [],
                    "practical_advice": "برای تفسیر دقیقتر، به گزارش کامل مراجعه کنید.",
                }],
            }

    rep = qa_repetition(sections)
    if rep:
        log.info("repetition warnings: %s", rep[:3])
    metrics["provider"] = sorted(metrics["provider"])
    return sections, metrics


async def generate_report(ctx: dict, report_id: str) -> None:
    """ARQ job: sections → DB → PDF."""
    with Session(db_engine) as session:
        rep = session.get(Report, report_id)
        if not rep:
            log.error("report %s not found", report_id)
            return
        chart = session.get(Chart, rep.chart_id)
        if not chart:
            rep.status = "failed"
            rep.error = "chart not found"
            session.commit()
            return

        rep.status = "running"
        session.commit()

        try:
            sections, metrics = await generate_sections_async(
                ctx["router"], chart.chart_json, report_id=report_id,
                plan_key=rep.plan_key or "full")
            rep.sections = sections
            rep.metrics = {**metrics, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

            # render PDF
            chart_json = chart.chart_json
            chart_json["birth"]["city_fa"] = chart_json["birth"].get("city_fa", "")
            report_json = build_report_json(chart_json, sections, rep.metrics)
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            pdf = render_report_pdf(report_json, REPORTS_DIR / f"{report_id}.pdf",
                                    plan_key=rep.plan_key or None)
            rep.pdf_path = str(pdf)
            from app.storage import upload_report
            rep.r2_key = upload_report(report_id, str(pdf))
            rep.status = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("report %s failed", report_id)
            rep.status = "failed"
            rep.error = str(e)[:500]
        session.commit()


async def startup(ctx: dict) -> None:
    ctx["router"] = build_router()
    log.info("worker started with router")


async def shutdown(ctx: dict) -> None:
    log.info("worker shutdown")


class WorkerSettings:
    functions = [generate_report]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 4
    job_timeout = 1800


if __name__ == "__main__":  # pragma: no cover — direct async test
    from app.astrology.engine import compute_from_fields

    async def _test():
        from arq import create_pool
        redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        chart = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
        res = await generate_sections_async(build_router(), chart)
        print("sections:", len(res[0]), "| cost:", res[1]["cost_usd"], "| calls:", res[1]["calls"])
        await redis.aclose()

    asyncio.run(_test())


FILE: app/security.py  (90 lines)
======================================================================
"""Security middleware: CSRF origin check + rate limiting + audit log helper.

- CSRF: for state-changing requests, require Origin header to match Host
  (defends against cross-site POSTs; all our forms are same-site).
- Rate limit: simple in-memory sliding window per (ip, scope).
- audit(): record admin actions to audit_logs table.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Request
from sqlmodel import Session, select

import app.config  # noqa: F401

_RATE_LIMITS: dict[str, deque] = defaultdict(deque)
_RATE_LIMITS_WINDOW = 60  # seconds
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class RateLimitExceeded(Exception):
    pass


def check_rate_limit(key: str, max_calls: int, window: int = _RATE_LIMITS_WINDOW) -> None:
    """Allow `max_calls` per `window` seconds for `key`. Raises RateLimitExceeded."""
    now = time.monotonic()
    q = _RATE_LIMITS[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_calls:
        raise RateLimitExceeded(key)
    q.append(now)


def csrf_protect(request: Request) -> bool:
    """Origin must match Host for non-safe methods. Returns True when OK."""
    if request.method in SAFE_METHODS:
        return True
    origin = request.headers.get("origin")
    if not origin:
        # Non-browser clients (curl, bots, server-to-server) — allow
        return True
    host = request.headers.get("host", "")
    try:
        from urllib.parse import urlparse
        return urlparse(origin).netloc == host
    except Exception:
        return False


async def security_guard(request: Request, call_next):
    """FastAPI middleware: CSRF + rate limit for sensitive scopes."""
    if not csrf_protect(request):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "CSRF: origin mismatch"}, status_code=403)

    # rate limit: OTP request (5/min per ip), webhooks (30/min), payments (20/min)
    path = request.url.path
    ip = request.client.host if request.client else "?"
    scope_key = None
    max_calls = 30
    if path.startswith("/api/auth/otp/request"):
        scope_key, max_calls = f"otp:{ip}", 5
    elif path.startswith("/api/v1/"):
        scope_key, max_calls = f"webhook:{ip}", 30
    elif path.startswith("/api/payments"):
        scope_key, max_calls = f"pay:{ip}", 20
    elif path.startswith("/api/chat"):
        scope_key, max_calls = f"chat:{ip}", 40
    if scope_key:
        try:
            check_rate_limit(scope_key, max_calls)
        except RateLimitExceeded:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "درخواست بیش از حد — کمی بعد تلاش کنید"}, status_code=429)
    return await call_next(request)


def audit(engine, admin: str, action: str, entity: str = "", details: str = "") -> None:
    """Write an audit_logs row (best-effort — never crashes the request)."""
    try:
        from app.models import AuditLog
        with Session(engine) as s:
            s.add(AuditLog(admin=admin, action=action, entity=entity, details=details[:500]))
            s.commit()
    except Exception:
        pass


FILE: app/seo/article_banner.py  (57 lines)
======================================================================
"""Article banner SVGs (1200×630) — brand-consistent, zero cost, deterministic.

Category → symbol map; dark glass + gold theme matching the site. No external
images, no LLM — instant generation for every article (plan: images for SEO
articles, free tier first; paid FLUX only if user approves)."""

SYMBOLS = {
    "برج‌ها": "♈",
    "آموزش نجوم": "☉",
    "سیارات": "☽",
    "خانه‌ها": "▣",
    "ترانزیت": "➶",
    "سازگاری": "⚭",
    "شغل و موفقیت": "⚖",
    "ماه": "☽",
    "پیش‌بینی": "◈",
}
FALLBACK = "✦"

GRAD = {
    "برج‌ها": ("#1a1530", "#3a2a5e"),
    "آموزش نجوم": ("#101a38", "#1f3a6e"),
    "سیارات": ("#14102a", "#3a1f4a"),
    "خانه‌ها": ("#0f1f2c", "#1f4a5e"),
    "ترانزیت": ("#10142e", "#2a2a5e"),
    "سازگاری": ("#2a1030", "#5e1f4a"),
    "شغل و موفقیت": ("#1c2a10", "#3a5e1f"),
    "ماه": ("#1a1a2a", "#3a3a5e"),
}


def article_banner_svg(category: str, title: str) -> str:
    sym = (SYMBOLS.get(category, FALLBACK) + "\ufe0e")  # \ufe0e = text presentation (no emoji)
    c1, c2 = GRAD.get(category, ("#12102a", "#2a2a5e"))
    t = title[:48]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>
    </linearGradient>
    <radialGradient id="r" cx="0.5" cy="0.45" r="0.6">
      <stop offset="0" stop-color="rgba(212,175,55,.16)"/><stop offset="1" stop-color="rgba(212,175,55,0)"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#g)"/>
  <rect width="1200" height="630" fill="url(#r)"/>
  <circle cx="1010" cy="120" r="180" fill="none" stroke="rgba(212,175,55,.25)" stroke-width="1"/>
  <circle cx="1010" cy="120" r="120" fill="none" stroke="rgba(212,175,55,.18)" stroke-width="1"/>
  <circle cx="140" cy="540" r="150" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="1"/>
  <text x="600" y="170" font-size="150" text-anchor="middle" fill="rgba(212,175,55,.9)" font-family="serif">{sym}</text>
  <line x1="340" y1="360" x2="860" y2="360" stroke="rgba(212,175,55,.5)" stroke-width="2"/>
  <text x="600" y="430" font-size="44" text-anchor="middle" fill="#f4efe2"
        font-family="Vazirmatn, Tahoma, sans-serif" font-weight="700">{t}</text>
  <text x="600" y="500" font-size="26" text-anchor="middle" fill="rgba(232,226,245,.7)"
        font-family="Vazirmatn, Tahoma, sans-serif">چارت تولد — نقشه‌ی آسمان تو</text>
</svg>"""


FILE: app/seo/content.py  (197 lines)
======================================================================
"""SEO content (plan §8) — deterministic Persian astrology knowledge base.

Every page gets UNIQUE content (programmatic-seo principle: no thin pages):
each sign has personality/love/work/challenge + Sun/Moon/Asc variations.
"""
from __future__ import annotations

SIGNS: dict[str, dict] = {
    "hamal": {
        "title": "برج حمل (آریس) — شخصیت، عشق و کار",
        "element": "آتش", "ruler": "مریخ", "slug": "hamal",
        "keywords": "برج حمل، خورشید در حمل، متولد فروردین، طالع حمل",
        "personality": "حمل‌ها پرانرژی، شجاع و پیشگام‌اند؛ عاشق شروع‌کردن و از چالش نمی‌ترسند. اراده‌ای آهنین و روحیه‌ای رقابتی دارند و معمولاً در هر جمعی جلوتر از بقیه حرکت می‌کنند.",
        "love": "در عشق صریح و پرشورند؛ عاشق تعقیب و شکارند. به شریکی نیاز دارند که هم‌پای انرژی‌شان باشد و استقلالشان را محدود نکند.",
        "work": "برای نقش‌های رهبری، کارآفرینی و میدان‌های رقابتی ساخته شده‌اند. از کارهای تکراری و کسل‌کننده بیزارند.",
        "challenge": "بی‌تابی، عجله و گاهی پرخاشگری؛ یادگیری صبر بزرگ‌ترین درس زندگی‌شان است.",
        "sun": "خورشید در حمل یعنی هویتی مستقل، رک و آغازگر. این افراد در هر شرایطی راه خودشان را پیدا می‌کنند.",
        "moon": "ماه در حمل = احساسات فوری و صادقانه؛ زود جوش می‌آورند و زود آرام می‌شوند.",
        "asc": "طالع حمل ظاهری مصمم، مستقیم و جوان‌پسند می‌دهد؛ اولین برخوردشان پرانرژی است.",
    },
    "sowr": {
        "title": "برج ثور (تائوروس) — شخصیت، عشق و کار",
        "element": "خاک", "ruler": "زهره", "slug": "sowr",
        "keywords": "برج ثور، خورشید در ثور، متولد اردیبهشت، طالع ثور",
        "personality": "ثوری‌ها صبور، قابل‌اعتماد و عاشق زیبایی و راحتی‌اند. به ثبات و امنیت نیاز دارند و هرگز عجله نمی‌کنند؛ اما وقتی تصمیم گرفتند، هیچ‌چیز جلودارشان نیست.",
        "love": "در عشق وفادار و حسی‌اند؛ عاشق لمس، غذاهای خوب و لحظه‌های آرام. آرام‌تر از آن‌اند که عاشقانه‌های پرسر و صدا بسازند، اما عمق عشقشان واقعی است.",
        "work": "در امور مالی، هنر، املاک و هر کاری که نیاز به پشتکار دارد عالی‌اند. به پول و نتیجه ملموس اهمیت می‌دهند.",
        "challenge": "لجاجت و مقاومت در برابر تغییر؛ دلبستگی بیش از حد به عادت‌ها.",
        "sun": "خورشید در ثور یعنی شخصیتی پایدار، حسی و مادی؛ ارزش‌هایشان بر اساس امنیت و زیبایی شکل می‌گیرد.",
        "moon": "ماه در ثور به آرامش عاطفی و امنیت مادی نیاز دارد؛ احساسات‌شان کُند اما عمیق است.",
        "asc": "طالع ثور چهره‌ای آرام، گرم و قابل‌اعتماد نشان می‌دهد.",
    },
    "jowza": {
        "title": "برج جوزا (جمینی) — شخصیت، عشق و کار",
        "element": "هوا", "ruler": "عطارد", "slug": "jowza",
        "keywords": "برج جوزا، خورشید در جوزا، متولد خرداد، طالع جوزا",
        "personality": "جوزایی‌ها کنجکاو، خوش‌صحبت و چندوجهی‌اند؛ ذهنی تیز و زبانی چابک دارند. از تنوع و تازگی تغذیه می‌شوند و در جمع‌ها می‌درخشند.",
        "love": "در عشق بازیگوش و پرمکالمه‌اند؛ عاشق شریک باهوش و خنده‌رو. به آزادی و گفت‌وگوی بی‌پایان نیاز دارند.",
        "work": "در ارتباطات، نوشتن، تدریس، رسانه و فروش عالی‌اند. چندکارگی نقطه قوت‌شان است.",
        "challenge": "پراکندگی، بی‌قراری و تصمیم‌های عجولانه؛ تمرکز بزرگ‌ترین درس‌شان است.",
        "sun": "خورشید در جوزا هویتی کنجکاو، ارتباطی و سریع‌الانتقال می‌سازد.",
        "moon": "ماه در جوزا احساسات را با کلمات پردازش می‌کند؛ باید حرف بزنند تا بفهمند چه حسی دارند.",
        "asc": "طالع جوزا چهره‌ای جوان، پرسشگر و خندان نشان می‌دهد.",
    },
    "sartan": {
        "title": "برج سرطان (کنسر) — شخصیت، عشق و کار",
        "element": "آب", "ruler": "ماه", "slug": "sartan",
        "keywords": "برج سرطان، خورشید در سرطان، متولد تیر، طالع سرطان",
        "personality": "سرطانی‌ها حساس، خانواده‌دوست و دلسوزند؛ خاطرات و احساسات را عمیقاً حفظ می‌کنند. به آشیانه‌ای امن نیاز دارند و از کسانی که دوستشان دارند محافظت می‌کنند.",
        "love": "در عشق مهربان، وفادار و مراقب‌اند؛ عشق را با مراقبت و غذای خوب نشان می‌دهند. به امنیت عاطفی نیاز مبرم دارند.",
        "work": "در پرستاری، آموزش، آشپزی، املاک و هر کاری که به همدلی نیاز دارد درخشان‌اند.",
        "challenge": "حساسیت بیش از حد و چسبیدن به گذشته؛ یادگیری رهاکردن.",
        "sun": "خورشید در سرطان هویتی حسی، شهودی و مادرانه می‌سازد.",
        "moon": "ماه در سرطان (وطن ماه!) — احساسات موج‌وار و عمیق؛ خانه‌پایه‌ترین جایگاه ماه.",
        "asc": "طالع سرطان چهره‌ای نرم، مهربان و گاهی گوشه‌گیر نشان می‌دهد.",
    },
    "asad": {
        "title": "برج اسد (لئو) — شخصیت، عشق و کار",
        "element": "آتش", "ruler": "خورشید", "slug": "asad",
        "keywords": "برج اسد، خورشید در اسد، متولد مرداد، طالع اسد",
        "personality": "اسدی‌ها درخشان، سخاوتمند و ذاتاً رهبرند؛ عاشق مرکز توجه و قدردانی. قلب بزرگی دارند و از هر کسی که دوستش دارند حمایت می‌کنند.",
        "love": "در عشق رمانتیک و وفادارند؛ شریک‌شان باید قهرمان‌شان باشد و به آن‌ها احترام بگذارد. عاشق هدیه و جشن‌اند.",
        "work": "برای نقش‌های نمایشی، مدیریت و هنر ساخته شده‌اند؛ جایی که دیده شوند می‌درخشند.",
        "challenge": "غرور و نیاز به تأیید؛ یادگیری تواضع.",
        "sun": "خورشید در اسد = جایگاه سلطنتی خورشید؛ هویتی درخشان، خلاق و خودآگاه.",
        "moon": "ماه در اسد احساسات پرغرور و گرمی دارد؛ باید در مرکز توجه باشند تا احساس امنیت کنند.",
        "asc": "طالع اسد حضوری باشکوه و جذاب می‌سازد؛ همه را به خود جذب می‌کند.",
    },
    "sowza": {
        "title": "برج سنبله (ویرگو) — شخصیت، عشق و کار",
        "element": "خاک", "ruler": "عطارد", "slug": "sowza",
        "keywords": "برج سنبله، خورشید در سنبله، متولد شهریور، طالع سنبله",
        "personality": "سنبله‌ای‌ها دقیق، تحلیل‌گر و کمال‌گرایند؛ به جزئیات توجهی حیرت‌انگیز دارند. سخت‌کوش و متواضع‌اند و همیشه به دنبال بهترکردن خودشان.",
        "love": "در عشق محتاط و خدمت‌گزارند؛ عشق را با کارهای کوچک و مفید نشان می‌دهند. شریک منظم و صادق می‌خواهند.",
        "work": "در پزشکی، حسابداری، تحلیل داده و هر کاری که دقت می‌خواهد بی‌نظیرند.",
        "challenge": "وسواس و انتقاد از خود و دیگران؛ یادگیری پذیرش نقص.",
        "sun": "خورشید در سنبله هویتی دقیق، متواضع و خدمتگزار می‌سازد.",
        "moon": "ماه در سنبله احساسات را تحلیل می‌کند؛ باید مرتب باشند تا آرام باشند.",
        "asc": "طالع سنبله ظاهری منظم، آرام و هوشمند نشان می‌دهد.",
    },
    "mizan": {
        "title": "برج میزان (لیبرا) — شخصیت، عشق و کار",
        "element": "هوا", "ruler": "زهره", "slug": "mizan",
        "keywords": "برج میزان، خورشید در میزان، متولد مهر، طالع میزان",
        "personality": "میزانی‌ها دیپلمات، زیباپسند و عاشق عدالت‌اند؛ تعادل را در همه‌چیز می‌جویند. در جمع‌ها دلنشین‌اند و از تنش بیزارند.",
        "love": "در عشق رمانتیک، ظریف و متعهدند؛ شریک‌شان باید همراه هنری و گفت‌وگوی خوب باشد. عاشق تعارف و زیبایی‌اند.",
        "work": "در حقوق، دیپلماسی، هنر، طراحی و مذاکره عالی‌اند؛ میانجی‌های طبیعی.",
        "challenge": "دو‌دلی و اجتناب از تعارض؛ یادگیری تصمیم‌گیری قاطع.",
        "sun": "خورشید در میزان هویتی متعادل، اجتماعی و زیباپسند می‌سازد.",
        "moon": "ماه در میزان به هماهنگی و روابط آرام نیاز دارد؛ بی‌عدالتی آن‌ها را می‌آزارد.",
        "asc": "طالع میزان چهره‌ای خوش‌برخورد، جذاب و متین نشان می‌دهد.",
    },
    "aghrab": {
        "title": "برج عقرب (اسکورپیو) — شخصیت، عشق و کار",
        "element": "آب", "ruler": "پلوتو/مریخ", "slug": "aghrab",
        "keywords": "برج عقرب، خورشید در عقرب، متولد آبان، طالع عقرب",
        "personality": "عقربی‌ها عمیق، پرشور و اسرارآمیزند؛ احساسات‌شان اقیانوسی است که کسی به عمقش نمی‌رسد. اراده‌ای فولادی و حافظه‌ای عجیب دارند.",
        "love": "در عشق تمام‌وکمال و شدیدند؛ یا هیچ یا همه. به شریک وفادار و صادق نیاز دارند و خیانت را هرگز نمی‌بخشند.",
        "work": "در تحقیق، روانشناسی، جراحی، مدیریت بحران و امور مالی پرقدرت‌اند.",
        "challenge": "حسادت و رازداری افراطی؛ یادگیری اعتماد و رهاکردن کنترل.",
        "sun": "خورشید در عقرب هویتی مغناطیسی، عمیق و دگرگون‌ساز می‌سازد.",
        "moon": "ماه در عقرب احساسات آتشین و پنهان؛ باید اعتماد کنند تا احساساتشان را نشان دهند.",
        "asc": "طالع عقرب نگاه نافذ و حضوری مرموز و قدرتمند می‌سازد.",
    },
    "ghows": {
        "title": "برج قوس (سجیتاریوس) — شخصیت، عشق و کار",
        "element": "آتش", "ruler": "مشتری", "slug": "ghows",
        "keywords": "برج قوس، خورشید در قوس، متولد آذر، طالع قوس",
        "personality": "قوسی‌ها خوش‌بین، ماجراجو و آزادی‌خواهند؛ عاشق سفر، فلسفه و معنا. راست‌گویی و خنده‌شان مسری است.",
        "love": "در عشق صادق و ماجراجویند؛ به شریکی نیاز دارند که هم‌سفرشان باشد، نه زنجیرشان. از حسادت و محدودیت فرار می‌کنند.",
        "work": "در آموزش، انتشارات، گردشگری، حقوق و هر کار بین‌المللی درخشان‌اند.",
        "challenge": "بی‌ملاحظگی و تعهدگریزی؛ یادگیری مسئولیت‌پذیری.",
        "sun": "خورشید در قوس هویتی خوش‌بین، فلسفی و آزاد می‌سازد.",
        "moon": "ماه در قوس به معنا و ماجراجویی نیاز دارد؛ احساسات شاد و مستقیم.",
        "asc": "طالع قوس چهره‌ای خندان، رک و ورزشکار نشان می‌دهد.",
    },
    "jadi": {
        "title": "برج جدی (کاپریکورن) — شخصیت، عشق و کار",
        "element": "خاک", "ruler": "زحل", "slug": "jadi",
        "keywords": "برج جدی، خورشید در جدی، متولد دی، طالع جدی",
        "personality": "جدی‌ها جاه‌طلب، منظم و صبورند؛ برای رسیدن به قله، سال‌ها آرام قدم برمی‌دارند. مسئولیت‌پذیرترین علامت زودیاک‌اند.",
        "love": "در عشق محتاط و متعهدند؛ عشق برایشان جدی است و آهسته ابراز می‌شود. به شریک بالغ و قابل‌اعتماد نیاز دارند.",
        "work": "در مدیریت، بانکداری، مهندسی و سیاست ساخته شده‌اند؛ کوه‌نوردان حرفه‌ای دنیا.",
        "challenge": "خشکی عاطفی و کارگزاری افراطی؛ یادگیری لذت‌بردن از زندگی.",
        "sun": "خورشید در جدی هویتی جاه‌طلب، منضبط و هدف‌محور می‌سازد.",
        "moon": "ماه در جدی احساسات مهارشده؛ به امنیت و موفقیت به عنوان آرامش نیاز دارد.",
        "asc": "طالع جدی ظاهری جدی، بالغ و قابل‌اعتماد نشان می‌دهد.",
    },
    "dalv": {
        "title": "برج دلو (آکواریوس) — شخصیت، عشق و کار",
        "element": "هوا", "ruler": "اورانوس/زحل", "slug": "dalv",
        "keywords": "برج دلو، خورشید در دلو، متولد بهمن، طالع دلو",
        "personality": "دلویی‌ها آینده‌نگر، مستقل و انسان‌دوست‌اند؛ ذهنی خلاق و نگاهی غیرمتعارف دارند. دوستان زیادی دارند اما به حریم شخصی‌شان حساس‌اند.",
        "love": "در عشق غیرمنتظره و باهوشند؛ اول دوست می‌شوند، بعد عاشق. شریکی می‌خواهند که به آزادی‌شان احترام بگذارد.",
        "work": "در فناوری، علم، نوآوری و کارهای بشردوستانه بی‌نظیرند؛ ذهن‌های فردای دنیا.",
        "challenge": "دوری عاطفی و عجیب‌بودن عمدی؛ یادگیری نزدیک‌شدن به دیگران.",
        "sun": "خورشید در دلو هویتی نوآور، مستقل و جمع‌گرا می‌سازد.",
        "moon": "ماه در دلو احساسات منطقی و فاصله‌دار؛ به دوستی و ایده نیاز دارد.",
        "asc": "طالع دلو ظاهری خاص، باهوش و متفاوت نشان می‌دهد.",
    },
    "hout": {
        "title": "برج حوت (پیسسز) — شخصیت، عشق و کار",
        "element": "آب", "ruler": "نپتون/مشتری", "slug": "hout",
        "keywords": "برج حوت، خورشید در حوت، متولد اسفند، طالع حوت",
        "personality": "حوتی‌ها رویایی، شهودی و مهربان‌اند؛ مرز میان واقعیت و خیال برایشان نازک است. هنرمندترین و همدل‌ترین علامت زودیاک‌اند.",
        "love": "در عشق رمانتیک، فداکار و غرق‌شونده‌اند؛ عشق را با همدلی و فداکاری نشان می‌دهند. شریکی مهربان و الهام‌بخش می‌خواهند.",
        "work": "در هنر، موسیقی، سینما، مددکاری و هر کار خلاقانه می‌درخشند.",
        "challenge": "فرار از واقعیت و مرزنداشتن؛ یادگیری قاطعیت.",
        "sun": "خورشید در حوت هویتی هنری، شهودی و فداکار می‌سازد.",
        "moon": "ماه در حوت (تعالی ماه) — حساس‌ترین و شهودی‌ترین جایگاه ماه.",
        "asc": "طالع حوت چهره‌ای رویایی، مهربان و هنرمند نشان می‌دهد.",
    },
}

PLANETS: dict[str, dict] = {
    "sun": {"title": "خورشید در چارت تولد", "text": "خورشید هویت اصلی، اراده و مسیر زندگی شماست؛ نشان‌دهنده آن‌که هستید، نه آن‌که به نظر می‌رسید."},
    "moon": {"title": "ماه در چارت تولد", "text": "ماه دنیای درون، احساسات و نیازهای عاطفی شماست؛ نشان می‌دهد در چه چیزی احساس امنیت می‌کنید."},
    "mercury": {"title": "عطارد در چارت تولد", "text": "عطارد طرز فکر، زبان و نحوه ارتباط شما را نشان می‌دهد؛ ذهن شما چطور یاد می‌گیرد و حرف می‌زند."},
    "venus": {"title": "زهره در چارت تولد", "text": "زهره عشق، زیبایی، سلیقه و نحوه دوست‌داشتن شماست؛ نشان می‌دهد چه چیزی برایتان جذاب است."},
    "mars": {"title": "مریخ در چارت تولد", "text": "مریخ انرژی، اراده و نحوه جنگیدن شماست؛ نشان می‌دهد چطور به خواسته‌هایتان می‌رسید."},
    "jupiter": {"title": "مشتری در چارت تولد", "text": "مشتری خوش‌شانسی، رشد و گسترش است؛ نشان می‌دهد در کجای زندگی شما برکت و فرصت جاری است."},
    "saturn": {"title": "زحل در چارت تولد", "text": "زحل مسئولیت، نظم و درس‌های سخت زندگی است؛ نشان می‌دهد کجا باید صبور و بالغ باشید."},
    "uranus": {"title": "اورانوس در چارت تولد", "text": "اورانوس نبوغ، آزادی و شورش است؛ نشان می‌دهد در کجا خلاقانه و غیرمنتظره رفتار می‌کنید."},
    "neptune": {"title": "نپتون در چارت تولد", "text": "نپتون الهام، رویا و شهود است؛ نشان می‌دهد در کجا رؤیاپرداز و معنوی هستید."},
    "pluto": {"title": "پلوتو در چارت تولد", "text": "پلوتو قدرت، دگرگونی و تولد دوباره است؛ نشان می‌دهد در کجای زندگی دگرگونی‌های عمیق را تجربه می‌کنید."},
}

HOUSES: dict[str, dict] = {
    "1": {"title": "خانه اول — خود و ظاهر", "text": "خانه اول شخصیت، ظاهر و رویکرد شما به زندگی است؛ همان‌که طالع نامیده می‌شود."},
    "2": {"title": "خانه دوم — دارایی و ارزش‌ها", "text": "خانه دوم پول، دارایی و احساس ارزشمندی شماست؛ نشان می‌دهد با منابعتان چطور برخورد می‌کنید."},
    "3": {"title": "خانه سوم — ارتباطات و یادگیری", "text": "خانه سوم گفت‌وگو، خواهر و برادر، همسایه‌ها و یادگیری‌های روزمره را نشان می‌دهد."},
    "4": {"title": "خانه چهارم — خانواده و ریشه‌ها", "text": "خانه چهارم خانه پدری، خانواده و درون شماست؛ عمیق‌ترین پایه‌های امنیت عاطفی."},
    "5": {"title": "خانه پنجم — عشق و خلاقیت", "text": "خانه پنجم عاشقی، فرزند، هنر و سرگرمی است؛ جایی که از ته دل می‌درخشید."},
    "6": {"title": "خانه ششم — کار و سلامت", "text": "خانه ششم کار روزانه، عادت‌ها و سلامت جسمی شماست؛ نظم و خدمت."},
    "7": {"title": "خانه هفتم — شریک زندگی", "text": "خانه هفتم ازدواج و شراکت‌های مهم است؛ آینه‌ای که در روابط جدی می‌بینید."},
    "8": {"title": "خانه هشتم — تحول و سرمایه مشترک", "text": "خانه هشتم مرگ و تولد دوباره، پول مشترک و صمیمیت عمیق است؛ عمیق‌ترین خانه چارت."},
    "9": {"title": "خانه نهم — فلسفه و سفر", "text": "خانه نهم باورها، سفرهای دور، آموزش عالی و معنویت شماست؛ جست‌وجوی معنا."},
    "10": {"title": "خانه دهم — شغل و سرنوشت", "text": "خانه دهم (MC) مسیر شغلی، افتخار و جایگاه اجتماعی شماست؛ قلّه‌ای که به سمتش می‌روید."},
    "11": {"title": "خانه یازدهم — دوستان و آرزوها", "text": "خانه یازدهم دوستان، شبکه‌ها و آرزوهای بلند شماست؛ جایی که جمع جمع می‌شود."},
    "12": {"title": "خانه دوازدهم — ناخودآگاه", "text": "خانه دوازدهم تنهایی، رازها، بیمارستان‌ها و استعدادهای پنهان است؛ دنیای نامرئی."},
}

GUIDES: dict[str, dict] = {
    "birth-chart": {
        "title": "چارت تولد چیست؟ راهنمای کامل و ساده",
        "text": "چارت تولد (نقشه آسمان) عکس‌برداری دقیق از آسمان در لحظه و مکان تولد شماست. این نقشه موقعیت خورشید، ماه، سیارات و خانه‌ها را نشان می‌دهد و ۱۲ خانه آن، ۱۲ بخش زندگی شما را روشن می‌کند. با چارت تولد می‌فهمید چرا بعضی الگوها در زندگی‌تان تکرار می‌شود، استعدادهای ذاتی‌تان چیست و در چه فصل‌هایی از زندگی هستید.",
    },
    "big-three": {
        "title": "سه‌گانه اصلی چارت: خورشید، ماه و طالع",
        "text": "خورشید هویت اصلی شماست، ماه دنیای عاطفی‌تان و طالع (بالارونده) آن‌گونه که دیگران اول بار می‌بینند. ترکیب این سه، شخصیت واقعی شما را می‌سازد: مثلاً خورشید اسد، ماه حوت و طالع اسد یعنی درونِ سلطنتی با احساسات اقیانوسی که حضوری باشکوه دارد.",
    },
    "transit": {
        "title": "ترانزیت چیست؟ پیش‌بینی‌های نجومی روزانه",
        "text": "ترانزیت موقعیت فعلی سیارات نسبت به چارت تولد شماست. وقتی مشتری از روی خورشید تولدتان عبور می‌کند، سال رشد و فرصت دارید؛ وقتی زحل از روی ماه‌تان می‌گذرد، درس عاطفی سخت اما سازنده می‌گیرید. داشبورد ترانزیت روزانه ما این رویدادها را دقیق محاسبه می‌کند.",
    },
}


FILE: app/share/card.py  (74 lines)
======================================================================
"""Share card generator — 1200×630 OG-style card rendered via headless Chromium.

Persian text + chart wheel; cached PNG on disk keyed by chart_id.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.astrology.big_three import big_three
from app.astrology.svg_wheel import render_chart_svg

CACHE_DIR = Path(os.getenv("SHARE_CACHE_DIR", "/tmp/chart-share"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _card_html(chart_json: dict) -> str:
    bt = big_three(chart_json)
    wheel = render_chart_svg(chart_json)
    # strip width/height so CSS can size it
    wheel = wheel.replace('width="640"', 'width="300"').replace('height="640"', 'height="300"')
    signs = {
        "Sun": ("خورشید", bt.get("Sun", {}).get("sign_fa", "")),
        "Moon": ("ماه", bt.get("Moon", {}).get("sign_fa", "")),
        "ASC": ("طالع", bt.get("ASC", {}).get("sign_fa", "")),
    }
    badges = "".join(
        f'<div style="background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);'
        f'border-radius:16px;padding:14px 22px;text-align:center;">'
        f'<div style="font-size:15px;color:#a9b6e8;">{label}</div>'
        f'<div style="font-size:26px;font-weight:800;color:#fff;margin-top:4px;">{sign}</div></div>'
        for label, sign in signs.values()
    )
    return f"""<!DOCTYPE html><html dir="rtl" lang="fa"><head><meta charset="utf-8">
<style>
@font-face {{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-Bold.ttf'); }}
body {{ margin:0; font-family:Vazirmatn, Tahoma, sans-serif; }}
.card {{ width:1200px; height:630px; display:flex; align-items:center; gap:40px; padding:0 60px;
  background: radial-gradient(900px 600px at 80% -10%, #1b2350 0%, #0b1026 60%), #0b1026;
  box-sizing:border-box; }}
.wheel {{ flex:0 0 300px; }}
.info {{ flex:1; }}
h1 {{ color:#f5c518; font-size:34px; margin:0 0 6px; }}
.sub {{ color:#a9b6e8; font-size:18px; margin-bottom:26px; }}
.badges {{ display:flex; gap:14px; }}
</style></head><body>
<div class="card">
  <div class="wheel">{wheel}</div>
  <div class="info">
    <h1>چارت تولد من</h1>
    <div class="sub">گزارش اختصاصی با محاسبه‌ی دقیق نجومی</div>
    <div class="badges">{badges}</div>
  </div>
</div></body></html>"""


def render_share_card(chart_json: dict, chart_id: str) -> str:
    """Render + cache PNG. Returns file path."""
    key = hashlib.sha1(chart_id.encode()).hexdigest()[:16]
    out = CACHE_DIR / f"{key}.png"
    if out.exists():
        return str(out)

    html = _card_html(chart_json)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        pg.set_content(html)
        pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        b.close()
    return str(out)


FILE: app/storage.py  (67 lines)
======================================================================
"""Cloudflare R2 object storage for report PDFs (plan §11 R2).

Credentials come from chart-platform/.env (R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
R2_ENDPOINT, R2_BUCKET, R2_REGION). Bucket: hermes-voice-clone (shared with vc
project — keys prefixed `chart-reports/`). R2 buckets are private: downloads go
through 7-day presigned URLs. Falls back gracefully when not configured
(returns None) so local-disk serving keeps working.
"""
import os

import app.config  # noqa: F401 — ensure .env loaded

R2_ENDPOINT = os.getenv("R2_ENDPOINT", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "hermes-voice-clone").strip()
R2_REGION = os.getenv("R2_REGION", "auto").strip()
R2_ACCESS = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()

PREFIX = "chart-reports"  # keep chart-platform objects namespaced in the shared bucket


def configured() -> bool:
    return bool(R2_ACCESS and R2_SECRET and R2_ENDPOINT)


def _client():
    if not configured():
        return None
    import boto3
    endpoint = R2_ENDPOINT if R2_ENDPOINT.startswith("http") else f"https://{R2_ENDPOINT}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS,
        aws_secret_access_key=R2_SECRET,
        region_name=R2_REGION or "auto",
    )


def report_key(report_id: str) -> str:
    return f"{PREFIX}/{report_id}.pdf"


def upload_report(report_id: str, local_path: str) -> str | None:
    """Upload a generated PDF to R2. Returns the object key or None."""
    if not configured() or not os.path.exists(local_path):
        return None
    try:
        client = _client()
        client.upload_file(local_path, R2_BUCKET, report_key(report_id))
        return report_key(report_id)
    except Exception:  # noqa: BLE001 — storage must never break the report
        return None


def presigned_url(key: str, expires: int = 604800) -> str | None:
    """7-day presigned GET URL (R2 max). None when not configured/failed."""
    if not configured() or not key:
        return None
    try:
        client = _client()
        return client.generate_presigned_url(
            "get_object", Params={"Bucket": R2_BUCKET, "Key": key}, ExpiresIn=expires
        )
    except Exception:  # noqa: BLE001
        return None


FILE: app/templates/account.html  (80 lines)
======================================================================
{% extends "base.html" %}
{% block title %}حساب کاربری | گزارش‌ها و خریدها{% endblock %}
{% block meta %}<meta name="robots" content="noindex,nofollow"><meta name="description" content="حساب کاربری چارت تولد: گزارش‌های خود، سفارش‌ها، اشتراک و دانلودها در یک جا">{% endblock %}

{% block content %}
<div style="max-width:560px; margin:0 auto; padding-top:36px;">
  <h1>حساب کاربری</h1>
  <p class="muted">سلام {{ user.phone }} 👋 — چارت‌ها، گزارش‌ها و سفارش‌هایت</p>

  {% if not profiles %}
  <div class="glass" style="margin-top:18px; padding:20px; text-align:center;">
    <p>هنوز چارتی نساخته‌ای.</p>
    <a class="btn" href="/birth-form" style="display:inline-block; margin-top:12px;">ساخت چارت رایگان ✨</a>
  </div>
  {% else %}
  <section class="glass" style="margin-top:18px; padding:20px;">
    <h2 style="font-size:1.05rem;">پروفایل‌های تولد ({{ profiles|length }})</h2>
    {% for p in profiles %}
    <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07);">
      <div>
        <b>{{ p.name or 'بدون نام' }}</b>
        <span class="muted" style="display:block; font-size:.82rem;">{{ p.raw_year }}/{{ p.raw_month }}/{{ p.raw_day }} — {{ p.city_fa or '—' }}</span>
      </div>
      <span class="chip" style="font-size:.75rem;">{{ 'ساعت دقیق' if p.time_known else 'بدون ساعت' }}</span>
    </div>
    {% endfor %}
  </section>

  <section class="glass" style="margin-top:14px; padding:20px;">
    <h2 style="font-size:1.05rem;">گزارش‌ها</h2>
    {% for r in reports %}
    <div style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07);">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
        <div>
          <b>گزارش #{{ r.id[:8] }}</b>
          <span class="muted" style="display:block; font-size:.82rem;">{{ r.status }}</span>
        </div>
        {% if r.status == 'done' %}
        <a class="btn" style="font-size:.8rem; padding:6px 14px;" href="/api/reports/{{ r.id }}/pdf">دانلود PDF</a>
        {% endif %}
      </div>
    </div>
    {% else %}
    <p class="muted" style="padding-top:8px;">گزارشی وجود ندارد — بعد از خرید گزارش کامل، اینجا می‌بینی.</p>
    {% endfor %}
  </section>

  <section class="glass" style="margin-top:14px; padding:20px;">
    <h2 style="font-size:1.05rem;">سفارش‌ها</h2>
    {% for o in orders %}
    <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,.07); font-size:.9rem;">
      <span>{{ o.plan_key }} — {{ '{:,}'.format(o.amount_rial // 10) }} تومان</span>
      <span class="chip" style="font-size:.75rem;">{{ o.status }}</span>
    </div>
    {% else %}
    <p class="muted" style="padding-top:8px;">سفارشی ثبت نشده.</p>
    {% endfor %}
  </section>
  {% endif %}

  <div class="glass glow" style="margin-top:14px; padding:20px; text-align:right;">
    <h2 style="font-size:1.05rem;">🎁 دعوت از دوستان</h2>
    <p class="muted" style="font-size:.85rem;">نفر جدید با لینک تو ۱۰٪ تخفیف می‌گیرد؛ تو ۵٪ پاداش ثبت می‌کنی.</p>
    <div style="display:flex; gap:8px; margin-top:10px; direction:ltr;">
      <input id="refLink" readonly value="{{ ref_url }}" style="flex:1; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06); color:#eee; font-size:.85rem;">
      <button onclick="navigator.clipboard.writeText(document.getElementById('refLink').value)" class="btn" style="padding:10px 14px;">کپی</button>
    </div>
  </div>

  <div style="margin-top:18px; display:flex; gap:10px;">
    <a class="btn btn-ghost" href="/plans" style="flex:1; text-align:center;">مشاهده پلن‌ها</a>
    <a class="btn btn-ghost" href="/birth-form" style="flex:1; text-align:center;">چارت جدید</a>
  </div>
  <form method="post" action="/account/delete" onsubmit="return confirm('همه داده‌های تو (چارت‌ها، گزارش‌ها، سفارش‌ها) برای همیشه حذف می‌شود. ادامه می‌دهی؟')" style="margin-top:10px;">
    <button class="btn btn-ghost" style="width:100%; color:#ff6b6b; border-color:rgba(255,107,107,.4);">حذف کامل حساب و داده‌ها</button>
  </form>
  <a class="muted" href="/privacy" style="display:block; text-align:center; margin-top:14px; font-size:.8rem;">حریم خصوصی</a>
</div>
{% endblock %}


FILE: app/templates/account_login.html  (59 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:400px; margin:0 auto; padding:40px 12px;">
  <div class="glass glow" style="padding:26px; border-radius:18px; text-align:center;">
    <h1 style="font-size:1.3rem;">ورود با شماره موبایل</h1>
    <p class="muted" style="margin-top:8px; font-size:.85rem;">کد تأیید ۵ رقمی به موبایلت پیامک می‌شود</p>

    <div x-data="login()" x-cloak style="margin-top:18px; text-align:right;">
      <template x-if="!sent">
        <form @submit.prevent="send()">
          <label>شماره موبایل</label>
          <input class="input" type="tel" x-model="phone" inputmode="numeric" placeholder="09xxxxxxxxx" dir="ltr" style="text-align:left;">
          <button class="btn" type="submit" style="width:100%; margin-top:12px;" :disabled="busy" x-text="busy ? 'در حال ارسال…' : 'ارسال کد'"></button>
        </form>
      </template>
      <template x-if="sent">
        <form @submit.prevent="verify()">
          <label>کد تأیید</label>
          <input class="input" type="tel" x-model="code" inputmode="numeric" placeholder="00000" dir="ltr" style="text-align:left; letter-spacing:.5em;">
          <p class="muted" style="font-size:.8rem; margin-top:6px;" x-show="devCode">کد تست (dev): <b x-text="devCode" style="color:#f5c518;"></b></p>
          <button class="btn" type="submit" style="width:100%; margin-top:12px;" :disabled="busy" x-text="busy ? 'در حال ورود…' : 'ورود'"></button>
          <button type="button" class="muted" style="background:none; border:none; margin-top:10px; width:100%; font-size:.8rem;" @click="sent=false">تغییر شماره</button>
        </form>
      </template>
      <p x-show="error" x-text="error" style="color:#ff6b6b; margin-top:10px; font-size:.85rem;"></p>
    </div>
  </div>
</div>

<script>
function login(){
  return {
    phone: '', code: '', sent: false, busy: false, error: '', devCode: '',
    async send(){
      this.busy = true; this.error = '';
      try{
        const fd = new FormData(); fd.append('phone', this.phone);
        const r = await fetch('/api/auth/otp/request', {method:'POST', body: fd});
        const d = await r.json();
        if(!r.ok) throw new Error(d.detail || 'خطا');
        this.sent = true; this.devCode = d.dev_code || '';
      }catch(e){ this.error = e.message; }
      finally{ this.busy = false; }
    },
    async verify(){
      this.busy = true; this.error = '';
      try{
        const fd = new FormData(); fd.append('phone', this.phone); fd.append('code', this.code);
        const r = await fetch('/api/auth/otp/verify', {method:'POST', body: fd});
        if(!r.ok){ const d = await r.json().catch(()=>({})); throw new Error(d.detail || 'کد نادرست'); }
        window.location.href = '/account';
      }catch(e){ this.error = e.message; }
      finally{ this.busy = false; }
    }
  };
}
</script>
{% endblock %}


FILE: app/templates/admin.html  (166 lines)
======================================================================
{% extends "base.html" %}
{% block robots %}<meta name="robots" content="noindex,nofollow">{% endblock %}
{% block content %}
<div style="max-width:1000px;margin:0 auto;padding:24px 14px 50px;">
  <h1 style="font-size:24px;font-weight:800;margin-bottom:18px;">دشبورد مدیریت 🛠️</h1>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px;">
    <div class="kpi"><b>{{ "{:,}".format(revenue_toman) }} تومان</b><span>درآمد پرداختی</span></div>
    {% for s, n in by_status.items() %}
    <div class="kpi"><b>{{ n }}</b><span>سفارش {{ {'pending':'در انتظار','paid':'پرداخت‌شده','failed':'ناموفق'}.get(s, s) }}</span></div>
    {% endfor %}
    <div class="kpi"><b>{{ reports|selectattr('status','equalto','done')|list|length }}</b><span>گزارش آماده</span></div>
    <div class="kpi"><b>{{ llm_cost_7d }}$</b><span>هزینه AI (۷ روز) — {{ llm_runs_7d }} درخواست</span></div>
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">پلن‌ها</h2>
  <div class="glass" style="overflow-x:auto;padding:4px;">
    <table style="width:100%;border-collapse:collapse;font-size:.85rem;min-width:560px;">
      <thead><tr style="color:var(--muted);text-align:right;"><th style="padding:10px 8px;">کلید</th><th>نام</th><th>قیمت (تومان)</th><th>فعال</th><th>ذخیره</th></tr></thead>
      <tbody>
        {% for p in plans %}
        <tr style="border-top:1px solid var(--stroke);">
          <td style="padding:9px 8px;" dir="ltr">{{ p.key }}</td>
          <td>{{ p.name_fa }}</td>
          <td><input x-data x-model="$store.plans['{{ p.key }}'].price" x-init="$store.plans['{{ p.key }}'] = {price: {{ p.price_toman }}, active: {{ 'true' if p.active else 'false' }}}" type="number" style="width:110px;background:rgba(255,255,255,.08);border:1px solid var(--stroke);border-radius:8px;padding:6px 8px;color:#fff;"></td>
          <td><label><input type="checkbox" x-data x-model="$store.plans['{{ p.key }}'].active" x-init="$store.plans['{{ p.key }}'] = {price: {{ p.price_toman }}, active: {{ 'true' if p.active else 'false' }}}"> فعال</label></td>
          <td><button class="btn" style="padding:5px 12px;font-size:.8rem;" @click="savePlan('{{ p.key }}')">💾</button></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">کاربران (آخرین ۵۰)</h2>
  <div class="glass" style="overflow-x:auto;padding:4px;">
    <table style="width:100%;border-collapse:collapse;font-size:.85rem;min-width:560px;">
      <thead><tr style="color:var(--muted);text-align:right;"><th style="padding:10px 8px;">تاریخ</th><th>موبایل</th><th>نام</th><th>نقش</th><th>وضعیت</th></tr></thead>
      <tbody>
        {% for u in users %}
        <tr style="border-top:1px solid var(--stroke);">
          <td style="padding:9px 8px;white-space:nowrap;">{{ u.created_at.strftime('%m-%d') }}</td>
          <td dir="ltr">{{ u.phone or '—' }}</td>
          <td>{{ u.email or '—' }}</td>
          <td>{{ u.role }}</td>
          <td>{{ u.status }}</td>
        </tr>
        {% endfor %}
        {% if not users %}<tr><td colspan="5" style="padding:14px;text-align:center;color:var(--muted);">کاربری ثبت نشده</td></tr>{% endif %}
      </tbody>
    </table>
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">لاگ ممیزی (آخرین ۳۰)</h2>
  <div class="glass" style="overflow-x:auto;padding:4px;">
    <table style="width:100%;border-collapse:collapse;font-size:.82rem;min-width:560px;">
      <thead><tr style="color:var(--muted);text-align:right;"><th style="padding:10px 8px;">زمان</th><th>ادمین</th><th>عملیات</th><th>موجودیت</th><th>جزئیات</th></tr></thead>
      <tbody>
        {% for a in audit %}
        <tr style="border-top:1px solid var(--stroke);">
          <td style="padding:8px;white-space:nowrap;">{{ a.created_at.strftime('%m-%d %H:%M') }}</td>
          <td>{{ a.admin }}</td>
          <td dir="ltr">{{ a.action }}</td>
          <td dir="ltr">{{ a.entity }}</td>
          <td style="color:var(--muted);">{{ a.details }}</td>
        </tr>
        {% endfor %}
        {% if not audit %}<tr><td colspan="5" style="padding:14px;text-align:center;color:var(--muted);">لاگی ثبت نشده</td></tr>{% endif %}
      </tbody>
    </table>
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">پرامپت‌ها (اورراید نسخه‌بندی‌شده)</h2>
  <p class="muted" style="font-size:.78rem;margin-bottom:8px;">متن جایگزین پرامپت در تولید گزارش‌های بعدی — نسخه‌ی جدید، نسخه‌ی قبلی را غیرفعال می‌کند.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;">
    {% for k in prompt_keys %}
    <div style="border:1px solid var(--stroke);border-radius:12px;padding:12px;background:rgba(255,255,255,.03);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <b style="font-size:.85rem;">{{ k }}</b>
        {% set pv = prompt_overrides|selectattr('key','equalto',k)|first %}
        <span style="font-size:.72rem;color:var(--muted);">{% if pv %}v{{ pv.version }}{% if pv.is_active %} ✅{% endif %}{% else %}پیش‌فرض{% endif %}</span>
      </div>
      <textarea id="prompt-{{ k }}" rows="5" style="width:100%;background:rgba(255,255,255,.06);border:1px solid var(--stroke);border-radius:8px;padding:8px;color:#fff;font-size:.78rem;direction:ltr;text-align:left;" placeholder="متن پیش‌فرض — فقط برای ویرایش بنویسید">{{ pv.content if pv and pv.is_active else '' }}</textarea>
      <button onclick="savePrompt('{{ k }}')" style="margin-top:8px;width:100%;padding:7px;border-radius:8px;background:linear-gradient(135deg,#8b5cf6,#6366f1);border:none;color:#fff;font-weight:700;cursor:pointer;">ذخیره نسخه‌ی جدید</button>
    </div>
    {% endfor %}
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">سفارش‌ها (آخرین ۱۰۰)</h2>
  <div class="glass" style="overflow-x:auto;padding:4px;">
    <table style="width:100%;border-collapse:collapse;font-size:.85rem;min-width:600px;">
      <thead>
        <tr style="color:var(--muted);text-align:right;">
          <th style="padding:10px 8px;">تاریخ</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>پیگیری</th><th>گزارش</th>
        </tr>
      </thead>
      <tbody>
        {% for o in orders %}
        <tr style="border-top:1px solid var(--stroke);">
          <td style="padding:9px 8px;white-space:nowrap;">{{ o.created_at.strftime('%m-%d %H:%M') }}</td>
          <td>{{ o.plan_key }}</td>
          <td>{{ "{:,}".format(o.amount_rial // 10) }} ت</td>
          <td style="color:{% if o.status == 'paid' %}#2a9d8f{% elif o.status == 'failed' %}#c0392b{% else %}#f5c518{% endif %};font-weight:700;">
            {{ {'pending':'در انتظار','paid':'پرداخت‌شده','failed':'ناموفق'}.get(o.status, o.status) }}
          </td>
          <td dir="ltr">{{ o.ref_id or '—' }}</td>
          <td>
            {{ '✔' if o.report_id else '—' }}
            {% if o.status == 'paid' %}
            <button onclick="regenOrder('{{ o.id }}')" title="بازتولید گزارش ناموفق" style="margin-right:6px;padding:3px 8px;border-radius:6px;background:rgba(139,92,246,.15);border:1px solid #8b5cf6;color:#c4b5fd;font-size:.72rem;cursor:pointer;">↻ بازتولید</button>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
        {% if not orders %}<tr><td colspan="6" style="padding:14px;text-align:center;color:var(--muted);">سفارشی ثبت نشده</td></tr>{% endif %}
      </tbody>
    </table>
  </div>

  <h2 style="font-size:17px;font-weight:700;margin:20px 0 10px;">گزارش‌ها (آخرین ۲۰)</h2>
  <div class="glass" style="overflow-x:auto;padding:4px;">
    <table style="width:100%;border-collapse:collapse;font-size:.85rem;min-width:600px;">
      <thead><tr style="color:var(--muted);text-align:right;"><th style="padding:10px 8px;">تاریخ</th><th>وضعیت</th><th>بخش‌ها</th><th>PDF</th></tr></thead>
      <tbody>
        {% for r in reports %}
        <tr style="border-top:1px solid var(--stroke);">
          <td style="padding:9px 8px;white-space:nowrap;">{{ r.created_at.strftime('%m-%d %H:%M') }}</td>
          <td style="color:{% if r.status == 'done' %}#2a9d8f{% elif r.status == 'failed' %}#c0392b{% else %}#f5c518{% endif %};font-weight:700;">{{ r.status }}</td>
          <td>{{ r.sections|length if r.sections else 0 }}</td>
          <td>{% if r.pdf_path %}<a href="/api/reports/{{ r.id }}/pdf" style="color:#f5c518;">دانلود</a>{% else %}—{% endif %}</td>
        </tr>
        {% endfor %}
        {% if not reports %}<tr><td colspan="4" style="padding:14px;text-align:center;color:var(--muted);">گزارشی ثبت نشده</td></tr>{% endif %}
      </tbody>
    </table>
  </div>
  <script>
    document.addEventListener('alpine:init', () => { Alpine.store('plans', {}); });
    async function regenOrder(id){
      if (!confirm('گزارش ناموفق این سفارش دوباره در صف تولید قرار می‌گیرد. ادامه می‌دهی؟')) return;
      const r = await fetch('/api/admin/orders/' + id + '/regenerate', {method:'POST'});
      const j = await r.json();
      if (j.ok) { alert('در صف تولید قرار گرفت (گزارش ' + j.report_id.slice(0,8) + ')'); location.reload(); }
      else alert('خطا: ' + (j.detail || 'نامشخص'));
    }
    async function savePrompt(key){
      const content = document.getElementById('prompt-' + key).value.trim();
      if (!content) return alert('متن خالی است');
      const fd = new FormData(); fd.append('content', content);
      const r = await fetch('/api/admin/prompts/' + key, {method:'POST', body:fd});
      const j = await r.json();
      if (j.ok) { alert('نسخه ' + j.version + ' ذخیره شد'); location.reload(); }
      else alert('خطا: ' + (j.detail || 'نامشخص'));
    }
    async function savePlan(key){
      const p = Alpine.store('plans')[key];
      if (!p) return;
      const fd = new FormData();
      fd.set('price_toman', p.price); fd.set('active', p.active ? '1' : '0');
      const r = await fetch('/api/admin/plans/' + key, {method:'PUT', body: fd});
      const d = await r.json();
      if (!r.ok) alert(d.detail || 'خطا');
    }
  </script>
</div>
{% endblock %}


FILE: app/templates/admin_login.html  (19 lines)
======================================================================
{% extends "base.html" %}
{% block robots %}<meta name="robots" content="noindex,nofollow">{% endblock %}
{% block content %}
<div style="max-width:420px;margin:0 auto;padding:40px 18px;">
  <div class="glass" style="padding:28px;border-radius:18px;text-align:center;">
    <div style="font-size:42px;margin-bottom:8px;">🔐</div>
    <h1 style="font-size:20px;font-weight:800;margin-bottom:16px;">ورود مدیریت</h1>
    {% if error %}<p style="color:#ff6b6b;margin-bottom:12px;">{{ error }}</p>{% endif %}
    <form method="post" action="/admin/login">
      <input name="pin" type="password" inputmode="numeric" pattern="[0-9]*" required
             placeholder="رمز ورود (فقط عدد)"
             style="width:100%;padding:14px;border-radius:12px;border:1px solid rgba(255,255,255,.15);
                    background:rgba(255,255,255,.06);color:var(--txt);font-size:18px;text-align:center;letter-spacing:6px;margin-bottom:14px;">
      <button type="submit" class="btn btn-lg" style="width:100%;">ورود</button>
    </form>
  </div>
</div>
{% endblock %}


FILE: app/templates/article.html  (33 lines)
======================================================================
{% extends 'base.html' %}
{% block title %}{{ art.title }}{% endblock %}
{% block meta %}<meta name="description" content="{{ art.meta }}">{% if art.keywords %}<meta name="keywords" content="{{ art.keywords }}">{% endif %}{% endblock %}
{% block content %}
<div class="wrap" style="max-width:760px;margin:0 auto;padding:40px 16px 80px;">
  <a href="/articles" style="font-size:.8rem;color:#9a92b0;text-decoration:none;">→ همه‌ی مقالات</a>
  <div class="article-banner" style="border-radius:18px; overflow:hidden; border:1px solid rgba(255,255,255,.08); margin:14px 0 18px; direction:ltr;">{{ banner_svg | safe }}</div>
  <h1 style="font-size:1.5rem;margin:10px 0 6px;line-height:1.6;">{{ art.title }}</h1>
  <div style="font-size:.75rem;color:#9a92b0;margin-bottom:16px;">{{ art.category }} · {{ art.date_fa }}</div>
  {% if art.image %}<img src="{{ art.image }}" alt="{{ art.title }}" style="width:100%;max-height:320px;object-fit:cover;border-radius:14px;margin-bottom:20px;">{% endif %}
  <article style="line-height:2;color:#ddd6ea;font-size:.95rem;">
    {% for sec in art.body %}
    {% if sec.h2 %}<h2 style="font-size:1.15rem;color:#d4af37;margin:26px 0 10px;">{{ sec.h2 }}</h2>{% endif %}
    <p style="margin-bottom:14px;">{{ sec.p }}</p>
    {% endfor %}
  </article>
  <div style="margin-top:36px;padding:20px;background:rgba(212,175,55,.08);border:1px solid rgba(212,175,55,.25);border-radius:14px;text-align:center;">
    <p style="margin-bottom:12px;font-weight:700;">این مطلب برایت جالب بود؟ چارت تولد خودت را ببین</p>
    <a class="btn-lg" href="/" style="display:inline-block;">ساخت چارت رایگان</a>
  </div>
  {% if others %}
  <div style="margin-top:40px;">
    <h2 style="font-size:1rem;color:#d4af37;margin-bottom:12px;">مقالات مرتبط</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;">
      {% for o in others %}
      <a href="/articles/{{ o.slug }}" style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:12px;text-decoration:none;font-size:.82rem;line-height:1.6;color:#f2edfa;">{{ o.title }}</a>
      {% endfor %}
    </div>
  </div>
  {% endif %}
</div>
{% endblock %}


FILE: app/templates/articles_index.html  (26 lines)
======================================================================
{% extends 'base.html' %}
{% block title %}{{ title }}{% endblock %}
{% block meta %}<meta name="description" content="{{ meta }}">{% endblock %}
{% block content %}
<div class="wrap" style="max-width:900px;margin:0 auto;padding:40px 16px 80px;">
  <h1 style="font-size:1.6rem;margin-bottom:6px;">{{ title }}</h1>
  <div style="height:3px;width:64px;background:linear-gradient(90deg,#d4af37,transparent);border-radius:2px;margin:10px 0 28px;"></div>
  {% if articles %}
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;">
    {% for a in articles %}
    <a href="/articles/{{ a.slug }}" style="display:block;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:14px;overflow:hidden;text-decoration:none;transition:transform .15s,border-color .15s;">
      {% if a.image %}<img src="{{ a.image }}" alt="{{ a.title }}" loading="lazy" style="width:100%;height:140px;object-fit:cover;display:block;">{% endif %}
      <div style="padding:14px;">
        <div style="font-size:.72rem;color:#d4af37;margin-bottom:6px;">{{ a.category }}</div>
        <div style="font-weight:700;font-size:.92rem;line-height:1.6;color:#f2edfa;">{{ a.title }}</div>
        <div style="font-size:.78rem;color:#9a92b0;margin-top:8px;">{{ a.excerpt }}</div>
      </div>
    </a>
    {% endfor %}
  </div>
  {% else %}
  <p style="color:#9a92b0;">مقالات به‌زودی منتشر می‌شوند.</p>
  {% endif %}
</div>
{% endblock %}


FILE: app/templates/base.html  (124 lines)
======================================================================
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  {% block robots %}{% endblock %}
  <title>{% block title %}چارت تولد{% endblock %}</title>
  <meta name="description" content="{% block description %}گزارش اختصاصی چارت تولد با محاسبه‌ی دقیق نجومی — شناخت شخصیت، مسیر شغلی، روابط و استعدادها.{% endblock %}">
  <meta property="og:title" content="{% block og_title %}چارت تولد — آینه‌ی خودشناسی{% endblock %}">
  <meta property="og:description" content="گزارش اختصاصی چارت تولد با محاسبه‌ی دقیق نجومی">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="fa_IR">
  <link rel="canonical" href="{{ request.url.scheme }}://{{ request.url.netloc }}{{ request.url.path }}">
  <meta name="theme-color" content="#0b1026">
  <link rel="manifest" href="/static/manifest.webmanifest">
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="apple-touch-icon" href="/static/icon-192.png">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"WebSite","name":"چارت تولد","inLanguage":"fa-IR","description":"گزارش اختصاصی چارت تولد با محاسبه‌ی دقیق نجومی"}
  </script>
  <script defer src="/static/vendor/alpine.min.js"></script>
  <script src="/static/vendor/htmx.min.js"></script>
  <script defer src="/static/sw-register.js"></script>
  <style>
    @font-face{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-Regular.ttf') format('truetype'); font-weight:400; font-display:swap; }
    @font-face{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-Medium.ttf') format('truetype'); font-weight:500; font-display:swap; }
    @font-face{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-Bold.ttf') format('truetype'); font-weight:700; font-display:swap; }
    @font-face{ font-family:'Vazirmatn'; src:url('/static/fonts/Vazirmatn-ExtraBold.ttf') format('truetype'); font-weight:800; font-display:swap; }
    /* ── Liquid Glass — plan v3.1 §11 ── */
    * { margin:0; padding:0; box-sizing:border-box; }
    :root{
      --bg:#0b1026; --bg2:#0e1533; --glass:rgba(255,255,255,.06);
      --stroke:rgba(255,255,255,.14); --gold:#f5c518; --txt:#e8ecff; --muted:#8fa3d8;
      --accent:#6a5acd; --radius:22px;
    }
    html,body{ background:radial-gradient(1200px 800px at 70% -10%, #1b2350 0%, var(--bg) 55%), var(--bg); color:var(--txt); font-family:Vazirmatn, Tahoma, sans-serif; min-height:100vh; overflow-x:hidden; }
    body{ padding-bottom:32px; }
    .starfield{ position:fixed; inset:0; pointer-events:none; opacity:.5; z-index:0;
      background-image:radial-gradient(1.5px 1.5px at 20% 30%, #fff8, transparent), radial-gradient(1px 1px at 80% 20%, #fffb, transparent),
      radial-gradient(1.2px 1.2px at 40% 70%, #fff6, transparent), radial-gradient(1px 1px at 60% 85%, #fff5, transparent),
      radial-gradient(1.8px 1.8px at 90% 55%, #fff4, transparent); }
    .wrap{ position:relative; z-index:1; max-width:960px; margin:0 auto; padding:0 16px; }
    /* glass card */
    .glass{ background:var(--glass); border:1px solid var(--stroke); border-radius:var(--radius);
      backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
      box-shadow:0 8px 32px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.08); }
    .glow{ box-shadow:0 0 40px rgba(106,90,205,.25), 0 8px 32px rgba(0,0,0,.4); }
    /* light bubble */
    .bubble{ position:absolute; border-radius:50%; filter:blur(60px); opacity:.5; pointer-events:none; }
    .btn{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:48px;
      padding:0 22px; border:none; border-radius:14px; cursor:pointer; font-family:inherit; font-size:1rem; font-weight:700;
      background:linear-gradient(135deg,#f5c518,#e08e0b); color:#1a1400; transition:transform .15s, box-shadow .15s; text-decoration:none; }
    .btn:active{ transform:scale(.97); }
    .btn-ghost{ background:rgba(255,255,255,.08); color:var(--txt); border:1px solid var(--stroke); }
    .btn-lg{ min-height:54px; padding:0 32px; font-size:1.1rem; border-radius:16px; }
    .chip{ display:inline-flex; align-items:center; min-height:44px; padding:0 16px; margin:4px;
      border:1px solid var(--stroke); border-radius:999px; background:rgba(255,255,255,.05); color:var(--txt); cursor:pointer; font-family:inherit; font-size:.95rem; transition:all .15s; }
    .chip.sel{ background:linear-gradient(135deg,#6a5acd,#4a3f8f); border-color:#8b7ce8; box-shadow:0 0 14px rgba(106,90,205,.45); }
    .input{ width:100%; min-height:50px; padding:0 14px; border-radius:14px; border:1px solid var(--stroke);
      background:rgba(255,255,255,.06); color:var(--txt); font-family:inherit; font-size:1rem; outline:none; }
    .input:focus{ border-color:var(--accent); box-shadow:0 0 0 3px rgba(106,90,205,.25); }
    .input::placeholder{ color:#6b7ab0; }
    label{ font-size:.85rem; color:var(--muted); display:block; margin:14px 0 6px; }
    h1{ font-size:clamp(1.6rem,4vw,2.4rem); line-height:1.35; }
    h2{ font-size:clamp(1.2rem,3vw,1.6rem); line-height:1.4; }
    .muted{ color:var(--muted); }
    .gold{ color:var(--gold); }
    .hidden{ display:none !important; }
    /* progress bar (glass step-by-step) */
    .steps{ display:flex; gap:8px; margin:18px 0 26px; }
    .step-dot{ flex:1; height:6px; border-radius:99px; background:rgba(255,255,255,.1); overflow:hidden; }
    .step-dot > i{ display:block; height:100%; width:0; background:linear-gradient(90deg,#f5c518,#e08e0b); border-radius:99px; transition:width .4s; }
    .step-dot.on > i{ width:100%; }
    /* sign cards */
    .sign-card{ background:rgba(255,255,255,.05); border:1px solid var(--stroke); border-radius:18px; padding:16px; text-align:center; }
    .sign-card b{ display:block; font-size:1.05rem; margin-top:6px; }
    .sign-card span{ font-size:.8rem; color:var(--muted); }
    /* result boxes */
    .kpi{ background:rgba(255,255,255,.05); border:1px solid var(--stroke); border-radius:18px; padding:18px; }
    .kpi b{ font-size:1.15rem; display:block; }
    .kpi span{ font-size:.85rem; color:var(--muted); display:block; margin-top:4px; }
    [x-cloak]{ display:none !important; }
    @media (max-width:640px){ .wrap{ padding:0 12px; } .btn-lg{ width:100%; } }
  .help-tip { position: relative; display: inline-flex; vertical-align: middle; margin-inline-start: 5px; }
  .help-tip-btn { width: 18px; height: 18px; border-radius: 50%; border: 1px solid var(--accent, #d4af37); color: var(--accent, #d4af37); background: transparent; font-size: .7rem; line-height: 1; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; padding: 0; font-family: inherit; }
  .help-tip-btn:hover { background: var(--accent, #d4af37); color: #1a1626; }
  .help-tip-box { position: absolute; z-index: 50; top: 24px; inset-inline-start: 0; width: 240px; max-width: 72vw; background: #241f33; border: 1px solid rgba(212,175,55,.35); border-radius: 10px; padding: 10px 12px; font-size: .8rem; line-height: 1.7; color: #e8e2f5; box-shadow: 0 8px 24px rgba(0,0,0,.45); text-align: start; font-weight: 400; }
  .help-tip-box::before { content: ''; position: absolute; top: -5px; inset-inline-start: 10px; width: 8px; height: 8px; background: #241f33; border-inline-start: 1px solid rgba(212,175,55,.35); border-top: 1px solid rgba(212,175,55,.35); transform: rotate(45deg); }
  .article-banner svg { width: 100%; height: auto; display: block; }
  </style>
</head>
<body>
  <div style="position:fixed; inset:0; overflow:hidden; pointer-events:none; z-index:0;">
    <div class="starfield"></div>
    <div class="bubble" style="width:260px;height:260px;background:#6a5acd;top:-60px;right:-60px;"></div>
    <div class="bubble" style="width:200px;height:200px;background:#2a9d8f;bottom:10%;left:-70px;"></div>
  </div>
  <div class="wrap" style="position:relative; z-index:1;">
    <nav style="display:flex; justify-content:space-between; align-items:center; padding:14px 2px 0;">
      <a href="/" style="font-weight:800; text-decoration:none; font-size:1.05rem;">🔭 چارت تولد</a>
      <div style="display:flex; gap:8px; font-size:.85rem; flex-wrap:wrap; justify-content:flex-end;">
        <a href="/articles" class="chip" style="text-decoration:none;">مقالات</a>
        <a href="/guide" class="chip" style="text-decoration:none;">راهنما</a>
        <a href="/birth-form" class="chip" style="text-decoration:none;">چارت رایگان</a>
        <a href="/account" class="chip" style="text-decoration:none;">حساب من</a>
      </div>
    </nav>
    {% block content %}{% endblock %}
    <footer style="margin-top:60px;padding:24px 2px 32px;border-top:1px solid rgba(255,255,255,.07);display:flex;flex-wrap:wrap;gap:14px;justify-content:space-between;align-items:center;font-size:.8rem;color:#9a92b0;">
      <div>🔭 چارت تولد — نقشه‌ی آسمان تو</div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;">
        <a href="/guide" style="text-decoration:none;color:inherit;">راهنما</a>
        <a href="/about" style="text-decoration:none;color:inherit;">درباره ما</a>
        <a href="/faq" style="text-decoration:none;color:inherit;">سؤالات پرتکرار</a>
        <a href="/articles" style="text-decoration:none;color:inherit;">مقالات</a>
        <a href="/privacy" style="text-decoration:none;color:inherit;">حریم خصوصی</a>
      </div>
    </footer>
  </div>
</body>
</html>


FILE: app/templates/chart.html  (152 lines)
======================================================================
{% extends "base.html" %}
{% block robots %}<meta name="robots" content="noindex,nofollow">{% endblock %}
{% block content %}
<div style="padding-top:36px;" x-data="reportState()" x-init="init()">
  <a href="/birth-form" class="muted" style="text-decoration:none; font-size:.9rem;">→ فرم جدید</a>
  <h1 style="margin-top:10px;">چارت تولد تو</h1>
  <p class="muted">محاسبه‌شده با موتور Swiss Ephemeris — دقت درجه‌ای</p>

  <!-- chart wheel -->
  <div class="glass glow" style="margin-top:18px; padding:14px; max-width:560px; margin-left:auto; margin-right:auto;">
    {{ svg | safe }}
  </div>

  <!-- Big Three -->
  <section style="margin-top:22px; padding:22px;" class="glass">
    <h2>سه‌گانه‌ی اصلی <span class="muted" style="font-size:.9rem;">(Big Three)</span></h2>
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-top:14px;">
      {% for key, label in [('Sun','خورشید'), ('Moon','ماه')] + ([('ASC','طالع')] if 'ASC' in big_three else []) %}
      {% set bt = big_three[key] %}
      <div class="sign-card" style="border-top:4px solid {{ bt.color }};">
        <div style="font-size:1.4rem;">{{ '☉' if key == 'Sun' else ('☽' if key == 'Moon' else '↑') }}</div>
        <b>{{ bt.sign_fa }}</b>
        <span>{{ label }} — {{ bt.element }} {{ bt.modality }}</span>
        <span style="color:{{ bt.color }}; margin-top:6px;">{{ bt.tone }}</span>
      </div>
      {% endfor %}
    </div>
  </section>

  <!-- visual widgets (plan §9.3) -->
  <section class="glass" style="margin-top:14px; padding:16px;">
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px;">
      {% if aspect_grid %}<div>{{ aspect_grid | safe }}</div>{% endif %}
      {% if element_donut %}<div>{{ element_donut | safe }}</div>{% endif %}
      {% if house_bar %}<div>{{ house_bar | safe }}</div>{% endif %}
    </div>
  </section>

  <!-- free insights (plan §8): Big Three + rule-engine preview -->
  <section class="glass" style="margin-top:22px; padding:22px;">
    <h2>نکته‌های کوتاه</h2>
    <ul style="margin-top:12px; list-style:none;">
      <li style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07); display:flex; gap:10px;">
        <span>🌙</span><span>ماه در {{ big_three['Moon'].sign_fa }} — {{ big_three['Moon'].gift }}؛ چالش: {{ big_three['Moon'].challenge }}</span>
      </li>
      <li style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07); display:flex; gap:10px;">
        <span>☀️</span><span>خورشید در {{ big_three['Sun'].sign_fa }} — {{ big_three['Sun'].gift }}؛ چالش: {{ big_three['Sun'].challenge }}</span>
      </li>
      {% if 'ASC' in big_three %}
      <li style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07); display:flex; gap:10px;">
        <span>⬆️</span><span>طالع {{ big_three['ASC'].sign_fa }} — {{ big_three['ASC'].gift }}؛ چالش: {{ big_three['ASC'].challenge }}</span>
      </li>
      {% endif %}
      <template x-for="ins in insights" :key="ins.domain">
        <li style="padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07); display:flex; gap:10px;">
          <span>✨</span><span x-text="ins.insight"></span>
        </li>
      </template>
    </ul>
    <p class="muted" style="font-size:.8rem; margin-top:8px;">برای تحلیل عمیق هر ۱۳ حوزه، گزارش کامل را تهیه کنید.</p>
  </section>

  <!-- annual transit timeline (plan §9.3) -->
  <section class="glass" style="margin-top:22px; padding:22px;">
    <h2>🌠 گذرهای سال آینده</h2>
    <p class="muted" style="font-size:.8rem; margin-top:4px;">وقتی سیارات کند (مشتری تا پلوتو) به سیارات شخصی چارتت می‌رسند — ماه به ماه.</p>
    <div style="margin-top:14px; overflow-x:auto; direction:ltr;">
      <img src="/api/charts/{{ chart.id }}/transit-year.svg" alt="نقشه گذرهای سالانه" loading="lazy" style="min-width:640px; width:100%;">
    </div>
  </section>

  <!-- CTA -->
  <section class="glass glow" style="margin-top:22px; padding:26px; text-align:center;">
    <h2>گزارش کامل — ۵۰ تا ۶۰ صفحه</h2>
    <p class="muted" style="margin-top:8px;">۱۳ حوزه‌ی زندگی + ترانزیت ۳ ساله + فصل اسلامی + PDF/Word</p>
    <div style="display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin:18px 0 8px;">
      <span class="chip">پایه ۱۴۹ هزار</span>
      <span class="chip">استاندارد ۳۴۹ هزار</span>
      <span class="chip">پرمیوم ۶۹۹ هزار</span>
    </div>
    <a class="btn btn-lg" href="/plans?chart={{ chart.id }}">خرید گزارش کامل ✨</a>
    <a class="btn btn-lg btn-ghost" href="/chat/{{ chart.id }}" style="margin-top:10px;">💬 گفت‌وگو با چارت</a>
    <button class="btn btn-lg btn-ghost" style="margin-top:10px;" @click="share()">📤 اشتراک‌گذاری چارت</button>
    <a class="btn btn-lg btn-ghost" href="/transit/{{ chart.id }}" style="margin-top:10px;">🌠 گذرهای کنونی</a>
    <div style="margin-top:14px;">
      <button class="btn btn-lg" id="genBtn" @click.prevent="genReport($event)">تولید گزارش کامل ✨</button>
      <div id="reportBox" style="margin-top:14px;" x-cloak>
        <template x-if="repStatus === 'queued' || repStatus === 'running'">
          <p class="muted">⏳ در حال تولید گزارش (۳–۵ دقیقه)...</p>
        </template>
        <template x-if="repStatus === 'done'">
          <a class="btn btn-lg" :href="pdfUrl" style="text-decoration:none;">📄 دانلود گزارش PDF</a>
        </template>
        <template x-if="repStatus === 'failed'">
          <p style="color:#ff6b6b;">تولید گزارش با خطا مواجه شد. لطفاً دوباره تلاش کنید.</p>
        </template>
      </div>
    </div>
  </section>
</div>
<script>
function reportState(){
  return {
    repStatus: '', pdfUrl: '', repId: '', checked: false, insights: [],
    share(){
      const url = location.origin + '/chart/{{ chart.id }}';
      const card = location.origin + '/api/share/{{ chart.id }}.png';
      window.open('https://t.me/share/url?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent('چارت تولد من ✨'), '_blank');
    },
    async init(){
      if(this.checked) return;
      this.checked = true;
      try{
        const p = await fetch('/api/charts/{{ chart.id }}/preview');
        const pd = await p.json();
        this.insights = (pd.insights || []).slice(0, 5);
      }catch(_e){}
      const r = await fetch('/api/charts/{{ chart.id }}/report');
      const d = await r.json();
      if(d.status === 'queued' || d.status === 'running'){ this.repStatus = d.status; this._poll(); }
      else if(d.status === 'done'){ this.repStatus = 'done'; this.pdfUrl = d.pdf_url; }
    },
    async genReport(e){
      const btn = e.currentTarget; btn.disabled = true; btn.style.opacity = .6;
      const r = await fetch('/api/charts/{{ chart.id }}/report', {method:'POST'});
      const d = await r.json();
      this.repId = d.report_id;
      if(d.queued){ this.repStatus = 'queued'; this._poll(); }
      else if(r.status === 403){
        this.repStatus = 'failed';
        location.href = '/plans?chart={{ chart.id }}';
      }
      else { this.repStatus = 'failed'; btn.disabled = false; btn.style.opacity = 1; }
    },
    async _poll(){
      while(this.repStatus === 'queued' || this.repStatus === 'running'){
        await new Promise(r => setTimeout(r, 6000));
        const r = await fetch('/api/charts/{{ chart.id }}/report');
        const d = await r.json();
        this.repStatus = d.status;
        if(d.pdf_url) this.pdfUrl = d.pdf_url;
        if(d.status === 'failed' || d.status === 'done'){
          const btn = document.getElementById('genBtn');
          if(btn){ btn.disabled = false; btn.style.opacity = 1; }
        }
      }
    }
  }
}
</script>
{% endblock %}


FILE: app/templates/chat.html  (64 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:720px;margin:0 auto;padding:20px 14px 40px;" x-data="chat()" x-init="init()">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
    <h1 style="font-size:22px;font-weight:800;color:#e8ecff;">گفت‌وگو با چارت تولد ✨</h1>
    <a class="btn btn-ghost" href="/chart/{{ chart_id }}" style="min-height:40px;padding:0 16px;font-size:.85rem;">← چارت</a>
  </div>
  <p class="muted" style="font-size:.9rem;margin-bottom:14px;">
    از چارتت هر چیزی بپرس: شخصیت، شغل، روابط، انرژی، آینده... پاسخ بر اساس محاسبهی دقیق چارت و گزارش اختصاصی توست.
  </p>

  <div id="msgs" style="display:flex;flex-direction:column;gap:10px;min-height:46vh;max-height:58vh;overflow-y:auto;padding:4px;" x-ref="box">
    <template x-for="m in msgs" :key="m.id">
      <div :style="m.me ? 'align-self:flex-end;background:linear-gradient(135deg,#6a5acd,#4a3f8f);color:#fff;border-radius:16px 16px 4px 16px;' : 'align-self:flex-start;background:rgba(255,255,255,.08);border:1px solid var(--stroke);color:#e8ecff;border-radius:16px 16px 16px 4px;'"
           style="max-width:82%;padding:11px 15px;font-size:.95rem;line-height:1.7;white-space:pre-wrap;">
        <span x-text="m.text"></span>
      </div>
    </template>
    <div x-show="busy" style="align-self:flex-start;color:var(--muted);font-size:.9rem;">⏳ در حال نوشتن...</div>
  </div>

  <form @submit.prevent="send()" style="display:flex;gap:8px;margin-top:12px;">
    <input class="input" x-model="q" placeholder="مثلاً: چه مسیر شغلی برای من بهتر است؟" required maxlength="500"
           :disabled="busy" style="flex:1;">
    <button class="btn btn-lg" :disabled="busy" style="min-height:50px;padding:0 22px;">ارسال</button>
  </form>

  <template x-if="locked">
    <p style="color:#ffb454;font-size:.9rem;margin-top:12px;text-align:center;">
      🔒 گفت‌وگو با چارت بخشی از پلن‌های <b>کامل</b> و <b>طلایی</b> است — <a href="/plans?chart={{ chart_id }}" style="color:#f5c518;">خرید و فعال‌سازی</a>
    </p>
  </template>
</div>
<script>
function chat(){
  return {
    msgs: [], q: '', busy: false, locked: false,
    async init(){
      const r = await fetch('/api/chat/access/{{ chart_id }}');
      const d = await r.json();
      this.locked = !d.allowed;
    },
    async send(){
      const text = this.q.trim(); if(!text || this.busy) return;
      this.msgs.push({id: Date.now(), text, me:true}); this.q=''; this.busy=true;
      this.$nextTick(() => { const b=this.$refs.box; b.scrollTop=b.scrollHeight; });
      try{
        const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
          body: new URLSearchParams({chart_id:'{{ chart_id }}', question:text})});
        const d = await r.json();
        if(r.status === 403){ this.locked = true; }
        else if(d.answer){ this.msgs.push({id: Date.now()+1, text: d.answer, me:false}); }
        else { this.msgs.push({id: Date.now()+1, text: 'پاسخی آماده نشد؛ دوباره تلاش کنید.', me:false}); }
      }catch(e){
        this.msgs.push({id: Date.now()+1, text: 'خطا در ارتباط با سرور.', me:false});
      }
      this.busy=false;
      this.$nextTick(() => { const b=this.$refs.box; b.scrollTop=b.scrollHeight; });
    }
  }
}
</script>
{% endblock %}


FILE: app/templates/faq.html  (22 lines)
======================================================================
{% extends 'base.html' %}
{% block title %}{{ title }}{% endblock %}
{% block meta %}<meta name="description" content="{{ meta }}">{% endblock %}
{% block content %}
<div class="wrap" style="max-width:760px;margin:0 auto;padding:40px 16px 80px;">
  <h1 style="font-size:1.6rem;margin-bottom:6px;">{{ title }}</h1>
  <div style="height:3px;width:64px;background:linear-gradient(90deg,#d4af37,transparent);border-radius:2px;margin:10px 0 28px;"></div>
  {% for item in items %}
  <details style="margin-bottom:12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:14px 16px;">
    <summary style="cursor:pointer;font-weight:700;font-size:.95rem;list-style:none;display:flex;justify-content:space-between;align-items:center;">
      {{ item.q }}<span style="color:#d4af37;">▾</span>
    </summary>
    <p style="margin-top:10px;line-height:1.9;color:#d9d2e8;font-size:.9rem;">{{ item.a }}</p>
  </details>
  {% endfor %}
  <div style="margin-top:40px;padding:20px;background:rgba(212,175,55,.08);border:1px solid rgba(212,175,55,.25);border-radius:14px;text-align:center;">
    <p style="margin-bottom:12px;font-weight:700;">سؤال دیگری داری؟</p>
    <a class="btn-lg" href="/" style="display:inline-block;">ساخت چارت رایگان</a>
  </div>
</div>
{% endblock %}


FILE: app/templates/form.html  (121 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="padding-top:36px;">
  <a href="/" class="muted" style="text-decoration:none; font-size:.9rem;">→ بازگشت</a>
  <h1 style="margin-top:10px;">فرم تولد</h1>
  <p class="muted">۵ گام ساده — چارت رایگان تو چند ثانیه آماده می‌شود.</p>

  <form id="birthForm" class="glass glow" style="padding:24px 20px;" x-data="formState()" @submit.prevent="submit($event)" x-cloak>
    <div class="steps">
      <template x-for="(s, i) in 5" :key="i">
        <div class="step-dot" :class="{'on': i < step}"><i></i></div>
      </template>
    </div>
    <!-- STEP 1: date -->
    <div x-show="step === 1" x-transition>
      <label>نوع تقویم {% with text='شمسی = تقویم ایرانی (جلالی)؛ میلادی = تقویم بین‌المللی. اگر تاریخ تولدت شمسی است «شمسی» را انتخاب کن — ما خودمان تبدیل می‌کنیم.' %}{% include 'partials/help_tip.html' %}{% endwith %}</label>
      <div>
        <button type="button" class="chip" :class="{'sel': cal === 'jalali'}" @click="cal = 'jalali'">شمسی</button>
        <button type="button" class="chip" :class="{'sel': cal === 'gregorian'}" @click="cal = 'gregorian'">میلادی</button>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;">
        <div><label>سال</label><input class="input" type="number" x-model.number="year" :placeholder="cal === 'jalali' ? '۱۳۷۳' : '۱۹۹۴'" min="1300" max="2100"></div>
        <div><label>ماه</label><input class="input" type="number" x-model.number="month" min="1" max="12"></div>
        <div><label>روز</label><input class="input" type="number" x-model.number="day" min="1" max="31"></div>
      </div>
    </div>

    <!-- STEP 2: time -->
    <div x-show="step === 2" x-transition>
      <label>ساعت تولد را می‌دانی؟ {% with text='ساعت دقیق تولد برای محاسبه‌ی طالع (برجِ طلوع‌کننده) و خانه‌های نجومی لازم است. اگر ساعت را نمی‌دانی، «نه» را بزن — خورشید و ماه و سیارات همچنان کامل محاسبه می‌شوند.' %}{% include 'partials/help_tip.html' %}{% endwith %}</label>
      <div>
        <button type="button" class="chip" :class="{'sel': timeKnown}" @click="timeKnown = true">بله، دقیق</button>
        <button type="button" class="chip" :class="{'sel': !timeKnown}" @click="timeKnown = false">نه / تقریبی</button>
      </div>
      <template x-if="timeKnown">
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px;">
          <div><label>ساعت</label><input class="input" type="number" x-model.number="hour" min="0" max="23"></div>
          <div><label>دقیقه</label><input class="input" type="number" x-model.number="minute" min="0" max="59"></div>
        </div>
      </template>
      <p class="muted" style="margin-top:10px; font-size:.85rem;" x-show="!timeKnown">بدون ساعت دقیق، طالع و خانه‌ها نمایش داده نمی‌شوند — اما خورشید، ماه و سیارات کامل محاسبه می‌شوند.</p>
    </div>

    <!-- STEP 3: city -->
    <div x-show="step === 3" x-transition>
      <label>شهر تولد {% with text='شهر برای مختصات جغرافیایی (عرض و طول) لازم است — موقعیت خورشید و خانه‌ها به محل تولد وابسته است. بیش از ۳۳۷ شهر ایران پشتیبانی می‌شود.' %}{% include 'partials/help_tip.html' %}{% endwith %}</label>
      <input class="input" type="text" x-model="cityQ" @input.debounce.250ms="searchCity()" placeholder="مثلاً تهران">
      <div style="margin-top:10px;">
        <template x-for="c in cities" :key="c.city_fa + c.province_fa">
          <button type="button" class="chip" :class="{'sel': picked === c.city_fa}" @click="pickCity(c)"><span x-text="c.city_fa"></span><span class="muted" style="font-size:.75rem;" x-text="' (' + c.province_fa + ')'"></span></button>
        </template>
      </div>
    </div>

    <!-- STEP 4: focus areas -->
    <div x-show="step === 4" x-transition>
      <label>حوزه‌های مورد علاقه‌ات (چندتایی) {% with text='بخش‌هایی از گزارش که بیشتر به آن‌ها علاقه‌داری. این انتخاب ترتیب و تأکید بخش‌های گزارش را شخصی‌سازی می‌کند — بعداً هم می‌توانی تغییرش بدهی.' %}{% include 'partials/help_tip.html' %}{% endwith %}</label>
      <div>
        <template x-for="a in areas" :key="a">
          <button type="button" class="chip" :class="{'sel': focus.includes(a)}" @click="toggleArea(a)" x-text="a"></button>
        </template>
      </div>
    </div>

    <!-- STEP 5: question + submit -->
    <div x-show="step === 5" x-transition>
      <label>سؤال شخصی (اختیاری)</label>
      <input class="input" type="text" x-model="question" placeholder="مثلاً: بهترین مسیر شغلی من چیست؟">
      <p class="muted" style="margin-top:12px; font-size:.9rem;">در گزارش کامل، پاسخ این سؤال با توجه به چارت تو تفسیر می‌شود.</p>
    </div>

    <div style="display:flex; gap:10px; margin-top:26px;">
      <button type="button" class="btn btn-ghost" x-show="step > 1" @click="step--" style="flex:1;">قبلی</button>
      <button type="button" class="btn" x-show="step < 5" @click="next()" style="flex:2;">ادامه</button>
      <button type="submit" class="btn" x-show="step === 5" style="flex:2;" :disabled="loading" x-text="loading ? 'در حال محاسبه…' : 'محاسبه چارت ✨'"></button>
    </div>
    <p x-show="error" x-text="error" style="color:#ff6b6b; margin-top:12px; font-size:.9rem;"></p>
  </form>
</div>

<script>
function formState(){
  return {
    step: 1, cal: 'jalali', year: 1373, month: 1, day: 1,
    timeKnown: true, hour: 12, minute: 0,
    cityQ: '', cities: [], picked: '', city: null,
    areas: ['هویت و شخصیت','ذهن و منطق','عواطف و شهود','پول و ثروت','شغل','روابط و ازدواج','خانواده','انرژی و تندرستی','خلاقیت','آموزش و مهاجرت','شبکه‌ها و دوستان','معنویت','کارما'],
    focus: [], question: '', loading: false, error: '',
    async searchCity(){
      if(!this.cityQ.trim()){ this.cities = []; return; }
      const r = await fetch('/api/cities?q=' + encodeURIComponent(this.cityQ));
      const d = await r.json(); this.cities = d.results;
    },
    pickCity(c){ this.picked = c.city_fa; this.city = c; this.cities = []; },
    toggleArea(a){ const i = this.focus.indexOf(a); i >= 0 ? this.focus.splice(i,1) : this.focus.push(a); },
    next(){
      if(this.step === 1 && (!this.year || !this.month || !this.day)){ this.error = 'تاریخ را کامل وارد کن'; return; }
      if(this.step === 3 && !this.city){ this.error = 'شهر تولد را انتخاب کن'; return; }
      this.error = ''; this.step++;
    },
    async submit(e){
      e.preventDefault(); this.loading = true; this.error = '';
      const fd = new FormData();
      fd.append('calendar', this.cal); fd.append('year', this.year); fd.append('month', this.month); fd.append('day', this.day);
      fd.append('time_known', this.timeKnown); fd.append('hour', this.hour); fd.append('minute', this.minute);
      fd.append('city_fa', this.picked); fd.append('lat', this.city ? this.city.lat : ''); fd.append('lon', this.city ? this.city.lon : '');
      fd.append('focus_areas', this.focus.join(','));
      try{
        const r = await fetch('/api/charts', {method:'POST', body: fd});
        const d = await r.json();
        if(!r.ok) throw new Error(d.detail || 'خطا');
        window.location.href = '/chart/' + d.chart_id;
      }catch(err){ this.error = err.message; }
      finally{ this.loading = false; }
    }
  };
}
document.addEventListener('alpine:init', () => { /* nothing — formState defined globally below */ });
</script>
{% endblock %}


FILE: app/templates/index.html  (42 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<header style="text-align:center; padding:56px 0 36px;">
  <div style="font-size:2.6rem; line-height:1;">🌌</div>
  <h1 style="margin-top:14px;">چارت تولدت را با دقت نجومی بشناس</h1>
  <p class="muted" style="margin-top:10px; font-size:1.05rem;">آینه‌ی خودشناسی، نه حکم درباره‌ی آینده.</p>
  <div style="margin-top:26px;">
    <a class="btn btn-lg" href="/birth-form">✨ چارت رایگان من</a>
  </div>
</header>

<section style="display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; margin-top:10px;">
  <div class="glass" style="padding:20px;">
    <div style="font-size:1.6rem;">🔭</div>
    <b style="display:block; margin-top:8px;">محاسبه‌ی مرجع جهانی</b>
    <p class="muted" style="margin-top:6px; font-size:.9rem; line-height:1.7;">موتور Swiss Ephemeris — همان استانداردی که اخترشناسان حرفه‌ای استفاده می‌کنند. دقت درجه‌ای، نه فال‌بازی.</p>
  </div>
  <div class="glass" style="padding:20px;">
    <div style="font-size:1.6rem;">🧠</div>
    <b style="display:block; margin-top:8px;">تفسیر با مدرک</b>
    <p class="muted" style="margin-top:6px; font-size:.9rem; line-height:1.7;">هر بینش با «Evidence» می‌آید: کدام سیاره، کدام خانه، کدام جنبه — قابل ردیابی تا درجه.</p>
  </div>
  <div class="glass" style="padding:20px;">
    <div style="font-size:1.6rem;">📜</div>
    <b style="display:block; margin-top:8px;">نگاه ایرانی-اسلامی صادقانه</b>
    <p class="muted" style="margin-top:6px; font-size:.9rem; line-height:1.7;">فصل فرهنگی جدا از تفسیر نجومی، با منابع معتبر — بدون ادعای غیب. تصمیم نهایی با عقل و استخاره.</p>
  </div>
</section>

<section class="glass glow" style="margin-top:22px; padding:26px 20px; text-align:center;">
  <h2>گزارش PDF ۵۰–۶۰ صفحه‌ای</h2>
  <p class="muted" style="margin-top:8px;">از ۱۴۹ هزار تومان — هزینه‌ی یک جلسه مشاوره، با خروجی دائمی و قابل ویرایش (Word).</p>
  <div style="display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin-top:16px;">
    <span class="chip">۳ حوزه‌ی زندگی</span>
    <span class="chip">Big Three</span>
    <span class="chip">ترانزیت ۳ ساله</span>
    <span class="chip">فصل اسلامی</span>
    <span class="chip">داشبورد شخصی</span>
  </div>
</section>
{% endblock %}


FILE: app/templates/page.html  (20 lines)
======================================================================
{% extends 'base.html' %}
{% block title %}{{ title }}{% endblock %}
{% block meta %}<meta name="description" content="{{ meta }}">{% endblock %}
{% block content %}
<div class="wrap" style="max-width:760px;margin:0 auto;padding:40px 16px 80px;">
  <h1 style="font-size:1.6rem;margin-bottom:6px;">{{ hero }}</h1>
  <div style="height:3px;width:64px;background:linear-gradient(90deg,#d4af37,transparent);border-radius:2px;margin:10px 0 28px;"></div>
  {% for s in sections %}
  <section style="margin-bottom:26px;">
    <h2 style="font-size:1.15rem;color:#d4af37;margin-bottom:8px;">{{ s.h2 }}</h2>
    <p style="line-height:1.9;color:#d9d2e8;font-size:.95rem;">{{ s.body }}</p>
  </section>
  {% endfor %}
  <div style="margin-top:40px;padding:20px;background:rgba(212,175,55,.08);border:1px solid rgba(212,175,55,.25);border-radius:14px;text-align:center;">
    <p style="margin-bottom:12px;font-weight:700;">آماده‌ای نقشه‌ی آسمان تولدت را ببینی؟</p>
    <a class="btn-lg" href="/" style="display:inline-block;">ساخت چارت رایگان</a>
  </div>
</div>
{% endblock %}


FILE: app/templates/partials/help_tip.html  (5 lines)
======================================================================
<span class="help-tip" x-data="{open:false}">
  <button type="button" class="help-tip-btn" @click="open=!open" aria-label="راهنما" title="راهنما">؟</button>
  <span class="help-tip-box" x-show="open" @click.outside="open=false" x-cloak>{{ text }}</span>
</span>


FILE: app/templates/payment_result.html  (30 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:560px;margin:0 auto;padding:50px 18px;text-align:center;">
  <div style="font-size:52px;margin-bottom:14px;">{% if order.status == 'paid' %}✅{% else %}⚠️{% endif %}</div>

  {% if order.status == 'paid' %}
  <h1 style="font-size:24px;font-weight:800;color:#2a9d8f;margin:0 0 8px;">پرداخت با موفقیت انجام شد</h1>
  <p style="color:#777;margin:0 0 24px;">
    پلن <b>{{ plan.name_fa if plan else '' }}</b> فعال شد — به زودی گزارش شما آماده میشود.
  </p>
  <div class="glass" style="padding:18px;border-radius:16px;margin-bottom:24px;text-align:right;font-size:13.5px;color:#444;">
    <div style="display:flex;justify-content:space-between;padding:4px 0;">
      <span>شماره پیگیری:</span><b dir="ltr">{{ order.ref_id or '—' }}</b>
    </div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;">
      <span>مبلغ:</span><b>{{ "{:,}".format(order.amount_rial // 10) }} تومان</b>
    </div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;">
      <span>وضعیت:</span><b style="color:#2a9d8f;">پرداختشده</b>
    </div>
  </div>
  <a class="btn btn-lg" href="/chart/{{ order.chart_id }}">مشاهدهی چارت تولد</a>
  {% else %}
  <h1 style="font-size:24px;font-weight:800;color:#c0392b;margin:0 0 8px;">پرداخت ناموفق بود</h1>
  <p style="color:#777;margin:0 0 24px;">در صورت کسر مبلغ، طی ۷۲ ساعت به حساب شما بازگردانده میشود.</p>
  <a class="btn btn-lg" href="/plans?chart={{ order.chart_id }}">تلاش دوباره</a>
  {% endif %}
</div>
{% endblock %}


FILE: app/templates/plans.html  (69 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:980px;margin:0 auto;padding:28px 18px 60px;" x-data="purchase()">
  <h1 style="text-align:center;font-size:26px;font-weight:800;color:#3b2f80;margin-bottom:6px;">گزارش کامل چارت تولد</h1>
  <p style="text-align:center;color:#777;margin-bottom:30px;">سه سطح انتخاب کن — هر کدام بر اساس چارت محاسبهشدهی خودت تولید میشود</p>

  <div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:center;">

    {% for p in plans %}
    <div class="glass" style="flex:1;min-width:250px;max-width:300px;padding:26px 22px;border-radius:20px;position:relative;display:flex;flex-direction:column;{% if loop.index == 2 %}border:2px solid #d5b94d;{% endif %}">
      {% if loop.index == 2 %}<div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#d5b94d;color:#fff;font-size:11px;font-weight:700;padding:3px 14px;border-radius:99px;">پیشنهاد ما</div>{% endif %}
      <h2 style="font-size:19px;font-weight:800;color:#3b2f80;margin:0 0 2px;">{{ p.name_fa }}</h2>
      <p style="color:#999;font-size:12px;margin:0 0 16px;">{{ p.subtitle_fa }}</p>
      <div style="font-size:24px;font-weight:800;color:#2a9d8f;margin-bottom:14px;">
        {{ "{:,}".format(p.price_toman) }} <span style="font-size:13px;color:#999;">تومان</span>
      </div>
      <ul style="list-style:none;padding:0;margin:0 0 22px;flex:1;">
        {% for f in p.features %}
        <li style="padding:5px 0;font-size:13.5px;color:#444;display:flex;gap:8px;">
          <span style="color:#2a9d8f;">✓</span>{{ f }}
        </li>
        {% endfor %}
      </ul>
      <button class="btn btn-lg" @click="buy('{{ p.key }}')"
              style="width:100%;{% if loop.index == 2 %}background:linear-gradient(135deg,#d5b94d,#c9a227);{% endif %}">
        خرید {{ p.name_fa }}
      </button>
    </div>
    {% endfor %}

  </div>

  <p style="text-align:center;color:#999;font-size:12px;margin-top:26px;">
    پرداخت امن از طریق درگاه زرینپال — بلافاصله پس از پرداخت، گزارش شما تولید میشود
  </p>
</div>

<div x-data="purchase()" x-cloak>
  <div x-show="busy" style="position:fixed;inset:0;background:rgba(20,10,40,.55);backdrop-filter:blur(4px);z-index:99;display:flex;align-items:center;justify-content:center;">
    <div class="glass" style="padding:26px 40px;border-radius:18px;text-align:center;">
      <div style="font-size:30px;margin-bottom:10px;">🔄</div>
      <div style="font-weight:700;">در حال اتصال به درگاه پرداخت...</div>
    </div>
  </div>
</div>

<script>
function purchase() {
  return {
    busy: false,
    async buy(planKey) {
      const chartId = new URLSearchParams(location.search).get('chart') || '';
      if (!chartId) { alert('ابتدا چارت تولدت را بساز'); return; }
      this.busy = true;
      try {
        const fd = new FormData();
        fd.append('plan_key', planKey);
        fd.append('chart_id', chartId);
        const r = await fetch('/api/orders', { method: 'POST', body: fd });
        const j = await r.json();
        if (!r.ok) { alert(j.detail || 'خطا در ایجاد سفارش'); this.busy = false; return; }
        window.location.href = j.payment_url;
      } catch (e) { alert('ارتباط با سرور برقرار نشد'); this.busy = false; }
    }
  };
}
</script>
{% endblock %}


FILE: app/templates/privacy.html  (19 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:640px; margin:0 auto; padding-top:36px;">
  <h1>حریم خصوصی</h1>
  <div class="glass" style="margin-top:16px; padding:24px;">
    <p>داده‌ی تولد تو (تاریخ، ساعت و شهر) یک داده‌ی حساس شخصی است. تعهد ما:</p>
    <ul style="margin:14px 0 0 18px; line-height:2;">
      <li>داده‌ی تولد فقط برای محاسبه و تفسیر چارت خودت استفاده می‌شود؛ هرگز فروخته یا منتشر نمی‌شود.</li>
      <li>محاسبات روی همین سرور انجام می‌شود و چارت تو فقط با لینک شخصی در دسترس است.</li>
      <li>گزارش‌ها و چارت‌ها با شماره موبایل تو (ورود امن با کد یک‌بارمصرف) قفل می‌شوند.</li>
      <li>در هر لحظه می‌توانی از صفحه «حساب من» همه‌ی داده‌هایت را برای همیشه حذف کنی.</li>
      <li>بدون ثبت‌نام، چارت رایگان ساخته می‌شود و هیچ داده‌ای به حساب کسی وصل نمی‌شود.</li>
      <li>پیامک‌ها فقط برای ورود (کد تأیید) ارسال می‌شود — بدون تبلیغات مزاحم.</li>
    </ul>
    <p class="muted" style="margin-top:14px; font-size:.85rem;">برای حذف کامل داده‌ها: ورود → حساب من → «حذف کامل حساب و داده‌ها».</p>
  </div>
</div>
{% endblock %}


FILE: app/templates/rectify.html  (118 lines)
======================================================================
{% extends "base.html" %}
{% block title %}یافتن ساعت تولد | بازسازی دقیق چارت تولد{% endblock %}
{% block meta %}<meta name="description" content="ساعت تولد را نمی‌دانید؟ با ابزار یافتن ساعت تولد بر اساس چند سؤال ساده، چارت دقیق‌تری بسازید">{% endblock %}

{% block content %}
<div style="max-width:560px; margin:0 auto; padding-top:36px;">
  <h1>🕵️ یافتن ساعت تولد</h1>
  <p class="muted">ساعت دقیق تولد را نمی‌دانی؟ چند رویداد مهم زندگی‌ات را بگو تا با محاسبه گذرهای سیاره‌ای، محتمل‌ترین ساعت تولدت را پیدا کنیم. (این روش علمیِ تثبیت‌شده نیست؛ یک تخمین نجومی است.)</p>

  <form id="recForm" style="margin-top:18px;">
    <input type="hidden" name="calendar" value="jalali">
    <div class="glass" style="padding:18px;">
      <h2 style="font-size:1rem;">📅 تاریخ تولد</h2>
      <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">
        <input name="year" type="number" placeholder="سال 1373" class="input" required>
        <input name="month" type="number" placeholder="ماه" class="input" required>
        <input name="day" type="number" placeholder="روز" class="input" required>
      </div>
      <input name="city_fa" placeholder="شهر تولد — مثلاً تهران" class="input" style="width:100%; margin-top:8px;" required autocomplete="off">
      <div class="city-sug" style="margin-top:6px;"></div>
    </div>

    <div class="glass" style="padding:18px; margin-top:12px;">
      <h2 style="font-size:1rem;">📌 رویدادهای مهم زندگی</h2>
      <p class="muted" style="font-size:.8rem;">حداقل ۲ رویداد با تاریخ تقریبی (سال/ماه/روز)</p>
      <div id="eventsBox"></div>
      <button type="button" id="addEvent" class="btn btn-ghost" style="width:100%; margin-top:8px; font-size:.85rem;">+ افزودن رویداد</button>
    </div>

    <button type="submit" class="btn" style="width:100%; margin-top:16px; padding:14px;">یافتن ساعت تولد 🕵️</button>
  </form>

  <div id="recResult" style="display:none; margin-top:20px;"></div>
</div>

<style>
.inp{ padding:11px; border-radius:10px; border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06); color:#eee; font-family:inherit; font-size:.9rem; box-sizing:border-box; }
.sug{ padding:10px; border-radius:8px; margin-top:4px; background:rgba(255,255,255,.08); cursor:pointer; font-size:.85rem; }
.ev{ display:grid; grid-template-columns:1.2fr .7fr .7fr .7fr; gap:6px; margin-top:6px; }
</style>
<script>
const CATS = {marriage:'ازدواج', child:'فرزند', job_change:'تغییر شغل', relocation:'مهاجرت', illness:'بیماری', windfall:'موفقیت مالی', fame:'شهرت', loss:'از دست دادن'};
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function addEventRow(cat, y, m, d) {
  const box = document.getElementById('eventsBox');
  const div = document.createElement('div');
  div.className = 'ev';
  const sel = document.createElement('select');
  sel.className = 'inp';
  Object.entries(CATS).forEach(([k, v]) => { const o = document.createElement('option'); o.value = k; o.textContent = v; if (k === cat) o.selected = true; sel.appendChild(o); });
  const iy = document.createElement('input'); iy.className = 'inp'; iy.type = 'number'; iy.placeholder = 'سال'; iy.value = y || '';
  const im = document.createElement('input'); im.className = 'inp'; im.type = 'number'; im.placeholder = 'ماه'; im.value = m || '';
  const id = document.createElement('input'); id.className = 'inp'; id.type = 'number'; id.placeholder = 'روز'; id.value = d || '';
  const del = document.createElement('button'); del.type = 'button'; del.textContent = '✕'; del.className = 'btn btn-ghost';
  del.style.padding = '6px 10px';
  del.onclick = () => div.remove();
  div.append(sel, iy, im, id, del);
  box.appendChild(div);
}
document.getElementById('addEvent').onclick = () => addEventRow('marriage');
addEventRow('marriage'); addEventRow('job_change');

const cityInput = document.querySelector('input[name=city_fa]');
let city = null;
cityInput.addEventListener('input', async () => {
  const q = cityInput.value.trim();
  if (q.length < 2) { document.querySelector('.city-sug').innerHTML = ''; return; }
  const r = await fetch('/api/cities?q=' + encodeURIComponent(q));
  const d = await r.json();
  const box = document.querySelector('.city-sug');
  box.innerHTML = '';
  (d.results || []).slice(0, 4).forEach(c => {
    const div = document.createElement('div');
    div.className = 'sug';
    div.textContent = c.city_fa + ' (' + c.province_fa + ')';
    div.onclick = () => { city = c; cityInput.value = c.city_fa; box.innerHTML = ''; };
    box.appendChild(div);
  });
});

document.getElementById('recForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!city) { alert('شهر را از لیست انتخاب کن'); return; }
  const events = [];
  document.querySelectorAll('#eventsBox .ev').forEach(row => {
    const [sel, iy, im, id] = row.children;
    if (iy.value && im.value && id.value) events.push([sel.value, +iy.value, +im.value, +id.value]);
  });
  if (events.length < 2) { alert('حداقل ۲ رویداد با تاریخ کامل لازم است'); return; }
  const f = new FormData();
  f.set('city_fa', city.city_fa);
  f.set('year', e.target.querySelector('input[name=year]').value);
  f.set('month', e.target.querySelector('input[name=month]').value);
  f.set('day', e.target.querySelector('input[name=day]').value);
  f.set('events_json', JSON.stringify(events));
  const btn = e.target.querySelector('button[type=submit]');
  btn.disabled = true; btn.textContent = 'در حال محاسبه (چند ثانیه)...';
  try {
    const r = await fetch('/api/rectify', { method: 'POST', body: f });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || 'خطا'); return; }
    const box = document.getElementById('recResult');
    box.style.display = 'block';
    box.innerHTML =
      '<div class="glass glow" style="padding:22px; text-align:center;">' +
      '<h2>🕵️ محتمل‌ترین ساعت تولد: <span style="color:#f5c518;">' + esc(d.best_time) + '</span></h2>' +
      '<p class="muted" style="margin-top:6px; font-size:.85rem;">بر اساس ' + d.events_used + ' رویداد — امتیاز هم‌راستایی: ' + d.score + '</p>' +
      '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-top:14px;">' +
      d.candidates.map(c => '<div class="glass" style="padding:10px;"><b>' + esc(c.time) + '</b><div class="muted" style="font-size:.75rem;">امتیاز ' + c.score + '</div></div>').join('') +
      '</div>' +
      '<p class="muted" style="margin-top:12px; font-size:.8rem;">⚠️ این تخمین جایگزین سند رسمی تولد نیست.</p>' +
      '<a href="/birth-form" class="btn" style="display:block; margin-top:12px;">ساخت چارت با این ساعت ✨</a></div>';
  } finally { btn.disabled = false; btn.textContent = 'یافتن ساعت تولد 🕵️'; }
});
</script>
{% endblock %}


FILE: app/templates/seo_index.html  (51 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:640px; margin:0 auto; padding-top:36px;">
  <h1>آموزش چارت تولد</h1>
  <p class="muted">هر چیزی که باید درباره چارت تولد، سیارات و خانه‌ها بدانید — به زبان ساده.</p>

  <h2 style="margin-top:26px;">راهنماهای اصلی</h2>
  {% for slug, g in guides.items() %}
    <a href="/learn/{{ slug }}" class="glass" style="display:block; margin-top:10px; padding:16px; text-decoration:none;">
      <b>{{ g.title }}</b>
      <div class="muted" style="font-size:.85rem; margin-top:4px;">{{ g.text[:90] }}…</div>
    </a>
  {% endfor %}

  <h2 style="margin-top:26px;">معنی سیارات</h2>
  <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; margin-top:12px;">
    {% for slug, p in planets.items() %}
      <a href="/learn/{{ slug }}" class="glass" style="padding:12px; text-decoration:none;">{{ p.title }}</a>
    {% endfor %}
  </div>

  <h2 style="margin-top:26px;">خانه‌های دوازده‌گانه</h2>
  <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; margin-top:12px;">
    {% for n, h in houses.items() %}
      <a href="/learn/{{ n }}" class="glass" style="padding:12px; text-decoration:none;">{{ h.title }}</a>
    {% endfor %}
  </div>

  <h2 style="margin-top:26px;">برج‌های دوازده‌گانه</h2>
  <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-top:12px;">
    <a href="/signs/hamal" class="glass" style="padding:12px; text-decoration:none;">♈ برج حمل</a>
    <a href="/signs/sowr" class="glass" style="padding:12px; text-decoration:none;">♉ برج ثور</a>
    <a href="/signs/jowza" class="glass" style="padding:12px; text-decoration:none;">♊ برج جوزا</a>
    <a href="/signs/sartan" class="glass" style="padding:12px; text-decoration:none;">♋ برج سرطان</a>
    <a href="/signs/asad" class="glass" style="padding:12px; text-decoration:none;">♌ برج اسد</a>
    <a href="/signs/sowza" class="glass" style="padding:12px; text-decoration:none;">♍ برج سنبله</a>
    <a href="/signs/mizan" class="glass" style="padding:12px; text-decoration:none;">♎ برج میزان</a>
    <a href="/signs/aghrab" class="glass" style="padding:12px; text-decoration:none;">♏ برج عقرب</a>
    <a href="/signs/ghows" class="glass" style="padding:12px; text-decoration:none;">♐ برج قوس</a>
    <a href="/signs/jadi" class="glass" style="padding:12px; text-decoration:none;">♑ برج جدی</a>
    <a href="/signs/dalv" class="glass" style="padding:12px; text-decoration:none;">♒ برج دلو</a>
    <a href="/signs/hout" class="glass" style="padding:12px; text-decoration:none;">♓ برج حوت</a>
  </div>

  <div class="glass glow" style="margin-top:28px; padding:22px; text-align:center;">
    <b>چارت تولد خودت را همین حالا بساز</b>
    <div style="margin-top:10px;"><a href="/birth-form" class="btn">ساخت چارت رایگان ✨</a></div>
  </div>
</div>
{% endblock %}


FILE: app/templates/seo_page.html  (28 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:640px; margin:0 auto; padding-top:36px;">
  <nav style="font-size:.8rem;" class="muted"><a href="/learn">آموزش</a> ← {{ page.title }}</nav>
  <h1 style="margin-top:8px;">{{ page.title }}</h1>
  <div class="glass" style="margin-top:18px; padding:22px; line-height:1.9;">
    {% if page.get("personality") %}
      <h2>شخصیت</h2><p>{{ page.personality }}</p>
      <h2>عشق</h2><p>{{ page.love }}</p>
      <h2>کار</h2><p>{{ page.work }}</p>
      <h2>چالش</h2><p>{{ page.challenge }}</p>
      <h2>خورشید در این برج</h2><p>{{ page.sun }}</p>
      <h2>ماه در این برج</h2><p>{{ page.moon }}</p>
      <h2>طالع این برج</h2><p>{{ page.asc }}</p>
    {% else %}
      <p>{{ page.text }}</p>
    {% endif %}
    <div style="margin-top:18px; padding-top:14px; border-top:1px solid rgba(255,255,255,.08); font-size:.85rem;" class="muted">
      عنصر: <b>{{ page.get("element", "—") }}</b> | حاکم: <b>{{ page.get("ruler", "—") }}</b>
    </div>
  </div>
  <div class="glass glow" style="margin-top:22px; padding:20px; text-align:center;">
    <b>این را در چارت خودت ببین</b>
    <div style="margin-top:10px;"><a href="/birth-form" class="btn">ساخت چارت رایگان ✨</a></div>
  </div>
</div>
{% endblock %}


FILE: app/templates/synastry.html  (143 lines)
======================================================================
{% extends "base.html" %}
{% block title %}سازگاری دو چارت تولد | بررسی کد‌مک با طالع بینی{% endblock %}
{% block meta %}<meta name="description" content="مقایسه دو چارت تولد برای سنجش سازگاری عاطفی، شغلی و ارتباطی دو نفر با محاسبات نجومی دقیق">{% endblock %}

{% block content %}
<div style="max-width:560px; margin:0 auto; padding-top:36px;">
  <h1>💞 سازگاری دو چارت</h1>
  <p class="muted">اطلاعات تولد دو نفر را وارد کن تا هم‌راستایی سیارات، حوزه‌های عشق/ذهن/کار و نمره کلی سازگاری‌تان را ببینی.</p>

  <form id="synForm" style="margin-top:18px;">
    <div class="glass" style="padding:18px;">
      <h2 style="font-size:1rem;">👤 نفر اول</h2>
      <input name="name_a" placeholder="نام (اختیاری)" class="input" style="width:100%;">
      <div style="display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:8px;">
        <input name="year_a" type="number" placeholder="سال 1373" class="input" required>
        <input name="month_a" type="number" placeholder="ماه" class="input" required>
        <input name="day_a" type="number" placeholder="روز" class="input" required>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:8px;">
        <input name="hour_a" type="number" placeholder="ساعت 06" class="input" required>
        <input name="minute_a" type="number" placeholder="دقیقه 10" class="input" required>
      </div>
      <input name="city_a" placeholder="شهر تولد — مثلاً تهران" class="input" style="width:100%; margin-top:8px;" required autocomplete="off">
      <div class="city-suggest-a" style="margin-top:6px;"></div>
    </div>

    <div class="glass" style="padding:18px; margin-top:12px;">
      <h2 style="font-size:1rem;">👤 نفر دوم</h2>
      <input name="name_b" placeholder="نام (اختیاری)" class="input" style="width:100%;">
      <div style="display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:8px;">
        <input name="year_b" type="number" placeholder="سال 1369" class="input" required>
        <input name="month_b" type="number" placeholder="ماه" class="input" required>
        <input name="day_b" type="number" placeholder="روز" class="input" required>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:8px;">
        <input name="hour_b" type="number" placeholder="ساعت 14" class="input" required>
        <input name="minute_b" type="number" placeholder="دقیقه 30" class="input" required>
      </div>
      <input name="city_b" placeholder="شهر تولد — مثلاً تهران" class="input" style="width:100%; margin-top:8px;" required autocomplete="off">
      <div class="city-suggest-b" style="margin-top:6px;"></div>
    </div>

    <button type="submit" class="btn" style="width:100%; margin-top:16px; padding:14px;">محاسبه سازگاری 💞</button>
  </form>

  <div id="synResult" style="display:none; margin-top:20px;"></div>
</div>

<style>
.inp{ padding:11px; border-radius:10px; border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06); color:#eee; font-family:inherit; font-size:.9rem; box-sizing:border-box; }
.sug{ padding:10px; border-radius:8px; margin-top:4px; background:rgba(255,255,255,.08); cursor:pointer; font-size:.85rem; }
</style>
<script>
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function citySearch(inp, box, sel) {
  inp.addEventListener('input', async () => {
    const q = inp.value.trim();
    if (q.length < 2) { box.innerHTML = ''; return; }
    const r = await fetch('/api/cities?q=' + encodeURIComponent(q));
    const d = await r.json();
    box.innerHTML = '';
    (d.results || []).slice(0, 4).forEach(c => {
      const div = document.createElement('div');
      div.className = 'sug';
      div.textContent = c.city_fa + ' (' + c.province_fa + ')';
      div.onclick = () => { sel(c); box.innerHTML = ''; };
      box.appendChild(div);
    });
  });
}
let cityA = null, cityB = null;
citySearch(document.querySelector('input[name=city_a]'), document.querySelector('.city-suggest-a'), c => { cityA = c; document.querySelector('input[name=city_a]').value = c.city_fa; });
citySearch(document.querySelector('input[name=city_b]'), document.querySelector('.city-suggest-b'), c => { cityB = c; document.querySelector('input[name=city_b]').value = c.city_fa; });

document.getElementById('synForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!cityA || !cityB) { alert('شهرها را از لیست انتخاب کن'); return; }
  const f = new FormData(e.target);
  f.set('city_a', cityA.city_fa); f.set('city_b', cityB.city_fa);
  const btn = e.target.querySelector('button');
  btn.disabled = true; btn.textContent = 'در حال محاسبه...';
  try {
    const r = await fetch('/api/synastry', { method: 'POST', body: f });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || 'خطا'); return; }
    const cls = d.score >= 65 ? '#4caf7d' : d.score >= 50 ? '#f5c518' : '#ff6b6b';
    document.getElementById('synResult').style.display = 'block';
    document.getElementById('synResult').innerHTML =
      '<div class="glass glow" style="padding:22px; text-align:center;">' +
      '<h2>نمره سازگاری: <span style="color:' + cls + ';">' + d.score + '</span></h2>' +
      '<p style="margin-top:8px;">' + esc(d.verdict) + '</p>' +
      '<p class="muted" style="margin-top:12px; font-size:.85rem;">💎 تحلیل کامل (۴ حوزه + ۲۵ ارتباط سیارهای) پس از خرید نمایش داده میشود.</p>' +
      '<button class="btn btn-lg" style="margin-top:14px;" onclick="buySyn()">خرید تحلیل کامل — ۴۹۹ هزار تومان 💎</button>' +
      '</div>';
  } finally { btn.disabled = false; btn.textContent = 'محاسبه سازگاری 💞'; }
});

let synOrderState = null;
async function buySyn() {
  const f = new FormData(document.getElementById('synForm'));
  f.set('city_a', cityA.city_fa); f.set('city_b', cityB.city_fa);
  const r = await fetch('/api/synastry/order', { method: 'POST', body: f });
  const d = await r.json();
  if (!r.ok) { alert(d.detail || 'خطا در ایجاد سفارش'); return; }
  synOrderState = { chart_a: d.chart_a, chart_b: d.chart_b, order_id: d.order_id };
  location.href = d.payment_url;  // → زرینپال → بازگشت به /payment/result
}

// after returning from zarinpal: /payment/result?order_id=... → user comes back to /synastry
// poll unlock: if the paid pair exists, fetch full analysis
async function tryUnlock() {
  if (!synOrderState) return;
  const acc = await fetch('/api/synastry/access?chart_a=' + synOrderState.chart_a + '&chart_b=' + synOrderState.chart_b);
  const ad = await acc.json();
  if (ad.full) {
    const fd = new FormData();
    fd.set('chart_a', synOrderState.chart_a); fd.set('chart_b', synOrderState.chart_b);
    const r = await fetch('/api/synastry/full', { method: 'POST', body: fd });
    const d = await r.json();
    if (r.ok) renderFullSyn(d);
  } else {
    setTimeout(tryUnlock, 4000);
  }
}
function renderFullSyn(d) {
  const cls = d.overall >= 65 ? '#4caf7d' : d.overall >= 50 ? '#f5c518' : '#ff6b6b';
  document.getElementById('synResult').innerHTML =
    '<div class="glass glow" style="padding:22px; text-align:center;">' +
    '<h2>نمره سازگاری: <span style="color:' + cls + ';">' + d.overall + '</span></h2>' +
    '<p style="margin-top:8px;">' + esc(d.verdict) + '</p>' +
    '<div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:16px;">' +
    ['love','mind','career','spirit'].map(k => {
      const labels = {love:'عشق 💘', mind:'ذهن 🧠', career:'کار 💼', spirit:'معنا ✨'};
      return '<div class="glass" style="padding:12px;"><b>' + labels[k] + '</b><br><span style="font-size:1.3rem;">' + d.domains[k] + '</span></div>';
    }).join('') + '</div>' +
    '<details style="margin-top:16px; text-align:right;"><summary style="cursor:pointer; font-size:.85rem;">' + d.connections_count + ' ارتباط سیارهای</summary>' +
    '<div style="max-height:260px; overflow-y:auto; margin-top:8px; font-size:.85rem;">' +
    d.connections.slice(0, 16).map(c => '<div style="padding:6px 0; border-bottom:1px solid rgba(255,255,255,.06);">' + c.a + ' (' + c.a_sign + ') ' + esc(c.aspect_fa) + ' ' + c.b + ' (' + c.b_sign + ') — اورب ' + c.orb + '°</div>').join('') +
    '</div></details></div>';
}
</script>
{% endblock %}


FILE: app/templates/transit.html  (34 lines)
======================================================================
{% extends "base.html" %}
{% block content %}
<div style="max-width:760px;margin:0 auto;padding:24px 14px 50px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
    <h1 style="font-size:23px;font-weight:800;">گذرهای کنونی سیارات 🌠</h1>
    <a class="btn btn-ghost" href="/chart/{{ chart_id }}" style="min-height:40px;padding:0 14px;font-size:.85rem;">← چارت</a>
  </div>
  <p class="muted" style="font-size:.9rem;margin-bottom:18px;">
    سیارات در حال گذر، با نقاط کلیدی چارت تولد تو پیوندهایی می‌سازند — این «آب‌وهوای» نجومی این روزهاست.
  </p>

  <div style="display:flex;flex-direction:column;gap:10px;">
    {% for e in events %}
    <div class="glass" style="display:flex;align-items:center;gap:14px;padding:14px 16px;">
      <div style="font-size:26px;min-width:44px;text-align:center;">🪐</div>
      <div style="flex:1;">
        <div style="font-weight:800;">{{ e.planet_fa }} <span style="color:#f5c518;">{{ e.aspect }}</span> {{ {'Sun':'خورشید تولد','Moon':'ماه تولد','ASC':'طالع تولد'}.get(e.target, e.target) }}</div>
        <div class="muted" style="font-size:.85rem;">در {{ e.sign_fa }} — اورب {{ e.orb }}°</div>
      </div>
    </div>
    {% endfor %}
    {% if not events %}
    <div class="glass" style="padding:20px;text-align:center;color:var(--muted);">
      گذر مهمی در این بازه فعال نیست — چارت تو در آرامش است.
    </div>
    {% endif %}
  </div>

  <p class="muted" style="font-size:.8rem;margin-top:16px;">
    تفسیر اختصاصی گذرها در پلن‌های کامل و طلایی — <a href="/plans?chart={{ chart_id }}" style="color:#f5c518;">مشاهده پلن‌ها</a>
  </p>
</div>
{% endblock %}

