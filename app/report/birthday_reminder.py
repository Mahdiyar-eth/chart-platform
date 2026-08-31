"""Birthday reminder — the one recurring sales engine that costs nothing.

Every user's birth date is already in `birth_profiles`, and «چارت سالیانه»
(the solar return) is by definition an annual product: it covers birthday to
birthday. So the most relevant sales moment of the year is knowable in advance
for every single user, with zero acquisition cost and no guessing.

Runs daily from the ARQ worker; sends at most ONE reminder per profile per
year, 14 days ahead, and honours the user's notification preferences.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import BirthProfile, NotificationPrefs, User

log = logging.getLogger("report.birthday_reminder")

DAYS_AHEAD = 14


def _next_birthday(month: int, day: int, today: date) -> date | None:
    """The next occurrence of this month/day on or after today."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:          # 29 Feb on a common year
            try:
                d = date(year, month, day - 1)
            except ValueError:
                return None
        if d >= today:
            return d
    return None


def due_profiles(session: Session, *, today: date | None = None,
                 days_ahead: int = DAYS_AHEAD) -> list[dict]:
    """Profiles whose birthday is exactly `days_ahead` days away.

    Pure and side-effect free so the schedule can be tested without sending.
    """
    today = today or datetime.now(timezone.utc).date()
    out: list[dict] = []
    rows = session.exec(select(BirthProfile).where(BirthProfile.user_id != None)).all()  # noqa: E711
    for p in rows:
        if not (p.raw_month and p.raw_day):
            continue
        nxt = _next_birthday(int(p.raw_month), int(p.raw_day), today)
        if nxt is None or (nxt - today).days != days_ahead:
            continue
        out.append({"profile_id": p.id, "user_id": p.user_id,
                    "name": p.name or "", "on": nxt, "year": nxt.year})
    return out


def reminder_text(name: str, days: int = DAYS_AHEAD) -> tuple[str, str]:
    who = f"{name}، " if name else ""
    return (
        "تولدت نزدیک است",
        f"{who}{days} روز تا تولدت مانده. چارت سالیانه‌ات — از این تولد تا تولد بعدی — "
        f"آمادهٔ ساخت است: تم سال، خانهٔ برجسته و ۵ گذر کلیدی با تاریخ.",
    )


async def run_birthday_reminders(*, deliver: bool = True,
                                 today: date | None = None) -> dict:
    """Daily cron entry. At most one reminder per profile per year."""
    from app.models import TransitAlertLog

    sent = skipped = failed = 0
    with Session(engine) as s:
        due = due_profiles(s, today=today)
    for item in due:
        key = f"bd-{item['year']}"   # one per (user, year) via user_key+week
        try:
            with Session(engine) as s:
                if s.exec(select(TransitAlertLog).where(
                        TransitAlertLog.user_key == item["user_id"],
                        TransitAlertLog.week == key)).first():
                    skipped += 1
                    continue
                prefs = s.get(NotificationPrefs, item["user_id"])
                if prefs and not getattr(prefs, "report_ready", True):
                    skipped += 1
                    continue
                user = s.get(User, item["user_id"])
                if not user:
                    skipped += 1
                    continue
                title, body = reminder_text(item["name"])
                if deliver:
                    from app.push import send_to_user
                    await send_to_user(item["user_id"], title, body, url="/plans")
                s.add(TransitAlertLog(user_key=item["user_id"], week=key,
                                      chart_id=item["profile_id"][:64]))
                s.commit()
                sent += 1
        except Exception as e:  # noqa: BLE001 — one bad profile must not stop the run
            failed += 1
            log.warning("birthday reminder failed for %s: %s", item["profile_id"], e)
    log.info("birthday-reminders: sent=%d skipped=%d failed=%d", sent, skipped, failed)
    return {"sent": sent, "skipped": skipped, "failed": failed, "due": len(due)}
