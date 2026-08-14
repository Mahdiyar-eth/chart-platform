"""H0.2 (HARDENING): account deletion must fully cascade — including RAG
embeddings (report_chunks). Before the fix, deleting an account whose report
was RAG-indexed raised IntegrityError (500) — reproduced on the test DB."""
from __future__ import annotations

import os
import uuid

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.auth import _user_cookie_value  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    BirthProfile, Chart, ChatMessage, LLMRun, Order, ReferralCode,
    ReferralEvent, Report, ReportChunk, Subscription, User, WeeklyReflection,
    WithdrawalRequest,
)

SUF = uuid.uuid4().hex[:8]


def _seed() -> str:
    """Full graph: user + profile + chart + RAG-indexed report + LLM run +
    chat msg + subscription + order + weekly reflection + withdrawal +
    referral pair. Returns the user id."""
    with Session(engine) as s:
        u = User(phone=f"+98h02{SUF}")
        s.add(u)
        s.flush()
        p = BirthProfile(user_id=u.id, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        s.add(p)
        s.flush()
        c = Chart(profile_id=p.id, chart_json={"birth": {"x": 1}})
        s.add(c)
        s.flush()
        rep = Report(chart_id=c.id, status="ready", r2_key=f"r2-{SUF}")
        s.add(rep)
        s.flush()
        # the RAG embedding row — the one that used to break deletion
        s.add(ReportChunk(report_id=rep.id, chunk_index=0, section_key="intro",
                          text="متن نمونه", embedding=[0.01] * 384))
        s.add(LLMRun(report_id=rep.id, provider="test", model="m",
                     prompt_tokens=1, completion_tokens=1, cost_usd=0.001, ok=True))
        s.add(ChatMessage(chart_id=c.id, role="user", content="hi"))
        s.add(Subscription(chart_id=c.id, plan="weekly", status="active",
                           ends_at="2099-01-01T00:00:00"))
        s.add(Order(chart_id=c.id, plan_key="gold", price_toman=100,
                    status="paid", amount_rial=10000))
        s.add(WeeklyReflection(chart_id=c.id, week_start="2026-01-01",
                               content="x", status="ready"))
        s.add(WithdrawalRequest(user_id=u.id, amount_rial=1000, status="pending"))
        s.add(ReferralCode(user_id=u.id, code="c" + SUF))
        s.add(ReferralEvent(referrer_user_id=u.id, code="c" + SUF,
                            reward_rial=500, status="pending"))
        s.commit()
        return u.id


def test_account_delete_with_rag_indexed_report() -> None:
    uid = _seed()
    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    from app.security import new_csrf_token  # noqa: PLC0415
    token = new_csrf_token()
    c.cookies.set("csrf_token", token)
    r = c.post("/account/delete", data={"csrf_token": token})
    assert r.status_code in (200, 303), r.text[:300]
    with Session(engine) as s:
        my_charts = [c.id for c in s.exec(select(Chart).where(Chart.profile_id.in_(
            [p.id for p in s.exec(select(BirthProfile).where(BirthProfile.user_id == uid)).all()]
        ))).all()]
        remaining = [
            len(s.exec(select(ReportChunk).where(ReportChunk.report_id.in_(
                [rep.id for rep in s.exec(select(Report).where(Report.chart_id.in_(my_charts))).all()]
            ))).all()),
            len(s.exec(select(LLMRun).where(LLMRun.report_id.in_(
                [rep.id for rep in s.exec(select(Report).where(Report.chart_id.in_(my_charts))).all()]
            ))).all()),
            len(s.exec(select(WithdrawalRequest).where(WithdrawalRequest.user_id == uid)).all()),
            len(s.exec(select(Report).where(Report.chart_id.in_(my_charts))).all()),
            len(s.exec(select(ChatMessage).where(ChatMessage.chart_id.in_(my_charts))).all()),
        ]
    assert sum(remaining) == 0, f"orphans left: {remaining}"
