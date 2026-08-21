"""G1 — funnel tracking acceptance tests.

Hermetic: test DB (conftest), anonymous /api/track, admin funnel dashboard.
Proves the event-recording beacon + the conversion-funnel computation.
"""
import uuid

from fastapi.testclient import TestClient

from app.db import engine
from app.main import app as main_app
from app.models import FunnelEvent
from sqlmodel import Session, select


def _mk_session():
    s = Session(engine)
    return s


def _track(c, event, sid=""):
    return c.post("/api/track", json={"event": event, "session_id": sid or ("s" + uuid.uuid4().hex[:8])})


def _admin_cookie(c: TestClient) -> dict:
    from app.main import _admin_cookie_value
    return {"chart_admin": _admin_cookie_value()}


def test_track_records_event():
    c = TestClient(main_app)
    r = _track(c, "birth_form_submit")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    with _mk_session() as s:
        ev = s.exec(select(FunnelEvent).where(FunnelEvent.event == "birth_form_submit").order_by(FunnelEvent.id.desc())).first()
        assert ev is not None and ev.event == "birth_form_submit"
        assert ev.session_id, "session_id must be stored"


def test_track_rejects_unknown_event():
    c = TestClient(main_app)
    r = _track(c, "totally_not_a_real_event")
    assert r.status_code == 400, r.text


def test_track_requires_event_field():
    c = TestClient(main_app)
    r = c.post("/api/track", json={"session_id": "s_abc"})
    assert r.status_code == 422, r.text  # pydantic requires event


def test_funnel_dashboard_computes_conversion():
    c = TestClient(main_app)
    # clear funnel_events so the exact-count assertion isn't polluted by other tests
    with _mk_session() as s:
        for ev in s.exec(select(FunnelEvent)).all():
            s.delete(ev)
        s.commit()
    # seed a realistic funnel (descending counts)
    seed = [("page_view_landing", 100), ("birth_form_start", 60), ("birth_form_submit", 40),
            ("chart_created", 30), ("signup_started", 20), ("checkout_started", 10),
            ("payment_success", 5)]
    with _mk_session() as s:
        for ev, n in seed:
            for _ in range(n):
                s.add(FunnelEvent(event=ev, session_id="s_seed"))
        s.commit()
    r = c.get("/api/admin/funnel", cookies=_admin_cookie(c))
    assert r.status_code == 200, r.text
    d = r.json()
    steps = d["steps"]
    assert [st["count"] for st in steps] == [100, 60, 40, 30, 20, 10, 5], "counts must match seed"
    # conversion vs prev: second step 60/100=0.6, chart 30/40=0.75, etc.
    conv = [st["conversion_vs_prev"] for st in steps]
    assert conv[1] == 0.6, f"60/100 -> {conv[1]}"
    assert conv[3] == 0.75, f"30/40 -> {conv[3]}"
    assert conv[6] == 0.5, f"5/10 -> {conv[6]}"
    assert conv[0] is None, "first step has no previous"
    assert d["total_events"] >= 265


def test_track_is_anonymous_no_auth():
    c = TestClient(main_app)
    r = _track(c, "explore_card_click")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
