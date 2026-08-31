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
    src = Path(__file__).resolve().parent / "data" / "cities_seed.json"
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
