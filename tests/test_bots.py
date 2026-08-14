"""Phase 6 tests — bot state machine + flow with FAKE bot API (no real calls)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.bots import handler as H
from app.bots.state import clear_chat_state


class FakeBotAPI:
    """Records outgoing calls instead of hitting Telegram/Bale."""
    calls: list[dict] = []

    @classmethod
    async def install(cls, monkeypatch):
        cls.calls = []
        async def fake_api(method, payload, platform):
            cls.calls.append({"method": method, "payload": payload, "platform": platform})
            return {"ok": True, "result": {"message_id": 1}}
        monkeypatch.setattr(H, "api_call", fake_api)


def test_start_command(monkeypatch):
    clear_chat_state(111, "telegram")
    import asyncio
    async def run():
        await FakeBotAPI.install(monkeypatch)
        await H.handle_update({
            "message": {"chat": {"id": 111}, "text": "/start",
                        "entities": [{"type": "bot_command", "offset": 0, "length": 6}]}
        }, "telegram")
    asyncio.run(run())
    assert FakeBotAPI.calls[0]["method"] == "sendMessage"
    assert "خوش آمدی" in FakeBotAPI.calls[0]["payload"]["text"]
    kb = FakeBotAPI.calls[0]["payload"]["reply_markup"]["inline_keyboard"]
    assert "ساخت چارت" in kb[0][0]["text"]


def test_full_chart_flow(monkeypatch):
    """callback chart_start → date → time → city → zodiac (buttons) → chart card."""
    clear_chat_state(222, "telegram")
    import asyncio
    async def run():
        await FakeBotAPI.install(monkeypatch)
        await H.handle_update({
            "callback_query": {"id": "c1", "data": "chart_start",
                               "message": {"chat": {"id": 222}}}
        }, "telegram")
        await H.handle_update({
            "message": {"chat": {"id": 222}, "text": "23/08/1994"}
        }, "telegram")
        await H.handle_update({
            "message": {"chat": {"id": 222}, "text": "06:10"}
        }, "telegram")
        await H.handle_update({
            "message": {"chat": {"id": 222}, "text": "تهران"}
        }, "telegram")
        # audit r3: zodiac system choice (buttons) before computing
        await H.handle_update({
            "callback_query": {"id": "c2", "data": "zodiac_tropical",
                               "message": {"chat": {"id": 222}}}
        }, "telegram")
    asyncio.run(run())
    methods = [c["method"] for c in FakeBotAPI.calls]
    assert methods.count("sendMessage") == 4   # ask date / time / city / zodiac
    zodiac_msg = next(c for c in FakeBotAPI.calls if c["method"] == "sendMessage"
                      and "سیستم نجومی" in c["payload"]["text"])
    kb = zodiac_msg["payload"]["reply_markup"]["inline_keyboard"]
    assert any(b["callback_data"] == "zodiac_sidereal" for row in kb for b in row)
    assert "sendPhoto" in methods              # chart card with actions
    photo_call = next(c for c in FakeBotAPI.calls if c["method"] == "sendPhoto")
    assert "api/share/" in photo_call["payload"]["photo"]
    assert photo_call["payload"]["reply_markup"]["inline_keyboard"]


def test_invalid_date_rejected(monkeypatch):
    clear_chat_state(333, "bale")
    import asyncio
    async def run():
        await FakeBotAPI.install(monkeypatch)
        await H.handle_update({
            "callback_query": {"id": "c1", "data": "chart_start",
                               "message": {"chat": {"id": 333}}}
        }, "bale")
        await H.handle_update({"message": {"chat": {"id": 333}, "text": "99/99/9999"}}, "bale")
    asyncio.run(run())
    msgs = [c for c in FakeBotAPI.calls if c["method"] == "sendMessage"]
    assert "⛔" in msgs[-1]["payload"]["text"]


def test_cancel_flow(monkeypatch):
    clear_chat_state(444, "telegram")
    import asyncio
    async def run():
        await FakeBotAPI.install(monkeypatch)
        await H.handle_update({
            "callback_query": {"id": "c1", "data": "chart_start",
                               "message": {"chat": {"id": 444}}}
        }, "telegram")
        await H.handle_update({
            "callback_query": {"id": "c2", "data": "cancel",
                               "message": {"chat": {"id": 444}}}
        }, "telegram")
    asyncio.run(run())
    msgs = [c for c in FakeBotAPI.calls if c["method"] == "sendMessage"]
    assert "لغو شد" in msgs[-1]["payload"]["text"]
