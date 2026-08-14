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


def _chart_tz(chart_json: dict) -> str:
    """H1.1: transits must use the CHART's timezone (not server UTC) — a
    user in New York should see 'today' as their local day."""
    try:
        return (chart_json.get("birth") or {}).get("tz_name") or "Asia/Tehran"
    except Exception:  # noqa: BLE001
        return "Asia/Tehran"


def _now_local_utc(chart_json: dict) -> datetime:
    """Current wall-clock time in the chart's timezone, converted to UTC —
    so ephemeris input stays UTC while 'today' follows the user's local day."""
    from zoneinfo import ZoneInfo
    try:
        local = datetime.now(ZoneInfo(_chart_tz(chart_json)))
        return local.replace(tzinfo=ZoneInfo(_chart_tz(chart_json))).astimezone(ZoneInfo("UTC"))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc)


def compute_transits(chart_json: dict, when: datetime | None = None) -> list[dict]:
    """Transit events: {planet, sign_fa, natal_target, target_sign_fa, aspect, orb}."""
    now = when or _now_local_utc(chart_json)
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

    # H1.1: 'today' = the chart's local day, not server UTC. Dates shown to
    # the user are LOCAL; the julian day input stays UTC.
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(_chart_tz(chart_json))
    now_local = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    events: list[dict] = []
    active: dict[tuple[int, str], tuple[str, float]] = {}

    for d in range(0, days + 1, step):
        local_when = now_local + timedelta(days=d)
        utc_when = local_when.astimezone(ZoneInfo("UTC"))
        jd = swe.julday(utc_when.year, utc_when.month, utc_when.day,
                        utc_when.hour + utc_when.minute / 60)
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
                            "start": local_when.strftime("%Y-%m-%d"),
                            "planet_fa": _planet_fa(pname),
                            "sign_fa": SIGNS_FA[int(lon // 30)],
                            "target": tname,
                            "aspect": name, "orb": orb,
                        })
                else:
                    active.pop((body, tname), None)
    events.sort(key=lambda e: e["start"])
    return events
