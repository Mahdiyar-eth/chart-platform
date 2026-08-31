"""Service-worker gates.

The PWA was dead code for its entire life: sw.js precached
``/static/tailwind_inline.css``, a file deleted when Tailwind was dropped.
``cache.addAll()`` is atomic — one 404 rejects the whole promise, the install
handler's waitUntil rejects, and the worker never activates.  Nothing surfaced
it, because a service worker that fails to install fails *silently*.

So: every asset the worker names must exist on disk, and the install must not
be all-or-nothing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SW = ROOT / "app" / "static" / "sw.js"
STATIC = ROOT / "app" / "static"


def _sw() -> str:
    return SW.read_text(encoding="utf-8")


def _sw_code() -> str:
    """sw.js with comments stripped — so prose about an anti-pattern doesn't
    read as the anti-pattern itself."""
    src = _sw()
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"^\s*//.*$", "", src, flags=re.M)


def _static_refs(src: str) -> list[str]:
    """Every /static/... URL the worker mentions in a string literal."""
    return sorted(set(re.findall(r'["\'](/static/[^"\']+)["\']', src)))


def test_sw_exists():
    assert SW.is_file()


@pytest.mark.parametrize("ref", _static_refs(_sw()))
def test_every_static_asset_the_worker_names_exists(ref: str):
    """Covers both the precache SHELL and the push notification icon/badge."""
    rel = ref[len("/static/"):]
    assert (STATIC / rel).is_file(), (
        f"sw.js references {ref}, which is not on disk. "
        "In the SHELL this makes install() reject and kills the whole PWA; "
        "in showNotification() it makes push notifications iconless."
    )


def test_precache_is_not_all_or_nothing():
    """A single missing/failing asset must not sink the install."""
    src = _sw_code()
    assert "addAll(" not in src, (
        "cache.addAll() is atomic — one bad entry rejects install and the "
        "worker never activates. Add entries individually and tolerate failure."
    )
    assert "allSettled" in src, "install should tolerate per-asset failure"


def test_shell_is_defined_and_nonempty():
    m = re.search(r"const\s+SHELL\s*=\s*\[(.*?)\]", _sw(), re.S)
    assert m, "SHELL precache list not found"
    assert m.group(1).strip(), "SHELL is empty"


def test_authenticated_pages_are_not_cached():
    """Caching every logged-in HTML page under a shared cache leaks one user's
    data to the next person on the device."""
    src = _sw_code()
    assert "PRIVATE" in src, (
        "the page handler must exclude authenticated/private routes from the "
        "cache instead of storing every 200 it sees"
    )
