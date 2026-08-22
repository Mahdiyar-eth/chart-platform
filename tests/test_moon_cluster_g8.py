"""G8b: «ماه در برج» cluster pages (12 unique SEO pages)."""
import pytest
from fastapi.testclient import TestClient

SLUGS = ["hamal","sowr","jowza","sartan","asad","sowza","mizan",
         "aghrab","ghows","jadi","dalv","hout"]


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_moon_index_lists_all_12(client):
    r = client.get("/moon")
    assert r.status_code == 200
    assert r.text.count("/moon-in/") >= 12


@pytest.mark.parametrize("slug", SLUGS)
def test_each_moon_page_unique_and_complete(client, slug):
    r = client.get(f"/moon-in/{slug}")
    assert r.status_code == 200
    txt = r.text
    for needle in ("عشق و رابطه", "کار و مسیر شغلی", "سایه و درس ماه", "راه آرامش"):
        assert needle in txt, slug
    # canonical is unique per slug
    assert f"/moon-in/{slug}" in txt


def test_moon_pages_have_distinct_content(client):
    bodies = set()
    for s in SLUGS[:4]:
        bodies.add(client.get(f"/moon-in/{s}").text)
    assert len(bodies) == 4  # no thin/duplicate pages


def test_unknown_sign_is_404(client):
    assert client.get("/moon-in/doesnotexist").status_code == 404


def test_sitemap_contains_moon_cluster(client):
    sm = client.get("/sitemap.xml").text
    assert "/moon</loc>" in sm
    for s in ["hamal", "hout"]:
        assert f"/moon-in/{s}</loc>" in sm
