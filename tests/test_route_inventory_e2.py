"""E2 — route inventory regression: every template href resolves to a real route.

Guards against 404 links sneaking into nav/footer/articles (the /signs/* class of bug).
"""
import re
from pathlib import Path
from app.main import app

TPL = Path(__file__).resolve().parent.parent / "app" / "templates"


def _routed_paths():
    paths = set()
    for r in app.routes:
        p = getattr(r, "path", "")
        if p.startswith("/static"):
            continue  # served by StaticFiles mount
        if "{" in p:
            paths.add(p.split("{")[0].rstrip("/"))  # dynamic prefix
        else:
            paths.add(p)
    return paths


def test_every_template_href_resolves():
    routed = _routed_paths()
    hrefs = set()
    for f in TPL.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r'href="(/[^"#?{}]*)"', s):
            u = m.group(1)
            if (u.startswith("//") or "{{" in u or u.startswith("/http")
                    or u.startswith("/static/")):
                continue  # static assets served by StaticFiles mount
            hrefs.add(u.split(";")[0])
    broken = []
    for u in sorted(hrefs):
        if u in routed:
            continue
        # allow dynamic prefixes (/chat/<id>, /signs/<slug>, ...)
        if any(u == p or u.startswith(p + "/") for p in routed if not p.endswith(".") ):
            continue
        broken.append(u)
    assert not broken, f"template links with no matching route: {broken}"


def test_nav_registry_urls_all_routed():
    from app.nav import NAV_ITEMS
    routed = _routed_paths()
    missing = [i.url for i in NAV_ITEMS if i.url not in routed]
    assert not missing, f"nav items pointing at unrouted pages: {missing}"
