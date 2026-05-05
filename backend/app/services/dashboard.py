"""Dashboard aggregation.

Fan-in of the v2 services into a single, chart-ready response the frontend
dashboard can render without making many separate round trips.

Phase 2: takes per-shop data via parameters so the same logic works for
real-DB shops and (in tests) synthetic fixtures. The route is the only
place that knows where the data comes from.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Sequence

from app.schemas import SkuDetail
from app.schemas_v2 import (
    DashboardKpi,
    DashboardResponse,
    DashboardSeriesPoint,
)
from app.services.abc_analysis import build_scorecards
from app.services.alerts import list_recent_events
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_engine import build_inventory_actions


# Type aliases — readability for the function-parameter signatures below.
DailyHistoryFn = Callable[[str, int], list[int]]  # (sku_id, days) -> daily qtys
RecentRevenueFn = Callable[[int], list[tuple[int, float]]]  # (days) -> [(offset, rev)]


def build_dashboard(
    skus: Sequence[SkuDetail],
    *,
    daily_history_fn: DailyHistoryFn,
    recent_revenue_fn: RecentRevenueFn,
    start_weekday: int,
) -> DashboardResponse:
    if not skus:
        return _empty_dashboard()

    actions = build_inventory_actions(list(skus))

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
            delta_pct=None,
            tone="positive",
        ),
        DashboardKpi(
            label="Inventory value",
            value=round(inventory_value, 0),
            unit="currency",
            delta_pct=None,
            tone="positive",
        ),
        DashboardKpi(
            label="Cash tied up",
            value=round(cash_tied_up, 0),
            unit="currency",
            delta_pct=None,
            tone="negative",
        ),
        DashboardKpi(
            label="Profit at risk",
            value=round(profit_at_risk, 0),
            unit="currency",
            delta_pct=None,
            tone="negative",
        ),
        DashboardKpi(
            label="Urgent SKUs",
            value=len(urgent),
            unit="count",
            delta_pct=None,
            tone="negative",
        ),
        DashboardKpi(
            label="Dead SKUs",
            value=len(dead),
            unit="count",
            delta_pct=None,
            tone="positive",
        ),
    ]

    # Revenue trend
    revenue_points = [
        DashboardSeriesPoint(label=str(offset), value=value)
        for offset, value in recent_revenue_fn(30)
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
    scorecards = build_scorecards(list(skus), lambda sid: daily_history_fn(sid, 90))
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
        history = daily_history_fn(sku.sku_id, 90)
        forecast = forecast_sku(
            ForecastInputs(
                sku_id=sku.sku_id,
                daily_history=history[:-7],  # forecast using all but last 7 days
                on_hand=sku.inventory,
                start_weekday=start_weekday,
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


def _empty_dashboard() -> DashboardResponse:
    """Render the dashboard for a shop with zero imported data.

    Every series is empty rather than zero-valued — the frontend renders a
    "no data yet" state when these come back empty, which is more honest
    than charts at zero.
    """
    zero = lambda label: DashboardKpi(label=label, value=0, unit="count", delta_pct=None, tone="positive")
    return DashboardResponse(
        kpis=[
            zero("Revenue (30d)"),
            zero("Inventory value"),
            zero("Cash tied up"),
            zero("Profit at risk"),
            zero("Urgent SKUs"),
            zero("Dead SKUs"),
        ],
        revenue_trend_30d=[],
        stock_health_breakdown=[],
        top_movers=[],
        abc_distribution=[],
        cash_at_risk_by_vendor=[],
        forecast_vs_actual_7d=[],
        alert_counts_by_severity=[],
        generated_at=datetime.now(timezone.utc),
    )
