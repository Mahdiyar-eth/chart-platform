#!/usr/bin/env python3
"""P0-4: seed CMS tables from the historical JSON files (one-time / idempotent).

JSON stays as source-of-truth ONLY for the initial content; after seeding,
PostgreSQL is the source of truth (per external review #3).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

import app.config  # noqa: F401
from app.db import engine
from app.models_cms import Article, Page

CONTENT = Path(__file__).resolve().parent.parent / "app" / "content"


def seed_articles() -> int:
    arts = json.load(open(CONTENT / "articles.json", encoding="utf-8"))
    n = 0
    with Session(engine) as s:
        for a in arts:
            slug = a.get("slug") or a.get("id", "")
            if s.exec(select(Article).where(Article.slug == slug)).first():
                continue
            body_raw = a.get("body", "")
            if isinstance(body_raw, (list, dict)):
                body_raw = json.dumps(body_raw, ensure_ascii=False)
            s.add(Article(
                title=a.get("title", slug), slug=slug,
                category=a.get("category", "عمومی"),
                excerpt=a.get("excerpt", ""), body=body_raw or
                "\n\n".join(f"## {h}\n\n{p}" for h, p in zip(a.get("sections", []), a.get("paragraphs", []))),
                keywords=a.get("keywords", ""),
                meta_title=a.get("meta_title", a.get("title", ""))[:120],
                meta_description=a.get("meta_description", a.get("excerpt", ""))[:300],
                canonical=a.get("canonical", ""),
                featured_image=a.get("image", ""),
                status="published",
            ))
            n += 1
        s.commit()
    return n


def seed_pages() -> int:
    pages = json.load(open(CONTENT / "pages.json", encoding="utf-8"))
    n = 0
    with Session(engine) as s:
        for key, p in pages.items():
            existing = s.exec(select(Page).where(Page.key == key)).first()
            if existing:
                # upgrade path: backfill extra (categories/items/sections/meta) lost in v1 seed
                if not (existing.extra or {}):
                    existing.extra = {k: v for k, v in p.items()
                                      if k not in ("title", "content")}
                    s.add(existing)
                    n += 1
                continue
            s.add(Page(key=key, title=p.get("title", key), content=p.get("content", ""),
                       extra={k: v for k, v in p.items() if k not in ("title", "content")}))
            n += 1
        s.commit()
    return n


if __name__ == "__main__":
    a = seed_articles()
    p = seed_pages()
    print(f"seeded: {a} articles, {p} pages")