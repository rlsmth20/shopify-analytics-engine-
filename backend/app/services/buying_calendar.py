"""Buying calendar for future reorder timing.

The existing PO draft endpoint focuses on the buys that are already inside the
reorder window. This service keeps that workflow intact and adds a forward view:
when each SKU is projected to cross its reorder point, grouped into supplier-week
buying events.
"""
from __future__ import annotations

import math
import re
import statistics
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from app.config.lead_time import LeadTimeConfig
from app.schemas import SkuDetail
from app.schemas_v2 import BuyingCalendarEvent, BuyingCalendarLine, PurchaseOrderDraft
from app.services.reorder_optimizer import (
    DEFAULT_HOLDING_RATE,
    DEFAULT_ORDER_COST,
    DEFAULT_REVIEW_PERIOD_DAYS,
    _resolve_lead_time,
    _z_for_service_level,
)


def build_buying_calendar_events(
    skus: list[SkuDetail],
    history_for_sku: Callable[[str], list[int]],
    *,
    lead_time_config: LeadTimeConfig,
    saved_purchase_orders: list[PurchaseOrderDraft] | None = None,
    service_level: float = 0.95,
    order_cost: float = DEFAULT_ORDER_COST,
    horizon_days: int = 180,
    today: date | None = None,
) -> list[BuyingCalendarEvent]:
    today = today or date.today()
    horizon_days = max(horizon_days, 0)
    order_cost = max(order_cost, 0.0)
    saved_purchase_orders = saved_purchase_orders or []

    grouped: dict[tuple[str, str], list[BuyingCalendarLineWithTiming]] = {}
    for sku in skus:
        item = _build_recommended_line(
            sku,
            history_for_sku(sku.sku_id) or [],
            lead_time_config=lead_time_config,
            service_level=service_level,
            order_cost=order_cost,
            today=today,
            horizon_days=horizon_days,
        )
        if item is None:
            continue
        key = (item.vendor, _week_start(item.order_by_date).isoformat())
        grouped.setdefault(key, []).append(item)

    events = [
        _recommended_event(vendor, items, today=today, order_cost=order_cost)
        for (vendor, _week), items in grouped.items()
    ]
    events.extend(_saved_event(po, today=today) for po in saved_purchase_orders if _is_open_po(po))
    events.sort(key=lambda event: (event.order_by_date, event.vendor, event.source))
    return events


class BuyingCalendarLineWithTiming:
    def __init__(
        self,
        *,
        vendor: str,
        order_by_date: date,
        expected_arrival_date: date,
        line: BuyingCalendarLine,
    ) -> None:
        self.vendor = vendor
        self.order_by_date = order_by_date
        self.expected_arrival_date = expected_arrival_date
        self.line = line


def _build_recommended_line(
    sku: SkuDetail,
    history: list[int],
    *,
    lead_time_config: LeadTimeConfig,
    service_level: float,
    order_cost: float,
    today: date,
    horizon_days: int,
) -> BuyingCalendarLineWithTiming | None:
    mean_daily = _mean_daily_demand(sku, history)
    if mean_daily <= 0:
        return None

    lead_time_days = _resolve_lead_time(sku, lead_time_config)
    sigma_daily = statistics.pstdev(history) if len(history) > 1 else max(mean_daily * 0.3, 0.5)
    safety_stock = _z_for_service_level(service_level) * sigma_daily * math.sqrt(max(lead_time_days, 1))
    reorder_point = mean_daily * lead_time_days + safety_stock
    order_up_to = reorder_point + DEFAULT_REVIEW_PERIOD_DAYS * mean_daily
    days_until_order = 0
    if sku.inventory > reorder_point:
        days_until_order = int(math.ceil((sku.inventory - reorder_point) / mean_daily))
    if days_until_order > horizon_days:
        return None

    projected_inventory_at_order = max(0.0, sku.inventory - mean_daily * days_until_order)
    recommended_qty = int(math.ceil(max(order_up_to - projected_inventory_at_order, 0.0)))
    eoq = _economic_order_qty(mean_daily, sku.cost, order_cost)
    if eoq > 0 and recommended_qty > 0:
        recommended_qty = max(recommended_qty, eoq)
    if recommended_qty <= 0:
        return None

    order_by = today + timedelta(days=days_until_order)
    expected_arrival = order_by + timedelta(days=lead_time_days)
    return BuyingCalendarLineWithTiming(
        vendor=sku.vendor or "Unassigned",
        order_by_date=order_by,
        expected_arrival_date=expected_arrival,
        line=BuyingCalendarLine(
            sku_id=sku.sku_id,
            name=sku.name,
            qty=recommended_qty,
            unit_cost=round(sku.cost, 2),
            extended_cost=round(recommended_qty * sku.cost, 2),
            current_on_hand=sku.inventory,
            reorder_point=round(reorder_point, 1),
            daily_velocity=round(mean_daily, 2),
            lead_time_days=lead_time_days,
        ),
    )


