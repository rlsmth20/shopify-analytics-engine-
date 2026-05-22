"""Inventory health analytics for the operator analytics page."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.schemas import SkuDetail
from app.schemas_v2 import (
    ForecastResult,
    InventoryHealthBucket,
    InventoryHealthInsight,
    InventoryHealthKpi,
    InventoryHealthResponse,
    InventoryHealthSku,
)


def build_inventory_health(
    *,
    skus: list[SkuDetail],
    forecasts: list[ForecastResult],
) -> InventoryHealthResponse:
    forecast_by_sku = {forecast.sku_id: forecast for forecast in forecasts}
    sku_count = len(skus)

    inventory_cost = sum(_inventory_cost(sku) for sku in skus)
    inventory_retail = sum(sku.price * sku.inventory for sku in skus)
    dead_stock_cash = sum(
        _inventory_cost(sku)
        for sku in skus
        if sku.inventory > 0 and sku.days_since_last_sale >= 90
    )
    stockout_revenue_risk = sum(
        _stockout_revenue_risk(sku, forecast_by_sku.get(sku.sku_id))
        for sku in skus
    )
    stockout_margin_risk = sum(
        _stockout_margin_risk(sku, forecast_by_sku.get(sku.sku_id))
        for sku in skus
    )
    high_confidence_count = sum(1 for forecast in forecasts if forecast.confidence == "high")
    warning_count = sum(len(forecast.data_quality_warnings) for forecast in forecasts)

    dead_stock_pct = dead_stock_cash / inventory_cost if inventory_cost > 0 else 0.0
    confidence_pct = high_confidence_count / len(forecasts) if forecasts else 0.0
    avg_days_of_cover = _average_days_of_cover(skus)

    health_counts = Counter(_health_bucket(sku, forecast_by_sku.get(sku.sku_id)) for sku in skus)
    confidence_counts = Counter(forecast.confidence for forecast in forecasts)

    return InventoryHealthResponse(
        kpis=[
            InventoryHealthKpi(
                label="Inventory cost on hand",
                value=round(inventory_cost, 0),
                unit="currency",
                tone="neutral",
                note=f"{_currency(inventory_retail)} at retail across {sku_count} SKUs.",
            ),
            InventoryHealthKpi(
                label="Stockout revenue risk",
                value=round(stockout_revenue_risk, 0),
                unit="currency",
                tone="negative" if stockout_revenue_risk > 0 else "positive",
                note=f"{_currency(stockout_margin_risk)} estimated gross margin exposed.",
            ),
            InventoryHealthKpi(
                label="Dead-stock capital",
                value=round(dead_stock_cash, 0),
                unit="currency",
                tone="negative" if dead_stock_cash > 0 else "positive",
                note=f"{dead_stock_pct * 100:.0f}% of inventory cost is stale 90+ days.",
            ),
            InventoryHealthKpi(
                label="High-confidence forecasts",
                value=round(confidence_pct, 3),
                unit="percent",
                tone="positive" if confidence_pct >= 0.6 else "neutral",
                note=f"{warning_count} forecast data-quality notes need review.",
            ),
            InventoryHealthKpi(
                label="Average days of cover",
                value=round(avg_days_of_cover, 1),
                unit="days",
                tone="neutral",
                note="Based on current 30-day sales velocity.",
            ),
        ],
        health_buckets=[
            InventoryHealthBucket(label="Healthy", value=health_counts["healthy"], tone="positive"),
            InventoryHealthBucket(label="Stockout risk", value=health_counts["stockout"], tone="negative"),
            InventoryHealthBucket(label="Overstock", value=health_counts["overstock"], tone="negative"),
            InventoryHealthBucket(label="Dead stock", value=health_counts["dead"], tone="negative"),
            InventoryHealthBucket(label="No signal", value=health_counts["no_signal"], tone="neutral"),
        ],
        forecast_confidence=[
            InventoryHealthBucket(label="High", value=confidence_counts["high"], tone="positive"),
            InventoryHealthBucket(label="Medium", value=confidence_counts["medium"], tone="neutral"),
            InventoryHealthBucket(label="Low", value=confidence_counts["low"], tone="negative"),
        ],
        top_cash_trapped=_top_cash_trapped(skus),
        top_stockout_risk=_top_stockout_risk(skus, forecast_by_sku),
        insights=_build_insights(
            stockout_revenue_risk=stockout_revenue_risk,
            dead_stock_cash=dead_stock_cash,
            dead_stock_pct=dead_stock_pct,
            confidence_pct=confidence_pct,
            warning_count=warning_count,
            health_counts=health_counts,
        ),
        generated_at=datetime.now(timezone.utc),
    )


def _inventory_cost(sku: SkuDetail) -> float:
    return max(sku.cost, 0.0) * max(sku.inventory, 0)


def _stockout_revenue_risk(sku: SkuDetail, forecast: ForecastResult | None) -> float:
    if forecast is None:
        return 0.0
    shortage_units = max(forecast.projected_30_day_demand - sku.inventory, 0.0)
    return shortage_units * sku.price * forecast.stockout_probability_30d


def _stockout_margin_risk(sku: SkuDetail, forecast: ForecastResult | None) -> float:
    if forecast is None:
        return 0.0
    shortage_units = max(forecast.projected_30_day_demand - sku.inventory, 0.0)
    gross_margin = max(sku.price - sku.cost, 0.0)
    return shortage_units * gross_margin * forecast.stockout_probability_30d


def _average_days_of_cover(skus: list[SkuDetail]) -> float:
    values: list[float] = []
    for sku in skus:
        velocity = sku.last_30_day_sales / 30
        if velocity > 0:
            values.append(min(sku.inventory / velocity, 365))
    return sum(values) / len(values) if values else 0.0


def _health_bucket(sku: SkuDetail, forecast: ForecastResult | None) -> str:
    if sku.inventory > 0 and sku.days_since_last_sale >= 90:
        return "dead"
    if forecast is not None and forecast.stockout_probability_30d >= 0.6:
        return "stockout"
    velocity = sku.last_30_day_sales / 30
    if velocity <= 0:
        return "no_signal"
    if sku.inventory / velocity >= 120:
        return "overstock"
    return "healthy"


def _top_cash_trapped(skus: list[SkuDetail]) -> list[InventoryHealthSku]:
    candidates = [
        sku
        for sku in skus
        if sku.inventory > 0 and (sku.days_since_last_sale >= 60 or _days_of_cover(sku) >= 120)
    ]
    candidates.sort(key=_inventory_cost, reverse=True)
    return [
        InventoryHealthSku(
            sku_id=sku.sku_id,
            name=sku.name,
            vendor=sku.vendor,
            value=round(_inventory_cost(sku), 0),
            note=f"{sku.inventory} on hand, {sku.days_since_last_sale} days since last sale.",
            severity="critical" if sku.days_since_last_sale >= 120 else "warning",
        )
        for sku in candidates[:8]
    ]


def _top_stockout_risk(
    skus: list[SkuDetail],
    forecast_by_sku: dict[str, ForecastResult],
) -> list[InventoryHealthSku]:
    ranked = sorted(
        (
            (sku, forecast_by_sku.get(sku.sku_id))
            for sku in skus
            if forecast_by_sku.get(sku.sku_id) is not None
        ),
        key=lambda pair: _stockout_revenue_risk(pair[0], pair[1]),
        reverse=True,
    )
    rows: list[InventoryHealthSku] = []
    for sku, forecast in ranked[:8]:
        if forecast is None:
            continue
        value = _stockout_revenue_risk(sku, forecast)
        if value <= 0:
            continue
        rows.append(
            InventoryHealthSku(
                sku_id=sku.sku_id,
                name=sku.name,
                vendor=sku.vendor,
                value=round(value, 0),
                note=(
                    f"{forecast.stockout_probability_30d * 100:.0f}% stockout risk, "
                    f"{forecast.projected_30_day_demand:.0f} units forecast."
                ),
                severity="critical" if forecast.stockout_probability_30d >= 0.75 else "warning",
            )
        )
    return rows


def _build_insights(
    *,
    stockout_revenue_risk: float,
    dead_stock_cash: float,
    dead_stock_pct: float,
    confidence_pct: float,
    warning_count: int,
    health_counts: Counter,
) -> list[InventoryHealthInsight]:
    insights: list[InventoryHealthInsight] = []
    if stockout_revenue_risk > 0:
        insights.append(
            InventoryHealthInsight(
                title="Protect revenue first",
                severity="critical" if stockout_revenue_risk >= 5000 else "warning",
                description=(
                    "Several SKUs are forecast to sell more units than are currently on hand. "
                    "Review the stockout-risk list before placing broad replenishment orders."
                ),
                metric_label="Revenue exposed",
                metric_value=_currency(stockout_revenue_risk),
            )
        )
    if dead_stock_cash > 0:
        insights.append(
            InventoryHealthInsight(
                title="Recover trapped cash",
                severity="warning",
                description=(
                    "Dead and over-covered inventory is tying up cash that could fund higher-velocity buys."
                ),
                metric_label="Stale cost",
                metric_value=f"{_currency(dead_stock_cash)} ({dead_stock_pct * 100:.0f}%)",
            )
        )
    if confidence_pct < 0.5 or warning_count > 0:
        insights.append(
            InventoryHealthInsight(
                title="Improve forecast trust",
                severity="info",
                description=(
                    "Low-confidence forecasts usually mean limited history, sparse demand, or stockout-limited sales. "
                    "Use the forecast page warnings before acting on large buys."
                ),
                metric_label="High confidence",
                metric_value=f"{confidence_pct * 100:.0f}%",
            )
        )
    if health_counts["healthy"] == 0 and sum(health_counts.values()) > 0:
        insights.append(
            InventoryHealthInsight(
                title="Catalog needs triage",
                severity="warning",
                description="No SKUs currently fall into the healthy bucket. Start with stockouts, then dead stock.",
                metric_label="Healthy SKUs",
                metric_value="0",
            )
        )
    return insights[:4]


def _days_of_cover(sku: SkuDetail) -> float:
    velocity = sku.last_30_day_sales / 30
    if velocity <= 0:
        return 999.0
    return sku.inventory / velocity


def _currency(value: float) -> str:
    return f"${value:,.0f}"
