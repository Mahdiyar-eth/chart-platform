"""Admin prompt overrides (plan v3.0 §8 — مدیریت پرامپتها).

Worker merges active overrides into generated prompts at report time;
admin UI saves new versions. Never raises: generation must not break
if the table is missing or DB is down.
"""
from app.db import Session, engine
from app.models import PromptVersion
from sqlmodel import select


def get_overrides() -> dict[str, str]:
    """Active overrides: {prompt_key: content}. Empty dict on any failure."""
    try:
        with Session(engine) as s:
            rows = s.exec(select(PromptVersion).where(PromptVersion.is_active == True)).all()  # noqa: E712
            return {r.prompt_key: r.content for r in rows}
    except Exception:  # noqa: BLE001 — overrides are an enhancement, never a blocker
        return {}


def set_override(session, prompt_key: str, content: str) -> PromptVersion:
    """Bump version: deactivate old active row, insert new one. Returns new row."""
    from datetime import datetime, timezone

    old = session.exec(select(PromptVersion).where(
        PromptVersion.prompt_key == prompt_key,
        PromptVersion.is_active == True)).first()  # noqa: E712
    next_version = (old.version + 1) if old else 1
    if old:
        old.is_active = False
        session.add(old)
    row = PromptVersion(prompt_key=prompt_key, version=next_version,
                        content=content, is_active=True,
                        updated_at=datetime.now(timezone.utc))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
