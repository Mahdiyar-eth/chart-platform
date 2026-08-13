#!/usr/bin/env python3
"""Build PLAIN-REPORT.md → Persian RTL PDF (weasyprint pipeline)."""
import markdown
from weasyprint import HTML

OUT = "/root/chart-platform/docs/audit"
SRC = f"{OUT}/PLAIN-REPORT.md"
PDF = "/tmp/چارت-تولد-گزارش-صفر-تا-صد.pdf"

md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])
body = md.convert(open(SRC, encoding="utf-8").read())

html = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>
@font-face {{ font-family:'Vazirmatn'; src:url('/root/astrology/fonts/vazirmatn/fonts/ttf/Vazirmatn-Regular.ttf') format('truetype'); font-weight:400; }}
@font-face {{ font-family:'Vazirmatn'; src:url('/root/astrology/fonts/vazirmatn/fonts/ttf/Vazirmatn-Bold.ttf') format('truetype'); font-weight:700; }}
@page {{ size:A4; margin:2cm 1.8cm;
  @bottom-center {{ content: counter(page) " / " counter(pages); font-size:9pt; color:#888; }} }}
body {{ direction:rtl; font-family:Vazirmatn, Tahoma; font-size:11pt; line-height:1.9; color:#1c2333; }}
h1 {{ color:#0f3460; border-bottom:3px solid #f5c518; padding-bottom:8px; font-size:19pt; }}
h2 {{ color:#0f3460; font-size:14pt; margin-top:22px; }}
h3 {{ color:#6a5acd; font-size:12pt; }}
blockquote {{ background:#f4f0ff; border-right:4px solid #6a5acd; padding:8px 14px; border-radius:8px; margin:10px 0; }}
table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
th {{ background:#0f3460; color:#fff; padding:8px 10px; text-align:right; }}
td {{ border:1px solid #dde3f0; padding:7px 10px; }}
tr:nth-child(even) td {{ background:#f6f8fd; }}
code {{ direction:ltr; unicode-bidi:embed; background:#eef1f8; padding:1px 6px; border-radius:5px; font-size:9.5pt; }}
li {{ margin:4px 0; }}
</style></head><body>
<h1 style="text-align:center; border:none;">📜 گزارش صفر تا صد پروژه چارت تولد</h1>
<p style="text-align:center; color:#6b7ab0; margin-top:-6px;">نسخه ساده و غیرفنی — تهیه‌شده: ۲۲ مرداد ۱۴۰۵ (۱۳ اوت ۲۰۲۶)</p>
{body}
</body></html>"""

HTML(string=html, base_url=OUT).write_pdf(PDF)
print("PDF written:", PDF)
