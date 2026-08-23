#!/usr/bin/env python
"""R.5 / V7 — brand-language gate as an explicit file:line ALLOWLIST.

The old scan negated banned words with a growing substring `grep -v` chain. Each
added phrase weakened the whole whitelist (a new legit-use line could slip through
if it happened to contain an allowed substring). The review (P2-1) asked for an
allowlist keyed by file:line instead:

  - Scan app/templates|content|bots|report|chat for the banned words.
  - app/report/qa.py is the detector itself and is always allowed.
  - Every OTHER hit MUST appear in scripts/brand_allowlist.txt as `path:line`.
  - A hit not in the allowlist = FAIL (exit 1). A legit new line requires an
    explicit allowlist entry — deliberate, not accidental.

This is intentionally strict: adding a new legitimate sentence means adding its
file:line to the allowlist, so nothing is silently grandfathered.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO / "scripts/brand_allowlist.txt"

DIRS = ["app/templates", "app/content", "app/bots", "app/report", "app/chat"]
EXT = {".html", ".json", ".py"}
# The detector module contains the banned words as its regexes — always allowed.
ALWAYS_ALLOW = re.compile(r"^app/report/qa\.py")
BANNED = re.compile(r"پیش ?بینی|فال|طالع ?بینی", re.IGNORECASE)


def allowed_set() -> set[str]:
    if not ALLOWLIST.exists():
        return set()
    return {
        ln.strip()
        for ln in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    }


def scan() -> list[str]:
    allowed = allowed_set()
    out = []
    for d in DIRS:
        base = REPO / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.suffix not in EXT:
                continue
            rel = str(f.relative_to(REPO)).replace("\\", "/")
            if ALWAYS_ALLOW.match(rel):
                continue
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, ln in enumerate(lines, 1):
                if BANNED.search(ln):
                    key = f"{rel}:{i}"
                    if key not in allowed:
                        out.append(f"{key}: {ln.strip()[:150]}")
    return out


def main() -> int:
    bad = scan()
    if bad:
        print("❌ banned brand-language found (add each file:line to "
              "scripts/brand_allowlist.txt ONLY if legitimately anti-fortune-telling):")
        for b in bad:
            print("  " + b)
        return 1
    print(f"✓ no banned brand-language ({len(allowed_set())} allowlisted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
