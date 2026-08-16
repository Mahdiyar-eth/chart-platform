"""A6 (ChatGPT directive) — report regeneration versioning & preservation."""
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import BirthProfile, Chart, Order, Report, User
from tests.conftest import fake_authority


def _seed(plan='basic'):
    with Session(engine) as s:
        u = User(phone='+98a6' + fake_authority(8), credits=10)
        s.add(u); s.commit(); s.refresh(u)
        p = BirthProfile(user_id=u.id, name='ن', raw_year=1373, raw_month=6, raw_day=1,
                         hour=6, minute=10, city_fa='تهران', time_known=True)
        s.add(p); s.commit(); s.refresh(p)
        c = Chart(profile_id=p.id, chart_json={'planets': {'Sun': {'longitude': 120.0}}})
        s.add(c); s.commit(); s.refresh(c)
        o = Order(user_id=u.id, chart_id=c.id, profile_id=p.id, amount_rial=1490000,
                  plan_key=plan, status='paid', authority='authtest')
        s.add(o); s.commit(); s.refresh(o)
        r = Report(chart_id=c.id, plan_key=plan, status='done', r2_key='reports/' + o.id + '.pdf')
        s.add(r); s.commit(); s.refresh(r)
        return u.id, o.id, r.id


def _seed_chart(oid):
    with Session(engine) as s:
        return s.get(Order, oid).chart_id


def test_done_report_regeneration_mints_new_version_keeps_old():
    u, oid, rid = _seed()
    c = TestClient(app)
    with patch('app.routes.admin._enqueue_report', return_value=True):
        with patch('app.routes.admin._is_admin', return_value=True):
            r = c.post('/api/admin/orders/' + oid + '/regenerate')
    assert r.status_code == 200
    new_id = r.json()['report_id']
    assert new_id != rid
    with Session(engine) as s:
        old = s.get(Report, rid)
        new = s.get(Report, new_id)
        assert old.status == 'done'      # old report preserved
        assert old.r2_key is not None    # artifact untouched
        assert new.status == 'queued'
        assert new.chart_id == old.chart_id


def test_failed_report_requeued_in_place_no_duplicate():
    u, oid, rid = _seed()
    with Session(engine) as s:
        rep = s.get(Report, rid)
        rep.status = 'failed'
        rep.error = 'llm boom'
        s.add(rep); s.commit()
    c = TestClient(app)
    with patch('app.routes.admin._enqueue_report', return_value=True):
        with patch('app.routes.admin._is_admin', return_value=True):
            r = c.post('/api/admin/orders/' + oid + '/regenerate')
    assert r.status_code == 200
    assert r.json()['report_id'] == rid   # same row requeued
    with Session(engine) as s:
        rows = s.exec(select(Report).where(Report.chart_id == _seed_chart(oid))).all()
        assert len(rows) == 1  # no duplicate created
