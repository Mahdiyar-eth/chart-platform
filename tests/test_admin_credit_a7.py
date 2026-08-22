"""A7 — admin credit-economy panel acceptance tests (hermetic, no LLM)."""
import os, uuid
os.environ["DATABASE_URL"]="postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
os.environ["CREATE_ALL_ON_BOOT"]="1"

from sqlmodel import Session, select
from fastapi.testclient import TestClient
from app.main import app as main_app, _admin_cookie_value
from app.models import User, AuditLog
from app.credits import get_price, balance
from app.db import engine


def _mk_user(n: int = 0) -> str:
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, phone=None, email=None, credits=n)
        s.add(u); s.commit()
        return u.id


def _admin_cookie():
    return {"chart_admin": _admin_cookie_value()}


def test_admin_edit_credit_price():
    before = get_price(Session(engine), "explore_card")
    c = TestClient(main_app)
    r = c.post("/api/admin/credit-price/explore_card", data={"credits": "3"}, cookies=_admin_cookie())
    assert r.status_code == 200, r.text
    assert get_price(Session(engine), "explore_card") == 3
    # restore so other tests are unaffected
    c.post("/api/admin/credit-price/explore_card", data={"credits": str(before)}, cookies=_admin_cookie())


def test_admin_manual_grant_credits_user():
    uid = _mk_user(0)
    c = TestClient(main_app)
    r = c.post("/api/admin/credits/grant", data={"user_id": uid, "amount": "5", "reason": "test_grant"}, cookies=_admin_cookie())
    assert r.status_code == 200, r.text
    assert balance(Session(engine), uid) == 5


def test_admin_grant_writes_audit_log():
    uid = _mk_user(0)
    c = TestClient(main_app)
    c.post("/api/admin/credits/grant", data={"user_id": uid, "amount": "3", "reason": "audit_grant"}, cookies=_admin_cookie())
    with Session(engine) as s:
        rows = s.exec(select(AuditLog).where(AuditLog.action == "credit_grant", AuditLog.entity == "User")).all()
    assert any("audit_grant" in r.details for r in rows), [(r.action, r.details) for r in rows]


def test_admin_non_admin_403():
    uid = _mk_user(0)
    c = TestClient(main_app)
    r = c.post("/api/admin/credits/grant", data={"user_id": uid, "amount": "5"}, cookies={"chart_admin": "wrong"})
    assert r.status_code == 403, r.status_code
