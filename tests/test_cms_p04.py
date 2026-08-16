"""P0-4 — CMS: authz, CRUD, validation, revisions, audit, DB-first reads."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi import HTTPException, Request
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import AuditLog
from app.models_cms import Article, ContentVersion, Page
from app.routes import cms_admin

init_db()


@pytest.fixture(autouse=True)
def _clean_cms():
    with Session(engine) as s:
        for t in (ContentVersion, Article, Page):
            for r in s.exec(select(t)).all():
                s.delete(r)
        s.commit()


def _req(admin: bool = True) -> Request:
    import os
    import hmac as _hm
    import hashlib as _hs

    class _State:
        is_admin = admin

        def get(self, k, d=None):
            return d
    r = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    r.scope["state"] = _State()
    if admin:
        secret = os.getenv("ADMIN_SECRET", "")
        pin = os.getenv("ADMIN_PIN", "test-pin")
        ck = _hm.new(secret.encode(), pin.encode(), _hs.sha256).hexdigest()
        r._cookies = {"chart_admin": ck}
    return r


def _json_body(data: dict) -> Request:
    import json
    r = _req()
    r._body = json.dumps(data).encode()
    return r


def _create(slug: str = "my-article") -> str:
    with Session(engine) as s:
        a = Article(title="تست", slug=slug, category="عمومی",
                    excerpt="خلاصه", body="# متن", status="draft")
        s.add(a)
        s.commit()
        return a.id


# ── authz (400/403 semantics) ───────────────────────────────────────────

def test_articles_requires_admin():
    with pytest.raises(HTTPException):
        cms_admin.cms_articles(_req(admin=False), Session(engine))


def test_create_requires_admin():
    with pytest.raises(HTTPException):
        cms_admin.cms_article_create(_req(admin=False), Session(engine))


# ── CRUD + validation ───────────────────────────────────────────────────

def test_create_and_validation():
    with Session(engine) as s:
        cms_admin.cms_article_create(_json_body({"title": "سلام دنیا", "slug": "salam"}), s)
        a = s.exec(select(Article).where(Article.slug == "salam")).first()
        assert a is not None and a.status == "draft" and a.version == 1
        # duplicate slug → 409
        with pytest.raises(HTTPException) as e:
            cms_admin.cms_article_create(_json_body({"title": "دوباره", "slug": "salam"}), s)
        assert e.value.status_code == 409
        # invalid slug → 422
        with pytest.raises(HTTPException) as e2:
            cms_admin.cms_article_create(_json_body({"title": "x", "slug": "نامعتبر!!"}), s)
        assert e2.value.status_code == 422
        # empty title → 422
        with pytest.raises(HTTPException) as e3:
            cms_admin.cms_article_create(_json_body({"title": "", "slug": "ok-slug"}), s)
        assert e3.value.status_code == 422


def test_update_bumps_version_snapshot_status():
    aid = _create("ver")
    with Session(engine) as s:
        out = cms_admin.cms_article_update(aid, _json_body({"title": "ویرایش"}), s)
        assert out["version"] == 2
        v = s.exec(select(ContentVersion).where(ContentVersion.object_id == aid)).all()
        assert any(x.version == 1 for x in v)
        cms_admin.cms_article_update(aid, _json_body({"status": "published"}), s)
        a = s.get(Article, aid)
        assert a.status == "published" and a.publish_at is not None
        cms_admin.cms_article_update(aid, _json_body({"status": "unpublished"}), s)
        assert s.get(Article, aid).status == "unpublished"


def test_delete_removes():
    aid = _create("del")
    with Session(engine) as s:
        cms_admin.cms_article_delete(aid, _req(), s)
        assert s.get(Article, aid) is None


# ── pages ───────────────────────────────────────────────────────────────

def test_page_crud_and_404():
    with Session(engine) as s:
        p = Page(key="about", title="درباره", content="متن", extra={"meta": "m"})
        s.add(p)
        s.commit()
    with Session(engine) as s:
        cms_admin.cms_page_update("about", _json_body({"content": "متن جدید", "extra": {"x": 1}}), s)
        p = s.exec(select(Page).where(Page.key == "about")).first()
        assert p.content == "متن جدید" and p.extra == {"x": 1} and p.version == 2
        with pytest.raises(HTTPException):
            cms_admin.cms_page_get("nope", _req(), s)


# ── revisions ───────────────────────────────────────────────────────────

def test_revisions_and_restore():
    aid = _create("rev")
    with Session(engine) as s:
        cms_admin.cms_article_update(aid, _json_body({"title": "نسخه دوم"}), s)
        cms_admin.cms_article_restore(aid, 1, _req(), s)
        a = s.get(Article, aid)
        assert a.title == "تست"  # back to v1 snapshot


# ── audit ───────────────────────────────────────────────────────────────

def test_audit_written_on_update():
    aid = _create("audit")
    with Session(engine) as s:
        cms_admin.cms_article_update(aid, _json_body({"title": "x"}), s)
    with Session(engine) as s:
        rows = s.exec(select(AuditLog).where(AuditLog.action == "article.update")).all()
        assert any(aid == r.entity for r in rows)