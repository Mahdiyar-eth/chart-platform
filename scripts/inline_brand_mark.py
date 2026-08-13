#!/usr/bin/env python3
"""Inline the ZAYCHE mark into the header brand link (replaces the generic star)."""
import pathlib

ticks = "".join(
    f'<line x1="32" y1="7" x2="32" y2="12" transform="rotate({i * 30} 32 32)"/>'
    for i in range(12)
)

new_svg = (
    '<svg viewBox="0 0 64 64" aria-hidden="true">'
    '<defs><linearGradient id="zg-brand" gradientUnits="userSpaceOnUse" '
    'x1="17" y1="17" x2="47" y2="47">'
    '<stop offset="0" stop-color="#F0C75E"/><stop offset="1" stop-color="#C8901E"/>'
    '</linearGradient></defs>'
    '<circle cx="32" cy="32" r="28" fill="none" stroke="url(#zg-brand)" stroke-width="3.5"/>'
    '<circle cx="32" cy="32" r="20.5" fill="none" stroke="url(#zg-brand)" stroke-width="1" opacity="0.5"/>'
    f'<g stroke="url(#zg-brand)" stroke-width="2.2" stroke-linecap="round">{ticks}</g>'
    '<path d="M32 17 L35.8 28.2 L47 32 L35.8 35.8 L32 47 L28.2 35.8 L17 32 L28.2 28.2 Z" '
    'fill="url(#zg-brand)"/>'
    '</svg>'
)

old_svg = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>'
    '</svg>'
)

p = pathlib.Path("app/templates/base.html")
s = p.read_text()
if old_svg not in s:
    raise SystemExit("ERROR: brand star svg not found in base.html")
s = s.replace(old_svg, new_svg)
p.write_text(s)
print("brand mark inlined into base.html")
