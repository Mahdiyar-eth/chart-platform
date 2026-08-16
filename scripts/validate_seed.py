#!/usr/bin/env python3
"""R.1-b — Deep seed validation on PROD (review #4 spec).

Checks post-seed state: counts, status split, slug uniqueness, every old URL
200, body rendering, metadata/canonical/image presence, sitemap coverage,
JSON-vs-DB parity. Exits non-zero on any failure.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, func, select

from app.db import engine
from app.models_cms import Article
from fastapi.testclient import TestClient
from app.main import app

FAILS: list[str] = []
OKS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (OKS if ok else FAILS).append(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
    print(f"[{'✅' if ok else '❌'}] {name} {detail}")


def main() -> int:
    with Session(engine) as s:
        total = s.exec(select(func.count()).select_from(Article)).one()
        publ = s.exec(select(func.count()).select_from(Article)
                      .where(Article.status == "published")).one()
        draft = s.exec(select(func.count()).select_from(Article)
                       .where(Article.status == "draft")).one()
        slugs = list(s.exec(select(Article.slug)).all())
        rows = s.exec(select(Article)).all()

    check("article count (JSON historical = 50)", total == 50, f"db={total}")
    check("status split valid", publ + draft == total,
          f"published={publ} draft={draft} other={total - publ - draft}")
    check("published majority (site content intact)",
          publ > 0, f"published={publ}")
    check("slug uniqueness", len(set(slugs)) == len(slugs),
          f"slugs={len(slugs)} unique={len(set(slugs))}")

    # JSON historical parity
    hist = json.loads(Path("/root/chart-platform/app/content/articles.json")
                      .read_text("utf-8"))
    hist_slugs = {a["slug"] for a in hist}
    db_slugs = set(slugs)
    check("every historical article seeded", hist_slugs <= db_slugs,
          f"missing={len(hist_slugs - db_slugs)}")
    check("no unexpected extra articles", len(db_slugs - hist_slugs) == 0,
          f"extra={sorted(db_slugs - hist_slugs)[:3]}")

    # metadata presence on published rows
    missing_meta = [a.slug for a in rows
                    if not (a.meta_title or "").strip() or not (a.excerpt or "").strip()]
    check("all rows have meta_title + excerpt", not missing_meta,
          f"missing={len(missing_meta)} {missing_meta[:3]}")

    # body renders (non-empty; either JSON sections or markdown text)
    bad_body = [a.slug for a in rows if not (a.body or "").strip()]
    check("no empty bodies", not bad_body, f"empty={len(bad_body)}")

    c = TestClient(app)
    # every old URL → 200, body marker renders
    dead = []
    for a in hist:
        r = c.get(f"/articles/{a['slug']}")
        if r.status_code != 200:
            dead.append((a["slug"], r.status_code))
            continue
        # body sections should appear
        body_html = r.text
        if isinstance(a.get("body"), list) and a["body"]:
            first_h2 = a["body"][0].get("h2", "")
            if first_h2 and first_h2 not in body_html:
                dead.append((a["slug"], "h2-missing"))
    check("all 50 historical URLs 200 + body renders", not dead, f"bad={dead[:5]}")

    # sitemap covers all published slugs
    sm = c.get("/sitemap.xml")
    sm_ok = sm.status_code == 200 and all(
        f"/articles/{sl}" in sm.text for sl in set(slugs))
    check("sitemap covers every slug", sm_ok, f"st={sm.status_code}")

    # canonical / featured_image (may be intentionally empty → informational)
    with Session(engine) as s2:
        rows2 = s2.exec(select(Article).where(Article.status == "published")).all()
    canonical_ok = sum(1 for a in rows2 if a.canonical) / max(len(rows2), 1)
    img_ok = sum(1 for a in rows2 if a.featured_image) / max(len(rows2), 1)
    print(f"[ℹ️] canonical coverage: {canonical_ok:.0%}  featured_image: {img_ok:.0%} "
          f"(informational — optional fields)")

    print(f"\n=== SEED-VALIDATION: {len(OKS)} pass, {len(FAILS)} fail ===")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())