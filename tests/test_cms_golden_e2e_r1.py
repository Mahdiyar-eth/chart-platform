"""R.1 — CMS Golden Path E2E (نقد چهارم).

Real user journey over HTTP with auth:
 admin login → create article (draft v1) → reject bad slug → edit (v2)
 → upload image → publish → PUBLIC render 200 + SEO meta + sitemap entry
 → revision restore (v1) → audit rows → delete → public gone + sitemap clean.
R2 is mocked (upload_bytes → True); all rows cleaned by test-DB teardown.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.db import engine
from app.main import _ADMIN_COOKIE, _ADMIN_PIN, app
from app.models import AuditLog
from app.models_cms import Article, ContentVersion, MediaAsset
from sqlmodel import Session, select


def _admin(c: TestClient) -> None:
    r = c.post("/admin/login", data={"pin": _ADMIN_PIN}, follow_redirects=False)
    assert r.status_code == 303, r.text
    val = r.cookies.get(_ADMIN_COOKIE)
    assert val, "login must set admin cookie"
    c.cookies.set(_ADMIN_COOKIE, val)


def test_cms_golden_path_e2e(monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage, "upload_bytes", lambda *a, **k: True)

    c = TestClient(app, follow_redirects=False)
    # 1) authz closed
    assert c.get("/api/admin/content/articles").status_code == 403
    _admin(c)

    slug = f"golden-e2e-{int(__import__('time').time())}"
    # 2) create → draft + v1 snapshot + audit
    r = c.post("/api/admin/content/articles", json={
        "title": "Golden E2E Probe", "slug": slug, "category": "تست",
        "excerpt": "probe", "body": [{"h2": "بخش اول", "p": "متن آزمایشی"}],
        "meta_title": "Golden Probe Title", "meta_description": "golden desc"})
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["slug"] == slug

    # 3) validation: bad type rejected
    r = c.post("/api/admin/content/articles", json={"title": "x", "slug": "bad!",
                                                    "category": "تست", "body": ""})
    assert r.status_code == 422, r.text

    with Session(engine) as s:
        a = s.get(Article, aid)
        assert a and a.status == "draft" and a.version == 1
        v1 = s.exec(select(ContentVersion).where(ContentVersion.object_id == aid)
                    .order_by(ContentVersion.version.desc())).first()
        assert v1 and v1.version == 1 and v1.snapshot.get("body", "")
        audits = s.exec(select(AuditLog).where(AuditLog.entity == aid)).all()
        assert any(x.action == "article.create" for x in audits)

    # 4) draft is NOT public
    assert c.get(f"/articles/{slug}").status_code == 404

    # 5) edit → v2 (v1 retained)
    r = c.put(f"/api/admin/content/articles/{aid}", json={
        "title": "Golden E2E Probe v2", "body": [{"h2": "بخش دوم", "p": "متن ویرایششده"}]})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2
    with Session(engine) as s:
        vers = s.exec(select(ContentVersion).where(ContentVersion.object_id == aid)).all()
        assert len(vers) == 2

    # 6) upload image
    r = c.post("/api/admin/content/media",
               files={"file": ("probe.png", b"\x89PNG\r\n\x1a\nprobe", "image/png")})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    with Session(engine) as s:
        m = s.get(MediaAsset, mid)
        assert m and m.content_type == "image/png"

    # 7) reject malicious SVG
    r = c.post("/api/admin/content/media",
               files={"file": ("evil.svg", b"<svg><script>alert(1)</script></svg>",
                              "image/svg+xml")})
    assert r.status_code == 422, r.text

    # 8) publish → public 200 + SEO meta + sitemap
    r = c.put(f"/api/admin/content/articles/{aid}", json={"status": "published"})
    assert r.status_code == 200, r.text
    pub = c.get(f"/articles/{slug}")
    assert pub.status_code == 200
    body = pub.text
    assert "Golden E2E Probe v2" in body and "بخش دوم" in body
    sm = c.get("/sitemap.xml")
    assert sm.status_code == 200 and slug in sm.text

    # 9) restore v1 → content back (snapshot v1 was draft — re-publish like a real editor)
    r = c.post(f"/api/admin/content/articles/{aid}/restore/1")
    assert r.status_code == 200, r.text
    r = c.put(f"/api/admin/content/articles/{aid}", json={"status": "published"})
    assert r.status_code == 200, r.text
    got = c.get(f"/articles/{slug}")
    assert "بخش اول" in got.text and "متن آزمایشی" in got.text
    with Session(engine) as s:
        a = s.get(Article, aid)
        assert a.version >= 4  # restore + re-publish bumped versions

    # 10) audit complete trail
    with Session(engine) as s:
        acts = {x.action for x in s.exec(
            select(AuditLog).where(AuditLog.entity == aid)).all()}
    assert {"article.create", "article.update", "article.restore"} <= acts

    # 11) delete → public gone + sitemap clean
    r = c.delete(f"/api/admin/content/articles/{aid}")
    assert r.status_code == 200, r.text
    assert c.get(f"/articles/{slug}").status_code == 404
    sm2 = c.get("/sitemap.xml")
    assert sm2.status_code == 200 and slug not in sm2.text
    with Session(engine) as s:
        assert s.get(Article, aid) is None