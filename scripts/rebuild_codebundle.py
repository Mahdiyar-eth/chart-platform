#!/usr/bin/env python3
"""Regenerate docs/audit/CODEBUNDLE.md from the CURRENT source tree."""
from pathlib import Path

ROOT = Path("/root/chart-platform")
FILES = sorted(
    list((ROOT / "app").rglob("*.py"))
    + list((ROOT / "app").rglob("*.html"))
)
# drop __pycache__
FILES = [f for f in FILES if "__pycache__" not in str(f)]

parts = []
total = 0
for f in FILES:
    rel = f.relative_to(ROOT)
    txt = f.read_text(encoding="utf-8")
    lines = txt.count("\n") + 1
    parts.append(f"FILE: {rel}  ({lines} lines)\n{'=' * 70}\n{txt}\n")
    total += len(txt)

out = "\n".join(parts)
(ROOT / "docs" / "audit" / "CODEBUNDLE.md").write_text(out, encoding="utf-8")
print(f"files: {len(FILES)} | chars: {total} | KB: {total/1024:.0f}")
