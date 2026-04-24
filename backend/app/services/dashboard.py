"""Dashboard aggregation.

Fan-in of the v2 services into a single, chart-ready response the frontend
dashboard can render without making many separate round trips.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.mock_data import MOCK_SKUS
from app.mock_data_v2 import (
    daily_history_for_sku,
    recent_daily_revenue,
    start_weekday_for_history,
    supplier_observations,
)
from app.schemas_v2 import (
    DashboardKpi,
    DashboardResponse,
    DashboardSeriesPoint,
)
from app.services.abc_analysis import build_scorecards
from app.services.alerts import list_recent_events
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_engine import build_inventory_actions
from app.services.supplier_scoring import build_supplier_scorecards


def build_dashboard() -> DashboardResponse:
    skus = MOCK_SKUS
    actions = build_inventory_actions(skus)

    # KPIs
    urgent = [a for a in actions if a.status == "urgent"]
    optimize = [a for a in actions if a.status == "optimize"]
    dead = [a for a in actions if a.status == "dead"]

    profit_at_risk = sum(
        getattr(a, "estimated_profit_impact", 0) for a in urgent
    )
    cash_tied_up = sum(
        getattr(a, "cash_tied_up", 0) for a in optimize
    ) + sum(getattr(a, "cash_tied_up", 0) for a in dead)

    revenue_30d = sum(sku.price * sku.last_30_day_sales for sku in skus)
    inventory_value = sum(sku.cost * sku.inventory for sku in skus)

    kpis = [
        DashboardKpi(
            label="Revenue (30d)",
            value=round(revenue_30d, 0),
            unit="currency",
            delta_pct=8.2,
            tone="positive",
        ),
        DashboardKpi(
            label="Inventory value",
            value=round(inventory_value, 0),
            unit="currency",
            delta_pct=-2.4,
            tone="positive",
        ),
        DashboardKpi(
            label="Cash tied up",
            value=round(cash_tied_up, 0),
            unit="currency",
            delta_pct=3.1,
            tone="negative",
        ),
        DashboardKpi(
            label="Profit at risk",
            value=round(profit_at_risk, 0),
            unit="currency",
            delta_pct=12.7,
            tone="negative",
        ),
        DashboardKpi(
            label="Urgent SKUs",
            value=len(urgent),
            unit="count",
            delta_pct=50.0,
            tone="negative",
        ),
        DashboardKpi(
            label="Dead SKUs",
            value=len(dead),
            unit="count",
            delta_pct=-14.3,
            tone="positive",
        ),
    ]

    # Revenue trend
    revenue_points = [
        DashboardSeriesPoint(label=str(offset), value=value)
        for offset, value in recent_daily_revenue(days=30)
    ]

    # Stock health breakdown
    healthy_count = len(skus) - len(urgent) - len(optimize) - len(dead)
    stock_health = [
        DashboardSeriesPoint(label="Urgent", value=len(urgent)),
        DashboardSeriesPoint(label="Optimize", value=len(optimize)),
        DashboardSeriesPoint(label="Dead", value=len(dead)),
        DashboardSeriesPoint(label="Healthy", value=max(healthy_count, 0)),
    ]

    # Top movers (last 30d)
    top_movers = sorted(skus, key=lambda s: s.last_30_day_sales, reverse=True)[:8]
    top_movers_series = [
        DashboardSeriesPoint(label=s.name, value=s.last_30_day_sales * s.price)
        for s in top_movers
    ]

    # ABC distribution
    scorecards = build_scorecards(skus, daily_history_for_sku)
    abc_counts = {"A": 0, "B": 0, "C": 0}
    for sc in scorecards:
        abc_counts[sc.abc_class] += 1
    abc_distribution = [
        DashboardSeriesPoint(label=cls, value=count) for cls, count in abc_counts.items()
    ]

    # Cash at risk by vendor
    cash_by_vendor: dict[str, float] = {}
    for a in actions:
        if a.status in ("optimize", "dead"):
            cash_by_vendor[_vendor_for_sku(a.sku_id, skus)] = (
                cash_by_vendor.get(_vendor_for_sku(a.sku_id, skus), 0)
                + getattr(a, "cash_tied_up", 0)
            )
    cash_by_vendor_series = sorted(
        [DashboardSeriesPoint(label=v, value=round(c, 0)) for v, c in cash_by_vendor.items()],
        key=lambda p: p.value,
        reverse=True,
    )[:6]

    # Forecast vs actual 7d (simple: forecast 30d then compare days)
    forecast_vs_actual: list[DashboardSeriesPoint] = []
    for sku in top_movers[:5]:
        history = daily_history_for_sku(sku.sku_id, days=90)
        forecast = forecast_sku(
            ForecastInputs(
                sku_id=sku.sku_id,
                daily_history=history[:-7],  # forecast using all but last 7 days
                on_hand=sku.inventory,
                start_weekday=start_weekday_for_history(),
            ),
            horizon_days=7,
        )
        predicted = forecast.projected_30_day_demand / 30 * 7
        actual = sum(history[-7:])
        forecast_vs_actual.append(
            DashboardSeriesPoint(
                label=sku.name, value=round((actual - predicted) / max(predicted, 0.01) * 100, 1)
            )
        )

    # Alert counts by severity (from recent events registry)
    events = list_recent_events(limit=500)
    severity_counts = {"critical": 0, "warning": 0, "info": 0}
    for event in events:
        severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
    alert_counts = [
        DashboardSeriesPoint(label=k, value=v) for k, v in severity_counts.items()
    ]

    return DashboardResponse(
        kpis=kpis,
        revenue_trend_30d=revenue_points,
        stock_health_breakdown=stock_health,
        top_movers=top_movers_series,
        abc_distribution=abc_distribution,
        cash_at_risk_by_vendor=cash_by_vendor_series,
        forecast_vs_actual_7d=forecast_vs_actual,
        alert_counts_by_severity=alert_counts,
        generated_at=datetime.now(timezone.utc),
    )


def _vendor_for_sku(sku_id: str, skus) -> str:
    for sku in skus:
        if sku.sku_id == sku_id:
            return sku.vendor
    return "Unknown"
