"""Reserve a bounded maximum before model I/O; uncertain cost remains charged."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import os
from uuid import uuid4

from sqlalchemy import func, select, text

from app.db.copilot_models import CopilotBudgetDay, CopilotUsage

MODEL = "gpt-5.6-luna"
# Official model page verified 2026-09-07, USD per million tokens.
INPUT_RATE, CACHED_RATE, OUTPUT_RATE = Decimal("0.20"), Decimal("0.02"), Decimal("1.20")
MAX_OUTPUT_TOKENS = 550
MAX_PAYLOAD_BYTES = 24000
TIMEOUT_SECONDS = 15
MONEY_UNIT = Decimal("0.00000001")


class BudgetError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ChatPolicy:
    enabled: bool = False
    model: str = MODEL
    daily_usd: Decimal = Decimal("0")
    shop_daily_usd: Decimal = Decimal("0.05")
    shop_daily_requests: int = 30
    shop_per_minute: int = 3

    @classmethod
    def from_env(cls):
        try:
            daily = Decimal(os.getenv("AI_CHAT_DAILY_USD", "0"))
            shop = Decimal(os.getenv("AI_CHAT_SHOP_DAILY_USD", "0.05"))
            count = int(os.getenv("AI_CHAT_SHOP_DAILY_REQUESTS", "30"))
            minute = int(os.getenv("AI_CHAT_SHOP_PER_MINUTE", "3"))
            model = os.getenv("AI_CHAT_MODEL", MODEL).strip()
            if not daily.is_finite() or not shop.is_finite() or daily < 0 or shop < 0 or count < 1 or minute < 1 or model != MODEL:
                raise ValueError()
            return cls(os.getenv("AI_CHAT_ENABLED", "false").lower() == "true", model, daily, shop, count, minute)
        except (ValueError, InvalidOperation):
            raise BudgetError("invalid_configuration") from None


def utc_now():
    return datetime.now(timezone.utc)


def _lock(db):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(739201607)"))
    else:
        raise BudgetError("budget_unavailable")


def reserve(factory, *, shop_id, input_token_bound, policy):
    if not policy.enabled:
        raise BudgetError("disabled")
    if policy.model != MODEL:
        raise BudgetError("invalid_configuration")
    if policy.daily_usd <= 0 or policy.shop_daily_usd <= 0:
        raise BudgetError("budget_disabled")
    maximum = ((input_token_bound * INPUT_RATE + MAX_OUTPUT_TOKENS * OUTPUT_RATE) / 1_000_000).quantize(MONEY_UNIT, rounding=ROUND_CEILING)
    with factory() as db:
        _lock(db)
        now = utc_now()
        day = now.date().isoformat()
        daily = db.get(CopilotBudgetDay, day)
        charged = daily.charged_usd if daily else Decimal("0")
        if charged + maximum > policy.daily_usd:
            raise BudgetError("global_budget_exhausted")
        spent, count = db.execute(select(func.coalesce(func.sum(func.coalesce(CopilotUsage.estimated_usd, CopilotUsage.reserved_usd)), 0),
            func.count(CopilotUsage.id)).where(CopilotUsage.shop_id == shop_id, CopilotUsage.day == day)).one()
        if spent + maximum > policy.shop_daily_usd or count >= policy.shop_daily_requests:
            raise BudgetError("shop_budget_exhausted")
        recent = db.scalar(select(func.count(CopilotUsage.id)).where(CopilotUsage.shop_id == shop_id,
            CopilotUsage.created_at >= now - timedelta(minutes=1)))
        if recent >= policy.shop_per_minute:
            raise BudgetError("shop_rate_limited")
        if daily is None:
            daily = CopilotBudgetDay(day=day, charged_usd=0)
            db.add(daily)
        daily.charged_usd = charged + maximum
        key = str(uuid4())
        db.add(CopilotUsage(id=key, shop_id=shop_id, day=day, created_at=now, model=policy.model,
                            reserved_usd=maximum, outcome="reserved"))
        db.commit()
        return key


def _token_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def finish(factory, key, *, usage, outcome, latency_ms):
    usage = usage if isinstance(usage, dict) else {}
    input_tokens = _token_count(usage.get("input_tokens"))
    output_tokens = _token_count(usage.get("output_tokens"))
    details = usage.get("input_tokens_details") or {}
    cached = _token_count(details.get("cached_tokens", 0)) if isinstance(details, dict) else None
    known = input_tokens is not None and output_tokens is not None and cached is not None and cached <= input_tokens
    cost = ((input_tokens - cached) * INPUT_RATE + cached * CACHED_RATE + output_tokens * OUTPUT_RATE) / 1_000_000 if known else None
    with factory() as db:
        _lock(db)
        row = db.get(CopilotUsage, key)
        if row is None or row.outcome != "reserved":
            return  # Privacy deletion or a repeated completion must not refund twice.
        row.outcome = outcome
        row.latency_ms = max(0, int(latency_ms))
        if cost is not None:
            row.input_tokens, row.cached_input_tokens, row.output_tokens = input_tokens, cached, output_tokens
            row.estimated_usd = cost.quantize(MONEY_UNIT, rounding=ROUND_CEILING)
            day = db.get(CopilotBudgetDay, row.day)
            if day:
                day.charged_usd = max(Decimal("0"), day.charged_usd - row.reserved_usd + row.estimated_usd)
        db.commit()
