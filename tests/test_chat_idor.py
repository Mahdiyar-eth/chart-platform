"""Chat IDOR tests — audit P0 (round 3): chat page/history/access/POST must NOT be
reachable by bare UUID alone; ownership (user or capability token) is required."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app


def _create_chart(client: TestClient) -> tuple[str, str]:
    r = client.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["chart_id"], d.get("access_token", "")


def test_chat_page_bare_uuid_redirects():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/chat/{cid}", follow_redirects=False)
    assert r.status_code == 303


def test_chat_page_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/chat/{cid}?t={tok}")
    assert r.status_code == 200


def test_chat_history_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/api/chat/history/{cid}")
    assert r.status_code == 403


def test_chat_history_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/api/chat/history/{cid}?t={tok}")
    assert r.status_code == 200
    assert r.json() == {"messages": []}


def test_chat_access_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/api/chat/access/{cid}")
    assert r.status_code == 403


def test_chat_access_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/api/chat/access/{cid}?t={tok}")
    assert r.status_code == 200
    assert r.json()["allowed"] is False  # no paid order yet


def test_chat_post_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).post("/api/chat", data={"chart_id": cid, "question": "سلام"})
    assert r.status_code == 403


def test_chat_post_owner_without_plan_403():
    # owner with token but no paid plan → 403 (gold/monthly required), not a leak
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).post(f"/api/chat?t={tok}", data={"chart_id": cid, "question": "سلام"})
    assert r.status_code == 403
