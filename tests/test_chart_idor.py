"""Endpoint-level IDOR tests — audit P0: chart page/preview/transit/report-status
must NOT be reachable by bare UUID alone (must be 303/403 without ownership)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app


def _create_chart(client: TestClient) -> tuple[str, str]:
    """Create a real chart via the public API; return (chart_id, access_token)."""
    r = client.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["chart_id"], d.get("access_token", "")


def test_chart_page_bare_uuid_redirects():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    # a FRESH client (no cookie) with bare UUID → redirected, not 200
    c2 = TestClient(app)
    r = c2.get(f"/chart/{cid}", follow_redirects=False)
    assert r.status_code == 303


def test_chart_page_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/chart/{cid}?t={tok}")
    assert r.status_code == 200


def test_preview_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/api/charts/{cid}/preview")
    assert r.status_code == 403


def test_preview_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/api/charts/{cid}/preview?t={tok}")
    assert r.status_code == 200


def test_transit_svg_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/api/charts/{cid}/transit-year.svg")
    assert r.status_code == 403


def test_report_status_bare_uuid_403():
    c = TestClient(app)
    cid, _tok = _create_chart(c)
    r = TestClient(app).get(f"/api/charts/{cid}/report")
    assert r.status_code == 403
