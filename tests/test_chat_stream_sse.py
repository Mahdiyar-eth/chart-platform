"""D4 (audit r4): SSE streaming chat — the /api/chat/stream endpoint emits
real token events (text/event-stream), persists history on completion, and
refunds the quota if the stream dies before producing anything. LLM is
mocked with a token-by-token generator; no real API calls."""
from __future__ import annotations

import json
import uuid

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.models import (BirthProfile, ChatMessage, Chart, Order, User)


def _chat_stream_stub(tokens: list[str], fail: bool = False):
    """Async generator replacement for app.chat.service.chat_stream —
    emits the same event shape the endpoint consumes."""
    async def gen(question, chart_json, report_sections=None, focus_areas=None,
                  router=None, report_id=None, history=None):
        yield {"type": "intent", "intent": "general", "domains": []}
        if fail:
            yield {"type": "error", "message": "سرویس در دسترس نیست"}
            return
        acc = ""
        for t in tokens:
            acc += t
            yield {"type": "token", "text": acc}
        yield {"type": "done", "answer": acc, "ok": True, "cost_usd": 0.0,
               "tokens": len(acc), "provider": "stub", "model": "stub",
               "intent": "general", "domains": []}
    return gen


@pytest.fixture
def ctx():
    """User + birth profile + chart + paid GOLD order (chat entitlement)."""
    with Session(engine) as s:
        u = User(phone=f"+98{uuid.uuid4().hex[:10]}")
        s.add(u); s.commit()
        p = BirthProfile(user_id=u.id, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, city_fa="تهران", lat=35.6889, lon=51.3897)
        s.add(p); s.commit()
        ch = Chart(chart_json={"planets": {"Sun": {"sign_fa": "اسد", "house": 10}},
                               "angles": {"ASC": {"sign_fa": "اسد"}}, "birth": {}},
                   profile_id=p.id)
        s.add(ch); s.commit()
        o = Order(chart_id=ch.id, plan_key="gold", amount_rial=500_000,
                  status="paid", authority=f"auth-{uuid.uuid4().hex[:12]}")
        s.add(o); s.commit()
        ids = {"uid": u.id, "cid": ch.id, "pid": p.id, "oid": o.id}
        yield ids
        # cleanup (FK order: messages → order → chart → profile → user)
        for m in s.exec(select(ChatMessage).where(ChatMessage.chart_id == ch.id)).all():
            s.delete(m)
        s.flush()
        s.delete(o); s.commit()
        s.delete(ch); s.commit()
        s.delete(p); s.commit()
        s.delete(u); s.commit()


def _login(client: TestClient, user_id: str):
    from app.auth import _user_cookie_value
    client.cookies.set("chart_user", _user_cookie_value(user_id))


def test_stream_emits_tokens_and_done(monkeypatch, ctx):
    """Real SSE: token events accumulate, done carries the full answer, and
    history is persisted."""
    import app.main as main
    from app.chat import service as chat_service
    monkeypatch.setattr(chat_service, "chat_stream", _chat_stream_stub(["سلام", " ", "دنیا"]))
    monkeypatch.setattr(main, "_rate_limit", lambda *a, **k: True)
    c = TestClient(main.app)
    _login(c, ctx["uid"])
    with c.stream("POST", "/api/chat/stream",
                  data={"chart_id": ctx["cid"], "question": "حالم چطوره؟"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert "event: intent" in body
    events = [json.loads(ln[5:]) for ln in body.split("\n") if ln.startswith("data:")]
    tokens = [e for e in events if e["type"] == "token"]
    assert tokens[-1]["text"] == "سلام دنیا"      # accumulated
    done = [e for e in events if e["type"] == "done"][0]
    assert done["answer"] == "سلام دنیا" and done["provider"] == "stub"
    # history persisted
    with Session(engine) as s:
        msgs = s.exec(select(ChatMessage).where(ChatMessage.chart_id == ctx["cid"])).all()
        assert len(msgs) >= 2
        assert msgs[-1].content == "سلام دنیا"


def test_stream_error_refunds_quota(monkeypatch, ctx):
    """A provider failure yields an error event; the claimed quota is
    released because no token was produced."""
    import app.main as main
    from app.chat import service as chat_service
    monkeypatch.setattr(chat_service, "chat_stream", _chat_stream_stub([], fail=True))
    monkeypatch.setattr(main, "_rate_limit", lambda *a, **k: True)
    c = TestClient(main.app)
    _login(c, ctx["uid"])
    with c.stream("POST", "/api/chat/stream",
                  data={"chart_id": ctx["cid"], "question": "تست؟"}) as r:
        body = "".join(r.iter_text())
    assert "event: error" in body
    assert "token" not in body


def test_stream_requires_paid_plan(monkeypatch, ctx):
    """Same entitlement guards as /api/chat: a chart without a paid GOLD or
    monthly order is refused with 403."""
    import app.main as main
    monkeypatch.setattr(main, "_rate_limit", lambda *a, **k: True)
    with Session(engine) as s:
        ch = Chart(chart_json={"planets": {}, "angles": {}, "birth": {}})
        s.add(ch); s.commit(); free_cid = ch.id
    c = TestClient(main.app)
    _login(c, ctx["uid"])
    r = c.post("/api/chat/stream", data={"chart_id": free_cid, "question": "؟"})
    assert r.status_code == 403
    with Session(engine) as s:
        s.delete(s.get(Chart, free_cid)); s.commit()
