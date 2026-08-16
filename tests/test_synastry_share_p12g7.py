"""G7 (§18) — synastry viral share: signed guest link with only score+verdict."""
from fastapi.testclient import TestClient

from app.main import app


def _mint(client, name_a="علی", name_b="مریم", score=72, verdict="هماهنگی خوب"):
    return client.post("/api/synastry/share",
                       data={"name_a": name_a, "name_b": name_b,
                             "score": score, "verdict": verdict})


def test_share_mints_signed_url():
    c = TestClient(app)
    r = _mint(c)
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/s/") and "?p=" in url


def test_share_page_renders_and_validates():
    c = TestClient(app)
    url = _mint(c).json()["url"]
    r = c.get(url)
    assert r.status_code == 200
    assert "72" in r.text and "هماهنگی خوب" in r.text
    # tampered token → 404 (no leak)
    r2 = c.get(url.replace("?p=", "?p=X"))
    assert r2.status_code == 404
    # wrong signature → 404
    r3 = c.get("/s/deadbeefdeadbeefdeadbeef?p=علی|مریم|72|هماهنگی")
    assert r3.status_code == 404


def test_share_rejects_invalid_score():
    c = TestClient(app)
    assert _mint(c, score=999).status_code == 400
    assert _mint(c, score=-1).status_code == 400
