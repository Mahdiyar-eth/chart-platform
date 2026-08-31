"""A5 — account-enforcement + anonymous-chart claim acceptance tests (hermetic, no LLM)."""
import os, uuid
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"
from sqlmodel import Session
from fastapi.testclient import TestClient
from app.main import app as main_app, claim_anonymous_charts
from app.models import BirthProfile, Chart, User
from app.db import engine


def _mk_user(credits=5):
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, credits=credits)
        s.add(u)
        s.commit()
        return u.id


def _chart(cap, owner_id=None):
    with Session(engine) as s:
        p = BirthProfile(user_id=owner_id, raw_year=1373, raw_month=1, raw_day=1)
        s.add(p)
        s.flush()
        c = Chart(profile_id=p.id, chart_json={"k": "v"}, access_token=cap)
        s.add(c)
        s.commit()
        return c.id


def _profile_user(chart_id):
    with Session(engine) as s:
        ch = s.get(Chart, chart_id)
        if not ch or not ch.profile_id:
            return None
        p = s.get(BirthProfile, ch.profile_id)
        return p.user_id if p else None


def test_purchase_requires_login():
    """A5 (F3): the credit purchase path REQUIRES an account — anonymous -> 401."""
    c = TestClient(main_app)
    r = c.post("/api/purchase", json={"action_key": "chat_pack_20"})
    assert r.status_code == 401, r.text
    assert r.json()["login_required"] is True


def test_claim_links_anonymous_chart_to_user():
    uid = _mk_user()
    cap = "cap_" + uuid.uuid4().hex
    cid = _chart(cap)  # guest (owner None)
    with Session(engine) as s:
        assert claim_anonymous_charts(s, uid, cap) == 1
    assert _profile_user(cid) == uid


def test_claim_idempotent_no_duplicate():
    uid = _mk_user()
    cap = "cap_" + uuid.uuid4().hex
    cid = _chart(cap)
    with Session(engine) as s:
        assert claim_anonymous_charts(s, uid, cap) == 1
        assert claim_anonymous_charts(s, uid, cap) == 0  # already linked -> no-op
    assert _profile_user(cid) == uid


def test_claim_never_steals_other_users_chart():
    owner = _mk_user()
    other = _mk_user()
    cap = "cap_" + uuid.uuid4().hex
    cid = _chart(cap, owner_id=owner)  # owned by another user
    with Session(engine) as s:
        assert claim_anonymous_charts(s, other, cap) == 0  # -> not claimed
    assert _profile_user(cid) == owner  # ownership untouched


def test_claim_wrong_token_noop():
    uid = _mk_user()
    with Session(engine) as s:
        assert claim_anonymous_charts(s, uid, "cap_missing_" + uuid.uuid4().hex) == 0
