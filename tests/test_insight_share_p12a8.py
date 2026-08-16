"""A8 (ChatGPT directive) — insight/transit share cards (mirror G7)."""
from fastapi.testclient import TestClient

from app.main import app


def test_insight_share_mint_and_guest_view():
    c = TestClient(app)
    r = c.post("/api/insight/share", data={
        "kind": "transit", "title": "گذرهای امروز",
        "headline": "ماه امروز در حمل با خورشید تو در اسد در تربیع است",
        "date_fa": "۲۶ مرداد ۱۴۰۵",
    })
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/si/")
    g = c.get(url)
    assert g.status_code == 200
    assert "گذرهای امروز" in g.text
    assert "ماه امروز در حمل" in g.text
    assert "پیدا نشد" not in g.text


def test_insight_share_tamper_404():
    c = TestClient(app)
    r = c.post("/api/insight/share", data={"kind": "insight", "title": "ت",
               "headline": "امروز روز خوبی است", "date_fa": "امروز"})
    url = r.json()["url"]
    # flip one char in the token → must 404, no leak
    tok, q = url.split("?")
    bad = tok[:-1] + ("0" if tok[-1] != "0" else "1")
    g = c.get(bad + "?" + q)
    assert g.status_code == 404


def test_insight_share_bad_kind_rejected():
    c = TestClient(app)
    r = c.post("/api/insight/share", data={"kind": "hack", "title": "x",
               "headline": "y", "date_fa": "z"})
    assert r.status_code == 400
