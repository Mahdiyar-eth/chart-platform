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
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
import swisseph as swe

EPHE_PATH = os.getenv("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")
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

# audit backend (re-run): set_sid_mode is a GLOBAL swisseph state — setting it
# per-request races with concurrent requests. Set it ONCE at import (Lahiri is
# the only sidereal mode the product uses) and never mutate it again.
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

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

    local = birth.local_dt()
    utc = to_utc(local, birth.tz_name)
    jd = jd_from_utc(utc)
    is_sidereal = cfg["zodiac"] == "sidereal"
    # audit backend (re-run): always compute TROPICAL and subtract the Lahiri
    # ayanamsa manually — no per-request swe.set_sid_mode global mutation.
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    ayan = swe.get_ayanamsa_ut(jd) if is_sidereal else 0.0

    planets = {}
    for name, pid in PLANET_DEFS:
        pos, _ = swe.calc_ut(jd, pid, flags)
        lon = (pos[0] - ayan) % 360 if ayan else pos[0]
        speed = pos[3]
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
def validate_birth_fields(year: int, month: int, day: int, jalali: bool = False) -> tuple[bool, str]:
    """Basic sanity check for birth date parts (audit backend: jalali-aware)."""
    try:
        if jalali:
            if not (1300 <= year <= 1405):
                return False, "سال تولد باید بین ۱۳۰۰ و ۱۴۰۵ باشد"
            if not (1 <= month <= 12):
                return False, "ماه نامعتبر است"
            import jdatetime
            try:
                jdatetime.date(year, month, day)
            except ValueError:
                return False, "روز نامعتبر است"
            return True, ""
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
