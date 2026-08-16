"""P0-2 — multi-layer budget gates (daily/monthly/user/report)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import app.report.worker as w
from app.report.worker import generate_report  # noqa: F401


def _fake_engine():
    class _E:
        pass
    return _E()


@pytest.mark.asyncio
async def test_monthly_budget_gate_degrades(monkeypatch):
    """Monthly ceiling hit produces a reason → worker degrades honestly."""
    monkeypatch.setattr(w, "month_llm_cost", lambda e: 999.0)
    monkeypatch.setattr(w, "today_llm_cost", lambda e: 0.01)
    monkeypatch.setattr(w, "user_today_llm_cost", lambda e, u: 0.0)
    assert any("monthly" in r for r in w._budget_reasons(engine=_fake_engine()))


def test_budget_reasons_compose(monkeypatch):
    monkeypatch.setattr(w, "month_llm_cost", lambda e: 40.0)
    monkeypatch.setattr(w, "today_llm_cost", lambda e: 4.0)
    monkeypatch.setattr(w, "user_today_llm_cost", lambda e, u: 9.0)
    reasons = w._budget_reasons(engine=_fake_engine(), user_today=w.user_today_llm_cost(None, "u"))
    assert len(reasons) == 3  # daily + monthly + user
    assert any("user-24h" in r for r in reasons)


def test_no_reasons_when_under_budget(monkeypatch):
    monkeypatch.setattr(w, "month_llm_cost", lambda e: 0.1)
    monkeypatch.setattr(w, "today_llm_cost", lambda e: 0.1)
    monkeypatch.setattr(w, "user_today_llm_cost", lambda e, u: 0.1)
    assert w._budget_reasons(engine=_fake_engine(), user_today=0.1) == []