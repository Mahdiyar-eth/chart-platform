"""Buying a report must produce a report.

This was the single largest hole in the funnel. POST /api/charts/{id}/report
has exactly one caller in the whole codebase — genReport() in chart.html —
and that button only exists inside the `failed` and `stalled` templates, i.e.
states that are unreachable until a report already exists.

Meanwhile grant_from_credits() created an entitlement and enqueued nothing.
Auto-creation lived only on the legacy Zarinpal order path, which /plans has
not used since purchases moved to /api/purchase.

The concrete outcome for a paying customer:

  open /plans?chart=X -> buy "شناخت کامل — ۷ اعتبار" -> credits deducted,
  entitlement created -> redirected to /account -> return to /chart/X ->
  status is {"status": "none"} -> nothing renders. No report, no button, no
  error, and no way to start one. Seven credits, nothing delivered.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app as main_app
from app.models import CreditTransaction, Entitlement, Report, User

# Report.plan_key holds the TIER, not the action key: PLAN_SECTIONS is keyed
# by tier, and storing "report_basic" would fall through to the 13-section
# default — a basic buyer silently receiving the full report.
REPORT_ACTIONS = [("report_basic", "basic"), ("report_full", "full"),
                  ("report_gold", "gold")]


def _phone() -> str:
    return "0912" + str(uuid.uuid4().int)[:8]


def _mk_chart(c):
    d = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897"}).json()
    return d["chart_id"], d["access_token"]


def _login(c, monkeypatch) -> str:
    from app import security as _sec
    _sec._RATE_LIMITS.pop("otp:testclient", None)
    monkeypatch.setattr("app.auth._OTP_DEV_MODE", True)
    phone = _phone()
    dev = c.post("/api/auth/otp/request", data={"phone": phone}).json()["dev_code"]
    r = c.post("/api/auth/otp/verify", data={"phone": phone, "code": dev})
    assert r.status_code == 200, r.text
    return c.get("/api/auth/me").json()["user"]["id"]


def _fund(uid: str, credits: int) -> None:
    with Session(engine) as s:
        u = s.get(User, uid)
        u.credits = credits
        s.add(u)
        s.add(CreditTransaction(user_id=uid, amount=credits, reason="test_topup",
                                idempotency_key=f"topup:{uuid.uuid4()}"))
        s.commit()


@pytest.mark.parametrize("action,tier", REPORT_ACTIONS)
def test_buying_a_report_queues_it(action, tier, monkeypatch):
    enqueued: list[str] = []
    monkeypatch.setattr("app.main._enqueue_report",
                        lambda rid: (enqueued.append(rid), True)[1])

    c = TestClient(main_app, base_url="https://testserver")
    cid, _tok = _mk_chart(c)
    uid = _login(c, monkeypatch)
    _fund(uid, 50)

    r = c.post("/api/purchase", json={"action_key": action, "chart_id": cid})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    with Session(engine) as s:
        reps = s.exec(select(Report).where(Report.chart_id == cid)).all()
    assert len(reps) == 1, (
        f"buying {action} created {len(reps)} reports — the customer paid and "
        "the chart page will render nothing at all"
    )
    assert reps[0].status == "queued"
    assert reps[0].plan_key == tier
    assert enqueued == [reps[0].id], "report row created but never enqueued"


def test_report_id_is_returned_so_the_ui_can_go_there(monkeypatch):
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: True)
    c = TestClient(main_app, base_url="https://testserver")
    cid, _ = _mk_chart(c)
    uid = _login(c, monkeypatch)
    _fund(uid, 50)
    r = c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid})
    assert r.json().get("report_id"), (
        "the purchase response carries no report_id, so the UI has nothing to "
        "navigate to and lands the buyer on /account instead"
    )


def test_entitlement_is_bound_to_the_report_it_paid_for(monkeypatch):
    """Otherwise one purchase could unlock a second report."""
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: True)
    c = TestClient(main_app, base_url="https://testserver")
    cid, _ = _mk_chart(c)
    uid = _login(c, monkeypatch)
    _fund(uid, 50)
    r = c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid})
    rid = r.json()["report_id"]
    with Session(engine) as s:
        ent = s.get(Entitlement, r.json()["entitlement_id"])
        assert ent.ref_id == rid, "entitlement not bound to the report it bought"


def test_buying_twice_does_not_create_two_reports(monkeypatch):
    """The idempotency key makes the second purchase a no-op; it must not
    leave a second queued job behind either."""
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: True)
    c = TestClient(main_app, base_url="https://testserver")
    cid, _ = _mk_chart(c)
    uid = _login(c, monkeypatch)
    _fund(uid, 50)
    c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid})
    c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid})
    with Session(engine) as s:
        reps = s.exec(select(Report).where(Report.chart_id == cid)).all()
    assert len(reps) == 1, f"{len(reps)} reports for one purchase"


def test_non_report_purchase_creates_no_report(monkeypatch):
    """Buying an explore card or a chat pack must not queue a report."""
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: True)
    c = TestClient(main_app, base_url="https://testserver")
    cid, _ = _mk_chart(c)
    uid = _login(c, monkeypatch)
    _fund(uid, 50)
    c.post("/api/purchase", json={"action_key": "solar_return", "chart_id": cid})
    with Session(engine) as s:
        reps = s.exec(select(Report).where(Report.chart_id == cid)).all()
    assert not reps, "a non-report purchase queued a report"
