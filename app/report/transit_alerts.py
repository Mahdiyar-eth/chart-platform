"""B4 — weekly transit alerts (user-return engine).

For every active subscription chart: scan the next 7 days of transit events
(B1 engine, cached) and if any has weight >= 18, deliver ONE notification per
user per week. Anti-duplicate via TransitAlertLog; respects NotificationPrefs.
"""
from __future__ import annotations

import json, logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import (BirthProfile, Chart, NotificationPrefs, Subscription,
                        TransitAlertLog, TransitForecast)

log = logging.getLogger("report.transit_alerts")

_MIN_WEIGHT = 18          # plan B4: only notable events trigger a push
_DAYS_AHEAD = 7           # weekly window


def pick_alert_event(events: list[dict], *, today: datetime | None = None) -> dict | None:
    """Highest-weight event whose exact date falls within the next _DAYS_AHEAD days.
    Returns None when nothing qualifies (no push this week)."""
    now = (today or datetime.now(timezone.utc)).date()
    best = None
    for e in events or []:
        for iso in e.get("exact_dates") or []:
            try:
                d = datetime.strptime(iso[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if now <= d <= now + timedelta(days=_DAYS_AHEAD):
                if best is None or e.get("weight", 0) > best.get("weight", 0):
                    best = e
                break  # one matching date is enough for this event
    return best


def alert_text(e: dict) -> tuple[str, str]:
    """(title, body) — honest teaser, no fixed promises."""
    t = e.get("transit_planet_fa") or e.get("transit_planet")
    tgt = e.get("natal_target_fa") or e.get("natal_target") or ""
    asp = e.get("aspect_fa") or e.get("aspect") or ""
    title = "گذر پیشِ رو"
    body = f"در هفتهٔ پیشِ رو {t} با {tgt} زاویهٔ {asp} میسازد — ببین."
    return title, body


async def run_transit_alerts(*, deliver=True) -> dict:
    """Weekly cron entry: at most ONE alert per user per ISO-week."""
    from app.bots.handler import send_message

    now = datetime.now(timezone.utc)
    week = now.strftime("%G-W%V")
    sent = skipped = failed = 0
    with Session(engine) as s:
        subs = s.exec(select(Subscription).where(Subscription.active == True)).all()  # noqa: E712
    seen_users: set[str] = set()
    for sub in subs:
        try:
            with Session(engine) as s:
                chart = s.get(Chart, sub.chart_id)
                if not chart:
                    continue
                prof = s.get(BirthProfile, chart.profile_id)
                uid = (prof.user_id if prof else None) or f"bot:{sub.chat_id}:{sub.platform}"
                if uid in seen_users:
                    continue  # max 1/week per user
                prefs = s.get(NotificationPrefs, uid)
                if prefs and not getattr(prefs, "transit_alerts", True):
                    skipped += 1
                    seen_users.add(uid)
                    continue
                row = s.exec(select(TransitForecast).where(
                    TransitForecast.chart_id == chart.id)).first()
                evs = json.loads(row.payload_json).get("events", []) if row and row.payload_json else []
                ev = pick_alert_event(evs)
                if not ev:
                    continue
                # anti-duplicate: one log row per user+week+chart
                dup = s.exec(select(TransitAlertLog).where(
                    TransitAlertLog.user_key == str(uid),
                    TransitAlertLog.week == week,
                    TransitAlertLog.chart_id == chart.id)).first()
                if dup:
                    skipped += 1
                    continue
                title, body = alert_text(ev)
                url = f"/transits?c={chart.id}"
                if deliver:
                    if sub.chat_id:
                        await send_message(int(sub.chat_id), f"{title}\n{body}\n{url}", sub.platform)
                    else:
                        from app.push import send_to_user
                        send_to_user(uid, title, body, "/transits", s)
                s.add(TransitAlertLog(user_key=str(uid), week=week, chart_id=chart.id))
                s.commit()
            seen_users.add(uid)
            sent += 1
        except Exception as e:  # noqa: BLE001 — one bad sub must not kill the loop
            failed += 1
            log.error("transit alert failed for sub %s: %s", sub.id, e)
    return {"sent": sent, "skipped": skipped, "failed": failed, "week": week}

