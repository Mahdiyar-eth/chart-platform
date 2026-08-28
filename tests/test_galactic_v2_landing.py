"""Galactic v2 / Phase 1 — landing page contract.

The v2 landing exists behind a flag (`?v=2` or ZAYCHE_UI_V2=1) so the live
funnel is never at risk while the redesign is built. These tests lock:

  1. the flag resolves correctly and v1 stays the default
  2. the landing carries the pricing anchor (the whole marketing thesis)
  3. the free-chart promise and the deep-report chapters are both stated
  4. no hash classes, no un-namespaced classes leak in
  5. every static asset and sprite icon it references exists
  6. exactly one primary CTA target — the free chart — above the fold
"""
from __future__ import annotations

import pathlib
import re

from starlette.testclient import TestClient

from app.main import app

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "index_v2.html"
CSS = ROOT / "app" / "static" / "css" / "landing.css"

client = TestClient(app)


def _v2() -> str:
    r = client.get("/?v=2")
    assert r.status_code == 200
    return r.text


# ── 1. the flag ─────────────────────────────────────────────────────────
def test_v1_is_still_the_default_landing():
    """Until we flip the switch, real visitors must keep seeing v1."""
    html = client.get("/").text
    assert 'data-page="landing-v2"' not in html


def test_v2_flag_renders_the_new_shell():
    html = _v2()
    assert 'data-page="landing-v2"' in html
    assert "gx-appbar" in html and "gx-bottomnav" in html


def test_explicit_v1_beats_everything():
    assert 'data-page="landing-v2"' not in client.get("/?v=1").text


def test_referral_cookie_still_works_on_v2():
    """The flag must not break the referral funnel."""
    r = client.get("/?v=2&ref=abc123")
    assert r.status_code == 200
    assert "chart_ref" in r.cookies or "chart_ref" in r.headers.get("set-cookie", "")


# ── 2. the pricing anchor ───────────────────────────────────────────────
def test_landing_states_the_price_anchor():
    """The comparison IS the marketing argument — it must be on the page."""
    html = _v2()
    assert "astro.com" in html, "missing the external price anchor"
    assert "۷۴٫۹۰" in html or "74.90" in html, "missing astro.com's real price"
    assert "۱٬۰۰۰٬۰۰۰" in html, "missing our own price"
    assert "۱۰ اعتبار" in html, "price must be shown in credits too"


def test_dollar_rate_is_disclosed():
    """Quoting a toman equivalent without the rate would be dishonest."""
    assert "۲۰۰٬۰۰۰" in _v2(), "the dollar rate used for conversion must be stated"


# ── 3. the two promises ─────────────────────────────────────────────────
def test_free_chart_promise_is_explicit():
    html = _v2()
    assert "بدون ثبت‌نام" in html
    for promise in ("چرخ چارت تعاملی", "۷ بینش شخصی", "آسمان امروز"):
        assert promise in html, f"free-tier promise missing: {promise}"


def test_deep_report_chapters_include_the_new_four():
    """Plan §7: these four chapters are what justifies the flagship price."""
    html = _v2()
    for ch in ("باگ‌های تو", "نقشهٔ موفقیت", "۱۲ ماه پیش رو", "کارت یک‌صفحه‌ای"):
        assert ch in html, f"flagship chapter missing from landing: {ch}"


def test_sample_shows_evidence_and_action():
    """Our differentiator is astro evidence + a concrete action, not vague prose."""
    html = _v2()
    assert "شاهد نجومی" in html
    assert "راهکار" in html


# ── 4. markup hygiene ───────────────────────────────────────────────────
def test_no_hash_classes_in_v2_landing():
    hashes = re.findall(r"\b(?:u|st)-[0-9a-f]{8}\b", TPL.read_text(encoding="utf-8"))
    assert not hashes, f"hash classes leaked: {sorted(set(hashes))}"


def test_landing_classes_are_namespaced():
    html = TPL.read_text(encoding="utf-8")
    classes: set[str] = set()
    for attr in re.findall(r'class="([^"]+)"', html):
        classes.update(c for c in attr.split() if not c.startswith("{"))
    foreign = {c for c in classes if not c.startswith(("gx-", "lx-"))}
    assert not foreign, f"un-namespaced classes: {sorted(foreign)}"


def test_landing_css_obeys_the_perf_contract():
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    assert "backdrop-filter" not in css, "landing must add zero backdrop-filter"
    for m in re.finditer(r"@keyframes\s+[\w-]+\s*\{", css):
        i, depth, start = m.end(), 1, m.end()
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if not depth:
                    break
            i += 1
        block = css[start:i]
        for prop in ("width:", "height:", "box-shadow:", "filter:"):
            assert prop not in block, f"keyframe animates {prop}"


# ── 5. assets exist ─────────────────────────────────────────────────────
def test_every_sprite_icon_used_by_landing_exists():
    html = TPL.read_text(encoding="utf-8")
    sprite = (ROOT / "app" / "static" / "icons.svg").read_text(encoding="utf-8")
    have = set(re.findall(r'id="(icon-[a-z-]+)"', sprite))
    # icons referenced directly, plus those inside the Jinja tuple lists
    used = set(re.findall(r"icons\.svg#(icon-[a-z-]+)", html))
    used |= set(re.findall(r"'(icon-[a-z-]+)'", html))
    missing = sorted(used - have)
    assert not missing, f"landing references icons not in sprite: {missing}"


def test_landing_stylesheet_is_served():
    r = client.get("/static/css/landing.css")
    assert r.status_code == 200 and len(r.content) > 500


# ── 6. one clear primary action ─────────────────────────────────────────
def test_primary_cta_points_at_the_free_chart():
    html = _v2()
    primaries = re.findall(r'<a[^>]*gx-btn--primary[^>]*href="([^"]+)"', html) \
        + re.findall(r'<a[^>]*href="([^"]+)"[^>]*gx-btn--primary', html)
    assert primaries, "no primary CTA on the landing page"
    assert all(h == "/birth-form" for h in primaries), (
        f"primary CTA must always be the free chart, got: {set(primaries)}"
    )
