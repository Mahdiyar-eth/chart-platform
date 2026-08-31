"""Every icon the app asks for must exist in the sprite.

A <use> pointing at a symbol that does not exist renders nothing at all — no
error, no console warning, no fallback. icon-grid and icon-star were missing,
which meant the "چارت من" FAB and the "کاوش" tab in the bottom bar were an
empty gold circle and a bare label for every returning user. That is the whole
primary navigation for anyone who already has a chart.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPRITE = ROOT / "app" / "static" / "icons.svg"


def _available() -> set[str]:
    return set(re.findall(r'<symbol[^>]*id="([^"]+)"', SPRITE.read_text(encoding="utf-8")))


def _referenced() -> set[str]:
    """Every literal sprite reference. Jinja-interpolated names are skipped —
    those are covered by the nav test below."""
    out: set[str] = set()
    for d in ("templates", "static"):
        for f in (ROOT / "app" / d).rglob("*"):
            if f.suffix not in (".html", ".js", ".css") or not f.is_file():
                continue
            for m in re.finditer(r'icons\.svg[^"\']*#([a-z0-9][a-z0-9-]*)(.)',
                                 f.read_text(encoding="utf-8")):
                # skip Jinja-interpolated names like #icon-{{ card.icon }} —
                # those are data-driven and cannot be resolved statically
                if m.group(2) == "{":
                    continue
                out.add(m.group(1))
    return out


def test_sprite_is_valid_xml():
    import xml.etree.ElementTree as ET
    ET.parse(SPRITE)


@pytest.mark.parametrize("name", sorted(_referenced()))
def test_referenced_icon_exists(name: str):
    assert name in _available(), (
        f"{name} is referenced but not in icons.svg — a <use> pointing at a "
        "missing symbol renders nothing, silently"
    )


def test_every_nav_icon_exists():
    """nav.py names icons by string; they are interpolated into the sprite URL
    at render time, so a typo there is invisible until someone looks at the
    tab bar."""
    from app.nav import NAV_ITEMS
    have = _available()
    missing = sorted({n.icon for n in NAV_ITEMS if n.icon and n.icon not in have})
    assert not missing, (
        f"nav icons missing from the sprite: {missing} — these tabs render "
        "with a label and no icon"
    )
