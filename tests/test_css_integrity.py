"""UI-FIX: a stylesheet that fails to parse is invisible to every other gate.

A single unbalanced brace in utilities.css silently dropped 355 of 658 rules
on every page of the live site for three rounds — axe, page_gate and the
interaction sweep were all green while more than half the CSS was dead.
These checks are cheap and run in normal CI (no browser required).
"""
import re
from pathlib import Path

CSS_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "css"


def _sheets():
    return sorted(CSS_DIR.glob("*.css"))


def test_every_stylesheet_has_balanced_braces():
    """An unbalanced brace makes the browser discard the rest of the file."""
    bad = []
    for f in _sheets():
        text = f.read_text(encoding="utf-8")
        opens, closes = text.count("{"), text.count("}")
        if opens != closes:
            bad.append(f"{f.name}: {{={opens} }}={closes}")
    assert not bad, "unbalanced braces (browser will drop the rest of the file): " + "; ".join(bad)


def test_no_template_interpolation_leaked_into_css():
    """`${...}` is JavaScript. In CSS it is a parse error, not a value."""
    bad = []
    for f in _sheets():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "${" in line:
                bad.append(f"{f.name}:{i}: {line.strip()[:70]}")
    assert not bad, "JS interpolation leaked into CSS: " + "; ".join(bad)


def test_every_rule_block_is_closed_on_the_line_it_opens():
    """The utility sheets are one-rule-per-line; an unclosed line is the exact
    shape of the bug that killed 58% of utilities.css."""
    bad = []
    for name in ("utilities.css", "generated.css"):
        f = CSS_DIR / name
        if not f.exists():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if not s.startswith(".") or "{" not in s:
                continue
            if s.count("{") != s.count("}"):
                bad.append(f"{name}:{i}: {s[:70]}")
    assert not bad, "rule opened but not closed on its own line: " + "; ".join(bad)


def test_chrome_ink_tokens_exist_and_are_theme_independent():
    """appbar/bottomnav/drawer are dark navy in BOTH themes, so their ink must
    come from chrome-scoped tokens — theme tokens land invisible on navy."""
    tokens = (CSS_DIR / "tokens.css").read_text(encoding="utf-8")
    for tok in ("--chrome-bg", "--chrome-ink", "--chrome-ink-active", "--chrome-border"):
        assert tok in tokens, f"{tok} missing from tokens.css"
    # they must not be redefined inside a theme block
    for block in re.findall(r'\[data-theme="[^"]+"\]\s*\{[^}]*\}', tokens):
        for tok in ("--chrome-ink:", "--chrome-ink-active:", "--chrome-bg:"):
            assert tok not in block, f"{tok} must not flip with the theme"


def test_app_chrome_is_opaque():
    """Transparency without backdrop-filter just leaks page content through a
    fixed bar. The blur was removed for scroll performance; the alpha stayed."""
    base = (CSS_DIR / "base.css").read_text(encoding="utf-8")
    for sel in (".bottomnav{", "[data-theme=\"light\"] .appbar,"):
        idx = base.find(sel)
        assert idx != -1, f"selector {sel!r} not found"
        block = base[idx:idx + 400]
        assert "rgba(20,26,58,.92)" not in block and "rgba(17,22,49,.92)" not in block, \
            f"{sel} still uses a translucent chrome surface"
