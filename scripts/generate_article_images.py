#!/usr/bin/env python3
"""Generate FLUX images for SEO articles (plan V8 — تصاویر سئو).

- flux-dev 16:9  → header + og:image  ($0.025/img) → <slug>.webp
- flux-schnell    → thumbnail            ($0.003/img) → <slug>-thumb.webp

Outputs to app/static/articles/ (served by /static) and writes the "image"
+ "thumb" fields back into app/content/articles.json.

Usage:
  venv/bin/python scripts/generate_article_images.py --limit 1        # test
  venv/bin/python scripts/generate_article_images.py                  # all
  venv/bin/python scripts/generate_article_images.py --model dev      # headers only
  venv/bin/python scripts/generate_article_images.py --slug aries-... # one article
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_JSON = ROOT / "app" / "content" / "articles.json"
IMG_DIR = ROOT / "app" / "static" / "articles"
TOKEN_ENV = ROOT.parent / "voice-clone" / ".env"

load_dotenv(TOKEN_ENV, override=False)
import replicate  # noqa: E402

FLUX_DEV = "black-forest-labs/flux-dev"
FLUX_SCHNELL = "black-forest-labs/flux-schnell"

SIGN_MAP = {
    "aries": "the Aries ram constellation", "taurus": "the Taurus bull constellation",
    "gemini": "the Gemini twins constellation", "cancer": "the Cancer crab constellation",
    "leo": "the Leo lion constellation", "virgo": "the Virgo maiden constellation",
    "libra": "the Libra scales constellation", "scorpio": "the Scorpio scorpion constellation",
    "sagittarius": "the Sagittarius archer constellation", "capricorn": "the Capricorn sea-goat constellation",
    "aquarius": "the Aquarius water-bearer constellation", "pisces": "the Pisces fish constellation",
}
PLANET_MAP = {
    "sun": "the radiant Sun", "moon": "the glowing full Moon", "mercury": "the planet Mercury",
    "venus": "the planet Venus", "mars": "the planet Mars", "jupiter": "the planet Jupiter",
    "saturn": "the ringed planet Saturn",
}
CAT_FALLBACK = {
    "آموزش نجوم": "an ancient celestial star chart with a zodiac wheel and constellations",
    "خانه": "an astrological chart with twelve glowing houses forming a wheel",
    "ترانزیت": "planets moving across a luminous astrological chart",
    "سازگاری": "two intertwined glowing constellations in a starry sky",
    "شغل": "a glowing staircase of stars rising toward a bright horizon",
    "ماه": "the luminous moon over a serene night sky",
}
STYLE = ("Elegant dark celestial illustration, deep navy and indigo night sky, "
         "glowing golden and violet accents, cinematic lighting, highly detailed, "
         "no text, no words, no letters, no watermark")


def prompt_for(art: dict) -> str:
    slug = art.get("slug", "").lower()
    cat = art.get("category", "")
    subject = None
    for k, v in SIGN_MAP.items():
        if k in slug:
            subject = v
            break
    if not subject:
        for k, v in PLANET_MAP.items():
            if k in slug:
                subject = v
                break
    if not subject:
        for k, v in CAT_FALLBACK.items():
            if k in cat:
                subject = v
                break
    if not subject:
        subject = "a luminous zodiac wheel in the night sky"
    return f"{STYLE}, {subject}"


def ascii_filename(slug: str, suffix: str = "") -> str:
    base = slug if slug.isascii() else f"art-{hashlib.md5(slug.encode()).hexdigest()[:10]}"
    return f"{base}{suffix}.webp"


def generate(model: str, prompt: str, aspect: str, output_path: Path) -> bool:
    """Create a prediction, poll, download. Returns True on success."""
    token = os.getenv("REPLICATE_API_TOKEN", "")
    if not token:
        print("  !! REPLICATE_API_TOKEN not found")
        return False
    client = replicate.Client(api_token=token)
    version = client.models.get(model).latest_version.id
    last_err = None
    for attempt in range(6):
        try:
            pred = client.predictions.create(
                version=version,
                input={"prompt": prompt, "aspect_ratio": aspect,
                       "output_format": "webp", "num_outputs": 1},
            )
            last_err = None
            break
        except Exception as e:  # rate limit / transient
            last_err = e
            print(f"  .. create attempt {attempt+1} failed ({e}); sleeping 20s")
            time.sleep(20)
    if last_err:
        print(f"  !! could not create prediction: {last_err}")
        return False
    # poll
    for _ in range(120):
        pred = client.predictions.get(pred.id)
        if pred.status == "succeeded":
            url = pred.output
            if isinstance(url, list):
                url = url[0]
            if not url:
                return False
            try:
                import httpx
                data = httpx.get(url, timeout=120, follow_redirects=True).content
                output_path.write_bytes(data)
                return True
            except Exception as e:
                print(f"  !! download failed: {e}")
                return False
        if pred.status in ("failed", "canceled"):
            print(f"  !! {pred.status}: {pred.error}")
            return False
        time.sleep(6)
    print("  !! timeout polling")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only process first N articles")
    ap.add_argument("--slug", type=str, default="", help="process one slug")
    ap.add_argument("--model", choices=["dev", "schnell", "both"], default="both")
    ap.add_argument("--aspect", default="16:9")
    args = ap.parse_args()

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    arts = json.loads(ARTICLES_JSON.read_text("utf-8"))

    todo = [a for a in arts if a.get("slug") == args.slug] if args.slug else arts
    if args.limit:
        todo = todo[: args.limit]

    print(f"Generating images for {len(todo)} articles (model={args.model})")
    for i, art in enumerate(todo, 1):
        slug = art["slug"]
        prompt = prompt_for(art)
        print(f"[{i}/{len(todo)}] {slug}")

        changed = False
        if args.model in ("dev", "both"):
            fn = ascii_filename(slug)
            if not (IMG_DIR / fn).exists():
                if generate(FLUX_DEV, prompt, args.aspect, IMG_DIR / fn):
                    art["image"] = f"/static/articles/{fn}"
                    changed = True
                    print(f"    dev ✓ {fn} ({IMG_DIR / fn})")
                time.sleep(14)
            else:
                art["image"] = f"/static/articles/{fn}"
        if args.model in ("schnell", "both"):
            fn = ascii_filename(slug, "-thumb")
            if not (IMG_DIR / fn).exists():
                if generate(FLUX_SCHNELL, prompt, args.aspect, IMG_DIR / fn):
                    art["thumb"] = f"/static/articles/{fn}"
                    changed = True
                    print(f"    schnell ✓ {fn}")
                time.sleep(14)
            else:
                art["thumb"] = f"/static/articles/{fn}"

        if changed:
            # re-read fresh before writing to avoid clobbering concurrent edits
            try:
                fresh = json.loads(ARTICLES_JSON.read_text("utf-8"))
                by_slug = {a["slug"]: a for a in fresh}
                if slug in by_slug:
                    if args.model in ("dev", "both") and art.get("image"):
                        by_slug[slug]["image"] = art["image"]
                    if args.model in ("schnell", "both") and art.get("thumb"):
                        by_slug[slug]["thumb"] = art["thumb"]
                    ARTICLES_JSON.write_text(json.dumps(fresh, ensure_ascii=False, indent=2), "utf-8")
                    print("    (articles.json updated)")
            except Exception as e:
                print(f"    !! articles.json save failed: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
