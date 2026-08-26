"""The birthday reminder is a money feature: it must fire exactly once per
user per year, at the right distance from the birthday, and never for someone
who opted out. These tests pin the schedule without sending anything.
"""
import os
import uuid
from datetime import date

os.environ.setdefault("DATABASE_URL",
                      "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from sqlmodel import Session

from app.db import engine
from app.models import BirthProfile, User
from app.report.birthday_reminder import _next_birthday, due_profiles, reminder_text


def _profile(month: int, day: int) -> str:
    uid = "u" + uuid.uuid4().hex[:10]
    pid = "p" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t"))
        s.commit()                      # the profile FK needs the user committed first
    with Session(engine) as s:
        s.add(BirthProfile(id=pid, user_id=uid, name="تست",
                           raw_year=1994, raw_month=month, raw_day=day,
                           lat=35.7, lon=51.4, tz_name="Asia/Tehran"))
        s.commit()
    return pid


def test_fires_exactly_fourteen_days_before():
    pid = _profile(6, 15)
    with Session(engine) as s:
        due = {d["profile_id"] for d in due_profiles(s, today=date(2026, 6, 1))}
        assert pid in due, "a birthday 14 days out must be due"
        for offset_day in (5, 2, 16, 20):   # 13, 10, 30 and 26 days away
            other = {d["profile_id"] for d in due_profiles(s, today=date(2026, 6, offset_day))}
            assert pid not in other, f"must not fire on 2026-06-{offset_day}"


def test_rolls_over_the_year_end():
    """A January birthday seen from December must resolve to NEXT year."""
    assert _next_birthday(1, 5, date(2026, 12, 22)) == date(2027, 1, 5)
    pid = _profile(1, 5)
    with Session(engine) as s:
        due = {d["profile_id"] for d in due_profiles(s, today=date(2026, 12, 22))}
    assert pid in due


def test_leap_day_does_not_crash_on_a_common_year():
    """29 Feb must fall back to the 28th rather than raising."""
    assert _next_birthday(2, 29, date(2027, 2, 1)) == date(2027, 2, 28)


def test_a_profile_with_no_owner_is_never_due():
    pid = "p" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(BirthProfile(id=pid, user_id=None, name="مهمان",
                           raw_year=1994, raw_month=6, raw_day=15,
                           lat=35.7, lon=51.4, tz_name="Asia/Tehran"))
        s.commit()
        due = {d["profile_id"] for d in due_profiles(s, today=date(2026, 6, 1))}
    assert pid not in due, "an unclaimed guest profile has nobody to remind"


def test_message_names_the_product_and_the_countdown():
    title, body = reminder_text("مهدی")
    assert "تولد" in title
    assert "مهدی" in body and "14 روز" in body and "سالیانه" in body
