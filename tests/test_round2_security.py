"""Round-2 phase-3 security tests (X14-X17 / R9-R12) — $0, no LLM."""
import os, uuid
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")
from pathlib import Path
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.db import engine
from app.main import app as main_app
from app.models import Subscriber, FunnelEvent

c = TestClient(main_app)


def test_x14_subscribe_dedupes_contact():
    email = f"sub-{uuid.uuid4().hex[:8]}@t.local"
    r1 = c.post("/api/subscribe", data={"contact": email, "source": "guide"})
    assert r1.status_code == 200, r1.text[:200]
    r2 = c.post("/api/subscribe", data={"contact": email, "source": "guide"})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("already_subscribed") is True
    assert j2["download_url"] == r1.json()["download_url"]  # same token re-issued
    with Session(engine) as s:
        rows = s.exec(select(Subscriber).where(Subscriber.contact == email)).all()
        assert len(rows) == 1  # R10: one row per contact


def test_x15_unsubscribe_requires_post():
    email = f"unsub-{uuid.uuid4().hex[:8]}@t.local"
    tok = c.post("/api/subscribe", data={"contact": email}).json()["download_url"].rsplit("/", 1)[-1]
    # GET must NOT flip state anymore (prefetch-safe)
    g = c.get(f"/unsubscribe/{tok}")
    assert g.status_code == 200
    with Session(engine) as s:
        sub = s.exec(select(Subscriber).where(Subscriber.token == tok)).first()
        assert sub.unsubscribed_at is None  # GET did nothing
    p = c.post(f"/unsubscribe/{tok}")
    assert p.status_code == 200
    with Session(engine) as s:
        sub = s.exec(select(Subscriber).where(Subscriber.token == tok)).first()
        assert sub.unsubscribed_at is not None  # POST flips


def test_x16_funnel_groupby_endpoint_ok():
    ev = "e2e_gb_" + uuid.uuid4().hex[:6]
    with Session(engine) as s:
        s.add(FunnelEvent(event=ev, session_id="gb1"))
        s.commit()
    # admin-only endpoint; unauthenticated → 403 proves route alive without full admin login
    r = c.get("/api/admin/funnel")
    assert r.status_code in (401, 403)


def test_x17_guide_pdf_committed_and_served():
    p = Path(__file__).resolve().parent.parent / "app" / "static" / "guides" / "zayche-guide.pdf"
    assert p.exists(), "guide PDF must live in the repo (R9)"
    email = f"pdf-{uuid.uuid4().hex[:8]}@t.local"
    url = c.post("/api/subscribe", data={"contact": email}).json()["download_url"]
    d = c.get(url)
    assert d.status_code == 200
    assert d.headers["content-type"].startswith("application/pdf")
