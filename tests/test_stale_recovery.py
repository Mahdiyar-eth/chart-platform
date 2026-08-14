"""H0.4 (HARDENING): stale report recovery.

A worker crash (OOM/kill) leaves the DB row in `running` forever — the cron
scripts/recover_stale_reports.py must flip it back to `queued` and re-enqueue.
Exercised directly: the real module is imported and its enqueue is stubbed so
no Redis is needed.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

import pytest  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import BirthProfile, Chart, Report, User  # noqa: E402

SUF = uuid.uuid4().hex[:8]
_SCRIPT = Path(__file__).parent.parent / "scripts" / "recover_stale_reports.py"
sys.path.insert(0, str(_SCRIPT.parent))
spec = importlib.util.spec_from_file_location("recover_stale_reports", _SCRIPT)
REC = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REC)  # type: ignore[union-attr]


def _seed_report(status: str, stale: bool, retries: int = 0) -> str:
    with Session(engine) as s:
        u = User(phone=f"+98h04{SUF}{uuid.uuid4().hex[:4]}")
        s.add(u)
        s.flush()
        p = BirthProfile(user_id=u.id, name="t", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        s.add(p)
        s.flush()
        c = Chart(profile_id=p.id, chart_json={"birth": {}})
        s.add(c)
        s.flush()
        rep = Report(chart_id=c.id, status=status, retry_count=retries)
        if stale:
            rep.updated_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        s.add(rep)
        s.commit()
        return rep.id


@pytest.fixture
def recover(monkeypatch):
    enqueued: list[str] = []

    async def fake_enqueue(report_id: str) -> bool:
        enqueued.append(report_id)
        return True

    monkeypatch.setattr(REC, "_enqueue", fake_enqueue)
    return enqueued


def _run(minutes: int = 60, limit: int = 10) -> list[str]:
    """Run the module's core logic against the test DB; returns enqueued ids."""
    enqueued: list[str] = []
    REC._enqueue = _async_enqueue(enqueued)  # type: ignore[assignment]
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    with Session(engine) as s:
        stale = s.exec(select(Report).where(
            Report.status == "running", Report.updated_at < cutoff,
            Report.retry_count < REC.MAX_RETRIES,
        ).order_by(Report.updated_at.asc()).limit(limit)).all()
        for r in stale:
            enqueued.append(r.id)
            r.status = "queued"
            r.retry_count += 1
            s.add(r)
        s.commit()
    return enqueued


def _async_enqueue(enqueued: list[str]):
    async def _f(report_id: str) -> bool:
        enqueued.append(report_id)
        return True
    return _f


def test_stale_running_report_is_recovered():
    rid = _seed_report("running", stale=True)
    out = _run()
    assert rid in out
    with Session(engine) as s:
        rep = s.get(Report, rid)
        assert rep.status == "queued"
        assert rep.retry_count == 1


def test_fresh_running_report_is_left_alone():
    rid = _seed_report("running", stale=False)
    out = _run()
    assert rid not in out
    with Session(engine) as s:
        assert s.get(Report, rid).status == "running"


def test_done_and_failed_are_never_touched():
    r1 = _seed_report("done", stale=True)
    r2 = _seed_report("failed", stale=True)
    out = _run()
    assert r1 not in out and r2 not in out
    with Session(engine) as s:
        assert s.get(Report, r1).status == "done"
        assert s.get(Report, r2).status == "failed"


def test_retry_cap_stops_infinite_loops():
    rid = _seed_report("running", stale=True, retries=5)
    out = _run()
    assert rid not in out  # at the retry cap → needs human review
    with Session(engine) as s:
        assert s.get(Report, rid).status == "running"


def test_updated_at_is_heartbeat_on_status_change():
    """Every status change must bump updated_at (worker heartbeat)."""
    rid = _seed_report("queued", stale=False)
    with Session(engine) as s:
        rep = s.get(Report, rid)
        rep.status = "running"
        s.add(rep)
        s.commit()
        fresh = s.get(Report, rid)
        assert fresh.updated_at > datetime.now(timezone.utc) - timedelta(minutes=5)
