"""The streaming endpoint must enforce everything /api/chat enforces.

chat.html posts exclusively to /api/chat/stream (chat.html:87). /api/chat is
the endpoint nothing in the UI calls. Guards were added to the one nobody uses:

  * ent_consume ran only in /api/chat, so a chat_pack_20 buyer got unlimited
    messages — we sold 20 and delivered infinity.
  * flag("chat", "on"), the ops kill switch for halting AI spend instantly,
    was checked only in /api/chat. Flipping it off stopped nothing real.
  * the stream emitted a `quota` frame on error but never on success, so the
    remaining-questions counter in the UI never moved.

These are parity tests: whatever the non-streaming path guards, the streaming
path must guard too.
"""
from __future__ import annotations

import inspect
import re

import app.main as m


def _src(fn) -> str:
    return inspect.getsource(fn)


def test_stream_has_the_kill_switch():
    src = _src(m.api_chat_stream)
    assert 'flag("chat"' in src, (
        "/api/chat/stream has no feature-flag check — the ops kill switch "
        "cannot actually stop chat spend, because this is the endpoint the UI uses"
    )


def test_stream_consumes_the_chat_pack():
    src = _src(m.api_chat_stream)
    assert "consume" in src, (
        "/api/chat/stream never consumes the chat-pack entitlement, so "
        "chat_pack_20 buyers get unlimited messages"
    )


def test_stream_emits_quota_on_success():
    """Not only on the error path — the counter has to move after an answer.

    Sliced between the done and error branches on purpose: the error branch
    also yields a quota frame, so a naive "quota appears after done" check
    passes even when the success path emits nothing.
    """
    src = _src(m.api_chat_stream)
    assert '== "done"' in src and '== "error"' in src
    done_only = src.split('== "done"', 1)[1].split('== "error"', 1)[0]
    assert "event: quota" in done_only, (
        "the stream emits no quota frame on a successful answer, so the "
        "remaining-questions counter never decrements"
    )


def test_both_chat_endpoints_guard_the_same_things():
    plain, stream = _src(m.api_chat), _src(m.api_chat_stream)
    for needle, why in [
        ('flag("chat"', "feature kill switch"),
        ("consume", "chat-pack consumption"),
        ("_chat_guarded_context", "auth/ownership/daily-quota guard"),
    ]:
        assert (needle in plain) == (needle in stream), (
            f"{why} is present in one chat endpoint but not the other"
        )


def test_ui_posts_to_the_stream_endpoint():
    """Guards belong where the traffic is; assert where the traffic actually goes."""
    from pathlib import Path
    html = (Path(__file__).resolve().parent.parent
            / "app" / "templates" / "chat.html").read_text(encoding="utf-8")
    assert "/api/chat/stream" in html
    assert not re.search(r"fetch\(\s*['\"]/api/chat['\"]", html), (
        "chat.html posts to the non-streaming endpoint somewhere — if that "
        "changes, the guard parity assumptions here need revisiting"
    )
