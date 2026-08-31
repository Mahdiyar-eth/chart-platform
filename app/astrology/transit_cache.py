"""B1 — TTL cache accessor for transit forecasts (transit_forecasts table).

The engine (`forecast`) is pure; this layer persists a payload per
(chart_id, months) and reuses it for 7 days, matching plan B1.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.astrology.transit_forecast import forecast
from app.models import TransitForecast

TTL_DAYS = 7


def _now_naive() -> datetime:
    """Naive UTC — the DateTime column round-trips naive (see A3)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cached_forecast(session, chart_id: str, months: int, chart_json: dict,
                    start=None, ttl_days: int = TTL_DAYS) -> list[dict]:
    """Return cached forecast for (chart_id, months) or compute + store it."""
    row = None
    if session is not None:
        row = session.exec(select(TransitForecast).where(
            TransitForecast.chart_id == chart_id,
            TransitForecast.months == months,
        )).first()
    now = _now_naive()
    if row is not None and row.computed_at and (now - row.computed_at) <= timedelta(days=ttl_days):
        data = json.loads(row.payload_json)
        # X1/R1: payload may hold the merged dict {events, narratives} after a paid
        # analyze — always normalize to the events list for callers.
        if isinstance(data, dict):
            return data.get("events") or []
        return data

    result = forecast(chart_json, months=months, start=start)
    if session is not None:
        if row is None:
            row = TransitForecast(chart_id=chart_id, months=months)
        else:
            # X-R22: TTL rewrite must NOT wipe paid narratives. Re-merge them onto
            # the fresh deterministic list.
            try:
                prev = json.loads(row.payload_json or "{}")
            except Exception:  # noqa: BLE001
                prev = {}
            if isinstance(prev, dict) and prev.get("narratives"):
                # Y17/N12b: drop narratives whose event vanished after recompute
                # (content drift, not crash) so the page never shows analysis for
                # a transit that no longer exists in this window.
                _live = {e.get("id") for e in result}
                _kept = [n for n in prev["narratives"]
                         if not (n.get("event") or {}).get("id")  # legacy: no anchor → keep
                         or n["event"]["id"] in _live]
                row.payload_json = json.dumps({"events": result,
                                               "narratives": _kept},
                                              ensure_ascii=False)
                row.computed_at = now
                session.add(row)
                session.commit()
                return result
        row.payload_json = json.dumps(result, ensure_ascii=False)
        row.computed_at = now
        session.add(row)
        session.commit()
    return result


def store_transit_analysis(session, chart_id: str, months: int, payload: dict) -> None:
    """B3 — persist a paid transit analysis into the (chart_id, months) cache row,
    merging the deterministic forecast with the narratives so a page refresh never
    re-charges the user for analysis they already paid for."""
    from sqlmodel import select
    from app.models import TransitForecast
    row = session.exec(select(TransitForecast).where(
        TransitForecast.chart_id == chart_id, TransitForecast.months == months)).first()
    if row is None:
        row = TransitForecast(chart_id=chart_id, months=months)
    try:
        merged = json.loads(row.payload_json or "{}")
    except Exception:  # noqa: BLE001
        merged = {}
    if isinstance(merged, list):
        merged = {"events": merged}
    merged.update(payload)
    row.payload_json = json.dumps(merged, ensure_ascii=False)
    row.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(row)
    session.commit()
