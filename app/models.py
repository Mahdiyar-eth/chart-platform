"""Database models (plan v3.1 §7) — users → birth_profiles → charts.

Gender is OPTIONAL (Claude review #6): NULL-safe, never affects computation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, UniqueConstraint, text
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
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
    balance_rial: int = Field(default=0)  # referral wallet (D3)
    credits: int = Field(default=0, sa_column=Column(Integer, default=0, server_default="0"))
    free_exploration_used: bool = Field(default=False, sa_column=Column(Boolean, default=False, server_default="false"))
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
    zodiac: str = Field(default="tropical")  # tropical | sidereal (Vedic/Lahiri) — audit r3
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
    user_id: str | None = Field(default=None, index=True)  # H1.3: who paid
    kind: str = Field(default="report")  # H1.3: report|chat|transit|article
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
    # M5 (multi-provider plan): per-key / per-section observability.
    key_slot: str | None = Field(default=None, index=True)   # go-1 / go-2 / zen-free / deepseek
    section: str | None = Field(default=None)                # report domain (career/love/…)
    attempt: int = Field(default=0)                          # 0-based retry attempt
    error_code: str | None = Field(default=None)             # 429 / empty / timeout / 5xx / …
    fallback_used: bool = Field(default=False)               # provider chain fell back
    prompt_version: str | None = Field(default=None)         # prompt template version
    # H1.3 indexes (match migrations bad790d98ddf): kind + (created_at, kind)
    __table_args__ = (
        Index("ix_llm_runs_kind", "kind"),
        Index("ix_llm_runs_created_kind", "created_at", "kind"),
    )


class ChatMessage(SQLModel, table=True):
    """AI chat turn — serves both user-visible history and admin usage metering."""
    __tablename__ = "chat_messages"
    id: str = Field(default_factory=_uuid, primary_key=True)
    chart_id: str = Field(default=None, foreign_key="charts.id", index=True)
    role: str = Field(default="user")  # user | assistant
    content: str = Field(default="")
    intent: str | None = Field(default=None)
    domains: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    provider: str | None = Field(default=None)
    model: str | None = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    ok: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Exploration(SQLModel, table=True):
    """P3 — self-discovery card exploration: 2–4 evidence-backed insights
    produced from chart factors via the same LLM→QA→retry pipeline."""
    __tablename__ = "explorations"
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    chart_id: str | None = Field(default=None, foreign_key="charts.id", index=True)
    card_key: str = Field(default="")            # intent id from CARD_CATALOG
    title_fa: str = Field(default="")            # card title snapshot
    status: str = Field(default="running")       # running | done | failed
    result: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # {insights[], evidence[]}
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # calls/retries/tokens/duration
    credits_cost: int = Field(default=1)
    refunded: bool = Field(default=False)
    error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreditTransaction(SQLModel, table=True):
    """Ledger for credit economy (P3/P6) — accounting invariant:
    sum(amount) per user == current credits, every row links a reason."""
    __tablename__ = "credit_transactions"
    # A1 — idempotency: a spend/grant keyed by the same idempotency_key never
    # double-charges. Enforced by uq_credit_tx_idem_key (unique index).
    __table_args__ = (Index("uq_credit_tx_idem_key", "idempotency_key", unique=True),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(default=None, foreign_key="users.id", index=True)
    amount: int = Field(default=0)               # +gift/topup, -exploration, +refund
    reason: str = Field(default="")              # free_gift|exploration|refund|topup|subscription
    ref_id: str | None = Field(default=None)     # exploration/order id
    idempotency_key: str | None = Field(default=None)   # A1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreditPrice(SQLModel, table=True):
    """A1 — per-action credit cost (unit-of-money = credit). Seeded from
    HERMES-PLAN-v1 section 3.2; admin-editable, never hard-coded in gates.
    Keyed by action_key (e.g. 'report_full', 'transit_12m')."""
    __tablename__ = "credit_prices"
    action_key: str = Field(primary_key=True)
    title_fa: str = Field(default="")
    credits: int = Field(default=1)
    active: bool = Field(default=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={
            "server_default": text("now()"),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )


class Entitlement(SQLModel, table=True):
    """A1 — entitlement grants belonging to a USER (not a chart), consumed by
    gated features. source: credit|order|subscription|migration."""
    __tablename__ = "entitlements"
    __table_args__ = (
        Index("ix_entitlements_user_kind", "user_id", "kind"),
        Index("ix_entitlements_chart_kind", "chart_id", "kind"),
    )
    id: str = Field(default_factory=_uuid, primary_key=True)
    # A1 — entitlement belongs to a USER; (user_id, kind) composite index covers
    # user-scoped lookups (no separate single-column index — matches plan A1).
    user_id: str = Field(default=None, foreign_key="users.id")
    kind: str = Field(default="")             # report|chat|transit|synastry|rectify|audio
    chart_id: str | None = Field(default=None)
    ref_id: str | None = Field(default=None)  # report_id / forecast_id
    quantity: int = Field(default=1)
    used: int = Field(default=0)
    expires_at: datetime | None = Field(default=None)
    source: str = Field(default="credit")
    source_ref: str | None = Field(default=None)   # credit_transactions.id / order.id
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
    updated_at: datetime = Field(  # H0.4: heartbeat for stale-job recovery
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={
            "server_default": text("now()"),
            "onupdate": lambda: datetime.now(timezone.utc),
        },
    )
    # H1.5: async report audio (edge-tts via worker) — none|generating|ready|failed
    audio_status: str = Field(default="none", index=True)  # ix_reports_audio_status
    audio_r2_key: str | None = Field(default=None)
    # H0.4/H1.5 indexes (match migrations cc51bd1b6bf1, 9d34ed9201c2)
    __table_args__ = (
        Index("ix_reports_status_updated", "status", "updated_at"),
    )


class Plan(SQLModel, table=True):
    """Sellable report plans (Phase 4 — commercial)."""
    __tablename__ = "plans"
    key: str = Field(primary_key=True)  # basic | full | gold
    name_fa: str
    subtitle_fa: str = Field(default="")
    price_toman: int  # e.g. 149_000 (تومان) — stored for display
    features: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    credits_grant: int = Field(default=0, sa_column=Column(Integer, default=0, server_default="0"))
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
    error: str | None = Field(default=None)  # audit r4 B6 — refund/gateway failure detail
    note: str | None = Field(default=None)   # D3 — payment method note (wallet)
    profile_id: str | None = Field(default=None, foreign_key="birth_profiles.id", index=True)
    chart_id: str | None = Field(default=None, foreign_key="charts.id", index=True)
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)  # P6: pack orders without chart
    # R13/N3: FK dropped to a plain indexed column — credit-action orders
    # (report_full etc.) don't reference plans.key. Legacy rows keep working.
    plan_key: str = Field(default=None, index=True)
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
    report_only: bool = Field(default=False)  # §13 — only on the FIRST deep report
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    """Paid monthly chat subscription (plan v3.0 §12). One per (chart, account)."""
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("uq_sub_chart_account", "chart_id",
              text("COALESCE(chat_id, '')"), unique=True),
    )
    id: str = Field(default_factory=_uuid, primary_key=True)
    chat_id: str | None = Field(default=None, index=True)  # None = web (non-bot) purchase
    platform: str = Field(default="telegram")   # telegram | bale
    chart_id: str = Field(index=True)
    freq: str = Field(default="daily")          # daily | weekly
    plan_key: str = Field(default="monthly")    # paid monthly plan (plan v3.0 §12)
    active: bool = Field(default=True)
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    order_id: str | None = Field(default=None, index=True)  # audit r4 B6 — originating order (refund closes the sub)
    last_credit_grant_at: datetime | None = Field(default=None)  # H — monthly 5-credit grant (once per month)
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


class DailyReflection(SQLModel, table=True):
    """P4/E — daily reflection per chart per LOCAL day.
    Unique (chart_id, day_local) → duplicate-day submissions are impossible
    (E5: cannot duplicate same day, cannot fake streak)."""
    __tablename__ = "daily_reflections"
    __table_args__ = (UniqueConstraint("chart_id", "day_local", name="uq_daily_reflection_chart_day"),)
    id: str = Field(default_factory=_uuid, primary_key=True)
    chart_id: str = Field(default=None, foreign_key="charts.id", index=True)
    day_local: str = Field(default="", index=True)   # 'YYYY-MM-DD' in USER tz
    tz_name: str = Field(default="Asia/Tehran")
    answer: str = Field(default="")
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


class WithdrawalRequest(SQLModel, table=True):
    """Wallet cash-out request (D3) — admin approves manually (status=paid)."""
    __tablename__ = "withdrawal_requests"
    # F-11 (audit v6 P0): partial unique index — at most ONE pending withdrawal
    # per user, enforced at the DB level against concurrent requests.
    __table_args__ = (
        Index("uq_withdrawal_one_pending", "user_id", unique=True,
              postgresql_where=text("status = 'pending'")),
    )
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    amount_rial: int = Field(default=0)
    status: str = Field(default="pending")   # pending | paid | rejected
    note: str = Field(default="")            # admin note (bank ref etc.)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = Field(default=None)


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


class PushSubscription(SQLModel, table=True):
    """Web Push subscription (D1) — one row per browser endpoint."""
    __tablename__ = "push_subscriptions"
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    user_id: str | None = Field(default=None, foreign_key="users.id", index=True)
    endpoint: str = Field(unique=True, index=True)
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConsentLog(SQLModel, table=True):
    """G9 (§85) — explicit consent records (terms/privacy/notifications/analytics).
    Append-only: one row per (user, purpose, version); first acceptance is
    recorded at signup, later rows for purpose-specific consent."""
    __tablename__ = "consent_logs"
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    user_id: str = Field(foreign_key="users.id", index=True)
    purpose: str = Field(default="terms")   # terms|privacy|notifications|analytics
    version: str = Field(default="v1")
    accepted: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationPrefs(SQLModel, table=True):
    """G8 (§57) — per-user notification preferences + quiet hours.
    One row per user; defaults are permissive (daily/weekly on, quiet 23-7)."""
    __tablename__ = "notification_prefs"
    user_id: str = Field(primary_key=True, foreign_key="users.id")
    daily_insight: bool = Field(default=True, sa_column=Column(Boolean, default=True, server_default="true"))
    weekly_reflection: bool = Field(default=True, sa_column=Column(Boolean, default=True, server_default="true"))
    report_ready: bool = Field(default=True, sa_column=Column(Boolean, default=True, server_default="true"))
    transit_alerts: bool = Field(default=True, sa_column=Column(Boolean, default=True, server_default="true", nullable=False))  # B4/Z11: NOT NULL (model = truth; c8d2 had flipped it nullable)
    quiet_start: int = Field(default=23)   # local hour (0-23)
    quiet_end: int = Field(default=7)      # local hour (0-23)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportChunk(SQLModel, table=True):
    """pgvector RAG (D2): semantic chunks of a finished report for grounded
    chat retrieval. embedding is a pgvector column (384-dim for e5-small)."""
    __tablename__ = "report_chunks"
    __table_args__ = (
        Index(
            "ix_report_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    report_id: str = Field(foreign_key="reports.id", index=True)
    chunk_index: int = Field(default=0)
    section_key: str = Field(default="")
    text: str = Field(default="")
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(384), nullable=True),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FunnelEvent(SQLModel, table=True):
    """G1 — funnel/analytics event (anonymous, append-only). Source of truth for
    the admin conversion funnel dashboard. Lightweight; no PII by design."""
    __tablename__ = "funnel_events"
    id: int = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    event: str = Field(index=True, max_length=64)
    session_id: str = Field(default="", index=True, max_length=64)
    path: str = Field(default="", max_length=255)
    ref: str = Field(default="", max_length=64)
    props: str = Field(default="{}", max_length=1024)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransitForecast(SQLModel, table=True):
    """B1 cache — transit forecast payload per chart + months, TTL 7 days."""
    __tablename__ = "transit_forecasts"
    __table_args__ = (
        UniqueConstraint("chart_id", "months", name="uq_transit_chart_months"),  # X-R23
    )
    id: int | None = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    # Z2/R3: FK restored — this table holds PAID narratives (personal data);
    # it must die with the chart (PRIVACY.md), not outlive it. The c8d2e3f4a5b6
    # migration had dropped the constraint to satisfy `alembic check` — fixed
    # in the right direction here (model first, then migration).
    chart_id: str = Field(
        max_length=64,
        sa_column=Column("chart_id", String(64),
                         sa.ForeignKey("charts.id", ondelete="CASCADE"),
                         nullable=False, index=True),
    )
    months: int = Field(default=12)
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransitAlertLog(SQLModel, table=True):
    """B4 — one row per (user_key, ISO-week, chart): weekly transit push anti-duplicate."""
    __tablename__ = "transit_alert_log"
    id: int | None = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    user_key: str = Field(index=True, max_length=128)   # users.id or bot:{chat_id}:{platform}
    week: str = Field(index=True, max_length=10)        # e.g. 2026-W34
    chart_id: str = Field(index=True, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Subscriber(SQLModel, table=True):
    """G3 — newsletter/lead-magnet contact. Explicit consent + mandatory unsubscribe."""
    __tablename__ = "subscribers"
    id: int | None = Field(primary_key=True, default=None, sa_column_kwargs={"autoincrement": True})
    contact: str = Field(index=True, max_length=200)          # phone or email
    channel: str = Field(default="sms", max_length=20)        # sms | email | telegram
    source: str = Field(default="guide", max_length=40)       # guide | weekly-sky | referral
    token: str = Field(default="", index=True, max_length=64) # one-time download / unsub link
    unsubscribed_at: datetime | None = Field(default=None)
    consent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
