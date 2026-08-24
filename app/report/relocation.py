"""MASTER W7 (N3, AC-5) — چارت مهاجرت (Relocation).

Birth TIME stays fixed; the PLACE changes. For each destination city we
recompute the chart with the same UTC instant but new coordinates → houses
and angles shift, planets don't. Output: per-city house moves + side-by-side
comparison of 1-3 cities. Explicit disclaimer: «نقشهٔ تمرکز است، نه توصیهٔ
مهاجرت». Gate: 6 credits (`relocation`, kind 'relocation').
Deterministic only — no LLM in v1.
"""
from __future__ import annotations

import swisseph as swe

from app.astrology.big_three import SIGNS_FA
from app.astrology.engine import jd_from_utc
from app.report.qa import FORBIDDEN_PATTERNS

swe.set_ephe_path("ephe")
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

_HOUSE_AREA_FA = {
    1: "هویت و دیده‌شدن", 2: "پول و دارایی", 3: "گفت‌وگو و یادگیری",
    4: "خانه و خانواده", 5: "عشق و خلاقیت", 6: "کار روزمره و سلامت",
    7: "شراکت و ازدواج", 8: "عمق و تحول", 9: "سفر و معنا",
    10: "مسیر شغلی", 11: "دوستان و آرزوها", 12: "درون و استراحت",
}


def _house_of_longitude(lon: float, cusps: list[float]) -> int:
    """Which house (1..12) contains `lon` given ascending cusp list."""
    n = len(cusps)
    for i in range(n):
        c1 = cusps[i]
        c2 = cusps[(i + 1) % n]
        if c2 <= c1:  # wrap-around segment (12th→1st)
            if lon >= c1 or lon < c2:
                return i + 1
        elif c1 <= lon < c2:
            return i + 1
    return 1


def relocation_chart(natal_chart: dict, lat: float, lon: float) -> dict:
    """Same UTC birth instant, NEW coordinates → shifted houses/angles."""
    b = natal_chart["birth"]
    utc_str = b["utc_time"]
    from datetime import datetime
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
    jd = jd_from_utc(utc_dt)
    is_sidereal = (natal_chart.get("engine_config") or {}).get("zodiac") == "sidereal"
    ayan = swe.get_ayanamsa_ut(jd) if is_sidereal else 0.0
    cusps_raw, ascmc_raw = swe.houses(jd, lat, lon, b"P")
    if ayan:
        cusps = [(c - ayan) % 360 for c in cusps_raw]
        ascmc = [(a - ayan) % 360 for a in ascmc_raw]
    else:
        cusps, ascmc = list(cusps_raw[:12]), list(ascmc_raw[:4])
    cusps12 = [cusps[i] for i in range(12)]
    # re-house every planet under the new cusps
    moved: dict[str, dict] = {}
    for name, p in natal_chart.get("planets", {}).items():
        old_house = p.get("house")
        new_house = _house_of_longitude(float(p["longitude"]), cusps12)
        moved[name] = {
            "planet_fa": {"Sun": "خورشید", "Moon": "ماه", "Mercury": "عطارد",
                          "Venus": "زهره", "Mars": "مریخ", "Jupiter": "مشتری",
                          "Saturn": "زحل"}.get(name, name),
            "old_house": old_house,
            "new_house": new_house,
            "changed": bool(old_house and new_house != old_house),
            "sign_fa": p.get("sign_fa", ""),
        }
    asc_lon = ascmc[0]
    mc_lon = ascmc[1]
    return {
        "asc_sign_fa": SIGNS_FA[int(asc_lon // 30)],
        "mc_sign_fa": SIGNS_FA[int(mc_lon // 30)],
        "moved": moved,
        "changed_count": sum(1 for m in moved.values() if m["changed"]),
    }


def compare_cities(natal_chart: dict, cities: list[dict]) -> dict:
    """cities: [{name_fa, lat, lon}] (1..3). Returns per-city focus + ranking.
    Ranking metric: how strongly the SR-style 'work/career' cluster (10th house
    occupancy + MC sign) shifts toward the user's top natal priorities — kept
    simple & honest: we rank by number of planets landing in the 10th/2nd/7th
    houses (career/money/partnership), the three questions Iranians ask most.
    """
    out = []
    for city in cities[:3]:
        rc = relocation_chart(natal_chart, float(city["lat"]), float(city["lon"]))
        h10 = [m["planet_fa"] for m in rc["moved"].values() if m["new_house"] == 10]
        h2 = [m["planet_fa"] for m in rc["moved"].values() if m["new_house"] == 2]
        h7 = [m["planet_fa"] for m in rc["moved"].values() if m["new_house"] == 7]
        score = len(h10) * 3 + len(h2) * 2 + len(h7) * 2
        # dominant area = house with most planets here
        counts: dict[int, int] = {}
        for m in rc["moved"].values():
            counts[m["new_house"]] = counts.get(m["new_house"], 0) + 1
        dom = max(counts, key=lambda k: counts[k]) if counts else 1
        out.append({
            "city": city.get("name_fa", ""),
            "asc_sign_fa": rc["asc_sign_fa"],
            "mc_sign_fa": rc["mc_sign_fa"],
            "changed_count": rc["changed_count"],
            "focus_area": _HOUSE_AREA_FA.get(dom, "—"),
            "dominant_house": dom,
            "h10_planets": h10,
            "score": score,
            "moves": [
                f"{m['planet_fa']}: خانهٔ {m['old_house']} ← {m['new_house']}"
                for m in rc["moved"].values() if m["changed"]
            ][:8],
        })
    out.sort(key=lambda x: -x["score"])
    return {
        "cities": out,
        "best_for_work": max(out, key=lambda x: len(x["h10_planets"]))["city"] if out else "",
        "disclaimer": "نقشهٔ مهاجرت یک نقشهٔ تمرکز است، نه توصیهٔ مهاجرت؛ تصمیم نهایی با شرایط واقعی زندگی خودتان است.",
    }


def brand_ok(text: str) -> bool:
    import re
    flat = text.replace("\u200c", "")
    return not any(re.search(p, flat) for p in FORBIDDEN_PATTERNS)
