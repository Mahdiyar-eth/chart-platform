"""M9 — daily LLM cost ceiling: reports degrade honestly (zero LLM calls)
when today's spend already exceeds the budget."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session

from app.core.llm import LLM_DAILY_BUDGET_USD  # noqa: F401
from app.db import engine
from app.models import BirthProfile, Chart, LLMRun, Report, User
from tests.conftest import fake_authority


def _seed():
    from app.astrology.engine import compute_from_fields
    chart_json = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
    with Session(engine) as s:
        u = User(phone='+98m9x' + fake_authority(8), credits=10)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name='ن', raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa='تهران', time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        c = Chart(profile_id=p.id, chart_json=chart_json)
        s.add(c); s.commit(); s.refresh(c)
        r = Report(chart_id=c.id, plan_key='basic', status='queued')
        s.add(r); s.commit(); s.refresh(r)
        # today's spend already over a tiny budget
        s.add(LLMRun(report_id=str(r.id), user_id=u.id, kind="report",
                     provider="go", model="m", cost_usd=0.5, ok=True))
        s.commit()
        return r.id, c.id, u.id


def test_budget_gate_degrades_without_llm(monkeypatch):
    rid, cid, uid = _seed()
    from app.report import worker as w
    calls = {"n": 0}

    class _FakeRouter:
        async def complete(self, *a, **k):
            calls["n"] += 1
            raise AssertionError("LLM must NOT be called when budget is hit")

    monkeypatch.setattr(w, "LLM_DAILY_BUDGET_USD", 0.01)   # below today's spend
    # render must not run either — degraded reports are intro-only
    monkeypatch.setattr(w, "render_report_pdf", lambda *a, **k: None)
    monkeypatch.setattr(w, "REPORTS_DIR", __import__("pathlib").Path("/tmp"))
    asyncio.run(w.generate_report({"router": _FakeRouter(), "chart_id": cid,
                                   "user_id": uid}, rid))
    with Session(engine) as s:
        rep = s.get(Report, rid)
        assert rep.status == "degraded", rep.status
        assert "budget" in (rep.error or "").lower()
        assert rep.sections
        for dom in rep.sections.values():
            assert dom["intro"].startswith("بر اساس عوامل")
    assert calls["n"] == 0  # zero LLM calls — the whole point of the ceiling


def test_budget_high_does_not_gate(monkeypatch):
    rid, cid, uid = _seed()
    from app.report import worker as w
    calls = []

    class _FakeRes:
        ok = False
        text = ""
        error = "provider down (simulated)"
        provider = "fake"
        model = "m"
        cost = 0.0
        usage = type("U", (), {"total": 0, "prompt_tokens": 0, "completion_tokens": 0})()
        latency_ms = 0
        error_code = "timeout"

    class _FakeRouter:
        async def complete(self, *a, **k):
            calls.append(1)
            return _FakeRes()

    monkeypatch.setattr(w, "LLM_DAILY_BUDGET_USD", 99.0)  # budget far above spend
    monkeypatch.setattr(w, "render_report_pdf", lambda *a, **k: None)
    monkeypatch.setattr(w, "REPORTS_DIR", __import__("pathlib").Path("/tmp"))
    asyncio.run(w.generate_report({"router": _FakeRouter(), "chart_id": cid,
                                   "user_id": uid}, rid))
    assert calls  # LLM was attempted (budget NOT the reason to degrade)
    with Session(engine) as s:
        assert s.get(Report, rid).status == "degraded"  # provider down, not budget