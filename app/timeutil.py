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
