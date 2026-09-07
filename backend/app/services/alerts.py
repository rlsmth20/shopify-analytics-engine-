"""Alert rule engine.

The engine evaluates the current inventory state against a set of rules and
produces AlertEvent records. Each event can be delivered through one or more
notification channels via the notifications module.

Rules, destinations, matched incidents and channel acceptance records persist
across restarts. Preview evaluates without queuing or recording a send.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy import select, update, text, func

from app.db.models import AlertRuleRecord, NotificationChannelRecord, Shop
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
from app.services.notifications import channel_availability
from app.services.notification_targets import validate_target
from app.services.alert_delivery import dispatch_alert, list_persisted_events, target_fingerprint, resolve_absent_incidents
from app.services.audit_log import record_audit_event


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
    channel = _channel_from_storage_key(record.channel)
    available, reason = channel_availability(channel)
    try:
        validate_target(channel, record.target)
        configured = True
    except ValueError:
        configured = False
    return NotificationChannelConfig(
        channel=cast(NotificationChannel, channel),
        enabled=record.enabled,
        target=record.target,
        verified=record.verified,
        available=available,
        availability_reason=reason,
        configured=configured,
        verification_label="Provider accepted the last saved-destination test" if record.verified else "Not tested",
    )


def seed_default_rules_and_channels(shop_id: int) -> None:
    """Idempotent seed scoped to one shop."""
    with SessionLocal() as session:
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        shop = session.scalar(select(Shop).where(Shop.id == shop_id).with_for_update())
        if shop is None:
            return
        existing = session.scalar(
            select(AlertRuleRecord).where(AlertRuleRecord.shop_id == shop_id).limit(1)
        )
        has_channels = session.scalar(select(NotificationChannelRecord.channel)
                                      .where(NotificationChannelRecord.channel.like(f"{shop_id}:%")).limit(1)) is not None
        if existing is not None or has_channels:
            for legacy in session.scalars(select(AlertRuleRecord).where(AlertRuleRecord.shop_id == shop_id,
                          AlertRuleRecord.name == "Forecast miss > 20%", AlertRuleRecord.trigger == "forecast_miss")).all():
                legacy.name = "High stockout probability"
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
                name="High stockout probability",
                trigger="forecast_miss",
                severity="info",
                channels=["email"],
                threshold=70.0,
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
    validate_rule_configuration(trigger=trigger, tags=tags, collections=collections, locations=locations)
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
    target = target.strip()
    if enabled:
        target = validate_target(channel, target)
    with SessionLocal() as session:
        # Serialize initial configuration with seeding, and destination edits
        # with each other. NO KEY UPDATE also allows the test audit's foreign-key
        # check while it holds the channel row. SQLite uses a write transaction.
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        shop = session.scalar(select(Shop).where(Shop.id == shop_id).with_for_update(key_share=True))
        if shop is None:
            raise ValueError("This workspace is no longer available.")
        key = _channel_storage_key(shop_id, channel)
        record = session.scalar(select(NotificationChannelRecord)
                                .where(NotificationChannelRecord.channel == key).with_for_update())
        same_target = record is not None and record.target == target
        # Preserve unchanged destinations that were already live before saved
        # tests existed. A replacement, new destination or paused untested
        # destination must not inherit that legacy permission. Reject rather
        # than silently accepting a stale UI save that claims it enabled alerts.
        if enabled and not (same_target and (record.verified or record.enabled)):
            raise ValueError(
                "Save the destination paused and send a successful test before enabling automatic alerts. "
                "Refresh settings if the destination changed in another tab."
            )
        if record is None:
            record = NotificationChannelRecord(
                channel=key,
                enabled=enabled,
                target=target,
                verified=False,
            )
            session.add(record)
        else:
            if record.target != target:
                record.verified = False
            record.enabled = enabled
            record.target = target
        session.commit()
        session.refresh(record)
        return _record_to_channel(record)


def list_recent_events(shop_id: int, limit: int = 50) -> list[AlertEvent]:
    return list_persisted_events(shop_id, limit)


def record_channel_test(*, shop_id: int, channel: str, target: str, delivery, user_id: int | None = None) -> bool:
    with SessionLocal() as session:
        changed = session.execute(update(NotificationChannelRecord)
            .where(NotificationChannelRecord.channel == _channel_storage_key(shop_id, channel),
                   func.trim(NotificationChannelRecord.target) == target.strip())
            .values(verified=delivery.status == "accepted"))
        saved_target = changed.rowcount == 1
        record_audit_event(session, shop_id=shop_id, user_id=user_id, event_type="alert_channel_test",
                           entity_type="notification_channel", entity_id=channel,
                           summary=f"{channel.title()} test: {delivery.status}.",
                           metadata={"status": delivery.status, "target_fingerprint": target_fingerprint(target),
                                     "provider_receipt": delivery.provider_receipt, "saved_target": saved_target,
                                     "error": delivery.error}, commit=False)
        session.commit()
        return bool(saved_target and delivery.status == "accepted")


@dataclass(frozen=True)
class EvaluationContext:
    actions: list[InventoryAction]
    forecasts: list[ForecastResult]
    supplier_scores: list[SupplierScorecard]
    sku_metadata: dict[str, dict[str, str]] = field(default_factory=dict)
    delivery_cooldown_seconds: int = 21600


def evaluate(
    shop_id: int,
    context: EvaluationContext,
    deliver_channels: bool = False,
    allowed_channels: set[NotificationChannel] | None = None,
    cooldown_seconds: int = 0,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    now = datetime.now(timezone.utc)
    context = replace(context, delivery_cooldown_seconds=cooldown_seconds)

    rules = list_rules(shop_id)
    channels_by_key = {c.channel: c for c in list_channel_configs(shop_id)}

    for rule in rules:
        if not rule.enabled:
            continue
        matches = _evaluate_rule(rule, context, now, False, channels_by_key, allowed_channels)
        if not deliver_channels:
            events.extend(matches)
            continue
        resolve_absent_incidents(shop_id, rule.id,
            {target_fingerprint(match.sku_id or match.sku_name or "storewide") for match in matches}, now)
        for match in matches:
            events.append(dispatch_alert(rule=rule, sku_id=match.sku_id, sku_name=match.sku_name,
                message=match.message, now=now, allowed_channels=allowed_channels, cooldown_seconds=cooldown_seconds))

    return [event for event in events if event is not None]


def validate_rule_configuration(*, trigger, tags=None, collections=None, locations=None):
    if trigger not in {"stockout_risk", "dead_stock", "overstock", "supplier_slip", "forecast_miss"}:
        raise ValueError("This alert trigger is not available yet.")
    if tags or collections or locations:
        raise ValueError("Tag, collection and location targeting are not available for automatic alerts yet. Use SKU, product, supplier or category targeting.")


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
        if not _sku_matches(rule, context, action.sku_id, action.name):
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
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels, context.delivery_cooldown_seconds))
    return events


def _dead_stock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for action in context.actions:
        if action.status != "dead" or not action.financial_values_known:
            continue
        if not _sku_matches(rule, context, action.sku_id, action.name):
            continue
        cash = getattr(action, "cash_tied_up", 0)
        if cash < rule.threshold:
            continue
        msg = (
            f"{action.name}: ${cash:,.0f} tied up in stale inventory. "
            f"Recommended: {action.recommended_action}"
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels, context.delivery_cooldown_seconds))
    return events


def _overstock_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for action in context.actions:
        if action.status != "optimize" or not action.sales_history_complete:
            continue
        if not _sku_matches(rule, context, action.sku_id, action.name):
            continue
        lead_time_days = getattr(action, "lead_time_days_used", 0) or 0
        target_coverage_days = getattr(action, "target_coverage_days", 0) or 0
        extra_cover_days = action.days_of_inventory - lead_time_days - target_coverage_days
        if extra_cover_days < rule.threshold:
            continue
        msg = (
            f"{action.name} has {action.days_of_inventory:.0f} days of cover, "
            f"a {lead_time_days:.0f}-day lead time, and a {target_coverage_days:.0f}-day target. "
            f"That leaves {extra_cover_days:.0f} extra days of cover. "
            + (f"${getattr(action, 'cash_tied_up', 0):,.0f} tied up in excess inventory."
               if action.financial_values_known else "Add unit costs to measure excess-inventory capital.")
        )
        events.append(_fire(rule, action.sku_id, action.name, msg, now, deliver_channels, channels_by_key, allowed_channels, context.delivery_cooldown_seconds))
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
        events.append(_fire(rule, None, vendor.vendor, msg, now, deliver_channels, channels_by_key, allowed_channels, context.delivery_cooldown_seconds))
    return events


def _forecast_events(rule, context, now, deliver_channels, channels_by_key, allowed_channels):
    events = []
    for forecast in context.forecasts:
        if not forecast.forecast_available:
            continue
        if not _sku_matches(rule, context, forecast.sku_id, forecast.sku_id):
            continue
        if forecast.stockout_probability_30d * 100 < rule.threshold:
            continue
        name = context.sku_metadata.get(forecast.sku_id, {}).get("name") or forecast.sku_id
        limited_history = forecast.history_days < 30
        if limited_history or forecast.confidence == "low":
            limitation = (
                f"Only {forecast.history_days} day{'s' if forecast.history_days != 1 else ''} of usable sales history; "
                f"forecast confidence is {forecast.confidence}."
                if limited_history else "Forecast confidence is low, so the likelihood is uncertain."
            )
            msg = (
                f"Stockout estimate: {name} may run out of current on-hand stock in the next 30 days. "
                f"{limitation} Verify recent sales, available stock and incoming orders before ordering."
            )
        else:
            probability_pct = forecast.stockout_probability_30d * 100
            probability_label = ("over 99%" if probability_pct > 99 else
                                 "under 1%" if 0 < probability_pct < 1 else f"{probability_pct:.0f}%")
            msg = (
                f"Forecast estimates a {probability_label} chance that 30-day demand for {name} "
                f"will exceed current on-hand stock ({forecast.confidence} confidence). "
                "Check available stock and incoming orders before ordering."
            )
        events.append(_fire(rule, forecast.sku_id, name, msg, now, deliver_channels, channels_by_key, allowed_channels, context.delivery_cooldown_seconds))
    return events


def _fire(rule, sku_id, sku_name, message, now, deliver_channels, channels_by_key, allowed_channels,
          cooldown_seconds=21600):
    if deliver_channels:
        return dispatch_alert(rule=rule, sku_id=sku_id, sku_name=sku_name, message=message, now=now,
                              allowed_channels=allowed_channels, cooldown_seconds=cooldown_seconds)
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
        channels_sent=[],
        delivered=False,
        preview=True,
        delivery_status="preview",
    )


def _sku_matches(rule, context, sku_id, name):
    metadata = context.sku_metadata.get(sku_id, {})
    return _rule_matches(rule, sku_id=sku_id, product_name=metadata.get("name", name),
                         category=metadata.get("category"), supplier=metadata.get("vendor"))


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
