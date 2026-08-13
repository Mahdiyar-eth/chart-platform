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

    # audit backend (re-run): cap events (CPU/DoS) + honour per-category rules
    events = list(events)[:3]
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
            # audit backend (re-run): _EVENT_RULES were defined but never used —
            # a marriage and a job change scored identically. Apply per-category
            # natal-point filters now (fallback: all points for unknown cats).
            rule_points = _EVENT_RULES.get(cat)
            for e in evs:
                if rule_points and e["natal"] not in rule_points:
                    continue
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
