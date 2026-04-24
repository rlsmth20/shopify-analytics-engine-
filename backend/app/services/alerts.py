"""Alert rule engine.

The engine evaluates the current inventory state against a set of rules and
produces AlertEvent records. Each event can be delivered through one or more
notification channels via the notifications module.

Rules + channels are stored in-memory for the MVP; swapping in a database-backed
store is a straight replacement of the module-level registries below.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.schemas import InventoryAction
from app.schemas_v2 import (
    AlertEvent,
    AlertRule,
    AlertSeverity,
    AlertTrigger,
    ForecastResult,
    NotificationChannel,
    NotificationChannelConfig,
    SupplierScorecard,
)
from app.services.notifications import deliver


# ---------------------------------------------------------------------------
# In-memory registries (swap out for DB-backed stores in production)
# ---------------------------------------------------------------------------

_RULES: dict[str, AlertRule] = {}
_CHANNEL_CONFIG: dict[NotificationChannel, NotificationChannelConfig] = {}
_EVENTS: list[AlertEvent] = []


def seed_default_rules_and_channels() -> None:
    """Idempotent seed so a fresh process has reasonable defaults."""
    if _RULES:
        return

    now = datetime.now(timezone.utc)
    defaults = [
        AlertRule(
            id=str(uuid.uuid4()),
            name="Critical stockout risk",
            trigger="stockout_risk",
            severity="critical",
            channels=["email", "slack"],
            threshold=3.0,  # days until stockout
            enabled=True,
            created_at=now,
        ),
        AlertRule(
            id=str(uuid.uuid4()),
            name="Dead stock capital review",
            trigger="dead_stock",
            severity="warning",
            channels=["email"],
            threshold=500.0,  # USD tied up
            enabled=True,
            created_at=now,
        ),
        AlertRule(
            id=str(uuid.uuid4()),
            name="Overstock hitting 90+ days",
            trigger="overstock",
            severity="warning",
            channels=["email"],
            threshold=90.0,  # days of cover
            enabled=True,
            created_at=now,
        ),
        AlertRule(
            id=str(uuid.uuid4()),
            name="Forecast miss > 20%",
            trigger="forecast_miss",
            severity="info",
            channels=["email"],
            threshold=20.0,  # percentage
            enabled=True,
            created_at=now,
        ),
        AlertRule(
            id=str(uuid.uuid4()),
            name="Supplier slipping on-time delivery",
            trigger="supplier_slip",
            severity="warning",
            channels=["email", "slack"],
            threshold=80.0,  # on-time percent
            enabled=True,
            created_at=now,
        ),
    ]
    for rule in defaults:
        _RULES[rule.id] = rule

    _CHANNEL_CONFIG["email"] = NotificationChannelConfig(
        channel="email", enabled=True, target="alerts@example.com", verified=False
    )
    _CHANNEL_CONFIG["sms"] = NotificationChannelConfig(
        channel="sms", enabled=False, target="", verified=False
    )
    _CHANNEL_CONFIG["slack"] = NotificationChannelConfig(
        channel="slack", enabled=False, target="", verified=False
    )
    _CHANNEL_CONFIG["webhook"] = NotificationChannelConfig(
        channel="webhook", enabled=False, target="", verified=False
    )


def list_rules() -> list[AlertRule]:
    return list(_RULES.values())


def create_rule(
    *,
    name: str,
    trigger: AlertTrigger,
    severity: AlertSeverity,
    channels: list[NotificationChannel],
    threshold: float,
    enabled: bool = True,
) -> AlertRule:
    rule = AlertRule(
        id=str(uuid.uuid4()),
        name=name,
        trigger=trigger,
        severity=severity,
        channels=list(channels),
        threshold=threshold,
        enabled=enabled,
        created_at=datetime.now(timezone.utc),
    )
    _RULES[rule.id] = rule
    return rule


def delete_rule(rule_id: str) -> bool:
    return _RULES.pop(rule_id, None) is not None


def toggle_rule(rule_id: str, enabled: bool) -> Optional[AlertRule]:
    rule = _RULES.get(rule_id)
    if rule is None:
        return None
    updated = rule.model_copy(update={"enabled": enabled})
    _RULES[rule_id] = updated
    return updated


def list_channel_configs() -> list[NotificationChannelConfig]:
    return list(_CHANNEL_CONFIG.values())


def update_channel_config(
    *,
    channel: NotificationChannel,
    enabled: bool,
    target: str,
) -> NotificationChannelConfig:
    existing = _CHANNEL_CONFIG.get(channel)
    updated = NotificationChannelConfig(
        channel=channel,
        enabled=enabled,
        target=target,
        verified=existing.verified if existing else False,
    )
    _CHANNEL_CONFIG[channel] = updated
    return updated


def list_recent_events(limit: int = 50) -> list[AlertEvent]:
    return list(_EVENTS[-limit:])


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationContext:
    actions: list[InventoryAction]
    forecasts: list[ForecastResult]
    supplier_scores: list[SupplierScorecard]


def evaluate(context: EvaluationContext, deliver_channels: bool = False) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    now = datetime.now(timezone.utc)

    for rule in _RULES.values():
        if not rule.enabled:
            continue
        events.extend(_evaluate_rule(rule, context, now, deliver_channels))

    _EVENTS.extend(events)
    return events


def _evaluate_rule(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    if rule.trigger == "stockout_risk":
        return _stockout_events(rule, context, now, deliver_channels)
    if rule.trigger == "dead_stock":
        return _dead_stock_events(rule, context, now, deliver_channels)
    if rule.trigger == "overstock":
        return _overstock_events(rule, context, now, deliver_channels)
    if rule.trigger == "supplier_slip":
        return _supplier_events(rule, context, now, deliver_channels)
    if rule.trigger == "forecast_miss":
        return _forecast_events(rule, context, now, deliver_channels)
    return []


def _stockout_events(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    for action in context.actions:
        if action.status != "urgent":
            continue
        days = getattr(action, "days_until_stockout", action.days_of_inventory)
        if days > rule.threshold:
            continue
        msg = (
            f"{action.name} will stock out in {days:.1f} days at current velocity. "
            f"Recommended: {action.recommended_action}"
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels))
    return events


def _dead_stock_events(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    for action in context.actions:
        if action.status != "dead":
            continue
        cash = getattr(action, "cash_tied_up", 0)
        if cash < rule.threshold:
            continue
        msg = (
            f"{action.name}: ${cash:,.0f} tied up in stale inventory. "
            f"Recommended: {action.recommended_action}"
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels))
    return events


def _overstock_events(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    for action in context.actions:
        if action.status != "optimize":
            continue
        if action.days_of_inventory < rule.threshold:
            continue
        msg = (
            f"{action.name} at {action.days_of_inventory:.0f} days of cover — "
            f"${getattr(action, 'cash_tied_up', 0):,.0f} parked inventory."
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels))
    return events


def _supplier_events(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    for vendor in context.supplier_scores:
        if vendor.on_time_pct >= rule.threshold:
            continue
        msg = (
            f"Vendor {vendor.vendor} on-time rate dropped to {vendor.on_time_pct:.0f}%. "
            "Consider extending safety stock for this vendor's SKUs."
        )
        events.append(_fire(rule, None, vendor.vendor, msg, now, deliver_channels))
    return events


def _forecast_events(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    for forecast in context.forecasts:
        if forecast.stockout_probability_30d * 100 < rule.threshold:
            continue
        msg = (
            f"Forecast flags {forecast.sku_id} with {forecast.stockout_probability_30d*100:.0f}% "
            "stockout probability in the next 30 days."
        )
        events.append(_fire(rule, forecast.sku_id, forecast.sku_id, msg, now, deliver_channels))
    return events


def _fire(
    rule: AlertRule,
    sku_id: Optional[str],
    sku_name: Optional[str],
    message: str,
    now: datetime,
    deliver_channels: bool,
) -> AlertEvent:
    channels_sent: list[NotificationChannel] = []
    delivered = True

    if deliver_channels:
        for channel in rule.channels:
            config = _CHANNEL_CONFIG.get(channel)
            if not config or not config.enabled or not config.target:
                continue
            record = deliver(
                channel=channel,
                target=config.target,
                subject=f"[{rule.severity.upper()}] {rule.name}",
                body=message,
            )
            if record.delivered:
                channels_sent.append(channel)
            else:
                delivered = False

    rule = _RULES[rule.id].model_copy(update={"last_fired_at": now})
    _RULES[rule.id] = rule

    return AlertEvent(
        id=str(uuid.uuid4()),
        rule_id=rule.id,
        rule_name=rule.name,
        severity=rule.severity,
        trigger=rule.trigger,
        sku_id=sku_id,
        sku_name=sku_name,
        message=message,
        fired_at=now,
        channels_sent=channels_sent,
        delivered=delivered,
    )
