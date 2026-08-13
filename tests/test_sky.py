"""«آسمان امروز» tests — audit G-3 (public, reflective, no prediction)."""
from app.astrology.sky import sky_today, weekly_reflection_prompt

BANNED = ["پیش‌بینی", "پیش بینی", "فال", "طالع بینی", "سرنوشت", "آینده", "بخت", "شانس"]


def test_sky_today_has_positions_and_phase():
    s = sky_today()
    assert s["date_fa"]
    assert s["moon_phase"] in {"ماه نو", "رو به رشد", "ماه کامل", "رو به کاهش"}
    assert len(s["planets"]) >= 7
    for p in s["planets"]:
        assert p["sign_fa"] and p["name_fa"] and p["glyph"]


def test_sky_today_not_predictive():
    s = sky_today()
    blob = " ".join([s["moon_phase"], s["reflection"], *[p["name_fa"] for p in s["planets"]]])
    for w in BANNED:
        assert w not in blob, f"banned word {w!r} in sky_today"


def test_reflection_rotates_by_week():
    from datetime import datetime
    a = weekly_reflection_prompt(datetime(2026, 8, 13))
    b = weekly_reflection_prompt(datetime(2026, 8, 20))
    assert a != b  # different ISO weeks → different prompt
