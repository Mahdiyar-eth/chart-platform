"""B4 — weekly transit alerts acceptance tests (delivery mocked, DB real)."""
import os, json, uuid
from pathlib import Path
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("SWISSEPH_EPHE_PATH", str(Path(__file__).resolve().parent.parent / "ephe"))
os.environ.setdefault("CREATE_ALL_ON_BOOT", "1")

from datetime import datetime, timedelta, timezone
import pytest

from app.db import engine
from sqlmodel import Session, select
from app.models import (BirthProfile, Chart, NotificationPrefs, Subscription,
                        TransitAlertLog, TransitForecast, User)
from app.report.transit_alerts import pick_alert_event, run_transit_alerts


def _ev(w, days_ahead, tp="Saturn", tgt="Sun", *, today=None):
    """R13 fix: the date must be relative to the `today` passed to
    pick_alert_event — datetime.now() made this test time-bomb (it passed in
    August, fails any day the offset crosses a month boundary)."""
    base = today or datetime.now(timezone.utc)
    d = (base + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    return {"transit_planet": tp, "transit_planet_fa": "زحل", "aspect": "conjunction",
            "aspect_fa": "هم‌نشینی", "natal_target": tgt, "natal_target_fa": "خورشید",
            "weight": w, "exact_dates": [d], "retro_passes": 1}


def test_1_picks_highest_weight_in_7day_window():
    today = datetime(2026, 8, 22, tzinfo=timezone.utc)
    evs = [_ev(10, 2, today=today), _ev(25, 5, tp="Jupiter", today=today),
           _ev(30, 9, today=today)]   # 3rd is day+9 → outside window
    got = pick_alert_event(evs, today=today)
    assert got and got["weight"] == 25 and got["transit_planet"] == "Jupiter"


def test_1b_no_push_when_all_outside_window():
    assert pick_alert_event([_ev(30, 8)], today=datetime(2026, 8, 22, tzinfo=timezone.utc)) is None


@pytest.mark.asyncio
async def test_2_respects_prefs_and_dedup_and_link():
    uid = "u" + uuid.uuid4().hex[:8]
    cid = "c" + uuid.uuid4().hex[:8]
    with Session(engine) as s:
        s.add(User(id=uid))
        s.commit()  # user first — birth_profiles.user_id has an FK
        s.add(BirthProfile(id="p"+uuid.uuid4().hex[:6], user_id=uid, name="تستی",
                           raw_year=1373, raw_month=6, raw_day=1, raw_hour=6, raw_minute=10,
                           city="تهران", lat=35.7, lon=51.4, tz_name="Asia/Tehran"))
        prof = s.exec(select(BirthProfile).where(BirthProfile.user_id == uid)).first()
        s.add(Chart(id=cid, profile_id=prof.id, chart_json={}))
        s.add(NotificationPrefs(user_id=uid, transit_alerts=False))
        s.commit()

    delivered = []
    import app.bots.handler as bh
    async def fake_send(chat_id, text, platform=None, **_k):
        delivered.append((chat_id, text, platform))
    orig = bh.send_message
    bh.send_message = fake_send
    try:
        # seed forecast cache + subscription AFTER prefs off → skipped, no delivery
        with Session(engine) as s:
            s.add(TransitForecast(chart_id=cid, months=12, payload_json=json.dumps({"events": [_ev(40, 3)]})))
            s.add(Subscription(chart_id=cid, platform="telegram", chat_id=str(999001), active=True))
            s.commit()
        r = await run_transit_alerts()
        assert not delivered, "prefs off must not deliver"
        assert r["skipped"] >= 1

        # turn prefs ON → delivers exactly once with the direct link
        with Session(engine) as s:
            pr = s.get(NotificationPrefs, uid)
            pr.transit_alerts = True
            s.add(pr)
            s.commit()
        _r2 = await run_transit_alerts()
        assert len(delivered) == 1
        chat_id, text, platform = delivered[0]
        assert f"/transits?c={cid}" in text
        # anti-dup row written
        with Session(engine) as s:
            rows = s.exec(select(TransitAlertLog).where(TransitAlertLog.user_key == uid)).all()
            assert len(rows) == 1

        # third run same week → no duplicate delivery
        await run_transit_alerts()
        assert len(delivered) == 1, "anti-duplicate: max one push per week"
    finally:
        bh.send_message = orig

