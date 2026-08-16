"""P0-4: CMS admin routes — articles/pages/media CRUD + revisions + audit.

Every mutation stores a ContentVersion snapshot AND an audit_logs row
(app.security.audit — same path as refunds/secrets). Media → R2.
"""
import hashlib
import hmac as _hmac
import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlmodel import Session, select

from app.db import engine as db_engine
from app.db import get_session
from app.models_cms import Article, ContentVersion, MediaAsset, Page
from app.security import audit

router = APIRouter()

# Same gate as app/main._is_admin — duplicated deliberately here to keep
# routes independent (no main↔routes import cycle).
_ADMIN_COOKIE = "chart_admin"


def _is_admin(request: Request) -> bool:
    import os
    try:
        import app.config  # noqa: F401 — load .env
    except Exception:
        pass
    secret = os.getenv("ADMIN_SECRET", "")
    pin = os.getenv("ADMIN_PIN", "")
    expected = _hmac.new(secret.encode(), pin.encode(), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(request.cookies.get(_ADMIN_COOKIE, ""), expected)

SLUG_RE = re.compile(r"^[a-z0-9\-]{2,120}$")
MUTABLE_ARTICLE_FIELDS = ("title", "category", "excerpt", "body", "keywords",
                          "meta_title", "meta_description", "canonical",
                          "featured_image", "author")


def _snapshot(obj: Any) -> dict:
    cols = getattr(obj, "__table__", None)
    if cols is None:
        return {}
    out: dict[str, Any] = {}
    for c in cols.columns:
        if not c.name.startswith("_"):
            v = getattr(obj, c.name)
            if isinstance(v, datetime):
                v = v.isoformat()
            elif isinstance(v, dict):
                v = {k: (val.isoformat() if isinstance(val, datetime) else val)
                     for k, val in v.items()}
            out[c.name] = v
    return out


def _save_version(session: Session, kind: str, oid: str, obj: Any) -> None:
    session.add(ContentVersion(
        object_kind=kind, object_id=oid, version=getattr(obj, "version", 0),
        snapshot=_snapshot(obj), changed_by="", reason="edit",
    ))


def _read_json(request: Request) -> dict:
    raw = getattr(request, "_body", None) or b"{}"
    if isinstance(raw, str):
        raw = raw.encode()
    try:
        data = json.loads(raw or b"{}")
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


# ── Articles ────────────────────────────────────────────────────────────

@router.get("/api/admin/content/articles")
def cms_articles(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    rows = session.exec(select(Article).order_by(Article.updated_at.desc())).all()
    return [{"id": a.id, "title": a.title, "slug": a.slug, "category": a.category,
             "status": a.status, "version": a.version,
             "updated_at": a.updated_at.isoformat() if a.updated_at else None} for a in rows]


@router.get("/api/admin/content/articles/{aid}")
def cms_article_get(aid: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    a = session.get(Article, aid)
    if not a:
        raise HTTPException(404)
    return _snapshot(a)


@router.post("/api/admin/content/articles")
def cms_article_create(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    data = _read_json(request)
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip().lower()
    if not title:
        raise HTTPException(422, "title required")
    if not slug or not SLUG_RE.match(slug):
        raise HTTPException(422, "invalid slug (a-z0-9-، ۲ تا ۱۲۰ کاراکتر)")
    if session.exec(select(Article).where(Article.slug == slug)).first():
        raise HTTPException(409, "duplicate slug")
    a = Article(
        title=title[:200], slug=slug,
        category=(data.get("category") or "عمومی")[:60],
        excerpt=(data.get("excerpt") or "")[:400],
        body=data.get("body") or "",
        keywords=(data.get("keywords") or "")[:400],
        meta_title=(data.get("meta_title") or "")[:120],
        meta_description=(data.get("meta_description") or "")[:300],
        canonical=(data.get("canonical") or "")[:300],
        featured_image=(data.get("featured_image") or "")[:500],
        author=(data.get("author") or "")[:80],
        status="draft",
    )
    session.add(a)
    _save_version(session, "article", a.id, a)
    session.commit()
    audit(db_engine, "cms", "article.create", a.id, title)
    return {"id": a.id, "slug": a.slug}


@router.put("/api/admin/content/articles/{aid}")
def cms_article_update(aid: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    a = session.get(Article, aid)
    if not a:
        raise HTTPException(404)
    data = _read_json(request)
    old = _snapshot(a)
    for f in MUTABLE_ARTICLE_FIELDS:
        if f in data:
            v = data[f]
            setattr(a, f, v.strip() if isinstance(v, str) else v)
    if "slug" in data and data["slug"] != a.slug:
        new_slug = (data["slug"] or "").strip().lower()
        if not SLUG_RE.match(new_slug):
            raise HTTPException(422, "invalid slug")
        if session.exec(select(Article).where(Article.slug == new_slug, Article.id != aid)).first():
            raise HTTPException(409, "duplicate slug")
        a.slug = new_slug
    if "status" in data and data["status"] in ("draft", "published", "unpublished"):
        a.status = data["status"]
        if data["status"] == "published":
            a.publish_at = datetime.now(timezone.utc)
    a.version += 1
    a.updated_at = datetime.now(timezone.utc)
    session.add(ContentVersion(object_kind="article", object_id=a.id, version=a.version - 1,
                               snapshot=old, changed_by="", reason="update"))
    session.commit()
    audit(db_engine, "cms", "article.update", a.id, f"v{a.version} {a.status}")
    return {"ok": True, "version": a.version}


@router.delete("/api/admin/content/articles/{aid}")
def cms_article_delete(aid: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    a = session.get(Article, aid)
    if not a:
        raise HTTPException(404)
    slug = a.slug
    session.delete(a)
    session.commit()
    audit(db_engine, "cms", "article.delete", aid, slug)
    return {"ok": True}


@router.get("/api/admin/content/articles/{aid}/revisions")
def cms_article_revisions(aid: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    rows = session.exec(select(ContentVersion)
                        .where(ContentVersion.object_kind == "article",
                               ContentVersion.object_id == aid)
                        .order_by(ContentVersion.version.desc())).all()
    return [{"version": r.version,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "snapshot": r.snapshot} for r in rows]


@router.post("/api/admin/content/articles/{aid}/restore/{version}")
def cms_article_restore(aid: str, version: int, request: Request,
                        session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    a = session.get(Article, aid)
    if not a:
        raise HTTPException(404)
    rv = session.exec(select(ContentVersion).where(
        ContentVersion.object_kind == "article", ContentVersion.object_id == aid,
        ContentVersion.version == version)).first()
    if not rv:
        raise HTTPException(404, "version not found")
    old = _snapshot(a)
    for k, v in (rv.snapshot or {}).items():
        if hasattr(a, k) and k not in ("id", "version", "created_at", "updated_at"):
            setattr(a, k, v)
    a.version += 1
    a.updated_at = datetime.now(timezone.utc)
    session.add(ContentVersion(object_kind="article", object_id=a.id, version=a.version - 1,
                               snapshot=old, changed_by="", reason=f"restore v{version}"))
    session.commit()
    audit(db_engine, "cms", "article.restore", aid, f"v{version}→v{a.version}")
    return {"ok": True, "version": a.version}


# ── Pages ───────────────────────────────────────────────────────────────

@router.get("/api/admin/content/pages")
def cms_pages_list(request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    rows = session.exec(select(Page).order_by(Page.key)).all()
    return [{"key": p.key, "title": p.title, "version": p.version} for p in rows]


@router.get("/api/admin/content/pages/{key}")
def cms_page_get(key: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    p = session.exec(select(Page).where(Page.key == key)).first()
    if not p:
        raise HTTPException(404)
    return _snapshot(p)


@router.put("/api/admin/content/pages/{key}")
def cms_page_update(key: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    p = session.exec(select(Page).where(Page.key == key)).first()
    if not p:
        raise HTTPException(404)
    data = _read_json(request)
    old = _snapshot(p)
    if "title" in data:
        p.title = (data["title"] or "").strip()[:200]
    if "content" in data:
        p.content = data["content"] or ""
    if "extra" in data and isinstance(data["extra"], dict):
        p.extra = data["extra"]
    p.version += 1
    p.updated_at = datetime.now(timezone.utc)
    session.add(ContentVersion(object_kind="page", object_id=key, version=p.version - 1,
                               snapshot=old, changed_by="", reason="update"))
    session.commit()
    audit(db_engine, "cms", "page.update", key, f"v{p.version}")
    return {"ok": True, "version": p.version}


# ── Media (R2) ──────────────────────────────────────────────────────────

@router.post("/api/admin/content/media")
async def cms_media_upload(request: Request, file: UploadFile,
                           session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    if file.content_type not in ("image/png", "image/jpeg", "image/webp", "image/svg+xml"):
        raise HTTPException(415, "unsupported type — png/jpeg/webp/svg only")
    data = await file.read()
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(413, "image too large — max 4MB")
    if file.content_type == "image/svg+xml" and b"<script" in data.lower():
        raise HTTPException(422, "malicious SVG rejected (script tag)")
    import uuid
    key = f"media/{datetime.now(timezone.utc):%Y%m%d}/{uuid.uuid4().hex[:12]}-{file.filename or 'image'}"
    from app.storage import upload_bytes
    ok = upload_bytes(key, data, file.content_type)
    if not ok:
        raise HTTPException(502, "R2 upload failed")
    m = MediaAsset(filename=file.filename or "image", content_type=file.content_type,
                   size_bytes=len(data), r2_key=key)
    session.add(m)
    session.commit()
    audit(db_engine, "cms", "media.upload", m.id, key)
    return {"id": m.id, "url": key, "size": len(data)}


@router.delete("/api/admin/content/media/{mid}")
def cms_media_delete(mid: str, request: Request, session: Session = Depends(get_session)):
    if not _is_admin(request):
        raise HTTPException(403)
    m = session.get(MediaAsset, mid)
    if not m:
        raise HTTPException(404)
    try:
        from app.storage import delete_object
        delete_object(m.r2_key)
    except Exception:  # noqa: BLE001 — best-effort R2 cleanup
        pass
    session.delete(m)
    session.commit()
    audit(db_engine, "cms", "media.delete", mid, m.r2_key)
    return {"ok": True}