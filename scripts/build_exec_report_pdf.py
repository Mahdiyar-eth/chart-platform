#!/usr/bin/env python3
"""Build EXECUTION-REPORT.pdf (Persian RTL) from EXECUTION-REPORT.md."""
import markdown
from pathlib import Path

SRC = Path("/root/chart-platform/docs/EXECUTION-REPORT.md")
OUT = Path("/root/chart-platform/docs/EXECUTION-REPORT.pdf")
FONT_DIR = "/root/astrology/fonts/vazirmatn/fonts/ttf"

md_text = SRC.read_text(encoding="utf-8")
body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])

html = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head><meta charset="utf-8">
<style>
@font-face {{ font-family: 'Vazirmatn'; src: url('file://{FONT_DIR}/Vazirmatn-Regular.ttf'); font-weight: normal; }}
@font-face {{ font-family: 'Vazirmatn'; src: url('file://{FONT_DIR}/Vazirmatn-Bold.ttf'); font-weight: bold; }}
@page {{ size: A4; margin: 1.8cm 1.6cm; @bottom-center {{ content: counter(page) " / " counter(pages); direction: ltr; font-size: 9pt; color: #888; }} }}
body {{ direction: rtl; font-family: 'Vazirmatn', sans-serif; line-height: 1.95; color: #1a1a1a; font-size: 11pt; }}
h1 {{ color: #0f3460; border-bottom: 2px solid #d4af37; padding-bottom: 6px; font-size: 20pt; margin-top: 26px; }}
h2 {{ color: #0f3460; font-size: 15pt; margin-top: 20px; border-right: 4px solid #d4af37; padding-right: 8px; }}
h3 {{ color: #333; font-size: 12.5pt; margin-top: 16px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; }}
th {{ background: #0f3460; color: #fff; padding: 7px 9px; text-align: right; }}
td {{ border: 1px solid #ddd; padding: 6px 9px; }}
tr:nth-child(even) td {{ background: #f7f7f7; }}
code {{ direction: ltr; unicode-bidi: embed; background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }}
pre {{ direction: ltr; text-align: left; background: #f5f5f5; padding: 10px; border-radius: 6px; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ border-right: 3px solid #d4af37; margin-right: 0; padding-right: 12px; color: #555; }}
li {{ margin: 3px 0; }}
strong {{ color: #0f3460; }}
</style></head>
<body>
{body}
</body></html>"""

from weasyprint import HTML
HTML(string=html).write_pdf(str(OUT))

import fitz
doc = fitz.open(str(OUT))
print("PDF pages:", doc.page_count)
# render page 1 for verification
doc[0].get_pixmap(dpi=70).save("/tmp/exec_report_p1.png")
print("OK ->", OUT)
