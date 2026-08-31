"""The app shell: client-side navigation, transitions, install, safe areas.

htmx 1.9.12 has been vendored and loaded on every page since the PWA work, and
used by exactly nothing — zero hx-* attributes in 47 templates, 48KB of dead
weight on every request. Turning it on is what makes navigation feel like an
app instead of a website: no white flash, no chrome repaint, a real transition
between pages, and a progress indicator during the fetch.

Two hazards this gates against:

  * hx-boost boosts forms as well as links. Alpine's @submit.prevent does not
    stop htmx's own submit listener, so a boosted Alpine form would submit
    twice — once via fetch() and once via htmx. Every form must opt out.
  * swapping <body> wholesale would re-run base.html's scripts on every
    navigation, stacking the /readiness setInterval and every other listener.
    The swap is scoped to #app-main so the chrome is never re-executed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates"
CSS = ROOT / "app" / "static" / "css"
BASE = (TPL / "base.html").read_text(encoding="utf-8")
ALL_TPL = sorted(TPL.rglob("*.html"))


def _css() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in CSS.glob("*.css"))


# ── client-side navigation ───────────────────────────────────────────────────
def test_body_is_boosted():
    assert re.search(r'<body[^>]*hx-boost="true"', BASE), (
        "hx-boost is not enabled, so every navigation is still a full page "
        "reload with a white flash"
    )


def test_swap_is_scoped_to_the_content_region():
    """Never swap <body> — base.html's scripts would re-run on every nav."""
    body = re.search(r"<body[^>]*>", BASE).group(0)
    assert 'hx-target="#app-main"' in body, "swap target is not scoped"
    assert 'hx-select="#app-main"' in body, "response is not filtered to the content"
    assert 'id="app-main"' in BASE, "#app-main container missing"


def test_content_block_lives_inside_app_main():
    m = re.search(r'<main[^>]*id="app-main"[^>]*>(.*?)</main>', BASE, re.S)
    assert m, "#app-main is not a <main> wrapping the content"
    assert "{% block content %}" in m.group(1), (
        "the content block is not inside #app-main, so nothing would swap"
    )


def test_swap_requests_a_view_transition():
    body = re.search(r"<body[^>]*>", BASE).group(0)
    assert "transition:true" in body, (
        "htmx swap does not request a View Transition, so pages pop instead "
        "of animating"
    )


@pytest.mark.parametrize("tpl", ALL_TPL, ids=lambda p: p.name)
def test_every_form_opts_out_of_boost(tpl: Path):
    """A boosted Alpine form submits twice: once by fetch, once by htmx."""
    for m in re.finditer(r"<form\b[^>]*>", tpl.read_text(encoding="utf-8")):
        assert 'hx-boost="false"' in m.group(0), (
            f"{tpl.name}: form is not exempt from hx-boost -> double submit\n"
            f"  {m.group(0)[:120]}"
        )


# ── transitions ──────────────────────────────────────────────────────────────
def test_view_transition_css_exists():
    css = _css()
    assert "::view-transition" in css or "@view-transition" in css, (
        "no View Transition styling — the swap would be instantaneous"
    )


def test_transitions_respect_reduced_motion():
    css = _css()
    assert "prefers-reduced-motion" in css, (
        "motion must be disabled for users who ask for it"
    )


# ── navigation progress ──────────────────────────────────────────────────────
def test_navigation_progress_bar_exists():
    assert 'id="navProgress"' in BASE, (
        "no cross-page progress indicator — with client-side nav the user gets "
        "no feedback at all that a page is loading"
    )


def test_progress_bar_is_driven_by_htmx_events():
    for ev in ("htmx:beforeRequest", "htmx:afterRequest"):
        assert ev in BASE, f"{ev} is not wired to the navigation progress bar"


def test_active_nav_is_recalculated_after_swap():
    """Highlighting ran once on DOMContentLoaded; with client-side nav that
    fires only on the first page, so the active tab would never move."""
    assert "htmx:afterSwap" in BASE or "htmx:afterSettle" in BASE, (
        "nav highlighting is not refreshed after a client-side navigation"
    )


# ── installable app ──────────────────────────────────────────────────────────
def test_install_prompt_is_captured():
    assert "beforeinstallprompt" in BASE, (
        "the browser's install prompt is never captured, so the site can "
        "never be installed as an app from a button"
    )


def test_standalone_mode_is_detectable():
    css = _css() + BASE
    assert "display-mode: standalone" in css or "display-mode:standalone" in css, (
        "nothing adapts when the app runs installed (standalone)"
    )


# ── iOS safe areas ───────────────────────────────────────────────────────────
def test_bottom_nav_respects_the_home_indicator():
    css = _css()
    assert "safe-area-inset-bottom" in css, (
        "the bottom nav would sit under the iOS home indicator"
    )


def test_viewport_covers_the_notch():
    assert "viewport-fit=cover" in BASE, (
        "without viewport-fit=cover the safe-area insets are always zero and "
        "the app letterboxes on notched iPhones"
    )


# ── icons ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tpl", ALL_TPL, ids=lambda p: p.name)
def test_no_fragment_only_icon_references(tpl: Path):
    """<use href="#icon-x"> resolves against the CURRENT document.

    The sprite is an external file (app/static/icons.svg), so fragment-only
    references matched nothing and every nav icon rendered at 0x0 — 22 of them
    across the top nav, drawer, bottom nav and the FAB. Text-only tabs looked
    deliberate enough that it survived several visual reviews.
    """
    src = tpl.read_text(encoding="utf-8")
    bad = re.findall(r'<use[^>]*href="#[^"]*"', src)
    assert not bad, (
        f"{tpl.name}: fragment-only sprite reference(s) render nothing: {bad[:3]}"
    )
