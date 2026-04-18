import math
from dataclasses import dataclass

from app.config.lead_time import LeadTimeConfig, MOCK_LEAD_TIME_CONFIG
from app.schemas import (
    Classification,
    DeadInventoryAction,
    InventoryAction,
    LeadTimeSource,
    OptimizeInventoryAction,
    SkuDetail,
    UrgencyLevel,
    UrgentInventoryAction,
)


OPTIMIZE_DAYS_THRESHOLD = 75
MAX_DAYS_OF_INVENTORY = 999.0


@dataclass(frozen=True)
class InventoryMetrics:
    sku: SkuDetail
    daily_velocity: float
    days_of_inventory: float
    reorder_point: float
    stockout_risk: bool
    overstock_risk: bool
    dead_stock: bool
    profit_per_unit: float
    lead_time_days_used: int
    safety_buffer_days: int
    lead_time_source: LeadTimeSource
    target_coverage_days: int


def build_inventory_actions(
    skus: list[SkuDetail],
    lead_time_config: LeadTimeConfig = MOCK_LEAD_TIME_CONFIG,
) -> list[InventoryAction]:
    actions = []
    for sku in skus:
        action = _build_action(_calculate_metrics(sku, lead_time_config))
        if action is not None:
            actions.append(action)

    return sorted(actions, key=lambda action: action.priority_score, reverse=True)


def _calculate_metrics(
    sku: SkuDetail, lead_time_config: LeadTimeConfig
) -> InventoryMetrics:
    daily_velocity = sku.last_30_day_sales / 30
    lead_time_days_used, lead_time_source = _resolve_lead_time(sku, lead_time_config)
    safety_buffer_days = lead_time_config.global_safety_buffer_days
    target_coverage_days = lead_time_days_used + safety_buffer_days

    # Days of cover uses on-hand inventory divided by trailing 30-day daily velocity.
    if daily_velocity > 0:
        days_of_inventory = sku.inventory / daily_velocity
    else:
        days_of_inventory = MAX_DAYS_OF_INVENTORY

    reorder_point = daily_velocity * lead_time_days_used
    stockout_risk = daily_velocity > 0 and days_of_inventory < target_coverage_days
    overstock_risk = days_of_inventory > 75
    dead_stock = sku.days_since_last_sale > 45
    profit_per_unit = sku.price - sku.cost

    return InventoryMetrics(
        sku=sku,
        daily_velocity=daily_velocity,
        days_of_inventory=days_of_inventory,
        reorder_point=reorder_point,
        stockout_risk=stockout_risk,
        overstock_risk=overstock_risk,
        dead_stock=dead_stock,
        profit_per_unit=profit_per_unit,
        lead_time_days_used=lead_time_days_used,
        safety_buffer_days=safety_buffer_days,
        lead_time_source=lead_time_source,
        target_coverage_days=target_coverage_days,
    )


def _resolve_lead_time(
    sku: SkuDetail, lead_time_config: LeadTimeConfig
) -> tuple[int, LeadTimeSource]:
    # Lead time priority: SKU override -> vendor -> category -> global default.
    if sku.sku_lead_time_days is not None:
        return sku.sku_lead_time_days, "sku_override"

    vendor_lead_time = lead_time_config.vendor_lead_times.get(sku.vendor)
    if vendor_lead_time is not None:
        return vendor_lead_time, "vendor"

    category_lead_time = lead_time_config.category_lead_times.get(sku.category)
    if category_lead_time is not None:
        return category_lead_time, "category"

    return lead_time_config.global_default_lead_time_days, "global_default"


def _build_action(metrics: InventoryMetrics) -> InventoryAction | None:
    status = _determine_status(metrics)
    if status == "healthy":
        return None

    base_payload = {
        "sku_id": metrics.sku.sku_id,
        "name": metrics.sku.name,
        "status": status,
        "recommended_action": _build_recommended_action(metrics, status),
        "days_of_inventory": round(metrics.days_of_inventory, 1),
        "lead_time_days_used": metrics.lead_time_days_used,
        "safety_buffer_days": metrics.safety_buffer_days,
        "lead_time_source": metrics.lead_time_source,
        "target_coverage_days": metrics.target_coverage_days,
        "priority_score": _calculate_priority_score(metrics, status),
    }

    if status == "urgent":
        days_until_stockout = round(metrics.days_of_inventory, 1)
        return UrgentInventoryAction(
            **base_payload,
            urgency_level=_determine_urgency_level(metrics.days_of_inventory),
            days_until_stockout=days_until_stockout,
            estimated_profit_impact=_estimate_profit_impact(metrics),
        )

    excess_units = _calculate_excess_units(metrics, status)
    cash_tied_up = _calculate_cash_tied_up(metrics, status)

    if status == "optimize":
        return OptimizeInventoryAction(
            **base_payload,
            excess_units=excess_units,
            cash_tied_up=cash_tied_up,
        )

    return DeadInventoryAction(
        **base_payload,
        excess_units=excess_units,
        cash_tied_up=cash_tied_up,
    )


