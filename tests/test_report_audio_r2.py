"""C1 (audit r4): report audio served from R2 via 30-min presigned URL.

Regression: the endpoint returned a FileResponse straight from /tmp (ephemeral
disk, no cache sharing). Now: R2 cache hit → presigned redirect (no TTS cost);
miss → generate → upload → presigned → temp file deleted.
"""
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlmodel import Session

import app.main as m
from app.main import app as main_app
from app.db import engine
from app.models import Order, Report


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    }).json()
    return d["chart_id"], d["access_token"]


def _done_report(s, cid):
    rep = Report(chart_id=cid, status="done", plan_key="gold",
                 sections={"intro": {"title": "مقدمه", "content": "متن نمونه"}})
    s.add(rep)
    s.commit()
    s.refresh(rep)
    o = Order(chart_id=cid, plan_key="gold", status="paid", amount_rial=99000,
              authority="AU" + uuid.uuid4().hex[:8], ref_id="REF1")
    s.add(o)
    s.commit()
    return rep.id


def test_audio_served_via_presigned_url(monkeypatch):
    """Miss path: upload + presigned redirect, temp file cleaned up."""
    monkeypatch.setattr("app.storage.upload_audio", lambda rid, path: f"chart-audio/{rid}.mp3")
    monkeypatch.setattr("app.storage.presigned_url", lambda key: f"https://r2.example/{key}?sig=1")
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    ck = {"chart_access": __import__("json").dumps({cid: tok})}
    with Session(engine) as s:
        rid = _done_report(s, cid)
    r = c.get(f"/api/reports/{rid}/audio", cookies=ck, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("https://r2.example/chart-audio/")
    assert "sig=1" in r.headers["location"]


def test_audio_cache_hit_skips_generation(monkeypatch):
    """Cache hit: presigned URL exists → redirect WITHOUT calling upload."""
    monkeypatch.setattr("app.storage.presigned_url", lambda key: f"https://r2.example/{key}?sig=1")
    calls = {"n": 0}

    def _upload(*a, **k):
        calls["n"] += 1
        return "chart-audio/x.mp3"
    monkeypatch.setattr("app.storage.upload_audio", _upload)
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    ck = {"chart_access": __import__("json").dumps({cid: tok})}
    with Session(engine) as s:
        rid = _done_report(s, cid)
    r = c.get(f"/api/reports/{rid}/audio", cookies=ck, follow_redirects=False)
    assert r.status_code == 302
    assert calls["n"] == 0, "cache hit must not regenerate/upload"


def test_audio_requires_paid_ownership():
    c = TestClient(main_app)
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        rid = _done_report(s, cid)
    # no cookie → not the owner → 403
    r = c.get(f"/api/reports/{rid}/audio", follow_redirects=False)
    assert r.status_code == 403
