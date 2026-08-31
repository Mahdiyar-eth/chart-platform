"""Typographic discipline.

Measured on the landing page at a 390px viewport before this gate existed:
body copy at 16.8px with a 33.6px line box — a leading ratio of 2.00 — and a
landing page 5805px tall, 6.9 full screens. Persian script does need more
leading than Latin (Vazirmatn reads well around 1.75-1.8), but 2.0 to 2.2 is
past comfortable and into sparse: barely three elements fit above the fold and
the page reads like a low-vision accessibility mode rather than a product.

These are ceilings, not targets. Headings may be tighter; nothing should be
looser.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "css"
SHEETS = sorted(CSS_DIR.glob("*.css"))

# Comfortable maximum for Persian body copy.
MAX_LEADING = 1.85


def _without_at_rules(src: str) -> str:
    """Drop @media / @supports bodies.

    A rule inside a media query is *meant* to override the base rule — that is
    what media queries are for — so those overrides are not conflicts.
    """
    out, i, n = [], 0, len(src)
    while i < n:
        at = src.find("@", i)
        if at == -1:
            out.append(src[i:])
            break
        brace = src.find("{", at)
        if brace == -1:
            out.append(src[i:])
            break
        head = src[at:brace]
        if not any(k in head for k in ("media", "supports", "container", "layer")):
            out.append(src[i:brace + 1])
            i = brace + 1
            continue
        out.append(src[i:at])
        depth, j = 1, brace + 1
        while j < n and depth:
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
            j += 1
        i = j
    return "".join(out)


def _leadings(path: Path):
    """(line number, value) for every unitless line-height in the sheet."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in re.finditer(r"line-height:\s*([0-9]*\.?[0-9]+)\s*[;}]", line):
            out.append((n, float(m.group(1))))
    return out


@pytest.mark.parametrize("sheet", SHEETS, ids=lambda p: p.name)
def test_no_cavernous_leading(sheet: Path):
    bad = [(n, v) for n, v in _leadings(sheet) if v > MAX_LEADING]
    assert not bad, (
        f"{sheet.name}: {len(bad)} rule(s) with leading above {MAX_LEADING} — "
        f"text this loose reads as sparse, not readable: {bad[:6]}"
    )


@pytest.mark.parametrize("sheet", SHEETS, ids=lambda p: p.name)
def test_leading_is_never_below_one(sheet: Path):
    """A unitless value under 1 is almost always a typo for a px value."""
    bad = [(n, v) for n, v in _leadings(sheet) if 0 < v < 1]
    assert not bad, f"{sheet.name}: leading below 1.0 clips glyphs: {bad[:5]}"


def test_no_class_sets_one_property_to_two_values_across_sheets():
    """The later sheet wins silently, so editing the earlier one does nothing.

    Declarations merge across sheets, so a class appearing twice is not by
    itself a problem. The trap is the same *property* set to different values
    in two sheets: .btn-lg had font-size in both base.css and components.css,
    components.css loads second, and changing base.css's value had no visible
    effect at all — which is exactly how an afternoon disappears.
    """
    # class -> property -> (value, sheet)
    seen: dict[str, dict[str, tuple[str, str]]] = {}
    conflicts: list[str] = []
    for sheet in SHEETS:
        src = _without_at_rules(sheet.read_text(encoding="utf-8"))
        for m in re.finditer(r"^\s*(\.[a-zA-Z][\w-]*)\s*\{([^}]*)\}", src, re.M):
            cls, body = m.group(1), m.group(2)
            props = seen.setdefault(cls, {})
            for decl in body.split(";"):
                if ":" not in decl:
                    continue
                k, _, v = decl.partition(":")
                k, v = k.strip(), v.strip()
                if not k or k.startswith("--"):
                    continue
                if k in props and props[k][1] != sheet.name and props[k][0] != v:
                    conflicts.append(
                        f"{cls} {{{k}}}: {props[k][0]!r} in {props[k][1]} vs "
                        f"{v!r} in {sheet.name}")
                else:
                    props.setdefault(k, (v, sheet.name))
    assert not conflicts, (
        "a class sets the same property to different values in two "
        "stylesheets; only the later one takes effect:\n"
        + "\n".join(sorted(set(conflicts))[:12])
    )
