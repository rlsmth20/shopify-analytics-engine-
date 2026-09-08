"""Ask Skubase economics only; never persist questions, answers or catalog context."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CopilotBudgetDay(Base):
    __tablename__ = "copilot_budget_days"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    charged_usd: Mapped[Decimal] = mapped_column(Numeric(16, 8), default=0)


class CopilotUsage(Base):
    __tablename__ = "copilot_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    model: Mapped[str] = mapped_column(String(80))
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(16, 8))
    estimated_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cached_input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="reserved")
