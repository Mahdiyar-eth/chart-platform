"""H1.6 (HARDENING): synastry Person B is a GUEST — no account required.

- /api/synastry/order stores chart B with an anonymous BirthProfile
  (user_id=NULL) and returns its capability token.
- The token in the chart_access cookie unlocks /api/synastry/full for B
  exactly like an owned chart — after a paid synastry order.
"""
from __future__ import annotations

import os
import uuid

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

import json  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BirthProfile, Chart, Order  # noqa: E402

SUF = uuid.uuid4().hex[:8]


def _mk_user_cookie(c) -> str:
    # create a User directly + sign the session cookie (no SMS in tests)
    from app.auth import _user_cookie_value
    from app.models import User
    phone = f"+98h16{uuid.uuid4().hex[:8]}"
    with Session(engine) as s:
        u = User(phone=phone)
        s.add(u)
        s.commit()
        uid = u.id
    c.cookies.set("chart_user", _user_cookie_value(uid))
    return _user_cookie_value(uid)


def _syn_form() -> dict:
    return {
        "name_a": "الف", "year_a": "1373", "month_a": "6", "day_a": "1",
        "hour_a": "6", "minute_a": "10", "city_a": "تهران",
        "name_b": "ب", "year_b": "1369", "month_b": "3", "day_b": "15",
        "hour_b": "14", "minute_b": "30", "city_b": "اصفهان",
    }


def test_synastry_order_makes_person_b_guest():
    """B's profile must be anonymous (user_id NULL) and a capability token
    returned so the buyer can unlock the full report later."""
    c = TestClient(app)
    sid = _mk_user_cookie(c)
    assert sid, "registration should set a session cookie"
    r = c.post("/api/synastry/order", data=_syn_form())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["token_b"] and len(d["token_b"]) >= 20
    with Session(engine) as s:
        cb = s.get(Chart, d["chart_b"])
        prof = s.get(BirthProfile, cb.profile_id)
        assert prof is not None and prof.user_id is None, "person B must be a guest"
        ca = s.get(Chart, d["chart_a"])
        assert ca.profile_id and s.get(BirthProfile, ca.profile_id).user_id is not None


def test_synastry_full_unlocks_via_guest_token_after_paid():
    """Full report works for B via cookie token even though B has no account."""
    c = TestClient(app)
    _mk_user_cookie(c)
    r = c.post("/api/synastry/order", data=_syn_form())
    d = r.json()
    cid_b, tok_b = d["chart_b"], d["token_b"]
    # simulate the client storing B's token in chart_access (A is owned via
    # the logged-in user, so it needs no token entry)
    ck = {"chart_access": json.dumps({cid_b: tok_b})}
    c.cookies.update(ck)
    # mark the order paid
    with Session(engine) as s:
        o = s.exec(select(Order).where(Order.id == d["order_id"])).first()
        o.status = "paid"
        s.add(o)
        s.commit()
    r = c.post("/api/synastry/full", data={"chart_a": d["chart_a"], "chart_b": cid_b})
    assert r.status_code == 200, r.text
    j = r.json()
    assert "overall" in j and "domains" in j


def test_synastry_full_guest_without_token_still_403():
    """No token for B → 403 (guest data is NOT publicly readable)."""
    c = TestClient(app)
    _mk_user_cookie(c)
    r = c.post("/api/synastry/order", data=_syn_form())
    d = r.json()
    cid_b = d["chart_b"]
    # only A is in the cookie (wrong/absent token for B) → B must stay locked
    ck = {"chart_access": json.dumps({d["chart_a"]: "x", cid_b: "wrong-token"})}
    c.cookies.update(ck)
    with Session(engine) as s:
        o = s.exec(select(Order).where(Order.id == d["order_id"])).first()
        o.status = "paid"
        s.add(o)
        s.commit()
    r = c.post("/api/synastry/full", data={"chart_a": d["chart_a"], "chart_b": d["chart_b"]})
    assert r.status_code == 403
