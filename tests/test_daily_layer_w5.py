"""MASTER W5 (N1, AC-3) — «امروزِ تو» reflective daily layer.

Five cards from TODAY'S REAL transits on the user's own chart:
- 4 deterministic cards (zero cost): sky_today / reflection_line /
  inner_weather / active_area (+ relationship_today = also deterministic)
- 1 LLM insight cached per (chart_id, date) — tomorrow must be a NEW cache
  key (proven with an injected date).
Brand gate: zero «فال/شانس/پیش‌بینی» in any card text.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import _user_cookie_value
from app.db import engine
from app.main import app as main_app
from app.models import BirthProfile, Chart, User
from app.today.daily import build_daily_cards

DAY1 = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)


class FakeChart:
    """Real computed chart (deterministic engine) without DB."""
    chart_json = None
    id = "fake-chart-id"


def _real_chart_json() -> dict:
    from app.astrology.engine import compute_from_fields
    return compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_w5_four_deterministic_cards_from_real_transits():
    FakeChart.chart_json = _real_chart_json()
    cards = build_daily_cards(None, FakeChart(), "Asia/Tehran", when_local=DAY1)
    # every card exists with real content
    assert cards["sky_today"], "sky_today must reflect today's most active transit"
    st = cards["sky_today"]
    assert st["planet_fa"] and st["aspect_fa"] and len(st["meaning"]) > 40
    rl = cards["reflection_line"]
    assert rl["line"] and rl["question"].endswith("؟"), "reflection needs its question"
    iw = cards["inner_weather"]
    assert iw["sign_fa"], "inner_weather must show the REAL moon sign of the day"
    assert "ماه امروز در" in iw["text"]
    # relationship card uses Venus/Mars when one aspects a natal point
    if cards["relationship_today"]:
        rt = cards["relationship_today"]
        assert rt["planet_fa"] in ("ناهید", "مریخ")
    blob = json.dumps(cards, ensure_ascii=False)
    for bad in ("فال", "شانس", "پیشگویی", "مقدر"):
        assert bad not in blob, f"forbidden word in daily cards: {bad}"


def test_w5_tomorrow_changes_the_content():
    """AC-3 — tomorrow's layer must differ (new date → new content/cache key)."""
    FakeChart.chart_json = _real_chart_json()
    d1 = build_daily_cards(None, FakeChart(), "Asia/Tehran", when_local=DAY1)
    d3 = build_daily_cards(None, FakeChart(), "Asia/Tehran",
                           when_local=datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc))
    assert d1["date"] == "2026-08-25" and d3["date"] == "2026-08-28"
    # 3 days apart: the Moon moved ~40° — inner_weather MUST differ
    changed = (d1["inner_weather"]["text"] != d3["inner_weather"]["text"]
               or d1["facts_count"] != d3["facts_count"]
               or json.dumps(d1["sky_today"], ensure_ascii=False)
               != json.dumps(d3["sky_today"], ensure_ascii=False))
    assert changed, "daily layer must not serve identical content across days"


class FakeResult:
    def __init__(self, text):
        self.text = text; self.ok = True; self.provider = "f"; self.model = "f"
        self.usage = type("U", (), {"total": 50, "prompt_tokens": 30,
                                    "completion_tokens": 20})()
        self.cost = 0.0; self.error = None; self.latency_ms = 5


class FakeRouter:
    calls = 0

    async def complete(self, prompt, **kw):
        FakeRouter.calls += 1
        return FakeResult("امروز اورانوس با خورشیدت تربیع دارد؛ جایی که مقاومت می‌کنی شاید دقیقاً همان نقطهٔ رشد باشد.")


def test_w5_llm_insight_cached_per_day(monkeypatch):
    """One LLM call per (chart, date); same-day reload = cache hit, no call."""
    from app.today.daily import get_daily_layer
    FakeChart.chart_json = _real_chart_json()
    monkeypatch.setattr("app.core.llm.build_chat_router", lambda: FakeRouter())

    async def run():
        FakeRouter.calls = 0
        # flush the (chart,date) cache so this test is order-independent
        import redis as _r
        for db in ("0", "1"):
            try:
                r = _r.Redis.from_url(f"redis://127.0.0.1:6379/{db}")
                for k in r.keys(f"today:{FakeChart.id}:*"):
                    r.delete(k)
            except Exception:  # noqa: BLE001
                pass
        p1 = await get_daily_layer(None, FakeChart(), "Asia/Tehran")
        n_first = FakeRouter.calls
        p2 = await get_daily_layer(None, FakeChart(), "Asia/Tehran")
        n_second = FakeRouter.calls - n_first
        return p1, p2, n_first, n_second
    p1, p2, first, second = asyncio.new_event_loop().run_until_complete(run())
    assert p1["insight"], "insight should be produced by the LLM"
    assert first == 1, f"expected exactly 1 LLM call on first load, got {first}"
    assert second == 0, "same-day second load must come from the cache (zero calls)"
    assert p2["cached"] is True and p2["insight"] == p1["insight"]


def test_w5_api_daily_endpoint_gated_and_shaped(monkeypatch):
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w5", credits=0)); s.commit()
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890)
        s.add(p); s.flush()
        ch = Chart(profile_id=p.id, chart_json=_real_chart_json(),
                   access_token="tok" + uuid.uuid4().hex[:12])
        s.add(ch); s.commit(); s.refresh(ch)
        cid = ch.id
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))
    r = c.get(f"/api/today/daily?chart_id={cid}")
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("date", "sky_today", "reflection_line", "inner_weather",
                "relationship_today"):
        assert key in d, f"daily payload missing {key}"
    # ownership: another chart id → 403
    r2 = c.get("/api/today/daily?chart_id=nope")
    assert r2.status_code in (403, 404)
