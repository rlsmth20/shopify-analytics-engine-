"""Additive growth tables; timestamps are UTC Unix seconds on both supported DBs."""
import time
import uuid

from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def uid() -> str:
    return uuid.uuid4().hex


class Memory(Base):
    __tablename__ = "growth_memory"
    __table_args__ = (UniqueConstraint("namespace", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    namespace: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class Evidence(Base):
    __tablename__ = "growth_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(240), unique=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(String(1000))
    epistemic: Mapped[str] = mapped_column(String(24), default="OBSERVATION")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    recorded_at: Mapped[float] = mapped_column(Float, default=time.time)


class Work(Base):
    __tablename__ = "growth_work"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(240), unique=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    due_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    lease_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class Contact(Base):
    __tablename__ = "growth_contacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    identity: Mapped[str] = mapped_column(String(320), unique=True)
    organization: Mapped[str] = mapped_column(String(255), default="Unknown")
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(1000))
    facts: Mapped[list] = mapped_column(JSON, default=list)
    characteristics: Mapped[dict] = mapped_column(JSON, default=dict)
    qualification: Mapped[dict] = mapped_column(JSON, default=dict)
    # Authority is set through owner-authenticated ingestion, never inferred by a model.
    contact_basis: Mapped[str] = mapped_column(String(40), default="research_only")
    status: Mapped[str] = mapped_column(String(40), default="prospect", index=True)
    suppressed: Mapped[bool] = mapped_column(default=False)
    shop_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Experiment(Base):
    __tablename__ = "growth_experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    specification: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[float] = mapped_column(Float, default=time.time)
    stop_at: Mapped[float] = mapped_column(Float)


class Message(Base):
    __tablename__ = "growth_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    contact_id: Mapped[str] = mapped_column(String(32), index=True)
    experiment_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(10))
    variant: Mapped[str] = mapped_column(String(64), default="health_check")
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    provider_id: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    reply_to_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    skill_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    sent_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class FirstContact(Base):
    """Shared first-contact admission ledger, including browser-operated channels."""
    __tablename__ = "growth_first_contacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    contact_id: Mapped[str] = mapped_column(String(32), unique=True)
    action_key: Mapped[str] = mapped_column(String(200), unique=True)
    channel: Mapped[str] = mapped_column(String(40))
    experiment_id: Mapped[str] = mapped_column(String(32))
    cohort: Mapped[dict] = mapped_column(JSON)
    body_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="reserved", index=True)
    reserved_at: Mapped[float] = mapped_column(Float, default=time.time)
    sent_at: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    receipt: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class Usage(Base):
    __tablename__ = "growth_usage"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[str] = mapped_column(String(24), default="model")
    model: Mapped[str] = mapped_column(String(100))
    task: Mapped[str] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserved_usd: Mapped[float] = mapped_column(Float, default=0)
    estimated_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(40), default="reserved")
    escalated_from: Mapped[str | None] = mapped_column(String(100), nullable=True)
    escalation_improved: Mapped[bool | None] = mapped_column(nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class SkillRevision(Base):
    __tablename__ = "growth_skills"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(default=1)
    specification: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
