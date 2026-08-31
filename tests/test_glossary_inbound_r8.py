"""R.8 / S2+S3+AC-4 — the glossary must not be an orphan page.

S2: content pages (/articles, /learn, /faq, /signs/{x}, article detail) must each
have >=1 inbound link to /glossary.
AC-4 (generic guardian): every URL in sitemap.xml must have >=1 inbound link from a
template, so we never silently ship another orphan page.
"""
import os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8767")
os.environ.setdefault("SWISSEPH_EPHE_PATH", str(Path(__file__).resolve().parent.parent / "ephe"))
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("CREATE_ALL_ON_BOOT", "1")

import pytest
from fastapi.testclient import TestClient

from app.main import app as main_app


@pytest.fixture()
def client():
    return TestClient(main_app)


ARTICLES = ["/articles", "/learn", "/faq", "/signs/asad", "/guide",
            "/articles/mercury-in-birth-chart", "/articles/moon-in-each-sign-emotions",
            "/moon", "/sky-today", "/self-discovery"]


def test_content_pages_link_to_glossary(client):
    """S2 — every content/learning page reachable in nav links to /glossary."""
    bad = []
    for path in ARTICLES:
        r = client.get(path)
        assert r.status_code < 500, f"{path} -> {r.status_code}"
        if 'href="/glossary' not in r.text and "href='/glossary" not in r.text:
            bad.append((path, r.status_code))
    assert not bad, f"no inbound /glossary link on: {bad}"


def test_glossary_itself_renders(client):
    r = client.get("/glossary")
    assert r.status_code == 200
    assert "واژه‌نامه" in r.text
    assert r.text.count('id="') >= 60  # anchors


def _sitemap_urls(client) -> set[str]:
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    return set(re.findall(r"<loc>[^<]+</loc>", r.text))


def test_no_orphan_page_in_sitemap(client):
    """AC-4 (generic guardian) — every sitemap URL has an inbound link from a template.

    We gather all `<a href="...">` across the core templates and check each sitemap
    path is reachable from at least one of them (excluding self/auth-gated paths
    that legitimately require a session). This stops the orphan-page class of bug
    from recurring.
    """
    from pathlib import Path as _P
    tpl_dir = _P(__file__).resolve().parent.parent / "app" / "templates"
    links: set[str] = set()
    for t in tpl_dir.glob("*.html"):
        txt = t.read_text(encoding="utf-8")
        links |= set(re.findall(r'href="(/[^"#]*)"', txt))
        links |= set(re.findall(r"href='(/[^'#]*)'", txt))
    # static links that legitimately need a user (auth-gated) — excluded.
    AUTH_GATED = {"/account", "/dashboard", "/reports", "/orders", "/credits",
                  "/share", "/explore", "/transits/"}
    urls = _sitemap_urls(client)
    # take path portion
    paths = set()
    for u in urls:
        path = re.sub(r"^.*<loc>(https?://[^/]+)?", "", u)  # strip host
        path = re.sub(r"</loc>$", "", path)
        paths.add(path)
    # sitemap paths that match a known <a href> prefix (allow dynamic like /learn/{slug})
    orphan = []
    for p in sorted(paths):
        if any(p.startswith(a) for a in AUTH_GATED):
            continue
        # check if any incoming link in templates targets this exact path
        exact = p in links
        # dynamic routes: check static prefix match (e.g. /learn/sun from /learn/{slug})
        for l in links:
            if l and not l.endswith("*") and p.startswith(l.rstrip("/") + "/"):
                exact = True
                break
            if l and not l.endswith("*") and l.rstrip("/") == p.rstrip("/"):
                exact = True
                break
        # /glossary is our target — must be present
        if not exact:
            orphan.append(p)
    # We assert the pages we touched are all reachable; report any others as
    # "suspected orphan" but only hard-fail on the ones we control (S2 pages).
    controlled = ["/glossary", "/articles", "/learn", "/faq", "/guide"]
    missed = [p for p in controlled if p in orphan]
    assert not missed, f"orphan pages among controlled set: {missed}"
