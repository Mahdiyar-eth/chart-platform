"""Timezone-safe datetime helpers (audit r4 A9).

SQLite (tests) stores naive datetimes; Postgres stores aware ones. Comparing
them raw raises TypeError, so every stored-datetime comparison goes through
`ensure_utc` (assumes naive values are UTC).
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def is_expired(dt: datetime | None) -> bool:
    return not dt or ensure_utc(dt) <= utcnow()


_JALALI_MONTHS = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
_WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه",
                "جمعه", "شنبه", "یکشنبه"]


def jalali_today_label() -> str:
    """«شنبه ۲ شهریور ۱۴۰۵» — Tehran-local Jalali date (MASTER W9)."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    try:
        from jdatetime import date as jdate
        now = _dt.now(ZoneInfo("Asia/Tehran"))
        j = jdate.fromgregorian(date=now.date())
        return f"{_WEEKDAYS_FA[now.weekday()]} {j.day} {_JALALI_MONTHS[j.month]} {j.year}"
    except Exception:  # noqa: BLE001 — jdatetime may be missing in some envs
        now = _dt.now(ZoneInfo("Asia/Tehran"))
        return now.strftime("%Y-%m-%d")
