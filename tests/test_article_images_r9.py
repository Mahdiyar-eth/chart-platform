"""R.9 / Q4 (AC-4) — article images ship with the repo, so a fresh deploy serves them.

The final audit found every article image 404 on a fresh host because
`app/static/articles/` was gitignored ("regenerable via FLUX") — 50 broken <img>
and 50 broken og:image. Images are now committed (~5.6MB). This gate asserts every
article's image/thumb path resolves to a real packaged file (independent of any
host without R2 / Replicate).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _articles():
    return json.load(open(ROOT / "app" / "content" / "articles.json", encoding="utf-8"))


def test_every_article_image_and_thumb_resolves():
    arts = _articles()
    assert len(arts) >= 50
    img_dir = ROOT / "app" / "static" / "articles"
    missing = []
    for a in arts:
        for key in ("image", "thumb"):
            v = (a.get(key) or "").replace("/static/articles/", "")
            if not v:
                continue
            if not (img_dir / v).is_file():
                missing.append((a.get("slug"), key, v))
    assert not missing, f"article image files not packaged: {missing[:10]}"


def test_every_article_has_an_image_field():
    """AC-4 companion: every article declares image+thumb (else og:image is empty)."""
    for a in _articles():
        assert a.get("image"), f"{a.get('slug')} missing image"
        assert a.get("thumb"), f"{a.get('slug')} missing thumb"


def test_article_images_committed_not_ignored():
    """Images must not be gitignored (the root cause of the fresh-host 404s)."""
    g = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "app/static/articles/" not in [l.strip() for l in g.splitlines()
                                          if l.strip() and not l.strip().startswith("#")], \
        "article images are gitignored again — fresh deploys will 404"
