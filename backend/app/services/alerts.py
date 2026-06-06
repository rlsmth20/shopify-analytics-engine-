"""Alert rule engine.

The engine evaluates the current inventory state against a set of rules and
produces AlertEvent records. Each event can be delivered through one or more
notification channels via the notifications module.

Rules and channel configs are persisted to the database (v0.3). Events remain
in-memory since they are a short-lived activity log; a dedicated events table
is future work.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import select

from app.db.models import AlertRuleRecord, NotificationChannelRecord
from app.db.session import SessionLocal
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


# Events remain in-memory (log-style). Rules + channels are persisted.
_EVENTS: list[tuple[int, AlertEvent]] = []


def _record_to_rule(record: AlertRuleRecord) -> AlertRule:
    return AlertRule(
        id=record.id,
        name=record.name,
        trigger=cast(AlertTrigger, record.trigger),
        severity=cast(AlertSeverity, record.severity),
        channels=[cast(NotificationChannel, c) for c in (record.channels or [])],
        threshold=record.threshold,
        scope=cast(str, record.scope or "storewide"),
        match_mode=cast(str, record.match_mode or "all"),
        target_skus=list(record.target_skus or []),
        product_title_contains=record.product_title_contains or "",
        categories=list(record.categories or []),
        suppliers=list(record.suppliers or []),
        tags=list(record.tags or []),
        collections=list(record.collections or []),
        locations=list(record.locations or []),
        enabled=record.enabled,
        created_at=record.created_at,
        last_fired_at=record.last_fired_at,
    )


def _channel_storage_key(shop_id: int, channel: str) -> str:
    return f"{shop_id}:{channel}"


def _channel_from_storage_key(key: str) -> str:
    return key.split(":", 1)[1] if ":" in key else key


def _record_to_channel(record: NotificationChannelRecord) -> NotificationChannelConfig:
    return NotificationChannelConfig(
        channel=cast(NotificationChannel, _channel_from_storage_key(record.channel)),
        enabled=record.enabled,
        target=record.target,
        verified=record.verified,
    )


def seed_default_rules_and_channels(shop_id: int) -> None:
    """Idempotent seed scoped to one shop."""
    with SessionLocal() as session:
        existing = session.scalar(
            select(AlertRuleRecord).where(AlertRuleRecord.shop_id == shop_id).limit(1)
        )
        if existing is not None:
            _seed_missing_channels(session, shop_id)
            session.commit()
            return

        defaults = [
            dict(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                name="Critical stockout risk",
                trigger="stockout_risk",
                severity="critical",
                channels=["email", "slack"],
                threshold=3.0,
                enabled=True,
            ),
            dict(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                name="Dead stock capital review",
                trigger="dead_stock",
                severity="warning",
                channels=["email"],
                threshold=500.0,
                enabled=True,
            ),
            dict(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                name="Overstock excess cover review",
                trigger="overstock",
                severity="warning",
                channels=["email"],
                threshold=30.0,
                enabled=True,
            ),
            dict(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                name="Forecast miss > 20%",
                trigger="forecast_miss",
                severity="info",
                channels=["email"],
                threshold=20.0,
                enabled=True,
            ),
            dict(
                id=str(uuid.uuid4()),
                shop_id=shop_id,
                name="Supplier slipping on-time delivery",
                trigger="supplier_slip",
                severity="warning",
                channels=["email", "slack"],
                threshold=80.0,
                enabled=True,
            ),
        ]
        for row in defaults:
            session.add(AlertRuleRecord(**row))

        _seed_missing_channels(session, shop_id)
        session.commit()


def _seed_missing_channels(session, shop_id: int) -> None:
    existing_channels = {
        _channel_from_storage_key(c.channel)
        for c in session.scalars(
            select(NotificationChannelRecord).where(
                NotificationChannelRecord.channel.like(f"{shop_id}:%")
            )
        ).all()
    }
    for channel in ("email", "sms", "slack", "webhook"):
        if channel in existing_channels:
            continue
        session.add(
            NotificationChannelRecord(
                channel=_channel_storage_key(shop_id, channel),
                enabled=False,
                target="",
                verified=False,
            )
        )


def list_rules(shop_id: int) -> list[AlertRule]:
    with SessionLocal() as session:
        records = session.scalars(
            select(AlertRuleRecord)
            .where(AlertRuleRecord.shop_id == shop_id)
            .order_by(AlertRuleRecord.created_at)
        ).all()
        return [_record_to_rule(r) for r in records]


def create_rule(
    *,
    shop_id: int,
    name: str,
    trigger: AlertTrigger,
    severity: AlertSeverity,
    channels: list[NotificationChannel],
    threshold: float,
    scope: str = "storewide",
    match_mode: str = "all",
    target_skus: list[str] | None = None,
    product_title_contains: str = "",
    categories: list[str] | None = None,
    suppliers: list[str] | None = None,
    tags: list[str] | None = None,
    collections: list[str] | None = None,
    locations: list[str] | None = None,
    enabled: bool = True,
) -> AlertRule:
    with SessionLocal() as session:
        record = AlertRuleRecord(
            id=str(uuid.uuid4()),
            shop_id=shop_id,
            name=name,
            trigger=str(trigger),
            severity=str(severity),
            channels=list(channels),
            threshold=threshold,
            scope=scope,
            match_mode=match_mode,
            target_skus=_clean_list(target_skus),
            product_title_contains=(product_title_contains or "").strip(),
            categories=_clean_list(categories),
            suppliers=_clean_list(suppliers),
            tags=_clean_list(tags),
            collections=_clean_list(collections),
            locations=_clean_list(locations),
            enabled=enabled,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _record_to_rule(record)


def delete_rule(shop_id: int, rule_id: str) -> bool:
    with SessionLocal() as session:
        record = session.get(AlertRuleRecord, rule_id)
        if record is None or record.shop_id != shop_id:
            return False
        session.delete(record)
        session.commit()
        return True


def toggle_rule(shop_id: int, rule_id: str, enabled: bool) -> Optional[AlertRule]:
    with SessionLocal() as session:
        record = session.get(AlertRuleRecord, rule_id)
        if record is None or record.shop_id != shop_id:
            return None
        record.enabled = enabled
        session.commit()
        session.refresh(record)
        return _record_to_rule(record)


def list_channel_configs(shop_id: int) -> list[NotificationChannelConfig]:
    with SessionLocal() as session:
        records = session.scalars(
            select(NotificationChannelRecord).where(
                NotificationChannelRecord.channel.like(f"{shop_id}:%")
            )
        ).all()
        return [_record_to_channel(r) for r in records]


def update_channel_config(
    *,
    shop_id: int,
    channel: NotificationChannel,
    enabled: bool,
    target: str,
) -> NotificationChannelConfig:
    with SessionLocal() as session:
        key = _channel_storage_key(shop_id, channel)
        record = session.get(NotificationChannelRecord, key)
        if record is None:
            record = NotificationChannelRecord(
                channel=key,
                enabled=enabled,
                target=target,
                verified=False,
            )
            session.add(record)
        else:
            record.enabled = enabled
            record.target = target
        session.commit()
        session.refresh(record)
        return _record_to_channel(record)


def list_recent_events(shop_id: int, limit: int = 50) -> list[AlertEvent]:
    return [event for event_shop_id, event in _EVENTS if event_shop_id == shop_id][-limit:]


@dataclass(frozen=True)
class EvaluationContext:
    actions: list[InventoryAction]
    forecasts: list[ForecastResult]
    supplier_scores: list[SupplierScorecard]


def evaluate(
    shop_id: int,
    context: EvaluationContext,
    deliver_channels: bool = False,
    allowed_channels: set[NotificationChannel] | None = None,
    cooldown_seconds: int = 0,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    now = datetime.now(timezone.utc)

    rules = list_rules(shop_id)
    channels_by_key = {c.channel: c for c in list_channel_configs(shop_id)}

    for rule in rules:
        if not rule.enabled:
            continue
        if deliver_channels and cooldown_seconds > 0 and rule.last_fired_at is not None:
            last_fired_at = rule.last_fired_at
            if last_fired_at.tzinfo is None:
                last_fired_at = last_fired_at.replace(tzinfo=timezone.utc)
            if (now - last_fired_at).total_seconds() < cooldown_seconds:
                continue
        events.extend(
            _evaluate_rule(
                rule,
                context,
                now,
                deliver_channels,
                channels_by_key,
                allowed_channels,
            )
        )

    _EVENTS.extend((shop_id, event) for event in events)
    return events


def _evaluate_rule(
    rule: AlertRule,
    context: EvaluationContext,
    now: datetime,
    deliver_channels: bool,
    channels_by_key: dict[NotificationChannel, NotificationChannelConfig],
    allowed_channels: set[NotificationChannel] | None,
) -> list[AlertEvent]:
    if rule.trigger == "stockout_risk":
        return _stockout_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels)
    if rule.trigger == "dead_stock":
        return _dead_stock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels)
    if rule.trigger == "overstock":
        return _overstock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels)
    if rule.trigger == "supplier_slip":
        return _supplier_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels)
    if rule.trigger == "forecast_miss":
        return _forecast_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels)
    return []


def _stockout_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for action in context.actions:
        if action.status != "urgent":
            continue
        if not _rule_matches(rule, sku_id=action.sku_id, product_name=action.name):
            continue
        days = getattr(action, "days_until_stockout", action.days_of_inventory)
        lead_time_days = getattr(action, "lead_time_days_used", 0)
        reorder_buffer_days = days - lead_time_days
        if reorder_buffer_days > rule.threshold:
            continue
        msg = (
            f"{action.name} has {days:.1f} days left and a {lead_time_days:.0f}-day lead time. "
            f"That leaves {reorder_buffer_days:.1f} days before a reorder may arrive too late. "
            f"Recommended: {action.recommended_action}"
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels))
    return events


def _dead_stock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for action in context.actions:
        if action.status != "dead":
            continue
        if not _rule_matches(rule, sku_id=action.sku_id, product_name=action.name):
            continue
        cash = getattr(action, "cash_tied_up", 0)
        if cash < rule.threshold:
            continue
        msg = (
            f"{action.name}: ${cash:,.0f} tied up in stale inventory. "
            f"Recommended: {action.recommended_action}"
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels))
    return events


def _overstock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for action in context.actions:
        if action.status != "optimize":
            continue
        if not _rule_matches(rule, sku_id=action.sku_id, product_name=action.name):
            continue
        lead_time_days = getattr(action, "lead_time_days_used", 0) or 0
        target_coverage_days = getattr(action, "target_coverage_days", 0) or 0
        extra_cover_days = action.days_of_inventory - lead_time_days - target_coverage_days
        if extra_cover_days < rule.threshold:
            continue
        msg = (
            f"{action.name} has {action.days_of_inventory:.0f} days of cover, "
            f"a {lead_time_days:.0f}-day lead time, and a {target_coverage_days:.0f}-day target. "
            f"That leaves {extra_cover_days:.0f} extra days of cover and "
            f"${getattr(action, 'cash_tied_up', 0):,.0f} tied up in excess inventory."
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels))
    return events


def _supplier_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for vendor in context.supplier_scores:
        if not _rule_matches(rule, supplier=vendor.vendor, product_name=vendor.vendor):
            continue
        if vendor.on_time_pct >= rule.threshold:
            continue
        msg = (
            f"Vendor {vendor.vendor} on-time rate dropped to {vendor.on_time_pct:.0f}%. "
            "Consider extending safety stock for this vendor's SKUs."
        )
        events.append(_fire(rule, None, vendor.vendor, msg, now, deliver_channels, channels_by_key, allowed_channels))
    return events


def _forecast_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for forecast in context.forecasts:
        if not _rule_matches(rule, sku_id=forecast.sku_id, product_name=forecast.sku_id):
            continue
        if forecast.stockout_probability_30d * 100 < rule.threshold:
            continue
        msg = (
            f"Forecast flags {forecast.sku_id} with {forecast.stockout_probability_30d*100:.0f}% "
            "stockout probability in the next 30 days."
        )
        events.append(_fire(rule, forecast.sku_id, forecast.sku_id, msg, now, deliver_channels, channels_by_key, allowed_channels))
    return events


def _fire(rule, sku_id, sku_name, message, now, deliver_channels, channels_by_key, allowed_channels):
    channels_sent = []
    delivered = not deliver_channels

    if deliver_channels:
        for channel in rule.channels:
            if allowed_channels is not None and channel not in allowed_channels:
                continue
            config = channels_by_key.get(channel)
            if not config or not config.enabled or not config.target:
                continue
            if _is_placeholder_target(config.target):
                continue
            record = deliver(
                channel=channel,
                target=config.target,
                subject=f"[{rule.severity.upper()}] {rule.name}",
                body=message,
            )
            if record.delivered:
                channels_sent.append(channel)
                delivered = True

    if deliver_channels:
        with SessionLocal() as session:
            rule_record = session.get(AlertRuleRecord, rule.id)
            if rule_record is not None:
                rule_record.last_fired_at = now
                session.commit()

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


def _is_placeholder_target(target: str) -> bool:
    return target.strip().lower() in {"alerts@example.com", "example@example.com"}


def _clean_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned = []
    seen = set()
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def _matches_any_text(value: str | None, filters: list[str]) -> bool:
    if not filters:
        return True
    if not value:
        return False
    normalized = value.strip().lower()
    return any(normalized == item.strip().lower() for item in filters if item.strip())


def _contains_text(value: str | None, needle: str) -> bool:
    needle = needle.strip().lower()
    if not needle:
        return True
    return needle in (value or "").strip().lower()


def _rule_matches(
    rule: AlertRule,
    *,
    sku_id: str | None = None,
    product_name: str | None = None,
    category: str | None = None,
    supplier: str | None = None,
    tags: list[str] | None = None,
    collections: list[str] | None = None,
    location: str | None = None,
) -> bool:
    """Apply saved alert targeting against the fields available for this event.

    Missing source fields fail only their corresponding condition. This keeps
    location/tag/collection rules honest until Shopify sync provides those
    attributes to alert evaluation.
    """
    if rule.scope != "custom":
        return True

    checks: list[bool] = []
    if rule.target_skus:
        checks.append(_matches_any_text(sku_id, rule.target_skus))
    if rule.product_title_contains:
        checks.append(_contains_text(product_name, rule.product_title_contains))
    if rule.categories:
        checks.append(_matches_any_text(category, rule.categories))
    if rule.suppliers:
        checks.append(_matches_any_text(supplier, rule.suppliers))
    if rule.locations:
        checks.append(_matches_any_text(location, rule.locations))
    if rule.tags:
        source_tags = {tag.strip().lower() for tag in (tags or [])}
        checks.append(any(tag.strip().lower() in source_tags for tag in rule.tags))
    if rule.collections:
        source_collections = {item.strip().lower() for item in (collections or [])}
        checks.append(any(item.strip().lower() in source_collections for item in rule.collections))

    if not checks:
        return True
    if rule.match_mode == "any":
        return any(checks)
    return all(checks)
