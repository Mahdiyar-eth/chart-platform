"""One name for one state.

app/models.py:208 documents Report.status as ``queued | running | done |
failed``, and the worker writes ``running`` (worker.py:321). But the
idempotency guard in POST /api/charts/{id}/report checked for ``processing``,
a status nothing ever writes. The consequences were not cosmetic:

  * A report actively being generated matched none of the guard's branches, so
    the handler fell through and created a *second* Report row and enqueued a
    *second* full 13-section LLM job. The "try again" button the stalled-state
    UI offers did exactly this — doubling the spend on a report that was
    already running fine.
  * reports.html mapped `processing` to Persian and therefore fell through to
    the raw English string `running` for the state users actually see.
  * account.html printed `{{ r.status }}` unmapped in every state.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app as main_app
from app.models import Report

ROOT = Path(__file__).resolve().parent.parent


def _phone() -> str:
    return "0912" + str(uuid.uuid4().int)[:8]


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def test_no_source_file_writes_the_phantom_processing_status():
    """Nothing writes it, so nothing may branch on it."""
    offenders = []
    for py in (ROOT / "app").rglob("*.py"):
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'["\']processing["\']', line) and "status" in line:
                offenders.append(f"{py.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "report status vocabulary is queued|running|done|degraded|failed; "
        "'processing' is written by nothing:\n" + "\n".join(offenders)
    )


def test_running_report_is_not_duplicated_by_a_retry(monkeypatch):
    """The retry button must not start a second paid job."""
    c = TestClient(main_app, base_url="https://testserver")
    cid, tok = _mk_chart(c)

    from app import security as _sec
    _sec._RATE_LIMITS.pop("otp:testclient", None)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    phone = _phone()
    dev = c.post("/api/auth/otp/request", data={"phone": phone}).json()["dev_code"]
    c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev})
    uid = c.get("/api/auth/me").json()["user"]["id"]

    # entitle the user, then put a report into the state the worker really uses
    from app.models import Entitlement
    with Session(engine) as s:
        s.add(Entitlement(user_id=uid, kind="report", chart_id=cid, quantity=1, used=0))
        s.commit()

    monkeypatch.setattr("app.main._enqueue_report", lambda _rid: True)
    r = c.post(f"/api/charts/{cid}/report")
    assert r.status_code == 200, r.text
    rid = r.json()["report_id"]

    with Session(engine) as s:
        rep = s.get(Report, rid)
        rep.status = "running"          # exactly what worker.py:321 writes
        s.add(rep)
        s.commit()

    r2 = c.post(f"/api/charts/{cid}/report")
    assert r2.status_code == 200, r2.text
    assert r2.json().get("existing") is True, "a running report was not recognised"
    assert r2.json()["report_id"] == rid

    with Session(engine) as s:
        rows = s.exec(select(Report).where(Report.chart_id == cid)).all()
    assert len(rows) == 1, (
        f"retry during generation created {len(rows)} reports — each one is a "
        "full 13-section LLM job billed to us"
    )


def test_every_report_status_has_persian_copy():
    """No user should ever be shown the raw English state name."""
    STATES = ("queued", "running", "done", "degraded", "failed")
    for tpl in ("reports.html", "account.html"):
        src = (ROOT / "app" / "templates" / tpl).read_text(encoding="utf-8")
        for st in STATES:
            assert f"'{st}'" in src, f"{tpl} has no Persian label for '{st}'"
