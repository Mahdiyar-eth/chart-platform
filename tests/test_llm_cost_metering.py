"""H1.3 (HARDENING): LLM cost metering — llm_runs carries user_id + kind;
/api/admin/llm-cost returns rich 24h/7d/30d breakdowns (model/user/fail)."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LLMRun, User, ChatMessage, BirthProfile  # noqa: E402

SUF = uuid.uuid4().hex[:8]


def _seed_runs() -> tuple[str, str]:
    """Two users; three runs: report (u1), chat (u1), chat (u2, failed)."""
    with Session(engine) as s:
        # F-P1: this test reads GLOBAL 7d aggregates (fail_rate, top_users),
        # so any LLMRun left behind by earlier/heavier tests (report QA runs,
        # metering seeds from interrupted runs…) breaks the assertions.
        # Purge ALL runs before seeding — this file is the only one asserting
        # global aggregates, and every run here is self-seeded.
        for r in s.exec(select(LLMRun)).all():
            s.delete(r)
        s.commit()
        u1 = User(phone=f"+98h13a{SUF}")
        u2 = User(phone=f"+98h13b{SUF}")
        s.add(u1)
        s.add(u2)
        s.flush()
        old = datetime.now(timezone.utc) - timedelta(days=10)
        s.add(LLMRun(user_id=u1.id, kind="report", provider="go", model="deepseek-v4-pro",
                     prompt_tokens=100, completion_tokens=50, cost_usd=5.0, ok=True,
                     created_at=datetime.now(timezone.utc)))
        s.add(LLMRun(user_id=u1.id, kind="chat", provider="go", model="deepseek-v4-flash",
                     prompt_tokens=10, completion_tokens=5, cost_usd=0.001, ok=True,
                     created_at=datetime.now(timezone.utc)))
        s.add(LLMRun(user_id=u2.id, kind="chat", provider="deepseek", model="deepseek-v4-flash",
                     prompt_tokens=20, completion_tokens=30, cost_usd=0.002, ok=False,
                     created_at=datetime.now(timezone.utc)))
        # old run (10 days ago) — must only appear in the 30d panel
        s.add(LLMRun(user_id=u1.id, kind="transit", provider="go", model="deepseek-v4-flash",
                     prompt_tokens=5, completion_tokens=5, cost_usd=0.0005, ok=True,
                     created_at=old))
        s.commit()
        return u1.id, u2.id


def _admin_client() -> TestClient:
    from app.main import _ADMIN_COOKIE, _admin_cookie_value
    c = TestClient(app)
    c.cookies.set(_ADMIN_COOKIE, _admin_cookie_value())
    return c


def test_llm_cost_endpoint_requires_admin():
    c = TestClient(app)
    r = c.get("/api/admin/llm-cost")
    assert r.status_code in (403, 401)


def test_llm_cost_breakdowns_are_consistent():
    u1, u2 = _seed_runs()
    r = _admin_client().get("/api/admin/llm-cost")
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"24h", "7d", "30d"}
    # 7d: at least our three fresh runs; 30d ≥ 7d (older runs may exist from
    # other tests — assertions are relative, seeded runs use fresh timestamps)
    assert j["7d"]["runs"] >= 3
    assert j["7d"]["cost_usd"] >= 5.001
    assert j["30d"]["runs"] >= j["7d"]["runs"]
    # kinds tracked
    assert j["7d"]["by_kind"].get("chat", 0) >= 2
    assert j["7d"]["by_kind"].get("report", 0) >= 1
    # fail rate: at least one failed run among ≥3
    assert j["7d"]["fail_rate"] > 0
    # top users sorted desc — u1 (5.001 fresh) must rank #1
    tu = j["7d"]["top_users"]
    assert tu[0]["user_id"] == u1 and tu[0]["cost_usd"] >= 5.001
    assert all(tu[i]["cost_usd"] >= tu[i + 1]["cost_usd"] for i in range(len(tu) - 1))
    # per-model rollup — flash (chat) present
    assert j["7d"]["by_model"].get("deepseek-v4-flash", 0) >= 0.003
    # teardown — remove seeded runs so repeated runs stay deterministic
    with Session(engine) as s:
        for r in s.exec(select(LLMRun).where(
                LLMRun.user_id.in_([u1, u2]))).all():
            s.delete(r)
        s.commit()


def test_chat_answer_writes_llm_run(monkeypatch):
    """F-P1: the real /api/chat path must land a kind='chat' llm_run
    (user-scoped) — chat_answer itself is pure; metering lives in the
    route (main.py), so we drive the route with a stubbed answer."""
    import app.main as main
    from app.models import Chart, Order

    with Session(engine) as s:
        u = User(phone=f"+98h13c{SUF}")
        s.add(u); s.commit()
        p = BirthProfile(user_id=u.id, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        s.add(p); s.commit()
        ch = Chart(chart_json={"planets": {}, "angles": {}, "birth": {}},
                   profile_id=p.id)
        s.add(ch); s.commit()
        o = Order(chart_id=ch.id, plan_key="gold", amount_rial=500_000,
                  status="paid", authority=f"auth-{uuid.uuid4().hex[:12]}")
        s.add(o); s.commit()
        ids = {"uid": u.id, "cid": ch.id, "oid": o.id, "pid": p.id}

    def _stub_answer(*a, **k):
        return {"answer": "پاسخ تست", "intent": "general", "domains": [],
                "provider": "go", "model": "deepseek-v4-flash",
                "cost_usd": 0.0001, "tokens": 10, "ok": True}

    monkeypatch.setattr(main, "chat_answer", _stub_answer)
    monkeypatch.setattr(main, "_rate_limit", lambda *a, **k: True)
    c = TestClient(main.app)
    from app.auth import _user_cookie_value
    c.cookies.set("chart_user", _user_cookie_value(ids["uid"]))
    r = c.post("/api/chat", data={"chart_id": ids["cid"], "question": "سلام"})
    assert r.status_code == 200
    with Session(engine) as s:
        runs = s.exec(select(LLMRun).where(LLMRun.kind == "chat",
                                           LLMRun.user_id == ids["uid"])).all()
        assert runs, "chat runs must be recorded by the route"
        assert runs[0].model == "deepseek-v4-flash" and runs[0].cost_usd > 0
        # teardown
        for m in s.exec(select(ChatMessage).where(ChatMessage.chart_id == ids["cid"])).all():
            s.delete(m)
        s.flush()
        o2 = s.get(Order, ids["oid"]); s.delete(o2); s.commit()
        s.delete(s.get(Chart, ch.id)); s.commit()
        s.delete(s.get(BirthProfile, ids["pid"])); s.commit()
        s.delete(s.get(User, ids["uid"])); s.commit()
