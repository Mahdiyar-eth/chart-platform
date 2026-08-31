"""REDESIGN-MASTER W1.4 — /design-system styleguide gate.

- dev/QA: 200 and renders the token names
- prod: 404 (the library never ships as a public page)
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient

from app.main import app


def test_design_system_renders_in_dev():
    c = TestClient(app)
    r = c.get("/design-system")
    assert r.status_code == 200, r.text
    body = r.text
    for token in ("--font-size-xl", "--space-4", "دیزاین‌سیستم"):
        assert token in body, f"styleguide missing {token}"


def test_design_system_hidden_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    c = TestClient(app)
    r = c.get("/design-system")
    assert r.status_code == 404
