"""A3-A5 (audit r4): transit / synastry / order endpoints must enforce the SAME
ownership model as chart/report/chat — bare/foreign UUID → 403, capability → OK.

Regression for: /api/charts/{id}/transits, /transit/{id},
/api/synastry/full, /api/synastry/access, POST /api/orders."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.db import engine


def _create_chart(client: TestClient) -> tuple[str, str]:
    r = client.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return d["chart_id"], d.get("access_token", "")


# ---------- A3: transit ----------

def test_transit_api_bare_uuid_403():
    c = TestClient(app)
    cid, _ = _create_chart(c)
    assert TestClient(app).get(f"/api/charts/{cid}/transits").status_code == 403


def test_transit_api_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    r = TestClient(app).get(f"/api/charts/{cid}/transits?t={tok}")
    assert r.status_code == 200
    assert "events" in r.json()


def test_transit_page_bare_uuid_403():
    c = TestClient(app)
    cid, _ = _create_chart(c)
    assert TestClient(app).get(f"/transit/{cid}").status_code == 403


def test_transit_page_with_token_200():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    assert TestClient(app).get(f"/transit/{cid}?t={tok}").status_code == 200


# ---------- A4: synastry ----------

def test_synastry_full_foreign_charts_403():
    c = TestClient(app)
    ca, _ = _create_chart(c)
    cb, _ = _create_chart(c)
    # a FRESH client (no cookies) trying to read the pair → 403 ownership
    r = TestClient(app).post("/api/synastry/full", data={"chart_a": ca, "chart_b": cb})
    assert r.status_code == 403


def test_synastry_access_foreign_403():
    c = TestClient(app)
    ca, _ = _create_chart(c)
    cb, _ = _create_chart(c)
    r = TestClient(app).get(f"/api/synastry/access?chart_a={ca}&chart_b={cb}")
    assert r.status_code == 403


def _cap_cookie(cid: str, tok: str) -> dict:
    """Cookie jar entry: chart_access={chart_id: token}."""
    import json
    return {"chart_access": json.dumps({cid: tok})}


def test_synastry_full_owned_but_unpaid_403():
    c = TestClient(app)
    ca, tok = _create_chart(c)
    cb, _ = _create_chart(c)
    c.cookies.update(_cap_cookie(ca, tok))
    r = c.post("/api/synastry/full", data={"chart_a": ca, "chart_b": cb})
    # owned pair, but no paid order → still 403 (purchase required)
    assert r.status_code == 403


# ---------- A5: order creation ----------

def test_order_foreign_chart_403():
    c = TestClient(app)
    cid, _ = _create_chart(c)
    r = TestClient(app).post("/api/orders", data={"plan_key": "credit6", "chart_id": cid})
    assert r.status_code == 403


def test_order_foreign_secondary_chart_403():
    c = TestClient(app)
    cid, _ = _create_chart(c)
    # secondary chart owned by the caller, primary foreign → 403
    r = c.post("/api/orders", data={"plan_key": "credit12", "chart_id": cid,
                                    "secondary_chart_id": cid})
    assert r.status_code == 403


def test_order_owned_chart_reaches_payment():
    c = TestClient(app)
    cid, tok = _create_chart(c)
    c.cookies.update(_cap_cookie(cid, tok))
    # R14-D2: credit packs require login — authenticate via user cookie
    from app.auth import _user_cookie_value
    from app.models import User as _U
    import uuid as _uuid2
    from sqlmodel import Session as _Session
    with _Session(engine) as _s:
        _uid = "u" + _uuid2.uuid4().hex[:10]
        _s.add(_U(id=_uid, phone=_uid + "@r4", credits=0)); _s.commit()
        c.cookies.update({"chart_user": _user_cookie_value(_uid)})
    r = c.post("/api/orders", data={"plan_key": "credit6", "chart_id": cid})
    assert r.status_code == 200, r.text
    assert "payment_url" in r.json()
