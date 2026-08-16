"""CMS content models (P0-4): articles, pages, media assets, versions.

Source of truth moves from JSON files to PostgreSQL; JSON stays as the
historical seed only (migrated by scripts/seed_content.py).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Article(SQLModel, table=True):
    """SEO + informational article. draft → published | unpublished."""
    __tablename__ = "cms_articles"

    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str = Field(max_length=200, index=True)
    slug: str = Field(max_length=200, index=True, unique=True)
    category: str = Field(default="عمومی", max_length=60)
    excerpt: str = Field(default="", max_length=400)
    body: str = Field(default="", sa_column=Column(Text))
    keywords: str = Field(default="", max_length=400)
    meta_title: str = Field(default="", max_length=120)
    meta_description: str = Field(default="", max_length=300)
    canonical: str = Field(default="", max_length=300)
    featured_image: str = Field(default="", max_length=500)  # media id or external URL
    author: str = Field(default="", max_length=80)
    status: str = Field(default="draft", max_length=20)  # draft | published | unpublished
    publish_at: datetime | None = Field(default=None)
    seo_score: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    version: int = Field(default=1)  # bumped on every edit (revisions)


class Page(SQLModel, table=True):
    """Static site page content, editable from admin (P0-4)."""
    __tablename__ = "cms_pages"

    id: str = Field(default_factory=_uuid, primary_key=True)
    key: str = Field(max_length=60, index=True, unique=True)   # home | about | guide | faq | terms | privacy | refund | contact ...
    title: str = Field(default="", max_length=200)
    content: str = Field(default="", sa_column=Column(Text))   # markdown/HTML body
    extra: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # hero_subtitle, cta_text, banner, social_links ...
    updated_at: datetime = Field(default_factory=_now)
    version: int = Field(default=1)


class MediaAsset(SQLModel, table=True):
    """Uploaded media (images) stored in R2."""
    __tablename__ = "cms_media"

    id: str = Field(default_factory=_uuid, primary_key=True)
    filename: str = Field(max_length=200)
    content_type: str = Field(max_length=80)
    size_bytes: int = Field(default=0)
    r2_key: str = Field(max_length=300)
    alt: str = Field(default="", max_length=200)
    created_at: datetime = Field(default_factory=_now)


class ContentVersion(SQLModel, table=True):
    """Revision history — every mutation stores the previous state (P0-4)."""
    __tablename__ = "cms_versions"

    id: str = Field(default_factory=_uuid, primary_key=True)
    object_kind: str = Field(max_length=20)   # article | page | media
    object_id: str = Field(max_length=64, index=True)
    version: int = Field(default=0)
    snapshot: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    changed_by: str = Field(default="", max_length=64)
    reason: str = Field(default="", max_length=300)
    created_at: datetime = Field(default_factory=_now)