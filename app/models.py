"""Database models (plan v3.1 §7) — users → birth_profiles → charts.

Gender is OPTIONAL (Claude review #6): NULL-safe, never affects computation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=_uuid, primary_key=True)
    phone: str | None = Field(default=None, unique=True, index=True)  # OTP login (lazy)
    email: str | None = Field(default=None, unique=True)
    password_hash: str | None = Field(default=None)
    role: str = Field(default="user")  # user | admin
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BirthProfile(SQLModel, table=True):
    """One person per profile — user can have many (self/mother/spouse/friend → synastry)."""
    __tablename__ = "birth_profiles"
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    name: str = Field(default="")
    gender: str | None = Field(default=None)  # OPTIONAL — never used in computation
    # raw input (auditable)
    calendar_system: str = Field(default="jalali")  # jalali | gregorian
    raw_year: int
    raw_month: int
    raw_day: int
    time_known: bool = Field(default=False)
    hour: int | None = Field(default=None)
    minute: int | None = Field(default=None)
    # location
    city_fa: str | None = Field(default=None)
    province_fa: str | None = Field(default=None)
    lat: float | None = Field(default=None)
    lon: float | None = Field(default=None)
    tz_name: str = Field(default="Asia/Tehran")
    utc_datetime: datetime | None = Field(default=None)  # computed
    focus_areas: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    personal_question: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chart(SQLModel, table=True):
    """Canonical Chart JSON (deterministic, cached) + engine config snapshot."""
    __tablename__ = "charts"
    id: str = Field(default_factory=_uuid, primary_key=True)
    profile_id: str | None = Field(default=None, foreign_key="birth_profiles.id", index=True)
    chart_json: dict = Field(sa_column=Column(JSONB))          # canonical output
    engine_config: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # snapshot
    svg_path: str | None = Field(default=None)
    # capability token: anonymous-ownership proof (audit P0-1) — download/report
    # gated by this token (or user_id) so a bare UUID can't leak birth data.
    access_token: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMRun(SQLModel, table=True):
    """Cost/usage metering per report call (Claude review #7)."""
    __tablename__ = "llm_runs"
    id: str = Field(default_factory=_uuid, primary_key=True)
    report_id: str | None = Field(default=None, index=True)
    provider: str
    model: str
    gateway: str | None = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    latency_ms: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    ok: bool = Field(default=True)
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Report(SQLModel, table=True):
    """Generated 13-section report (sections + metrics + PDF artifact)."""
    __tablename__ = "reports"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chart_id: str = Field(default=None, foreign_key="charts.id", index=True)
    status: str = Field(default="queued")  # queued | running | done | failed
    plan_key: str | None = Field(default=None)   # section set: basic|full|gold (plan v3.0 §10.3)
    sections: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    pdf_path: str | None = Field(default=None)
    r2_key: str | None = Field(default=None)   # R2 object key (reports/<id>.pdf) when uploaded
    error: str | None = Field(default=None)
    retry_count: int = Field(default=0)        # DLQ retry tracking (Phase 3)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Plan(SQLModel, table=True):
    """Sellable report plans (Phase 4 — commercial)."""
    __tablename__ = "plans"
    key: str = Field(primary_key=True)  # basic | full | gold
    name_fa: str
    subtitle_fa: str = Field(default="")
    price_toman: int  # e.g. 149_000 (تومان) — stored for display
    features: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    sort: int = Field(default=0)
    active: bool = Field(default=True)

    @property
    def price_rial(self) -> int:
        """Zarinpal v4 amount unit = Rial (ریال)."""
        return self.price_toman * 10


class Order(SQLModel, table=True):
    """Payment order — one per (profile, plan) purchase."""
    __tablename__ = "orders"
    id: str = Field(default_factory=_uuid, primary_key=True)
    profile_id: str | None = Field(default=None, foreign_key="birth_profiles.id", index=True)
    chart_id: str | None = Field(default=None, foreign_key="charts.id", index=True)
    plan_key: str = Field(default=None, foreign_key="plans.key", index=True)
    amount_rial: int
    status: str = Field(default="pending")  # pending | paid | failed | expired
    coupon_id: str | None = Field(default=None, foreign_key="coupons.id")
    authority: str | None = Field(default=None, index=True)
    ref_id: str | None = Field(default=None)
    card_pan: str | None = Field(default=None)
    report_id: str | None = Field(default=None, index=True)  # linked once generated
    secondary_chart_id: str | None = Field(default=None, index=True)  # synastry pair (plan §8)
    chat_id: str | None = Field(default=None, index=True)             # bot subscription (plan §7)
    platform: str | None = Field(default=None)                        # telegram | bale
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: datetime | None = Field(default=None)


class Coupon(SQLModel, table=True):
    __tablename__ = "coupons"
    id: str = Field(default_factory=_uuid, primary_key=True)
    code: str = Field(unique=True, index=True)
    percent: int = Field(default=0)          # discount percent (0-100)
    max_uses: int = Field(default=1)
    used_count: int = Field(default=0)
    expires_at: datetime | None = Field(default=None)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_id: str = Field(index=True)
    platform: str = Field(default="telegram")   # telegram | bale
    chart_id: str = Field(index=True)
    freq: str = Field(default="daily")          # daily | weekly
    plan_key: str = Field(default="monthly")    # paid monthly plan (plan v3.0 §12)
    active: bool = Field(default=True)
    expires_at: datetime | None = Field(default=None)
    last_sent_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WeeklyReflection(SQLModel, table=True):
    """Stored weekly reflection per chart («نگاهی به آسمان هفته» — audit P0-2)."""
    __tablename__ = "weekly_reflections"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chart_id: str = Field(index=True)
    week_start: str = Field(index=True)         # 'YYYY-MM-DD'
    text: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReferralEvent(SQLModel, table=True):
    __tablename__ = "referral_events"
    id: str = Field(default_factory=_uuid, primary_key=True)
    code: str = Field(index=True)            # referrer's public referral code (was phone — P1-1)
    referrer_user_id: str | None = Field(default=None)
    new_user_id: str | None = Field(default=None)
    order_id: str | None = Field(default=None, index=True)
    amount_rial: int = Field(default=0)
    reward_rial: int = Field(default=0)
    status: str = Field(default="pending")   # pending | rewarded
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReferralCode(SQLModel, table=True):
    """Stable random referral code per user (no PII in the URL — audit P1-1)."""
    __tablename__ = "referral_codes"
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    code: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PromptVersion(SQLModel, table=True):
    """Admin-editable prompt overrides (plan v3.0 §8 — مدیریت پرامپتها).
    One active row per prompt_key; save() bumps version."""
    __tablename__ = "prompt_versions"
    id: str = Field(default_factory=_uuid, primary_key=True)
    prompt_key: str = Field(index=True)      # domain key (identity..karma) or "cultural"
    version: int = Field(default=1)
    content: str
    is_active: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    id: int | None = Field(default=None, primary_key=True)
    admin: str = ""
    action: str = ""
    entity: str = ""
    details: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BotState(SQLModel, table=True):
    """Per-chat bot state machine row (v135 pattern)."""
    __tablename__ = "bot_chat_states"
    __table_args__ = (UniqueConstraint("platform", "chat_id", name="uq_botstate_platform_chat"),)
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    platform: str = Field(index=True)  # telegram | bale
    chat_id: int = Field(index=True)
    state: str = ""
    payload: str | None = None  # JSON
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Secret(SQLModel, table=True):
    """Admin-panel secret (encrypted at rest) — see app.secret_store."""
    __tablename__ = "secrets"
    key: str = Field(primary_key=True)
    value_encrypted: str
    updated_by: str = Field(default="admin")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

