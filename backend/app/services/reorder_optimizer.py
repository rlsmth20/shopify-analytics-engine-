"""Reorder optimizer — safety stock, reorder point, and EOQ.

Formulas:

* Safety stock   = z * sigma_d * sqrt(lead_time_days)
* Reorder point  = mean_daily_demand * lead_time_days + safety_stock
* Order-up-to    = reorder_point + review_period * mean_daily_demand
* EOQ            = sqrt( 2 * annual_demand * order_cost / holding_cost_per_unit )

The service-level z-score table is precomputed; merchants typically pick 0.90
through 0.99, so coarser interpolation is fine.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from app.config.lead_time import LeadTimeConfig, MOCK_LEAD_TIME_CONFIG
from app.schemas import SkuDetail
from app.schemas_v2 import ReorderSuggestion


SERVICE_LEVEL_Z = {
    0.80: 0.84,
    0.85: 1.04,
    0.90: 1.28,
    0.925: 1.44,
    0.95: 1.65,
    0.975: 1.96,
    0.99: 2.33,
    0.995: 2.58,
    0.999: 3.09,
}

DEFAULT_ORDER_COST = 35.0  # fixed cost per purchase order, USD
DEFAULT_HOLDING_RATE = 0.25  # annual holding cost as a fraction of unit cost
DEFAULT_REVIEW_PERIOD_DAYS = 7


@dataclass(frozen=True)
class ReorderInputs:
    sku: SkuDetail
    daily_history: list[float]
    lead_time_days: int
    service_level: float = 0.95
    order_cost: float = DEFAULT_ORDER_COST
    holding_rate: float = DEFAULT_HOLDING_RATE
    review_period_days: int = DEFAULT_REVIEW_PERIOD_DAYS


def build_reorder_suggestions(
    skus: list[SkuDetail],
    history_for_sku: callable,
    lead_time_config: LeadTimeConfig = MOCK_LEAD_TIME_CONFIG,
    service_level: float = 0.95,
) -> list[ReorderSuggestion]:
    suggestions: list[ReorderSuggestion] = []
    for sku in skus:
        lead_time = _resolve_lead_time(sku, lead_time_config)
        history = history_for_sku(sku.sku_id) or []
        inputs = ReorderInputs(
            sku=sku,
            daily_history=history,
            lead_time_days=lead_time,
            service_level=service_level,
        )
        suggestion = _build_suggestion(inputs)
        if suggestion.recommended_order_qty > 0:
            suggestions.append(suggestion)
    suggestions.sort(key=lambda s: s.extended_cost, reverse=True)
    return suggestions


def _build_suggestion(inputs: ReorderInputs) -> ReorderSuggestion:
    sku = inputs.sku
    history = inputs.daily_history or [sku.last_30_day_sales / 30]
    mean_daily = statistics.mean(history) if history else sku.last_30_day_sales / 30
    sigma_daily = statistics.pstdev(history) if len(history) > 1 else max(mean_daily * 0.3, 0.5)

    z = _z_for_service_level(inputs.service_level)
    safety_stock = z * sigma_daily * math.sqrt(max(inputs.lead_time_days, 1))
    reorder_point = mean_daily * inputs.lead_time_days + safety_stock
    order_up_to = reorder_point + inputs.review_period_days * mean_daily

    annual_demand = mean_daily * 365
    unit_cost = max(sku.cost, 0.0)
    holding_cost = unit_cost * inputs.holding_rate
    if unit_cost <= 0 or holding_cost <= 0 or annual_demand <= 0:
        eoq = 0
    else:
        eoq = int(math.ceil(math.sqrt((2 * annual_demand * inputs.order_cost) / holding_cost)))

    reorder_qty = max(0, int(math.ceil(order_up_to - sku.inventory)))

    # Align reorder qty with EOQ when EOQ is larger (avoid ordering less than economically optimal)
    if eoq > 0 and reorder_qty > 0:
        reorder_qty = max(reorder_qty, eoq)

    stockout_prob = _stockout_probability(
        on_hand=sku.inventory,
        mean_daily=mean_daily,
        sigma_daily=sigma_daily,
        lead_time_days=inputs.lead_time_days,
    )

    return ReorderSuggestion(
        sku_id=sku.sku_id,
        name=sku.name,
        vendor=sku.vendor,
        current_on_hand=sku.inventory,
        reorder_point=round(reorder_point, 1),
        safety_stock=round(safety_stock, 1),
        order_up_to=round(order_up_to, 1),
        recommended_order_qty=reorder_qty,
        economic_order_qty=eoq,
        service_level_target=inputs.service_level,
        expected_stockout_prob=round(stockout_prob, 3),
        unit_cost=round(sku.cost, 2),
        extended_cost=round(reorder_qty * sku.cost, 2),
        lead_time_days=inputs.lead_time_days,
        rationale=_rationale(
            sku=sku,
            reorder_qty=reorder_qty,
            eoq=eoq,
            service_level=inputs.service_level,
            lead_time_days=inputs.lead_time_days,
            mean_daily=mean_daily,
        ),
    )


def _resolve_lead_time(sku: SkuDetail, config: LeadTimeConfig) -> int:
    if sku.sku_lead_time_days is not None:
        return sku.sku_lead_time_days
    if sku.vendor in config.vendor_lead_times:
        return config.vendor_lead_times[sku.vendor]
    if sku.category in config.category_lead_times:
        return config.category_lead_times[sku.category]
    return config.global_default_lead_time_days


def _z_for_service_level(level: float) -> float:
    # Clamp to the range we tabulate, then nearest neighbor.
    best_key = min(SERVICE_LEVEL_Z.keys(), key=lambda k: abs(k - level))
    return SERVICE_LEVEL_Z[best_key]


def _stockout_probability(
    on_hand: int, mean_daily: float, sigma_daily: float, lead_time_days: int
) -> float:
    mean_lt = mean_daily * lead_time_days
    sigma_lt = max(sigma_daily * math.sqrt(max(lead_time_days, 1)), 0.001)
    z = (on_hand - mean_lt) / sigma_lt
    # 1 - CDF(z) = probability demand exceeds on_hand during lead time
    return max(0.0, min(1.0, 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))))


def _rationale(
    *,
    sku: SkuDetail,
    reorder_qty: int,
    eoq: int,
    service_level: float,
    lead_time_days: int,
    mean_daily: float,
) -> str:
    if reorder_qty <= 0:
        return "No reorder needed — inventory is already above the order-up-to target."

    coverage_after = (sku.inventory + reorder_qty) / max(mean_daily, 0.01)
    parts = [
        f"Order {reorder_qty} units to hit the {int(service_level * 100)}% service level target.",
        f"Restocks you to ~{coverage_after:.0f} days of cover (lead time {lead_time_days} days).",
    ]
    if eoq > 0 and reorder_qty >= eoq:
        parts.append(f"Matches or exceeds EOQ ({eoq}) so PO economics are sound.")
    elif eoq > 0:
        parts.append(f"Note: EOQ is {eoq}, consider upsizing this PO for better economics.")
    return " ".join(parts)


def build_vendor_totals(
    suggestions: list[ReorderSuggestion],
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for s in suggestions:
        totals[s.vendor] = round(totals.get(s.vendor, 0.0) + s.extended_cost, 2)
    return totals
