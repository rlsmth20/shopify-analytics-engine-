"""Inventory health analytics for the operator analytics page."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.schemas import SkuDetail
from app.services.cost_provenance import cost_known
from app.services.shop_skus import sku_identity_issues
from app.schemas_v2 import (
    ForecastResult,
    InventoryHealthBucket,
    InventoryHealthInsight,
    InventoryHealthKpi,
    InventoryHealthResponse,
    InventoryHealthSku,
    InventoryForecastCoverage,
)


def build_inventory_health(
    *,
    skus: list[SkuDetail],
    forecasts: list[ForecastResult],
) -> InventoryHealthResponse:
    forecast_by_sku = {(forecast.product_id or forecast.sku_id): forecast for forecast in forecasts}
    sku_count = len(skus)
    available = [forecast_by_sku[sku.product_id or sku.sku_id] for sku in skus
                 if _forecast_available(forecast_by_sku.get(sku.product_id or sku.sku_id))]
    coverage = InventoryForecastCoverage(
        total_skus=sku_count,
        available_skus=len(available),
        unavailable_skus=sku_count - len(available),
        low_confidence_skus=sum(_limited_forecast(forecast) for forecast in available),
        no_recent_sales_skus=sum(forecast.demand_signal == "no_recent_sales" for forecast in available),
    )
    risk_known = coverage.unavailable_skus == 0 and sku_count > 0

    inventory_cost = sum(_inventory_cost(sku) for sku in skus)
    inventory_retail = sum(sku.price * sku.inventory for sku in skus)
    dead_stock_cash = sum(
        _inventory_cost(sku)
        for sku in skus
        if not sku.identity_ambiguous and sku.sales_history_complete and sku.inventory > 0 and sku.days_since_last_sale >= 90
    )
    stockout_revenue_risk = sum(
        _stockout_revenue_risk(sku, forecast_by_sku.get(sku.product_id or sku.sku_id))
        for sku in skus
    )
    stockout_margin_risk = sum(
        _stockout_margin_risk(sku, forecast_by_sku.get(sku.product_id or sku.sku_id))
        for sku in skus
    )
    high_confidence_count = sum(1 for forecast in available if forecast.confidence == "high" and not _limited_forecast(forecast))
    warning_count = sum(len(forecast.data_quality_warnings) for forecast in forecasts)

    dead_stock_pct = dead_stock_cash / inventory_cost if inventory_cost > 0 else 0.0
    confidence_pct = high_confidence_count / sku_count if sku_count else 0.0
    avg_days_of_cover = _average_days_of_cover(skus)
    missing_cost_count = sum(not cost_known(sku) for sku in skus)
    inventory_known = all(cost_known(sku) for sku in skus if sku.inventory > 0)
    dead_known = all(not sku.identity_ambiguous and sku.sales_history_complete and (cost_known(sku) or sku.days_since_last_sale < 90)
                     for sku in skus if sku.inventory > 0)
    margin_known = risk_known and all(cost_known(sku) for sku in skus if _stockout_revenue_risk(sku, forecast_by_sku.get(sku.product_id or sku.sku_id)) > 0)

    health_counts = Counter(_health_bucket(sku, forecast_by_sku.get(sku.product_id or sku.sku_id)) for sku in skus)
    confidence_counts = Counter("low" if _limited_forecast(forecast) else forecast.confidence for forecast in available)
    if not available:
        risk_note = "Usable sales history or a unique SKU mapping is unavailable; stockout revenue and gross margin exposure cannot be assessed."
    elif not risk_known:
        risk_note = (f"Estimated revenue-risk subtotal: {_currency(stockout_revenue_risk)} from {coverage.available_skus} of {sku_count} SKUs. "
                     f"{coverage.unavailable_skus} cannot be assessed; total revenue and gross margin exposure are unknown.")
    else:
        risk_note = (f"{_currency(stockout_margin_risk)} estimated gross margin exposed."
                     if margin_known else "Gross margin exposure is unknown because unit costs are missing.")
    if coverage.low_confidence_skus:
        risk_note += f" {coverage.low_confidence_skus} available forecasts have limited history or low confidence; verify demand before ordering."
    if coverage.no_recent_sales_skus:
        risk_note += " Observed zero sales do not guarantee zero future demand."

    return InventoryHealthResponse(
        kpis=[
            InventoryHealthKpi(
                label="Inventory cost on hand",
                value=round(inventory_cost, 0),
                value_known=inventory_known,
                known_value=round(inventory_cost, 0) if inventory_known else None,
                unit="currency",
                tone="neutral",
                note=(f"{_currency(inventory_retail)} at retail across {sku_count} SKUs."
                      if inventory_known else "Unit costs are missing; total inventory cost is unknown."),
            ),
            InventoryHealthKpi(
                label="Stockout revenue risk",
                value=round(stockout_revenue_risk, 0),
                value_known=risk_known,
                known_value=round(stockout_revenue_risk, 0) if risk_known else None,
                unit="currency",
                tone="neutral" if not risk_known or coverage.low_confidence_skus else "negative" if stockout_revenue_risk > 0 else "positive",
                note=risk_note,
            ),
            InventoryHealthKpi(
                label="Dead-stock capital",
                value=round(dead_stock_cash, 0),
                value_known=dead_known,
                known_value=round(dead_stock_cash, 0) if dead_known else None,
                unit="currency",
                tone="negative" if dead_stock_cash > 0 else "positive",
                note=(f"{dead_stock_pct * 100:.0f}% of inventory cost is stale 90+ days."
                      if inventory_known and dead_known else "Complete sales history and unit costs are required to measure stale-stock capital and its share of inventory."),
            ),
            InventoryHealthKpi(
                label="High-confidence forecasts",
                value=round(confidence_pct, 3),
                unit="percent",
                tone="positive" if confidence_pct >= 0.6 else "neutral",
                note=f"{coverage.available_skus} of {sku_count} SKUs can be assessed; {warning_count} forecast data-quality notes need review.",
            ),
            InventoryHealthKpi(
                label="Average days of cover",
                value=round(avg_days_of_cover, 1) if avg_days_of_cover is not None else 0.0,
                value_known=avg_days_of_cover is not None,
                known_value=round(avg_days_of_cover, 1) if avg_days_of_cover is not None else None,
                unit="days",
                tone="neutral",
                note=("Average across SKUs with positive recorded 30-day sales velocity; excludes zero or missing demand."
                      if avg_days_of_cover is not None else "No positive recorded demand is available to calculate days of cover."),
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
            InventoryHealthBucket(label="Unavailable", value=coverage.unavailable_skus, tone="neutral"),
        ],
        top_cash_trapped=_top_cash_trapped(skus),
        top_stockout_risk=_top_stockout_risk(skus, forecast_by_sku),
        insights=_build_insights(
            stockout_revenue_risk=stockout_revenue_risk,
            dead_stock_cash=dead_stock_cash if dead_known and inventory_known else 0,
            dead_stock_pct=dead_stock_pct if dead_known and inventory_known else 0,
            confidence_pct=confidence_pct,
            warning_count=warning_count,
            health_counts=health_counts,
            risk_complete=risk_known,
        ) + ([InventoryHealthInsight(title="Add unit costs", severity="info",
              description="Cost-based profit, capital and purchasing estimates remain unknown until unit costs are recorded.",
              metric_label="SKUs missing unit cost", metric_value=str(missing_cost_count))] if missing_cost_count else []),
        forecast_coverage=coverage,
        identity_issues=sku_identity_issues(skus),
        generated_at=datetime.now(timezone.utc),
    )


def _inventory_cost(sku: SkuDetail) -> float:
    return max(sku.cost, 0.0) * max(sku.inventory, 0)


def _forecast_available(forecast: ForecastResult | None) -> bool:
    # Legacy fixtures may omit the additive flag. Zero usable history still
    # cannot turn the legacy numeric zero placeholders into measured risk.
    return forecast is not None and forecast.forecast_available and forecast.history_days > 0


def _limited_forecast(forecast: ForecastResult) -> bool:
    return forecast.confidence == "low" or forecast.history_days < 30


def _stockout_revenue_risk(sku: SkuDetail, forecast: ForecastResult | None) -> float:
    if not _forecast_available(forecast):
        return 0.0
    shortage_units = max(forecast.projected_30_day_demand - sku.inventory, 0.0)
    return shortage_units * sku.price * forecast.stockout_probability_30d


def _stockout_margin_risk(sku: SkuDetail, forecast: ForecastResult | None) -> float:
    if not _forecast_available(forecast):
        return 0.0
    shortage_units = max(forecast.projected_30_day_demand - sku.inventory, 0.0)
    gross_margin = max(sku.price - sku.cost, 0.0)
    return shortage_units * gross_margin * forecast.stockout_probability_30d


def _average_days_of_cover(skus: list[SkuDetail]) -> float | None:
    values: list[float] = []
    for sku in skus:
        velocity = sku.last_30_day_sales / 30
        if velocity > 0:
            values.append(min(sku.inventory / velocity, 365))
    return sum(values) / len(values) if values else None


def _health_bucket(sku: SkuDetail, forecast: ForecastResult | None) -> str:
    if sku.identity_ambiguous:
        return "no_signal"
    if sku.sales_history_complete and sku.inventory > 0 and sku.days_since_last_sale >= 90:
        return "dead"
    if not _forecast_available(forecast):
        return "no_signal"
    if forecast.stockout_probability_30d >= 0.6:
        return "stockout"
    if not sku.sales_history_complete:
        return "no_signal"
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
        if not sku.identity_ambiguous and sku.sales_history_complete and cost_known(sku) and sku.inventory > 0
        and (sku.days_since_last_sale >= 60 or _days_of_cover(sku) >= 120)
    ]
    candidates.sort(key=_inventory_cost, reverse=True)
    return [
        InventoryHealthSku(
            sku_id=sku.sku_id,
            product_id=sku.product_id,
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
            (sku, forecast_by_sku.get(sku.product_id or sku.sku_id))
            for sku in skus
            if _forecast_available(forecast_by_sku.get(sku.product_id or sku.sku_id))
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
                product_id=sku.product_id,
                name=sku.name,
                vendor=sku.vendor,
                value=round(value, 0),
                note=_stockout_note(forecast),
                severity="critical" if forecast.stockout_probability_30d >= 0.75 else "warning",
            )
        )
    return rows


def _stockout_note(forecast: ForecastResult) -> str:
    if _limited_forecast(forecast):
        history_note = (f"Only {forecast.history_days} day{'s' if forecast.history_days != 1 else ''} of usable sales history. "
                        if forecast.history_days < 30 else "")
        limitation = "Low-confidence stockout estimate. " if forecast.confidence == "low" else "Limited-history stockout estimate. "
        return (f"{limitation}{history_note}"
                "Verify recent sales, current stock and incoming orders before ordering.")
    percentage = forecast.stockout_probability_30d * 100
    probability = "over 99%" if percentage > 99 else "under 1%" if 0 < percentage < 1 else f"{percentage:.0f}%"
    return f"{probability} estimated stockout risk, {forecast.projected_30_day_demand:.0f} units forecast ({forecast.confidence} confidence)."


def _build_insights(
    *,
    stockout_revenue_risk: float,
    dead_stock_cash: float,
    dead_stock_pct: float,
    confidence_pct: float,
    warning_count: int,
    health_counts: Counter,
    risk_complete: bool = True,
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
                metric_label="Estimated revenue exposed" if risk_complete else "Estimated revenue-risk subtotal",
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
    if health_counts["healthy"] == 0 and any(health_counts[key] > 0 for key in ("stockout", "dead", "overstock")):
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
