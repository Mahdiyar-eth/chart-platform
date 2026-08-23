"""G2/G3 — claim banner (funnel leak fix) + lead-magnet subscribe/download/unsubscribe."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_claim_banner_for_guest_with_token():
    r = client.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "zodiac": "tropical", "time_known": "true", "hour": "6", "minute": "10",
        "city_fa": "تهران", "lat": "35.6892", "lon": "51.389", "tz_name": "Asia/Tehran",
    })
    assert r.status_code == 200
    d = r.json()
    page = client.get(f"/chart/{d['chart_id']}?t={d['access_token']}")
    assert page.status_code == 200
    assert "این چارت را از دست نده" in page.text


def test_subscribe_valid_phone_and_download():
    r = client.post("/api/subscribe", data={"contact": "09121234567", "source": "guide"})
    assert r.status_code == 200
    url = r.json()["download_url"]
    dl = client.get(url)
    assert dl.status_code == 200
    assert dl.content[:5] == b"%PDF-"


def test_subscribe_invalid_contact_422():
    r = client.post("/api/subscribe", data={"contact": "12345"})
    assert r.status_code == 422


def test_unsubscribe_flips_flag():
    from sqlmodel import select, Session
    from app.db import engine as eng
    from app.models import Subscriber
    
    with Session(eng) as s:
        for old_row in s.exec(select(Subscriber).where(Subscriber.token == "tok-unsub-1")).all():
            s.delete(old_row)
        s.commit()
        sub = Subscriber(contact="09123456789", source="test", token="tok-unsub-1")
        s.add(sub); s.commit()
    # X15/R11: state change is POST-only (GET renders a confirm page — email prefetch safe)
    r_get = client.get("/unsubscribe/tok-unsub-1")
    assert r_get.status_code == 200
    with Session(eng) as s:
        row = s.exec(select(Subscriber).where(Subscriber.token == "tok-unsub-1")).one()
        assert row.unsubscribed_at is None  # GET must NOT flip
    r = client.post("/unsubscribe/tok-unsub-1")
    assert r.status_code == 200
    with Session(eng) as s:
        row = s.exec(select(Subscriber).where(Subscriber.token == "tok-unsub-1")).one()
        assert row.unsubscribed_at is not None
