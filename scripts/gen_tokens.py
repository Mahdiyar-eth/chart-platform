#!/usr/bin/env python3
"""Generate app/static/css/tokens-v2.css from app/static/design-tokens.json.

Single source of truth: the JSON. The same JSON is consumed by a future native
app (React Native / Flutter), so the CSS is a DERIVED artifact — never hand-edit
tokens-v2.css, edit the JSON and re-run this script.

Usage:  venv/bin/python scripts/gen_tokens.py
Verify: git diff --exit-code app/static/css/tokens-v2.css   (in CI)
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "static" / "design-tokens.json"
OUT = ROOT / "app" / "static" / "css" / "tokens-v2.css"


def hsl_triplet(v: dict) -> str:
    """{h,s,l} -> '228 62% 7%' so CSS can do hsl(var(--x) / .5)."""
    return f"{v['h']} {v['s']}% {v['l']}%"


def resolve(value: str, prim_colors: dict) -> str:
    """A semantic value is either a primitive name or a literal CSS colour."""
    if isinstance(value, str) and value in prim_colors:
        return f"hsl(var(--c-{value}))"
    return value


def build() -> str:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    prim = data["primitive"]
    sem = data["semantic"]
    comp = data["component"]
    colors = prim["color"]

    L: list[str] = []
    add = L.append

    add("/* ══════════════════════════════════════════════════════════════")
    add(f" *  {data['_meta']['name']} v{data['_meta']['version']} — GENERATED FILE")
    add(" *  Source: app/static/design-tokens.json")
    add(" *  Regenerate: venv/bin/python scripts/gen_tokens.py")
    add(" *  DO NOT EDIT BY HAND — your changes will be overwritten.")
    add(" * ══════════════════════════════════════════════════════════════ */")
    add("")

    # ── layer 1: primitives ──────────────────────────────────────────────
    add(":root{")
    add("  /* ---- primitive: colour (HSL triplets for alpha compositing) ---- */")
    for name, v in colors.items():
        add(f"  --c-{name}: {hsl_triplet(v)};")

    add("")
    add("  /* ---- primitive: space (8pt) ---- */")
    for k, v in prim["space"].items():
        add(f"  --sp-{k}: {v}px;")

    add("")
    add("  /* ---- primitive: radius ---- */")
    for k, v in prim["radius"].items():
        add(f"  --r-{k}: {v}px;")

    add("")
    add("  /* ---- primitive: type ---- */")
    f = prim["font"]
    add(f"  --font-fa: {f['family-fa']};")
    add(f"  --font-num: {f['family-num']};")
    for k, v in f["size"].items():
        add(f"  --fs-{k}: {v}rem;")
    for k, v in f["weight"].items():
        add(f"  --fw-{k}: {v};")
    for k, v in f["leading"].items():
        add(f"  --lh-{k}: {v};")

    add("")
    add("  /* ---- primitive: motion ---- */")
    for k, v in prim["duration"].items():
        add(f"  --dur-{k}: {v}ms;")
    for k, v in prim["ease"].items():
        add(f"  --ease-{k}: {v};")

    add("")
    add("  /* ---- primitive: z-index ---- */")
    for k, v in prim["z"].items():
        add(f"  --z-{k}: {v};")

    add("")
    add("  /* ---- component ---- */")
    for k, v in comp["btn"]["height"].items():
        add(f"  --btn-h-{k}: {v}px;")
    add(f"  --appbar-h: {comp['appbar']['height']}px;")
    add(f"  --bottomnav-h: {comp['bottomnav']['height']}px;")
    add(f"  --progress-h: {comp['progress']['track-height']}px;")
    add(f"  --input-h: {comp['input']['height']}px;")
    add(f"  --touch-min: {comp['touch']['min']}px;")
    add(f"  --modal-backdrop: {comp['modal']['backdrop']};")

    add("")
    add("  /* ---- chrome (identical in both themes, by design) ---- */")
    for k, v in sem["chrome"].items():
        if k.startswith("_"):
            continue
        add(f"  --chrome-{k}: {v};")
    add("}")
    add("")

    # ── layer 2: semantic (dark default) ─────────────────────────────────
    add("/* ---- semantic: DARK is the default (deep-space product) ---- */")
    add(":root{")
    for k, v in sem["dark"].items():
        add(f"  --{k}: {resolve(v, colors)};")
    add("}")
    add("")

    add("/* ---- semantic: LIGHT ---- */")
    add('[data-theme="light"]{')
    for k, v in sem["light"].items():
        add(f"  --{k}: {resolve(v, colors)};")
    add("}")
    add("")

    # ── motion guard ─────────────────────────────────────────────────────
    add("/* ---- accessibility: honour reduced-motion globally ---- */")
    add("@media (prefers-reduced-motion: reduce){")
    add("  :root{ --dur-fast:1ms; --dur-base:1ms; --dur-slow:1ms; --dur-slower:1ms; }")
    add("  *,*::before,*::after{ animation-duration:1ms !important; animation-iteration-count:1 !important;")
    add("    transition-duration:1ms !important; scroll-behavior:auto !important; }")
    add("}")
    add("")

    return "\n".join(L) + "\n"


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: missing {SRC}", file=sys.stderr)
        return 1
    css = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(css, encoding="utf-8")
    n_vars = css.count("  --")
    print(f"OK: wrote {OUT.relative_to(ROOT)} ({len(css)} bytes, {n_vars} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
