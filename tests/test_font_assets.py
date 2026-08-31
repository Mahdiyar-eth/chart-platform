"""Fonts must be the format their filename and MIME type claim.

Every Vazirmatn-*.woff2 in the repo was a byte-identical copy of the matching
.ttf — TrueType data under a .woff2 name. The cost was paid twice on every
first visit:

  * base.css lists the .woff2 first with format('woff2'), so the browser
    fetches ~123KB, fails to decode it, and falls back to the .ttf — another
    ~123KB for the same glyphs.
  * base.html preloads two of them as type="font/woff2", so the preload is
    discarded and the warmup is wasted.

Real WOFF2 is Brotli-compressed, roughly a third of the TrueType size.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FONTS = Path(__file__).resolve().parent.parent / "app" / "static" / "fonts"
WOFF2 = sorted(FONTS.glob("*.woff2"))

# WOFF2 files begin with the signature 'wOF2'; TrueType with 0x00010000 or 'true'.
WOFF2_MAGIC = b"wOF2"


def test_woff2_files_exist():
    assert WOFF2, "no .woff2 fonts found"


@pytest.mark.parametrize("f", WOFF2, ids=lambda p: p.name)
def test_woff2_is_actually_woff2(f: Path):
    head = f.read_bytes()[:4]
    assert head == WOFF2_MAGIC, (
        f"{f.name} starts with {head!r}, not {WOFF2_MAGIC!r}. It is not a WOFF2 "
        "file, so the browser rejects it and re-downloads the TrueType fallback."
    )


@pytest.mark.parametrize("f", WOFF2, ids=lambda p: p.name)
def test_woff2_is_meaningfully_smaller_than_the_ttf(f: Path):
    ttf = f.with_suffix(".ttf")
    if not ttf.is_file():
        pytest.skip("no matching .ttf")
    assert f.stat().st_size < ttf.stat().st_size * 0.75, (
        f"{f.name} ({f.stat().st_size}B) is not meaningfully smaller than "
        f"{ttf.name} ({ttf.stat().st_size}B) — it is probably a copy"
    )