def _recommended_event(
    vendor: str,
    items: list[BuyingCalendarLineWithTiming],
    *,
    today: date,
    order_cost: float,
) -> BuyingCalendarEvent:
    ordered_items = sorted(items, key=lambda item: (item.order_by_date, item.line.name))
    order_by = min(item.order_by_date for item in ordered_items)
    expected_arrival = max(item.expected_arrival_date for item in ordered_items)
    subtotal = sum(item.line.extended_cost for item in ordered_items)
    estimated_cost = round(subtotal + (order_cost if subtotal > 0 else 0.0), 2)
    days_until_order = (order_by - today).days
    lead_time_days = max((item.line.lead_time_days or 0) for item in ordered_items)
    return BuyingCalendarEvent(
        event_id=f"CAL-{order_by.strftime('%Y%m%d')}-{_slug(vendor)}",
        vendor=vendor,
        source="recommended",
        status="planned",
        order_by_date=order_by.isoformat(),
        expected_arrival_date=expected_arrival.isoformat(),
        days_until_order=days_until_order,
        lead_time_days=lead_time_days,
        line_count=len(ordered_items),
        total_units=sum(item.line.qty for item in ordered_items),
        estimated_cost=estimated_cost,
        urgency=_urgency_for_days(days_until_order),
        rationale=(
            f"Projected to cross reorder point during the week of {_display_date(order_by)}. "
            f"Plan one consolidated {vendor} buy before lead time consumes the buffer."
        ),
        lines=[item.line for item in ordered_items],
    )


def _saved_event(po: PurchaseOrderDraft, *, today: date) -> BuyingCalendarEvent:
    order_by = _date_from_datetime(po.sent_at or po.approved_at or po.created_at) or today
    expected_arrival = _parse_date(po.expected_arrival_date) or order_by
    lead_time_days = max((expected_arrival - order_by).days, 0)
    days_until_order = (order_by - today).days
    lines = [
        BuyingCalendarLine(
            sku_id=line.sku_id,
            name=line.name,
            qty=max(line.qty - (line.received_qty or 0), 0),
            unit_cost=line.unit_cost,
            extended_cost=round(max(line.qty - (line.received_qty or 0), 0) * line.unit_cost, 2),
        )
        for line in po.lines
    ]
    open_lines = [line for line in lines if line.qty > 0]
    return BuyingCalendarEvent(
        event_id=f"SAVED-{po.po_id}",
        vendor=po.vendor,
        source="saved",
        status=po.status,
        order_by_date=order_by.isoformat(),
        expected_arrival_date=expected_arrival.isoformat(),
        days_until_order=days_until_order,
        lead_time_days=lead_time_days,
        line_count=len(open_lines),
        total_units=sum(line.qty for line in open_lines),
        estimated_cost=round(po.total_cost, 2),
        urgency="open",
        rationale=po.rationale,
        lines=open_lines,
    )


def _mean_daily_demand(sku: SkuDetail, history: list[int]) -> float:
    if history:
        return max(float(statistics.mean(history)), 0.0)
    return max(float(sku.last_30_day_sales) / 30, 0.0)


def _economic_order_qty(mean_daily: float, unit_cost: float, order_cost: float) -> int:
    annual_demand = mean_daily * 365
    holding_cost = max(unit_cost, 0.0) * DEFAULT_HOLDING_RATE
    if unit_cost <= 0 or holding_cost <= 0 or annual_demand <= 0:
        return 0
    return int(math.ceil(math.sqrt((2 * annual_demand * max(order_cost, 0.0)) / holding_cost)))


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _urgency_for_days(days_until_order: int) -> str:
    if days_until_order <= 0:
        return "due_now"
    if days_until_order <= 7:
        return "this_week"
    return "future"


def _is_open_po(po: PurchaseOrderDraft) -> bool:
    return po.status not in {"received", "cancelled"} and any(
        line.qty > (line.received_qty or 0) for line in po.lines
    )


def _date_from_datetime(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.date()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _display_date(value: date) -> str:
    return value.strftime("%b %d").replace(" 0", " ")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug or "unassigned")[:28]
