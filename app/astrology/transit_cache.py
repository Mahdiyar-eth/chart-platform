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
        return json.loads(row.payload_json)

    result = forecast(chart_json, months=months, start=start)
    if session is not None:
        if row is None:
            row = TransitForecast(chart_id=chart_id, months=months)
        row.payload_json = json.dumps(result, ensure_ascii=False)
        row.computed_at = now
        session.add(row)
        session.commit()
    return result
