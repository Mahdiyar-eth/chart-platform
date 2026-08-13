"""«آسمان امروز» tests — audit G-3 (public, reflective, no prediction)."""
from app.astrology.sky import sky_today, weekly_reflection_prompt

BANNED = ["پیش‌بینی", "پیش بینی", "فال", "طالع بینی", "سرنوشت", "آینده", "بخت", "شانس"]


def _full_text(s: dict) -> str:
    parts = [s["moon_phase"], s["moon_phase_meaning"], s["reflection"], s["moon_sign_fa"]]
    for p in s["planets"]:
        parts += [p["name_fa"], p["sign_fa"], p["theme"], p["element_fa"], p["modality_fa"]]
    for r in s["retrogrades"]:
        parts += [r["name_fa"], r["sign_fa"], r["review"]]
    for a in s["aspects"]:
        parts += [a["a_fa"], a["b_fa"], a["name"], a["meaning"]]
    for e in s["moon_events"]:
        parts += [e["label"], e["sign_fa"]]
    return " ".join(parts)


def test_sky_today_has_positions_and_phase():
    s = sky_today()
    assert s["date_fa"]
    assert s["moon_phase"] in {"ماه نو", "رو به رشد", "ماه کامل", "رو به کاهش"}
    assert len(s["planets"]) >= 7
    for p in s["planets"]:
        assert p["sign_fa"] and p["name_fa"] and p["glyph"]


def test_sky_today_has_new_sections():
    s = sky_today()
    assert s["moon_phase_meaning"]
    assert s["moon_sign_fa"]
    assert isinstance(s["moon_degree"], float)
    assert 0 <= s["moon_illumination"] <= 100
    # moon events: at least next new moon + next full moon
    labels = {e["label"] for e in s["moon_events"]}
    assert {"ماه نو", "ماه کامل"} <= labels
    for e in s["moon_events"]:
        assert e["date_fa"] and e["sign_fa"]


def test_planets_have_specialized_fields():
    s = sky_today()
    for p in s["planets"]:
        assert 0 <= p["degree"] < 30
        assert p["element_fa"] in {"آتش", "خاک", "هوا", "آب"}
        assert p["modality_fa"] in {"بنیادین", "ثابت", "متغیر"}
        assert p["theme"]


def test_aspects_valid():
    s = sky_today()
    assert isinstance(s["aspects"], list)
    for a in s["aspects"]:
        assert a["name"] in {"هم‌نشینی", "مقابله", "سه‌گانه", "تربیع", "شش‌گانه"}
        assert a["glyph"] and a["meaning"]
        assert 0 <= a["orb"] <= 8


def test_sky_today_not_predictive():
    s = sky_today()
    blob = _full_text(s)
    for w in BANNED:
        assert w not in blob, f"banned word {w!r} in sky_today"


def test_reflection_rotates_by_week():
    from datetime import datetime
    a = weekly_reflection_prompt(datetime(2026, 8, 13))
    b = weekly_reflection_prompt(datetime(2026, 8, 20))
    assert a != b  # different ISO weeks → different prompt
