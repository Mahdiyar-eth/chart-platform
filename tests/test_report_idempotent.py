"""A7 (audit r4): report generation is idempotent — repeated POSTs must not
enqueue multiple LLM jobs. queued/processing → same report; done → same unless
?regenerate=1; explicit regenerate → new report."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.models import Order
from app.db import engine
from sqlmodel import Session


def _chart_with_paid_order() -> tuple[TestClient, str, str]:
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    cid = r.json()["chart_id"]
    tok = r.json()["access_token"]
    with Session(engine) as s:
        s.add(Order(chart_id=cid, plan_key="full", status="paid", amount_rial=3_490_000))
        s.commit()
    return c, cid, tok


def _cookies(cid: str, tok: str) -> dict:
    import json
    return {"chart_access": json.dumps({cid: tok})}


def test_double_post_returns_same_report():
    c, cid, tok = _chart_with_paid_order()
    ck = _cookies(cid, tok)
    c.cookies.update(ck)
    r1 = c.post(f"/api/charts/{cid}/report")
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    r2 = c.post(f"/api/charts/{cid}/report")
    d2 = r2.json()
    assert d2["report_id"] == d1["report_id"]
    assert d2.get("existing") is True


def test_explicit_regenerate_creates_new_report():
    c, cid, tok = _chart_with_paid_order()
    ck = _cookies(cid, tok)
    c.cookies.update(ck)
    d1 = c.post(f"/api/charts/{cid}/report").json()
    d2 = c.post(f"/api/charts/{cid}/report?regenerate=1").json()
    assert d2["report_id"] != d1["report_id"]


def test_failed_report_requeued_not_duplicated():
    c, cid, tok = _chart_with_paid_order()
    ck = _cookies(cid, tok)
    c.cookies.update(ck)
    d1 = c.post(f"/api/charts/{cid}/report").json()
    # simulate worker failure
    with Session(engine) as s:
        from app.models import Report
        rep = s.get(Report, d1["report_id"])
        rep.status = "failed"
        rep.error = "worker crashed"
        s.add(rep)
        s.commit()
    d2 = c.post(f"/api/charts/{cid}/report").json()
    assert d2["report_id"] == d1["report_id"]  # re-queued, NOT a new row
    assert d2["status"] in ("queued", "failed")
