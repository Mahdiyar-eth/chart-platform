"""R.7 / T2 (AC-2) — /glossary returns a real, linkable glossary (plan F3).

Before this round /glossary 404'd (F3 was never built). AC-2: GET /glossary →
200 · ≥60 terms · each with a #anchor · linked from other pages.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient

from app.main import app
from app.seo.glossary import build_glossary

TERM_FLOOR = 60


def test_glossary_has_at_least_60_terms():
    g = build_glossary()
    assert len(g) >= TERM_FLOOR, f"only {len(g)} terms (<{TERM_FLOOR})"
    # every term has a non-empty Persian definition
    assert all(t.get("term") and t.get("def") for t in g), [t for t in g if not (t.get("term") and t.get("def"))]


def test_glossary_terms_unique():
    seen = {}
    for t in build_glossary():
        seen[t["term"]] = seen.get(t["term"], 0) + 1
    assert all(c == 1 for c in seen.values()), [k for k, c in seen.items() if c > 1]


def test_glossary_has_links_to_published_content():
    # at least half the terms should deep-link to a real /learn, /signs, /moon, /synastry page
    g = build_glossary()
    linked = [t for t in g if t.get("link")]
    assert len(linked) >= len(g) // 2, f"only {len(linked)}/{len(g)} linked"
    assert all(l["link"].startswith(("/learn/", "/signs/", "/moon", "/synastry")) for l in linked)


def test_glossary_route_200_with_anchors():
    c = TestClient(app)
    r = c.get("/glossary")
    assert r.status_code == 200
    body = r.text
    dts = body.count("<dt")
    assert dts >= TERM_FLOOR, f"rendered {dts} terms (<{TERM_FLOOR})"
    # each term <dt> carries an id anchor
    ids = re.findall(r'<dt id="([^"]+)"', body)
    assert len(ids) >= TERM_FLOOR, f"only {len(ids)} anchors"
    # a healthy number of deep links to /learn or /signs
    inner = re.findall(r'href="(/(?:learn|signs|moon|synastry)[^"]*)"', body)
    assert len(inner) >= TERM_FLOOR // 2, f"only {len(inner)} internal content links"
    assert "واژه‌نامه" in body


def test_glossary_in_sitemap():
    c = TestClient(app)
    r = c.get("/sitemap.xml")
    assert r.status_code == 200
    assert "/glossary" in r.text
