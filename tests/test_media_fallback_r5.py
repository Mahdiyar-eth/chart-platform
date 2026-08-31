"""R.5 / AC-3 / V4 — the CMS media fallback must be a REAL round-trip.

The review's P1-1: `upload_bytes` falls back to writing to MEDIA_DIR when R2 is
not configured, but nothing ever SERVED that file — a "semi-fallback" (writes yet
is never readable). The CMS test asserted only "bytes written == True".

Option A makes the write readable: upload a byte blob, then GET /media/{key} and
get the SAME bytes back. Also proves traversal (`../`) is neutralised. This runs
only when R2 is NOT configured (i.e. the local fallback is the active path); when
R2 IS configured the route intentionally 404s and this test is skipped.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

# Conftest does not set R2_* — so storage.configured() is False in tests and the
# local MEDIA_DIR fallback is the active path.
from app import storage
from app.main import app


@pytest.fixture()
def _local_media(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", str(tmp_path))
    return tmp_path


def test_media_upload_roundtrip(_local_media, monkeypatch):
    # Use the REAL upload_bytes (no mock) with R2 unconfigured → local write.
    key = "media/20260823/abc123-probe.png"
    blob = b"\x89PNG\r\n\x1a\n" + b"R5-round-trip" * 4
    monkeypatch.setattr(storage, "configured", lambda: False)
    assert storage.upload_bytes(key, blob, "image/png") is True

    # The write MUST be on disk under MEDIA_DIR.
    assert (_local_media / "media/20260823/abc123-probe.png").read_bytes() == blob

    # The new serving route must return the SAME bytes (no "semi-fallback").
    c = TestClient(app, base_url="http://testserver")
    r = c.get(f"/media/{key}")
    assert r.status_code == 200, r.text
    assert r.content == blob


def test_media_serve_rejects_traversal(_local_media, monkeypatch):
    """../ in the key must be neutralised → 404, never a file outside MEDIA_DIR."""
    monkeypatch.setattr(storage, "configured", lambda: False)
    # A real file just outside MEDIA_DIR that must never be served.
    (Path(_local_media).parent / "secrets.txt").write_text("top-secret")
    c = TestClient(app, base_url="http://testserver")
    for bad in ("../secrets.txt", "..%2fsecrets.txt", "%2e%2e/secrets.txt"):
        r = c.get(f"/media/{bad}")
        # traversal resolves out of MEDIA_DIR → not a file under it → 404
        assert r.status_code == 404, f"{bad=} -> {r.status_code}"


def test_media_serve_404_when_configured(_local_media, monkeypatch):
    """When R2 IS configured the route must refuse (real URL comes from presign)."""
    monkeypatch.setattr(storage, "configured", lambda: True)
    c = TestClient(app, base_url="http://testserver")
    assert c.get("/media/media/20260823/abc.png").status_code == 404
