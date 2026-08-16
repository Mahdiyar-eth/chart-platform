"""G11 (§108) — runtime feature flags: default-on, toggleable, audited."""
from fastapi.testclient import TestClient

from app.main import app


def test_flags_default_on():
    from app.feature_flags import all_flags, flag
    f = all_flags()
    assert f["chat"] is True and f["reports"] is True
    assert flag("nonexistent_flag_xyz", "off") is False


def test_flag_blocks_chat_when_off(monkeypatch):
    """Chat endpoint returns 503 when the chat flag is off (no deploy needed)."""
    monkeypatch.setattr("app.feature_flags.flag", lambda name, default="on": False)
    c = TestClient(app, follow_redirects=False)
    # unauthenticated request reaches the flag gate before ownership checks
    r = c.post("/api/chat", data={"chart_id": "x", "question": "سلام"})
    assert r.status_code == 503
    assert "ZAY-AI-002" in r.text


def test_flag_set_invalid_value(monkeypatch):
    """set_flag rejects garbage; admin PUT requires admin session."""
    from app.feature_flags import set_flag
    try:
        set_flag("chat", "banana")
        raise AssertionError("should have raised")
    except ValueError:
        pass
    c = TestClient(app)
    r = c.put("/api/admin/flags/chat", data={"value": "off"})
    assert r.status_code == 403  # not admin
