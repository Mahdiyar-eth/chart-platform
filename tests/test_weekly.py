"""Weekly reflection tests — audit P0-2.

The weekly «نگاهی به آسمان هفته» must be reflective (not predictive), carry
no fortune-telling language, and end with the agency/free-will framing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.astrology.engine import compute_from_fields
from app.report.weekly import build_weekly_reflection


def _chart():
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_reflection_is_not_predictive():
    txt = build_weekly_reflection(_chart())
    for banned in ("پیش‌بینی", "فال", "طالع", "آینده", "اتفاق می‌افتد"):
        assert banned not in txt, f"banned word present: {banned}"


def test_reflection_has_agency_framing():
    txt = build_weekly_reflection(_chart())
    assert "اختیار" in txt
    assert "نقشه" in txt  # "نقشهی موقعیتها، نه سرنوشت"


def test_reflection_has_title():
    txt = build_weekly_reflection(_chart())
    assert "نگاهی به آسمان هفته" in txt


def test_reflection_handles_empty_events():
    # a chart with no upcoming tight aspects still yields a non-empty reflection
    txt = build_weekly_reflection(_chart())
    assert len(txt) > 60


def test_web_subscription_chat_id_none_does_not_crash():
    """F-28 (runtime audit): web subs (chat_id=None) must not int(None)-crash
    the weekly delivery; the reflection row must still be stored."""
    import asyncio
    import uuid
    from unittest.mock import AsyncMock, patch

    from sqlmodel import Session, text

    from app.db import engine
    from app.models import Chart, Subscription
    from app.report import weekly as w

    cid = f"f28-{uuid.uuid4().hex[:10]}"
    with Session(engine) as s:
        s.add(Chart(id=cid, chart_json={}))
        s.add(Subscription(platform="web", chart_id=cid,
                           freq="weekly", plan_key="monthly", active=True))
        s.commit()

    async def _run():
        with (patch.object(w, "build_weekly_reflection", return_value="متن هفته"),
              patch("app.bots.handler.send_message", new_callable=AsyncMock) as sm_mock):
            res = await w.run_weekly_delivery()
        return res, sm_mock.call_count

    res, bot_calls = asyncio.run(_run())
    assert res == {"sent": 1, "failed": 0}
    assert bot_calls == 0  # web sub → push-only, no bot int(None)
    with Session(engine) as s:
        s.exec(text(f"DELETE FROM weekly_reflections WHERE chart_id='{cid}'"))
        s.exec(text(f"DELETE FROM subscriptions WHERE chart_id='{cid}'"))
        s.exec(text(f"DELETE FROM charts WHERE id='{cid}'"))
        s.commit()


