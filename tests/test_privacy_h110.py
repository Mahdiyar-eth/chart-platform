"""H1.10 (HARDENING): privacy policy is specific & complete — data collected,
third-party data flows, cookies, retention/security, user rights."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_privacy_page_renders():
    r = client.get("/privacy")
    assert r.status_code == 200


def test_privacy_covers_all_required_sections():
    r = client.get("/privacy").text
    required = [
        "دادهٔ تولد",           # what we collect
        "شماره موبایل",
        "زرین",                  # payment processor named
        "DeepSeek",              # AI third parties named
        "Edge TTS",              # audio provider named
        "chart_user",            # cookies section
        "chart_access",
        "Umami",                 # analytics
        "بکاپ",                  # retention
        "۳۰ روز",                # concrete retention window
        "حذف کامل",              # user rights / deletion
        "RAG",                   # search index cleanup
    ]
    missing = [k for k in required if k not in r]
    assert not missing, f"privacy policy missing: {missing}"


def test_privacy_has_update_stamp():
    assert "آخرین به‌روزرسانی" in client.get("/privacy").text
