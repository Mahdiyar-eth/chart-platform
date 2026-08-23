"""B1 — transit forecast engine acceptance tests (deterministic, no LLM)."""
import os, time, uuid
from pathlib import Path
os.environ.setdefault("SWISSEPH_EPHE_PATH", str(Path(__file__).resolve().parent.parent / "ephe"))
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
import swisseph as swe
from app.astrology.engine import compute_from_fields, ensure_ephe, jd_from_utc
from app.astrology.transit_forecast import forecast, TRANSIT_SWEE
from app.astrology.transit_cache import cached_forecast, _now_naive
from app.astrology import transit_cache
from app.astrology import transit_forecast as tf
from app.astrology.golden_data import GOLDEN_CHARTS
from app.models import TransitForecast
from app.db import engine
ensure_ephe()

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
REQ_KEYS = {"id","transit_planet","transit_planet_fa","natal_target","natal_target_fa",
            "aspect","aspect_fa","exact_dates","window_start","window_end",
            "retro_passes","weight","natal_house","transit_sign_fa"}
ASPECT_DEG = {"conjunction":0,"sextile":60,"square":90,"trine":120,"opposition":180}
def _mk_chart():
    """R4/W3: cache tests write TransitForecast (FK chart_id -> charts.id after Z2).
    Build a REAL chart so the FK is satisfied on a fresh/CI schema."""
    from app.models import BirthProfile, Chart
    cj = _golden()
    with Session(engine) as s:
        p = BirthProfile(user_id=None, raw_year=1373, raw_month=5, raw_day=10)
        s.add(p); s.flush()
        cid = "b1-" + uuid.uuid4().hex[:10]
        s.add(Chart(id=cid, profile_id=p.id, chart_json=cj))
        s.commit()
    return cid


def _golden(birth_id="chart-1-mahdi"):
    b = next(c["birth"] for c in GOLDEN_CHARTS if c["id"] == birth_id)
    return compute_from_fields(**b).chart_json

def _ev(months=12, birth_id="chart-1-mahdi", start=None):
    return forecast(_golden(birth_id), months=months, start=start or START)

def _target_lon(name):
    cj = _golden()
    p = (cj.get("planets") or {}).get(name)
    if p: return float(p["longitude"])
    ang = (cj.get("angles") or {}).get(name)
    if ang: return float(ang["longitude"])
    return None

def test_1_golden_deterministic_snapshot():
    assert _ev() == _ev()
    assert len(_ev()) > 5

def test_2_exact_dates_match_aspect_arcmin():
    checked = 0
    for e in _ev():
        if not e["exact_dates"]: continue
        body = TRANSIT_SWEE[e["transit_planet"]]
        target = _target_lon(e["natal_target"])
        if target is None: continue
        asp = ASPECT_DEG[e["aspect"]]
        for iso in e["exact_dates"]:
            jd = jd_from_utc(datetime.fromisoformat(iso))
            sep = ((swe.calc_ut(jd, body)[0][0] - target - asp) + 180) % 360 - 180
            assert abs(sep) < 0.02, (e["transit_planet"], e["aspect"], iso, sep)
            checked += 1
    assert checked > 0

def test_3_retrograde_station_3_passes():
    ev = _ev(months=24)
    # Jupiter stations near the ASC in this window and crosses it 3x (this is the
    # stationary-retro loop the plan expects the engine to group into ONE event).
    jup = [e for e in ev if e["transit_planet"] == "Jupiter"
           and e["natal_target"] == "ASC" and e["aspect"] == "conjunction"]
    assert jup and jup[0]["retro_passes"] == 3, f"expected a 3-pass retro group, got {jup[:1]}"
    dates = jup[0]["exact_dates"]
    assert len(dates) == len(set(dates)) == 3
    # the passes are spread across a retro arc (weeks apart), not a single day
    assert (datetime.fromisoformat(dates[2]) - datetime.fromisoformat(dates[0])).days >= 30

def test_4_sorted_by_window_start():
    ws = [e["window_start"] for e in _ev()]
    assert ws == sorted(ws)

def test_5_months3_is_subset_of_months12():
    k12 = {(e["transit_planet"],e["natal_target"],e["aspect"]) for e in _ev(12)}
    for e in _ev(3):
        assert (e["transit_planet"],e["natal_target"],e["aspect"]) in k12

def test_6_no_duplicate_events():
    ids = [e["id"] for e in _ev()]
    assert len(ids) == len(set(ids))

def test_7_no_time_chart_drops_asc_mc():
    evs = _ev(birth_id="chart-2-no-time")
    assert isinstance(evs, list)
    assert all(e["natal_target"] not in ("ASC","MC") for e in evs)

def test_8_southern_hemisphere_runs():
    assert isinstance(_ev(birth_id="chart-6-foreign-city"), list)

def test_9_performance_under_2s_12months():
    t0 = time.perf_counter(); _ev(12); dt = time.perf_counter() - t0
    assert dt < 2.0, "12-month scan %.2fs" % dt

def test_12_schema_exact_keys():
    for e in _ev():
        assert set(e.keys()) == REQ_KEYS, set(e.keys()) ^ REQ_KEYS

def test_10_cache_skips_recompute():
    cid = _mk_chart()
    cj = _golden(); n = {"v": 0}
    orig = transit_cache.forecast
    def wrap(chart_json, months=12, start=None):
        n["v"] += 1
        return tf.forecast(chart_json, months=months, start=start)
    transit_cache.forecast = wrap
    try:
        with Session(engine) as s:
            a = cached_forecast(s, cid, 6, cj, start=START)
            assert n["v"] == 1
            b = cached_forecast(s, cid, 6, cj, start=START)
            assert n["v"] == 1, "2nd call must reuse cache"
            assert a == b
            rows = s.exec(select(TransitForecast).where(TransitForecast.chart_id == cid)).all()
            assert len(rows) == 1
    finally:
        transit_cache.forecast = orig

def test_11_cache_invalidates_after_ttl():
    cid = _mk_chart()
    cj = _golden(); n = {"v": 0}
    orig = transit_cache.forecast
    def wrap(chart_json, months=12, start=None):
        n["v"] += 1
        return tf.forecast(chart_json, months=months, start=start)
    transit_cache.forecast = wrap
    try:
        with Session(engine) as s:
            cached_forecast(s, cid, 6, cj, start=START)
            assert n["v"] == 1
            row = s.exec(select(TransitForecast).where(TransitForecast.chart_id == cid)).first()
            row.computed_at = _now_naive() - timedelta(days=8)
            s.add(row); s.commit()
            cached_forecast(s, cid, 6, cj, start=START)
            assert n["v"] == 2, "stale cache must recompute"
    finally:
        transit_cache.forecast = orig

