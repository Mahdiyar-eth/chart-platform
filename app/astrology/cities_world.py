"""World city search (HARDENING H0.1) — geonames-derived seed with official IANA
timezone per city. Persian alias map covers ~160 well-known cities; the latin
search covers all 1100. Used by the birth form, chart API and bots."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data" / "cities_world_seed.json"
FA = Path(__file__).parent / "data" / "cities_fa_world.json"

_FA: dict[str, str] | None = None
_CITIES: list[dict] | None = None
_TF = None  # timezonefinder singleton (lazy — heavy import at first chart)


def _load() -> list[dict]:
    global _CITIES
    if _CITIES is None:
        _CITIES = json.loads(DATA.read_text(encoding="utf-8"))
    return _CITIES or []


def _fa_map() -> dict[str, str]:
    global _FA
    if _FA is None:
        _FA = json.loads(FA.read_text(encoding="utf-8"))
    return _FA or {}


def tz_from_coords(lat: float, lon: float) -> str | None:
    """IANA timezone for any coordinates (H0.1).

    F-06 (audit v5 P1): returns None when the lookup is unavailable instead of
    silently falling back to Asia/Tehran — a wrong UTC offset silently corrupts
    the whole chart for a non-Iranian user. Callers must decide: Iran-only
    flows may fall back to Tehran; anything else must ask the user for a city.
    Lazy singleton.
    """
    global _TF
    try:
        if _TF is None:
            import timezonefinder as _tzf
            _TF = _tzf.TimezoneFinder()
        tz = _TF.timezone_at(lng=lon, lat=lat)
        return tz or None
    except Exception:  # noqa: BLE001 — never break chart computation
        return None


IRAN_BBOX = {"min_lon": 44.0, "max_lon": 64.0, "min_lat": 25.0, "max_lat": 40.0}


def is_iran_coords(lat: float, lon: float) -> bool:
    """Rough Iran bounding box — used to decide whether the Tehran fallback is
    acceptable for a coordinate pair (F-06: Tehran fallback only for Iran)."""
    return (IRAN_BBOX["min_lon"] <= lon <= IRAN_BBOX["max_lon"]
            and IRAN_BBOX["min_lat"] <= lat <= IRAN_BBOX["max_lat"])


def resolve_tz_safe(lat: float, lon: float) -> str | None:
    """F-06: timezone with safe fallback — Asia/Tehran ONLY inside Iran;
    None for everywhere else (caller must 400 with 'pick a city')."""
    tz = tz_from_coords(lat, lon)
    if tz:
        return tz
    if is_iran_coords(lat, lon):
        return "Asia/Tehran"
    return None


def resolve_fa_alias(query: str) -> str | None:
    """Persian name -> geonames name (None if not in the alias map)."""
    q = query.strip()
    return _fa_map().get(q)


def search_cities_world(query: str, limit: int = 8) -> list[dict]:
    """Search world cities by Persian alias or latin name (prefix first,
    then substring). Returns [{name, country, lat, lon, tz}, ...]."""
    q = query.strip().lower()
    if not q:
        return []
    fa = resolve_fa_alias(query)
    if fa:
        q = fa.lower()
    cities = _load()
    exact, prefix, sub = [], [], []
    for c in cities:
        name = (c.get("ascii") or c["name"]).lower()
        if name == q:
            exact.append(c)
        elif name.startswith(q):
            prefix.append(c)
        elif q in name:
            sub.append(c)
    merged = (exact + prefix + sub)[:limit]
    return [
        {"name": c["name"], "country": c["country"], "lat": c["lat"],
         "lon": c["lon"], "tz": c["tz"], "pop": c.get("pop", 0)}
        for c in merged
    ]