def _determine_status(metrics: InventoryMetrics) -> Classification:
    if metrics.dead_stock:
        return "dead"
    if metrics.stockout_risk:
        return "urgent"
    if metrics.overstock_risk:
        return "optimize"
    return "healthy"


def _build_recommended_action(
    metrics: InventoryMetrics, status: Classification
) -> str:
    if status == "urgent":
        target_units = math.ceil(metrics.daily_velocity * metrics.target_coverage_days)
        reorder_quantity = max(target_units - metrics.sku.inventory, 0)
        post_reorder_units = metrics.sku.inventory + reorder_quantity
        post_reorder_coverage = _calculate_coverage_days(
            post_reorder_units, metrics.daily_velocity
        )
        reorder_window_days = _calculate_reorder_window_days(metrics.days_of_inventory)
        return (
            f"Reorder {reorder_quantity} units -> restores inventory to "
            f"~{post_reorder_coverage:.0f} days (target ~{metrics.target_coverage_days:.0f} days). "
            f"Reorder within {reorder_window_days} day"
            f"{'' if reorder_window_days == 1 else 's'}."
        )

    if status == "optimize":
        excess_units = _calculate_excess_units(metrics, status)
        return (
            f"Slow purchasing and work down roughly {excess_units} excess units "
            "before placing the next replenishment order."
        )

    if status == "dead":
        excess_units = _calculate_excess_units(metrics, status)
        return (
            f"Pause reorders and clear {excess_units} stale units with a markdown, "
            "bundle, or liquidation plan."
        )

    return "No immediate action. Inventory cover is within the target operating range."


def _estimate_profit_impact(metrics: InventoryMetrics) -> float:
    uncovered_days = max(
        metrics.target_coverage_days - metrics.days_of_inventory,
        1.0,
    )
    units_at_risk = max(metrics.daily_velocity * uncovered_days, metrics.daily_velocity)
    return round(units_at_risk * metrics.profit_per_unit, 2)


def _determine_urgency_level(days_until_stockout: float) -> UrgencyLevel:
    if days_until_stockout <= 3:
        return "critical"
    if days_until_stockout <= 7:
        return "high"
    return "medium"


def _calculate_reorder_window_days(days_until_stockout: float) -> int:
    return max(1, math.ceil((days_until_stockout - 1) / 2))


def _calculate_coverage_days(units: int, daily_velocity: float) -> float:
    if daily_velocity <= 0:
        return 0.0

    return units / daily_velocity


def _calculate_excess_units(metrics: InventoryMetrics, status: Classification) -> int:
    if status == "dead":
        return metrics.sku.inventory

    target_inventory = math.ceil(metrics.daily_velocity * OPTIMIZE_DAYS_THRESHOLD)
    return max(metrics.sku.inventory - target_inventory, 0)


def _calculate_cash_tied_up(metrics: InventoryMetrics, status: Classification) -> float:
    excess_units = _calculate_excess_units(metrics, status)
    return round(excess_units * metrics.sku.cost, 2)


def _calculate_inventory_severity(
    days_of_inventory: float, base_weight: float, extreme_weight: float
) -> float:
    severity_days = max(days_of_inventory - OPTIMIZE_DAYS_THRESHOLD, 0.0)
    extreme_days = max(days_of_inventory - 300.0, 0.0)
    return (severity_days * base_weight) + (extreme_days * extreme_weight)


def _calculate_priority_score(
    metrics: InventoryMetrics, status: Classification
) -> float:
    # Days until stockout drives urgent ranking, then profit and velocity refine it.
    if status == "urgent":
        days_until_stockout = max(metrics.days_of_inventory, 0.1)
        urgency_level = _determine_urgency_level(days_until_stockout)
        timing_factor = 700.0 / days_until_stockout
        urgency_bonus = {
            "critical": 110.0,
            "high": 35.0,
            "medium": 0.0,
        }[urgency_level]
        profit_factor = metrics.profit_per_unit * 3.0
        velocity_factor = metrics.daily_velocity * 24.0
        return round(
            900.0 + timing_factor + urgency_bonus + profit_factor + velocity_factor,
            2,
        )

    cash_tied_up = _calculate_cash_tied_up(metrics, status)
    excess_units = _calculate_excess_units(metrics, status)

    # Days of cover above 300 get extra weight so extreme overstock separates clearly.
    if status == "optimize":
        severity_factor = _calculate_inventory_severity(
            metrics.days_of_inventory,
            base_weight=0.32,
            extreme_weight=0.22,
        )
        cash_factor = cash_tied_up / 20.0
        unit_factor = excess_units * 0.1
        return round(160.0 + cash_factor + severity_factor + unit_factor, 2)

    severity_factor = _calculate_inventory_severity(
        metrics.days_of_inventory,
        base_weight=0.12,
        extreme_weight=0.08,
    )
    age_factor = max(metrics.sku.days_since_last_sale - 45, 0) * 0.8
    cash_factor = cash_tied_up / 35.0
    unit_factor = excess_units * 0.05
    return round(70.0 + cash_factor + severity_factor + age_factor + unit_factor, 2)
