"""G12 (§61) — city SEO pages: render, 404, flag-gate, sitemap entry."""
from fastapi.testclient import TestClient

from app.main import app


def test_city_page_renders():
    c = TestClient(app)
    r = c.get("/birth-chart/tehran")
    assert r.status_code == 200
    assert "تهران" in r.text and "طالع" in r.text


def test_city_page_unknown_slug_404():
    c = TestClient(app)
    assert c.get("/birth-chart/atlantis").status_code == 404


def test_city_page_flag_gated(monkeypatch):
    monkeypatch.setattr("app.feature_flags.flag", lambda name, default="on": False)
    c = TestClient(app)
    assert c.get("/birth-chart/tehran").status_code == 404


def test_sitemap_includes_cities():
    c = TestClient(app)
    xml = c.get("/sitemap.xml").text
    assert "/birth-chart/tehran" in xml and "/birth-chart/mashhad" in xml
