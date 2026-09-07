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
from app.schemas_v2 import BuyingCalendarEvent, BuyingCalendarLine, PurchaseOrderDraft, PurchaseOrderLine
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
    incoming_by_sku = _scheduled_inbound(saved_purchase_orders, today=today)

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
            incoming=incoming_by_sku.get(sku.sku_id, []),
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
        inbound_units: int = 0,
    ) -> None:
        self.vendor = vendor
        self.order_by_date = order_by_date
        self.expected_arrival_date = expected_arrival_date
        self.line = line
        self.inbound_units = inbound_units


def _build_recommended_line(
    sku: SkuDetail,
    history: list[int],
    *,
    lead_time_config: LeadTimeConfig,
    service_level: float,
    order_cost: float,
    today: date,
    horizon_days: int,
    incoming: list[tuple[date, int]] | None = None,
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

    order_by = today + timedelta(days=days_until_order)
    expected_arrival = order_by + timedelta(days=lead_time_days)
    inbound_units = _timely_inbound_units(incoming or [], on_hand=sku.inventory,
        mean_daily=mean_daily, today=today, arrival_horizon=expected_arrival)
    projected_inventory_at_order = max(0.0, sku.inventory - mean_daily * days_until_order)
    recommended_qty = int(math.ceil(max(order_up_to - projected_inventory_at_order - inbound_units, 0.0)))
    cost_source = getattr(sku, "cost_source", "recorded")
    cost_known = cost_source == "recorded"
    eoq = _economic_order_qty(mean_daily, sku.cost, order_cost) if cost_known else 0
    if eoq > 0 and recommended_qty > 0:
        # Already committed units participate in the existing order-size target;
        # an EOQ must not create another buy when the stock need is fully covered.
        recommended_qty = max(recommended_qty, eoq - inbound_units)
    if recommended_qty <= 0:
        return None

    return BuyingCalendarLineWithTiming(
        vendor=sku.vendor or "Unassigned",
        order_by_date=order_by,
        expected_arrival_date=expected_arrival,
        inbound_units=inbound_units,
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
            cost_source=cost_source,
            financial_values_known=cost_known,
            financial_values={"unit_cost": round(sku.cost, 2) if cost_known else None,
                              "extended_cost": round(recommended_qty * sku.cost, 2) if cost_known else None},
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
    estimated_cost = round(subtotal + (order_cost if any(item.line.qty > 0 for item in ordered_items) else 0.0), 2)
    days_until_order = (order_by - today).days
    lead_time_days = max((item.line.lead_time_days or 0) for item in ordered_items)
    inbound_units = sum(item.inbound_units for item in ordered_items)
    cost_known = all(getattr(item.line, "financial_values_known", True) for item in ordered_items)
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
        financial_values_known=cost_known,
        financial_values={"subtotal_cost": round(subtotal, 2) if cost_known else None,
                          "estimated_cost": estimated_cost if cost_known else None},
        urgency=_urgency_for_days(days_until_order),
        rationale=(
            f"Projected to cross reorder point during the week of {_display_date(order_by)}. "
            f"Plan one consolidated {vendor} buy before lead time consumes the buffer."
            + (f" Quantities already exclude {inbound_units} unreceived units on issued POs expected to arrive before stock runs out in this buying cycle." if inbound_units else "")
        ),
        lines=[item.line for item in ordered_items],
    )


def _saved_event(po: PurchaseOrderDraft, *, today: date) -> BuyingCalendarEvent:
    order_by = _date_from_datetime(po.sent_at or po.approved_at or po.created_at) or today
    expected_arrival = _parse_date(po.expected_arrival_date)
    lead_time_days = max((expected_arrival - order_by).days, 0) if expected_arrival else 0
    days_until_order = (order_by - today).days
    lines = [
        BuyingCalendarLine(
            sku_id=line.sku_id,
            name=line.name,
            qty=_outstanding_units(line),
            unit_cost=line.unit_cost,
            extended_cost=round(_outstanding_units(line) * line.unit_cost, 2),
            cost_source=line.cost_source,
            financial_values_known=line.financial_values_known,
        )
        for line in po.lines
    ]
    open_lines = [line for line in lines if line.qty > 0]
    cost_known = po.financial_values_known and all(line.financial_values_known for line in lines)
    return BuyingCalendarEvent(
        event_id=f"SAVED-{po.po_id}",
        vendor=po.vendor,
        source="saved",
        status=po.status,
        order_by_date=order_by.isoformat(),
        expected_arrival_date=expected_arrival.isoformat() if expected_arrival else "",
        days_until_order=days_until_order,
        lead_time_days=lead_time_days,
        line_count=len(open_lines),
        total_units=sum(line.qty for line in open_lines),
        estimated_cost=round(po.total_cost, 2),
        financial_values_known=cost_known,
        urgency="open",
        rationale=(po.rationale + " Existing PO, not an additional buy; units show the unreceived balance and cost shows the original PO total, not an unpaid balance."
                   + (" Arrival is undated or overdue; verify a new ETA before relying on it for replenishment." if not expected_arrival or expected_arrival < today else "")
                   + (" Not dispatched; it does not reduce new buying recommendations." if po.status not in {"sent", "partially_received"} else "")),
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
        _outstanding_units(line) > 0 for line in po.lines
    )


def _outstanding_units(line: PurchaseOrderLine) -> int:
    return max(line.qty - max(line.received_qty or 0, 0), 0)


def _scheduled_inbound(purchase_orders: list[PurchaseOrderDraft], *, today: date) -> dict[str, list[tuple[date, int]]]:
    """Only issued POs with a still-current dated arrival can offset planning.

    The schema records sent/receipt dates, not supplier acknowledgements. These
    remain ETA assumptions, never a guarantee. An overdue ETA needs revision.
    """
    result: dict[str, list[tuple[date, int]]] = {}
    for po in purchase_orders:
        if po.status not in {"sent", "partially_received"}:
            continue
        issued = _date_from_datetime(po.sent_at or po.received_at)
        arrival = _parse_date(po.expected_arrival_date)
        if issued is None or issued > today or arrival is None or arrival < today or arrival < issued:
            continue
        for line in po.lines:
            qty = _outstanding_units(line)
            if qty:
                result.setdefault(line.sku_id, []).append((arrival, qty))
    return result


def _timely_inbound_units(incoming: list[tuple[date, int]], *, on_hand: int, mean_daily: float,
                         today: date, arrival_horizon: date) -> int:
    """Offset the next buying cycle only, without hiding a gap before arrival.

    An earlier timely shipment can extend runway for a later one. Arrivals are
    treated as available at the start of their recorded calendar date.
    """
    units = 0
    for arrival, quantity in sorted(incoming):
        if arrival > arrival_horizon:
            continue
        balance_before_arrival = on_hand + units - mean_daily * (arrival - today).days
        if balance_before_arrival >= 0:
            units += quantity
    return units


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
