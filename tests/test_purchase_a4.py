"""A4 — unified purchase endpoint acceptance tests (hermetic, no LLM)."""
import os, uuid
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import app as main_app
from app.auth import _user_cookie_value, USER_COOKIE
from app.models import User, Entitlement
from app.db import engine
from app.credits import get_price, balance


def _mk_user(n):
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, credits=n)
        s.add(u)
        s.commit()
        return u.id


def _cookie(uid):
    return {USER_COOKIE: _user_cookie_value(uid)}


def test_purchase_requires_login():
    c = TestClient(main_app)
    r = c.post("/api/purchase", json={"action_key": "chat_pack_20"})
    assert r.status_code == 401, r.text
    assert r.json()["login_required"] is True


def test_purchase_unknown_action_400():
    uid = _mk_user(50)
    c = TestClient(main_app)
    r = c.post("/api/purchase", json={"action_key": "nonsense"}, cookies=_cookie(uid))
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "unknown_action"


def test_purchase_success_grants_entitlement():
    uid = _mk_user(50)
    c = TestClient(main_app)
    r = c.post("/api/purchase", json={"action_key": "chat_pack_20"}, cookies=_cookie(uid))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and j["entitlement_id"]
    assert balance(Session(engine), uid) == 50 - get_price(Session(engine), "chat_pack_20")
    with Session(engine) as s:
        ent = s.get(Entitlement, j["entitlement_id"])
        assert ent.kind == "chat" and ent.quantity >= 20 and ent.user_id == uid


def test_purchase_insufficient_returns_402_with_packs():
    uid = _mk_user(0)
    c = TestClient(main_app)
    r = c.post("/api/purchase", json={"action_key": "report_gold"}, cookies=_cookie(uid))
    assert r.status_code == 402, r.text
    j = r.json()
    assert j["needed"] > 0 and j["have"] == 0
    assert isinstance(j["packs"], list) and any(p["key"] == "credit12" for p in j["packs"])
