#!/usr/bin/env python3
"""C2 - migrate inline styles to generated utility CSS (pixel-identical).

For every STATIC style="..." attribute (no Jinja {{ }}):
  - emit a deterministic content class st-<hash8> into app/static/css/generated.css
  - merge that class into the tag's existing class="..." (or create one)
Dynamic values stay inline. Re-runs are no-ops (stable hash, idempotent).
generated.css must load LAST so declarations keep their original cascade position.
"""
import glob, hashlib, re, sys

GEN = "app/static/css/generated.css"
STYLE_RE = re.compile(r'style="([^"]*)"')
TAG_RE = re.compile(r"<[a-zA-Z][a-zA-Z0-9-]*(?:\"[^\"]*\"|'[^']*'|[^>])*?>", re.DOTALL)


def norm(v: str) -> str:
    return re.sub(r"\s+", " ", v.strip()).rstrip(";")


def migrate_text(src: str, classes: dict) -> tuple[str, int]:
    n = 0
    # pass 1: replace static style attrs with marker tokens \x02cls\x03
    def collect(m):
        val = m.group(1)
        if "{{" in val or "{%" in val or not val.strip():
            return m.group(0)
        key = norm(val)
        h = hashlib.sha1(key.encode()).hexdigest()[:8]
        cls = "st-" + h
        classes[cls] = key
        return "" + cls + ""
    src = STYLE_RE.sub(collect, src)
    # pass 2: fold markers into the enclosing tag's class attribute
    def fold(m):
        nonlocal n
        tag = m.group(0)
        if "" not in tag:
            return tag
        found = re.findall("([^\x03]+)", tag)
        if not found:
            return re.sub("[^\x03]+\s*", "", tag)
        tag = re.sub("[^\x03]+\s*", "", tag).rstrip()
        merged = " ".join(found)

        def add_cls(cm):
            existing = cm.group(1).strip()
            return 'class="' + (existing + " " + merged if existing else merged) + '"'
        tag2, k = re.subn(r'class="([^"]*)"', add_cls, tag, count=1)
        if k:
            n += len(found)
            return tag2
        # no class attr on this tag: insert one after the tag name
        mname = re.match(r"<([a-zA-Z][a-zA-Z0-9-]*)", tag)
        if not mname:
            return tag
        n += len(found)
        return "<" + mname.group(1) + ' class="' + merged + '"' + tag[mname.end():]
    src2 = TAG_RE.sub(fold, src)
    # any leftover marker (shouldn't happen) -> restore nothing, count as lost
    assert "" not in src2, "leftover migration markers"
    return src2, n


def main() -> int:
    classes: dict = {}
    per_file = []
    for f in sorted(glob.glob("app/templates/**/*.html", recursive=True)):
        src = open(f, encoding="utf-8").read()
        out, k = migrate_text(src, classes)
        if k:
            open(f, "w", encoding="utf-8").write(out)
            per_file.append((k, f))
    with open(GEN, "w", encoding="utf-8") as w:
        w.write("/* C2 generated utilities - DO NOT EDIT BY HAND.\n")
        w.write("   Source of truth: scripts/migrate_inline_styles.py */\n")
        for cls in sorted(classes, key=lambda c: classes[c]):
            w.write("." + cls + "{ " + classes[cls] + "; }\n")
    # ensure base.html links generated.css (idempotent)
    base_p = "app/templates/base.html"
    b = open(base_p, encoding="utf-8").read()
    if "generated.css" not in b:
        anchor = '<link rel="stylesheet" href="/static/css/components.css?v={{ asset_version }}">'
        if anchor in b:
            b = b.replace(anchor, anchor + '\n  <link rel="stylesheet" href="/static/css/generated.css?v={{ asset_version }}">')
            open(base_p, "w", encoding="utf-8").write(b)
        else:
            print("WARN: components.css link not found in base.html")
    for k, f in per_file:
        print(str(k).rjust(4), f)
    print("TOTAL migrated:", sum(k for k, _ in per_file), "| unique classes:", len(classes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
