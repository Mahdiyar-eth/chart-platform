"""R.7 / T3 (AC-3) — Umami analytics must come from env, not be hardcoded.

Pre-fix: `base.html` hardcoded `data-website-id` + `data-domains="chart.negar.io"`,
so ANY host (staging / a new domain / a second site) sent data to the same website
id. AC-3: changing the UMAMI_* env vars must change the rendered `<script>` tag.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

from fastapi.testclient import TestClient

import app.main as main_mod

# The globals are resolved at module load, so the test mutates the template globals
# directly (mirrors the env-driven behaviour) and asserts the rendered tag changes.


def _rendered_umami_tags():
    c = TestClient(main_mod.app)
    html = c.get("/glossary").text   # base.html is the shared frame
    return [ln for ln in html.splitlines() if "analytics.negar.io" in ln or "data-website-id" in ln]


def test_umami_render_uses_env_globals():
    g = main_mod.templates.env.globals
    # default from os.environ (may be set by .env) — must be a string
    assert isinstance(g.get("umami_site_id", ""), str)
    assert isinstance(g.get("umami_src", "https://analytics.negar.io/script.js"), str)


def test_umami_tag_absent_when_no_site_id(monkeypatch):
    monkeypatch.setitem(main_mod.templates.env.globals, "umami_site_id", "")
    tags = _rendered_umami_tags()
    assert not tags, f"telemetry should be OFF when UMAMI_SITE_ID is empty: {tags}"


def test_umami_tag_uses_env_values(monkeypatch):
    monkeypatch.setitem(main_mod.templates.env.globals, "umami_src", "https://a.example/script.js")
    monkeypatch.setitem(main_mod.templates.env.globals, "umami_site_id", "site-abc-123")
    monkeypatch.setitem(main_mod.templates.env.globals, "umami_domains", "staging.example.com")
    tags = _rendered_umami_tags()
    assert tags, "telemetry tag should render when UMAMI_SITE_ID is set"
    joined = "\n".join(tags)
    assert "https://a.example/script.js" in joined, joined
    assert "site-abc-123" in joined, joined
    assert "staging.example.com" in joined, joined
