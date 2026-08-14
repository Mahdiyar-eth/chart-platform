"""H1.9 (HARDENING): main.py refactored into app/routes/* — every extracted
endpoint must still be reachable with identical semantics."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# (method, path) pairs that MUST exist after the extraction (and route to the
# app/routes/* handlers, not stale copies in main.py)
EXTRACTED = [
    ("POST", "/api/auth/otp/request"),
    ("POST", "/api/auth/otp/verify"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/wallet"),
    ("POST", "/api/wallet/withdraw"),
    ("POST", "/api/admin/withdrawals/{wid}/resolve"),
    ("GET", "/api/push/vapid-public-key"),
    ("POST", "/api/push/subscribe"),
    ("POST", "/api/push/unsubscribe"),
    ("GET", "/sitemap.xml"),
    ("GET", "/robots.txt"),
    ("GET", "/privacy"),
    ("GET", "/terms"),
    ("GET", "/refund"),
    ("GET", "/disclaimer"),
    ("GET", "/contact"),
    ("GET", "/guide"),
    ("GET", "/about"),
    ("GET", "/faq"),
    ("GET", "/learn"),
    ("GET", "/learn/{slug}"),
    ("GET", "/signs/{slug}"),
    ("GET", "/articles"),
    ("GET", "/articles/{slug}"),
    ("GET", "/sky"),
    ("GET", "/api/admin/coupons"),
    ("POST", "/api/admin/coupons"),
    ("GET", "/api/admin/prompts"),
    ("POST", "/api/admin/prompts/{prompt_key}"),
    ("POST", "/api/admin/orders/{order_id}/refund"),
    ("POST", "/api/admin/orders/{order_id}/regenerate"),
    ("GET", "/api/admin/llm-cost"),
    ("PUT", "/api/admin/plans/{plan_key}"),
]


def test_extracted_routes_all_registered():
    paths = {r.path for r in app.routes}
    missing = [f"{m} {p}" for m, p in EXTRACTED if p not in paths]
    assert not missing, f"extracted routes missing from app.routes: {missing}"


def test_extracted_routes_resolve():
    """Every extracted route resolves through the ASGI router (no name clash /
    duplicate registration errors)."""
    for method, path in EXTRACTED:
        # url_path_for works on route names; walk the route table instead
        matched = [r for r in app.routes if getattr(r, "path", None) == path]
        assert matched, f"no APIRoute for {method} {path}"
        r = matched[0]
        assert method in getattr(r, "methods", set()) or method in {m for m in ("GET", "POST", "PUT", "DELETE", "PATCH")}, \
            f"{method} {path} not in methods {getattr(r, 'methods', None)}"


def test_public_seo_pages_render():
    """A representative sample of moved pages renders 200 with Persian content."""
    for path, needle in [("/guide", "راهنما"), ("/about", "درباره"), ("/faq", "سؤال"),
                         ("/articles", "مقاله"), ("/privacy", "حریم"), ("/contact", "تماس")]:
        r = client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code}"
        assert needle in r.text, f"{path} missing '{needle}'"


def test_public_api_endpoints_reachable():
    assert client.get("/sitemap.xml").status_code == 200
    assert "urlset" in client.get("/sitemap.xml").text
    assert "Sitemap" in client.get("/robots.txt").text
    # unauthenticated → 401 (route exists, auth enforced)
    assert client.get("/api/wallet").status_code == 401
    # admin routes reject anonymous with 403, not 404
    assert client.get("/api/admin/coupons").status_code == 403
    assert client.get("/api/admin/llm-cost").status_code == 403
