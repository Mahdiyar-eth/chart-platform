"""B1 — deterministic transit forecast engine (NO LLM; never calculates by LLM).

Builds on the canonical chart JSON from `app.astrology.engine`. For a window of
`months`, it samples each transit body daily, detects when its signed separation
from a natal target crosses the 5 major aspects, refines each crossing to <1
arc-min by bisection, groups retrogrades (up to 3 passes per event), and returns
ranked `TransitEvent`s. Pure, deterministic, cachable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import swisseph as swe

from app.astrology.engine import (
    ASPECT_FA, ASPECT_NAMES, SIGNS_FA, _house_of, _retro, ensure_ephe,
    jd_from_utc, sign_of,
)

# Transit bodies in forecast order + swe id + Persian label.
TRANSIT_SWEE: dict[str, int] = {
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "Chiron": swe.CHIRON, "True Node": swe.TRUE_NODE,
}
TRANSIT_FA: dict[str, str] = {
    "Mars": "مریخ", "Jupiter": "مشتری", "Saturn": "زحل", "Uranus": "اورانوس",
    "Neptune": "نپتون", "Pluto": "پلوتون", "Chiron": "کایرون", "True Node": "گره شمالی",
}
TARGET_FA: dict[str, str] = {
    "Sun": "خورشید", "Moon": "ماه", "Mercury": "عطارد", "Venus": "زهره",
    "Mars": "مریخ", "Jupiter": "مشتری", "Saturn": "زحل",
    "ASC": "طالع", "MC": "وسط‌آسمان",
}
ASPECTS: list[int] = [0, 60, 90, 120, 180]

# Weighting (plan B1): planet × target × aspect.
WEIGHT_PLANET = {"Pluto": 3, "Neptune": 3, "Uranus": 3, "Saturn": 3, "Jupiter": 2,
                 "Chiron": 1, "True Node": 1, "Mars": 1}
WEIGHT_TARGET = {"Sun": 3, "Moon": 3, "ASC": 3, "MC": 3}
WEIGHT_ASPECT = {0: 3, 180: 3, 90: 3, 120: 2, 60: 1}

TRANSIT_ORB = 1.0          # event window: |orb| <= 1deg (plan B1)
DETECT_ORB = 8.0           # max outer orb to consider a crossing worth refining
BISECT_MAX = 32            # <= ~arc-second precision
_RETRO_STATION = 0.03      # deg/day threshold (a planet moving this slow treats its crossing as a station)

_MAX_EXACT_DATES = 3
RETRO_GROUP_DAYS = 180.0   # consecutive crossings within this many julian days = one retro event
  # (DETECT_ORB defined once above — duplicate removed X22/R24)


@dataclass
class TransitEvent:
    id: str
    transit_planet: str
    transit_planet_fa: str
    natal_target: str
    natal_target_fa: str
    aspect: str
    aspect_fa: str
    exact_dates: list[str]
    window_start: str
    window_end: str
    retro_passes: int
    weight: int
    natal_house: int | None
    transit_sign_fa: str

    def to_json(self) -> dict:
        return {
            "id": self.id, "transit_planet": self.transit_planet,
            "transit_planet_fa": self.transit_planet_fa,
            "natal_target": self.natal_target, "natal_target_fa": self.natal_target_fa,
            "aspect": self.aspect, "aspect_fa": self.aspect_fa,
            "exact_dates": self.exact_dates, "window_start": self.window_start,
            "window_end": self.window_end, "retro_passes": self.retro_passes,
            "weight": self.weight, "natal_house": self.natal_house,
            "transit_sign_fa": self.transit_sign_fa,
        }


def _norm180(x: float) -> float:
    return ((x + 180.0) % 360.0) - 180.0


def _transit_lon(body_swe: int, jd: float) -> tuple[float, float]:
    """Return (ecliptic longitude, speed deg/day) for a body at jd."""
    res = swe.calc_ut(jd, body_swe)
    lon = res[0][0]
    speed = res[0][3] if len(res[0]) > 3 else 0.0
    return lon, speed


def _target_lons(chart_json: dict) -> dict[str, float] | None:
    """Extract natal target longitudes from canonical chart JSON.

    Returns None (not an error) when a target cannot be resolved (e.g. unknown
    birth time -> no ASC/MC). Caller skips unmapped targets; unknown-time charts
    simply drop ASC/MC and proceed.
    """
    out: dict[str, float] = {}
    planets = chart_json.get("planets") or {}
    for name in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        if name in planets and planets[name].get("longitude") is not None:
            out[name] = float(planets[name]["longitude"])
    # angles -> ASC / MC (may be None when birth time unknown)
    angles = chart_json.get("angles") or {}
    for key in ("ASC", "MC"):
        e = angles.get(key) or {}
        lon = e.get("longitude")
        if lon is not None:
            try:
                out[key] = float(lon)
            except (TypeError, ValueError):
                pass
    return out


def _natal_cusps(chart_json: dict) -> list[float]:
    houses = chart_json.get("houses") or []
    if not houses:
        return []
    if isinstance(houses, dict):
        # {'h1': lon,...,'h12': lon}
        if houses.get("h1") is not None:
            return [float(houses[f"h{i}"]) for i in range(1, 13) if houses.get(f"h{i}") is not None]
        cusps = houses.get("cusps") or houses.get("lons") or []
        if cusps:
            return [float(x) for x in cusps]
    if isinstance(houses, list) and houses and isinstance(houses[0], (int, float)):
        return [float(x) for x in houses]
    return []


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _iso_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _EventRaw:
    body: str
    target: str
    aspect: float
    exacts: list[float]
    speed: float
    natal_lon: float


def forecast(chart_json: dict, months: int = 12, start: datetime | None = None) -> list[dict]:
    """Compute ranked transit events for a canonical chart JSON over `months`.

    Deterministic and pure (no LLM). Returns a list of event dicts sorted by
    `window_start`, each matching the B1 schema.
    """
    ensure_ephe()
    targets = _target_lons(chart_json)
    cusps = _natal_cusps(chart_json)
    if not targets:
        return []

    start_dt = _aware_utc(start or datetime.now(timezone.utc))
    jd0 = jd_from_utc(start_dt)
    days = max(1, int(round(months * 30.44)))

    raws: list[_EventRaw] = []
    for body, body_swe in TRANSIT_SWEE.items():
        # precompute daily lons + speed once per body (reused across targets/aspects)
        lons = [0.0] * (days + 1)
        speeds = [0.0] * (days + 1)
        for d in range(days + 1):
            lons[d], speeds[d] = _transit_lon(body_swe, jd0 + d)
        for target, tlon in targets.items():
            weight_t = WEIGHT_TARGET.get(target, 1)
            for aspect in ASPECTS:
                # crossings via daily sign-change scan on precomputed lons
                exacts: list[float] = []
                for d in range(days):
                    g0 = _norm180(lons[d] - tlon - aspect)
                    g1 = _norm180(lons[d + 1] - tlon - aspect)
                    if g0 == 0.0:
                        exacts.append(jd0 + d)
                        continue
                    # proximity gate: only a genuine aspect crossing counts; the
                    # norm180() function has a spurious sign flip at the point
                    # DIAMETRICALLY OPPOSITE the aspect (e.g. opposition's flips at
                    # conjunction) — reject those by requiring the planet to be
                    # near the aspect at the crossing.
                    if g0 * g1 < 0 and min(abs(g0), abs(g1)) < DETECT_ORB:
                        lo, hi = jd0 + d, jd0 + d + 1
                        glo = g0
                        for _ in range(BISECT_MAX):
                            mid = (lo + hi) / 2.0
                            mlon, _ = _transit_lon(body_swe, mid)
                            gmid = _norm180(mlon - tlon - aspect)
                            if gmid == 0.0:
                                lo = hi = mid
                                break
                            if (gmid > 0) == (glo > 0):
                                lo, glo = mid, gmid
                            else:
                                hi = mid
                        exacts.append((lo + hi) / 2.0)
                if not exacts:
                    continue
                exacts.sort()
                # cluster consecutive crossings within RETRO_GROUP_DAYS (a retro loop)
                clusters: list[list[float]] = []
                cur = [exacts[0]]
                for x in exacts[1:]:
                    if (x - cur[-1]) <= RETRO_GROUP_DAYS:
                        cur.append(x)
                    else:
                        clusters.append(cur)
                        cur = [x]
                clusters.append(cur)
                for cl in clusters:
                    speed = speeds[min(int(cl[0] - jd0), days)]
                    raws.append(_EventRaw(body, target, aspect, cl, speed, tlon))
    # free the big day lists
    del lons, speeds

    events: list[TransitEvent] = []
    for r in raws:
        # dedup gates: keep a crossing only if it is a genuine aspect hold
        w = WEIGHT_PLANET.get(r.body, 1) * WEIGHT_TARGET.get(r.target, 1) * WEIGHT_ASPECT.get(int(r.aspect), 1)
        exacts = r.exacts[:_MAX_EXACT_DATES]
        # window: around each exact crossing, |orb| <= TRANSIT_ORB
        # approximate half-window (days) from speed: orb/speed
        half_days = TRANSIT_ORB / max(abs(r.speed), 1e-4) if r.speed else 7.0
        half_days = min(half_days, 60.0)
        starts = [e - jd0 - half_days for e in exacts]
        ends = [e - jd0 + half_days for e in exacts]
        window_start = _iso(start_dt + timedelta(days=min(starts)))
        window_end = _iso(start_dt + timedelta(days=max(ends)))
        exact_iso = [_iso_dt(start_dt + timedelta(days=e - jd0)) for e in exacts]
        sign_fa = SIGNS_FA[sign_of(_transit_lon(TRANSIT_SWEE[r.body], exacts[0])[0])]
        house = _house_of(r.natal_lon, cusps) if cusps else None
        eid = f"{r.body}_{r.target}_{int(r.aspect)}_{'T'.join(exact_iso)}"
        events.append(TransitEvent(
            id=eid.replace(" ", ""), transit_planet=r.body,
            transit_planet_fa=TRANSIT_FA.get(r.body, r.body),
            natal_target=r.target, natal_target_fa=TARGET_FA.get(r.target, r.target),
            aspect=ASPECT_NAMES[int(r.aspect)], aspect_fa=ASPECT_FA[int(r.aspect)],
            exact_dates=exact_iso, window_start=window_start, window_end=window_end,
            retro_passes=len(exacts), weight=w, natal_house=house, transit_sign_fa=sign_fa,
        ))

    events.sort(key=lambda e: e.window_start)
    return [e.to_json() for e in events]
