"""C1 — design-system extraction acceptance tests."""
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSS_DIR = BASE_DIR / "app" / "static" / "css"
TPL = (BASE_DIR / "app" / "templates" / "base.html").read_text(encoding="utf-8")

CSS_FILES = ["tokens.css", "base.css", "components.css"]


def _css_text():
    return {f: (CSS_DIR / f).read_text(encoding="utf-8") for f in CSS_FILES}


def test_css_files_exist_and_are_linked():
    for f in CSS_FILES:
        assert (CSS_DIR / f).exists(), f"{f} missing"
        assert f"/static/css/{f}?v=" in TPL, f"{f} not linked from base.html"


def test_no_physical_properties_in_css():
    # greedy left/right spacing/alignment must not appear in any css file
    pat = re.compile(r"margin-(left|right)|padding-(left|right)|text-align:\s*(left|right)")
    for f, text in _css_text().items():
        assert not pat.search(text), f"physical property found in {f}"


def test_no_hardcoded_hex_outside_tokens():
    # hex colors allowed ONLY in tokens.css (single source of truth)
    for f, text in _css_text().items():
        if f == "tokens.css":
            continue
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", text), f"hardcoded hex in {f}"


def test_tokens_cover_all_var_usages():
    tokens = _css_text()["tokens.css"]
    defined = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    used = set()
    for f in ["base.css", "components.css"]:
        used |= set(re.findall(r"var\((--[\w-]+)\)", _css_text()[f]))
    assert not (used - defined), "undefined var() tokens break styling"


def test_pages_still_return_200():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        for url in ["/", "/birth-form", "/account/login", "/admin/login", "/plans"]:
            r = client.get(url)
            assert r.status_code == 200, f"{url} -> {r.status_code}"
