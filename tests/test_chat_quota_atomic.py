"""A8 (audit r4): chat quota is ATOMIC and per-ACCOUNT.

Regression: count-then-act let concurrent requests overrun the daily limit
(check→LLM→save). Now a Redis INCR+TTL claim happens BEFORE the LLM call, so
N concurrent requests with a limit of 3 produce exactly 3 successes."""
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.main as main_mod
from app.db import engine
from app.models import Order
from app.secret_store import set_secret


@pytest.fixture()
def chat_ctx(monkeypatch):
    """Chart + paid GOLD order + fake LLM answer; quota limit forced to 3.

    The generic chat rate-limiter (20 req/60s per IP, shared Redis bucket) is
    neutralized so test repetition can't cause false 429s (debugged r4 A8)."""
    monkeypatch.setattr(main_mod, "chat_answer",
                        lambda *a, **k: {"answer": "پاسخ تستی", "ok": True,
                                         "intent": "career", "domains": [], "tokens": 10})
    monkeypatch.setattr(main_mod, "_rate_limit", lambda *a, **k: True)
    set_secret("chat_daily_limit_gold", "3")
    c = TestClient(main_mod.app)
    r = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    d = r.json()
    cid, tok = d["chart_id"], d["access_token"]
    with Session(engine) as s:
        s.add(Order(chart_id=cid, plan_key="gold", status="paid", amount_rial=6_990_000))
        s.commit()
    yield c, cid, tok
    # reset the secret so other tests see the default
    set_secret("chat_daily_limit_gold", "")


def _cookies(cid: str, tok: str) -> dict:
    return {"chart_access": json.dumps({cid: tok})}


def test_quota_exhausted_returns_429(chat_ctx):
    c, cid, tok = chat_ctx
    ck = _cookies(cid, tok)
    for _ in range(3):
        r = c.post("/api/chat", data={"chart_id": cid, "question": "سوال"},
                   cookies=ck)
        assert r.status_code == 200, r.text
    r = c.post("/api/chat", data={"chart_id": cid, "question": "سوال چهارم"},
               cookies=ck)
    assert r.status_code == 429


def test_concurrent_claims_exactly_limit_successes(chat_ctx):
    c, cid, tok = chat_ctx
    ck = _cookies(cid, tok)
    results = []
    barrier = threading.Barrier(10)
    lock = threading.Lock()

    def worker():
        tc = TestClient(main_mod.app)  # TestClient is not thread-safe
        try:
            barrier.wait()
            r = tc.post("/api/chat", data={"chart_id": cid, "question": "س"},
                        cookies=ck)
            with lock:
                results.append(r.status_code)
        except Exception as e:  # noqa: BLE001
            with lock:
                results.append(f"ERR:{type(e).__name__}:{e}")

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ok = results.count(200)
    assert ok == 3, f"expected exactly 3 successes, got {results}"
    assert results.count(429) == 7


def test_account_scope_shared_across_charts(chat_ctx):
    """Two charts of the SAME bot account (order.chat_id) share one daily pool.

    Anonymous browsers fall back to per-chart keys by design; the per-ACCOUNT
    promise is tested through the bot identity path (b:telegram:<chat_id>)."""
    c, cid, tok = chat_ctx
    import uuid as _uuid
    pool = f"t-{_uuid.uuid4().hex[:10]}"  # unique Redis pool key per run
    r = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "2",
        "hour": "7", "minute": "0", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    d2 = r.json()
    cid2, tok2 = d2["chart_id"], d2["access_token"]
    with Session(engine) as s:
        # both orders belong to the same account pool → one shared counter
        s.add(Order(chart_id=cid2, plan_key="gold", status="paid",
                    amount_rial=6_990_000, chat_id=pool, platform="telegram"))
        s.commit()
        from app.models import Order as O
        from sqlmodel import select as _select
        o1 = s.exec(_select(O).where(O.chart_id == cid)).first()
        o1.chat_id = pool
        o1.platform = "telegram"
        s.add(o1)
        s.commit()
    ck = {"chart_access": json.dumps({cid: tok, cid2: tok2})}
    for _ in range(3):  # 3 questions on chart 1
        assert c.post("/api/chat", data={"chart_id": cid, "question": "س"},
                      cookies=ck).status_code == 200
    # chart 2 is already exhausted by the same account pool
    r = c.post("/api/chat", data={"chart_id": cid2, "question": "س"},
               cookies=ck)
    assert r.status_code == 429
