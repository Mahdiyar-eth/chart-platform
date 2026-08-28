"""Galactic v2 / Phase 0 — the design-system contract.

These lock the decisions that the redesign is built on, so a later edit cannot
quietly undo them:

  1. tokens-v2.css is GENERATED — it must match design-tokens.json exactly
  2. the performance rule: backdrop-filter appears at most twice in galactic.css
     and never on a scrolling surface (.gx-card)
  3. animation is restricted to transform/opacity on the shell
  4. the shell has no machine-generated hash classes (u-xxxxxxx / st-xxxxxxx)
  5. touch targets meet the 44px floor
  6. PWA assets referenced by the shell actually exist on disk
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKENS_JSON = ROOT / "app" / "static" / "design-tokens.json"
TOKENS_CSS = ROOT / "app" / "static" / "css" / "tokens-v2.css"
SHELL_CSS = ROOT / "app" / "static" / "css" / "galactic.css"
SHELL_HTML = ROOT / "app" / "templates" / "base_v2.html"
SHELL_JS = ROOT / "app" / "static" / "js" / "galactic.js"


# ── 1. generated file is in sync ────────────────────────────────────────
def test_tokens_css_is_regenerated_from_json():
    """`tokens-v2.css` is derived. If someone hand-edits it, this fails."""
    before = TOKENS_CSS.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_tokens.py")],
                   cwd=ROOT, check=True, capture_output=True)
    after = TOKENS_CSS.read_text(encoding="utf-8")
    assert before == after, (
        "tokens-v2.css is out of sync with design-tokens.json — "
        "run: venv/bin/python scripts/gen_tokens.py"
    )


def test_design_tokens_json_is_valid_and_portable():
    """The JSON is the contract a future native app will consume."""
    data = json.loads(TOKENS_JSON.read_text(encoding="utf-8"))
    for key in ("primitive", "semantic", "component", "motion"):
        assert key in data, f"missing top-level token layer: {key}"
    assert {"dark", "light", "chrome"} <= set(data["semantic"])
    # every semantic colour name must exist in both themes (no half-theme)
    dark = {k for k in data["semantic"]["dark"] if not k.startswith("_")}
    light = {k for k in data["semantic"]["light"] if not k.startswith("_")}
    assert dark == light, f"theme mismatch: {dark ^ light}"


# ── 2 & 3. the performance contract ─────────────────────────────────────
def test_backdrop_filter_is_rationed():
    """Old scroll jank came from backdrop-filter on every glass card.

    v2 allows it on the appbar and the modal only.
    """
    css = SHELL_CSS.read_text(encoding="utf-8")
    hits = re.findall(r"^\s*(?:-webkit-)?backdrop-filter\s*:", css, re.MULTILINE)
    assert len(hits) <= 2, f"backdrop-filter used {len(hits)}x — max 2 (appbar, modal)"


def _strip_comments(css: str) -> str:
    """Drop /* … */ so a comment mentioning a property is not a false positive."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _rule_body(css: str, selector: str) -> str:
    """Return the declaration block for an exact top-level selector.

    A naive `\\{(.*?)\\}` regex over-matches, because CSS declarations contain
    no braces but at-rules do. Scan forward and balance braces instead.
    """
    pat = re.compile(r"(?m)^\s*" + re.escape(selector) + r"\s*\{")
    m = pat.search(css)
    assert m, f"{selector} rule not found"
    i = m.end()
    depth = 1
    out = []
    while i < len(css) and depth:
        ch = css[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if not depth:
                break
        out.append(ch)
        i += 1
    return "".join(out)


def test_scrolling_card_has_no_backdrop_filter():
    css = _strip_comments(SHELL_CSS.read_text(encoding="utf-8"))
    body = _rule_body(css, ".gx-card")
    assert "backdrop-filter" not in body, (
        ".gx-card must never use backdrop-filter — that is the scroll-perf bug"
    )


def test_keyframes_only_animate_transform_and_opacity():
    """Animating width/filter/box-shadow forces layout or paint every frame."""
    css = _strip_comments(SHELL_CSS.read_text(encoding="utf-8"))
    banned = ("filter:", "box-shadow:", "width:", "height:", "top:", "inset:")
    for m in re.finditer(r"@keyframes\s+[\w-]+\s*\{", css):
        i = m.end()
        depth = 1
        start = i
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if not depth:
                    break
            i += 1
        block = css[start:i]
        for prop in banned:
            assert prop not in block, (
                f"keyframe {m.group(0)!r} animates {prop} — use transform/opacity"
            )


# ── 4. no hash classes in the new shell ─────────────────────────────────
def test_shell_has_no_machine_generated_hash_classes():
    html = SHELL_HTML.read_text(encoding="utf-8")
    hashes = re.findall(r'\b(?:u|st)-[0-9a-f]{8}\b', html)
    assert not hashes, f"hash classes leaked into the v2 shell: {sorted(set(hashes))}"


def test_shell_classes_are_namespaced():
    """Every new class carries the gx- prefix so v1 and v2 can coexist."""
    html = SHELL_HTML.read_text(encoding="utf-8")
    classes: set[str] = set()
    for attr in re.findall(r'class="([^"]+)"', html):
        classes.update(attr.split())
    allowed_foreign = {"gx-sr"}  # utility already namespaced
    foreign = {c for c in classes
               if not c.startswith("gx-") and c not in allowed_foreign}
    assert not foreign, f"un-namespaced classes in v2 shell: {sorted(foreign)}"


# ── 5. touch targets ────────────────────────────────────────────────────
def test_interactive_elements_meet_44px_floor():
    css = SHELL_CSS.read_text(encoding="utf-8")
    assert "--touch-min" in css or "var(--touch-min)" in css
    for sel in (".gx-iconbtn", ".gx-drawer-item", ".gx-bn-item"):
        m = re.search(re.escape(sel) + r"\s*\{(.*?)\}", css, re.DOTALL)
        assert m, f"{sel} rule missing"
        body = m.group(1)
        assert "var(--touch-min)" in body or "min-height" in body, (
            f"{sel} has no explicit touch target"
        )


# ── 6. PWA assets referenced by the shell exist ─────────────────────────
def test_shell_static_references_exist_on_disk():
    html = SHELL_HTML.read_text(encoding="utf-8")
    refs = set(re.findall(r'(?:href|src)="(/static/[^"?#]+)', html))
    missing = [r for r in refs if not (ROOT / "app" / r.lstrip("/")).exists()]
    assert not missing, f"shell references missing static files: {missing}"


def test_shell_declares_ios_and_android_install_surface():
    html = SHELL_HTML.read_text(encoding="utf-8")
    for needle in ("manifest.webmanifest", "apple-touch-icon",
                   "apple-mobile-web-app-capable", "viewport-fit=cover"):
        assert needle in html, f"PWA shell is missing: {needle}"
    js = SHELL_JS.read_text(encoding="utf-8")
    assert "beforeinstallprompt" in js, "no Android install hook"
    assert "navigator.standalone" in js, "no iOS standalone detection"
    assert "serviceWorker" in js, "service worker never registered"


def test_icons_used_by_nav_exist_in_sprite():
    """A <use href="#icon-x"> pointing at nothing renders an invisible button."""
    from app.nav import NAV_ITEMS
    sprite = (ROOT / "app" / "static" / "icons.svg").read_text(encoding="utf-8")
    have = set(re.findall(r'id="(icon-[a-z-]+)"', sprite))
    needed = {i.icon for i in NAV_ITEMS if i.icon}
    missing = sorted(needed - have)
    assert not missing, f"nav references icons not in the sprite: {missing}"
