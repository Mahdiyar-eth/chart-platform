"""Bot per-chat state (v135 pattern) — state rows keyed by platform+chat_id."""
from __future__ import annotations

import json

from sqlmodel import Field, Session, select

from app.db import engine
from app.models import BotState


def get_chat_state(chat_id: int, platform: str) -> dict | None:
    """Return {"state": ..., "payload": {...}} or None."""
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if not row:
            return None
        return {"state": row.state, "payload": json.loads(row.payload or "{}")}


def set_chat_state(chat_id: int, platform: str, state: str, payload: dict | None = None) -> None:
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if not row:
            row = BotState(platform=platform, chat_id=chat_id)
            s.add(row)
        row.state = state
        row.payload = json.dumps(payload or {}, ensure_ascii=False)
        s.commit()


def clear_chat_state(chat_id: int, platform: str) -> None:
    with Session(engine) as s:
        row = s.exec(
            select(BotState).where(BotState.platform == platform, BotState.chat_id == chat_id)
        ).first()
        if row:
            s.delete(row)
            s.commit()
