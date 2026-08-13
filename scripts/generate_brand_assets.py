#!/usr/bin/env python3
"""Generate the ZAYCHE (زایچه) brand mark as SVG + PNG icons.

Mark: a birth-chart wheel — gold ring, 12 house ticks, central 4-point star.
Outputs:
  app/static/favicon.svg     — mark only (favicon)
  app/static/logo.svg        — mark + wordmark (for og:image / brand use)
  app/static/icon-192.png    — PWA icon (via rsvg-convert)
  app/static/icon-512.png    — PWA icon
"""
import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "app" / "static"

GOLD_A = "#F0C75E"
GOLD_B = "#C8901E"
INDIGO = "#1B1236"

def ticks() -> str:
    out = []
    for i in range(12):
        out.append(
            f'    <line x1="32" y1="7" x2="32" y2="12" transform="rotate({i * 30} 32 32)"/>'
        )
    return "\n".join(out)

mark = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="زایچه">
  <defs>
    <linearGradient id="zgold" gradientUnits="userSpaceOnUse" x1="17" y1="17" x2="47" y2="47">
      <stop offset="0" stop-color="{GOLD_A}"/>
      <stop offset="1" stop-color="{GOLD_B}"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="28" fill="none" stroke="url(#zgold)" stroke-width="3.5"/>
  <circle cx="32" cy="32" r="20.5" fill="none" stroke="url(#zgold)" stroke-width="1" opacity="0.5"/>
  <g stroke="url(#zgold)" stroke-width="2.2" stroke-linecap="round">
{ticks()}
  </g>
  <path d="M32 17 L35.8 28.2 L47 32 L35.8 35.8 L32 47 L28.2 35.8 L17 32 L28.2 28.2 Z" fill="url(#zgold)"/>
</svg>'''

logo = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 64" role="img" aria-label="زایچه">
  <defs>
    <linearGradient id="zgold" gradientUnits="userSpaceOnUse" x1="17" y1="17" x2="47" y2="47">
      <stop offset="0" stop-color="{GOLD_A}"/>
      <stop offset="1" stop-color="{GOLD_B}"/>
    </linearGradient>
  </defs>
  <g transform="translate(0,0)">
    <circle cx="32" cy="32" r="28" fill="none" stroke="url(#zgold)" stroke-width="3.5"/>
    <circle cx="32" cy="32" r="20.5" fill="none" stroke="url(#zgold)" stroke-width="1" opacity="0.5"/>
    <g stroke="url(#zgold)" stroke-width="2.2" stroke-linecap="round">
{ticks()}
    </g>
    <path d="M32 17 L35.8 28.2 L47 32 L35.8 35.8 L32 47 L28.2 35.8 L17 32 L28.2 28.2 Z" fill="url(#zgold)"/>
  </g>
  <text x="76" y="41" font-family="Vazirmatn, 'Noto Naskh Arabic', Tahoma, sans-serif" font-size="26" font-weight="700" fill="{GOLD_A}">زایچه</text>
  <text x="76" y="56" font-family="Vazirmatn, 'Noto Naskh Arabic', Tahoma, sans-serif" font-size="11" fill="#C9C0E0" letter-spacing="2">ZAYCHE</text>
</svg>'''

(ROOT / "favicon.svg").write_text(mark)
(ROOT / "logo.svg").write_text(logo)
print("wrote favicon.svg + logo.svg")

for size in (192, 512):
    src = str(ROOT / "favicon.svg")
    dst = str(ROOT / f"icon-{size}.png")
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), src, "-o", dst], check=True)
    print(f"wrote icon-{size}.png ({pathlib.Path(dst).stat().st_size} bytes)")
