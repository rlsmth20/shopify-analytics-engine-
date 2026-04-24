"""Extended schemas for v2 engine features.

These live alongside the existing schemas.py so the v1 API contract is untouched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Classification enums for richer inventory intelligence
# ---------------------------------------------------------------------------

AbcClass = Literal["A", "B", "C"]
XyzClass = Literal["X", "Y", "Z"]
TrendDirection = Literal["rising", "steady", "declining", "volatile"]
SeasonalityPattern = Literal["weekend_heavy", "weekday_heavy", "flat", "unknown"]
NotificationChannel = Literal["email", "sms", "slack", "webhook"]
AlertSeverity = Literal["info", "warning", "critical"]
AlertTrigger = Literal[
    "stockout_risk",
    "dead_stock",
    "overstock",
    "forecast_miss",
    "supplier_slip",
    "bundle_break",
    "price_drop",
]
PurchaseOrderStatus = Literal["draft", "ready", "sent", "received", "cancelled"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ForecastPoint(ApiModel):
    day_offset: int = Field(ge=0)
    expected_units: float = Field(ge=0)
    lower_bound: float = Field(ge=0)
    upper_bound: float = Field(ge=0)


class ForecastResult(ApiModel):
    sku_id: str
    horizon_days: int
    method: Literal["moving_average", "exponential_smoothing", "seasonal_ema", "naive"]
    trend: TrendDirection
    seasonality: SeasonalityPattern
    weekly_index: list[float] = Field(
        default_factory=list,
        description="7 multipliers for Mon-Sun showing the detected weekly pattern."
    )
    confidence: Literal["high", "medium", "low"]
    projected_30_day_demand: float
    projected_60_day_demand: float
    projected_90_day_demand: float
    stockout_probability_30d: float = Field(ge=0, le=1)
    points: list[ForecastPoint] = Field(default_factory=list)
    explain: str


class ForecastFeedResponse(ApiModel):
    forecasts: list[ForecastResult]


# ---------------------------------------------------------------------------
# ABC / XYZ classification + scorecard
# ---------------------------------------------------------------------------

class SkuScorecard(ApiModel):
    sku_id: str
    name: str
    vendor: str
    category: str
    abc_class: AbcClass
    xyz_class: XyzClass
    contribution_pct: float
    variability_cv: float
    avg_daily_units: float
    avg_daily_revenue: float
    profit_per_unit: float
    sell_through_30d: float
    inventory_on_hand: int
    classification_note: str


class ScorecardResponse(ApiModel):
    scorecards: list[SkuScorecard]
    a_count: int
    b_count: int
    c_count: int
    cutoff_a_pct: float = 0.8
    cutoff_b_pct: float = 0.95


# ---------------------------------------------------------------------------
# Reorder optimizer
# ---------------------------------------------------------------------------

class ReorderSuggestion(ApiModel):
    sku_id: str
    name: str
    vendor: str
    current_on_hand: int
    reorder_point: float
    safety_stock: float
    order_up_to: float
    recommended_order_qty: int
    economic_order_qty: int
    service_level_target: float
    expected_stockout_prob: float
    unit_cost: float
    extended_cost: float
    lead_time_days: int
    rationale: str


class ReorderFeedResponse(ApiModel):
    service_level: float
    suggestions: list[ReorderSuggestion]
    total_extended_cost: float
    vendor_totals: dict[str, float]


# ---------------------------------------------------------------------------
# Supplier scoring
# ---------------------------------------------------------------------------

class SupplierScorecard(ApiModel):
    vendor: str
    sku_count: int
    on_time_pct: float
    fill_rate_pct: float
    avg_lead_time_days: float
    lead_time_variance_days: float
    cost_stability_score: float
    overall_score: float
    tier: Literal["preferred", "acceptable", "at_risk"]
    notes: list[str]


class SupplierScoreboardResponse(ApiModel):
    vendors: list[SupplierScorecard]


# ---------------------------------------------------------------------------
# Bundle / Kit
# ---------------------------------------------------------------------------

class BundleComponent(ApiModel):
    component_sku_id: str
    qty_per_bundle: int


class BundleHealth(ApiModel):
    bundle_sku_id: str
    bundle_name: str
    max_bundles_sellable: int
    limiting_component_sku_id: str
    limiting_component_name: str
    component_status: list[str]
    total_component_value_at_risk: float
    recommended_action: str


class BundleHealthResponse(ApiModel):
    bundles: list[BundleHealth]


# ---------------------------------------------------------------------------
# Multi-location transfers
# ---------------------------------------------------------------------------

class TransferRecommendation(ApiModel):
    sku_id: str
    name: str
    from_location: str
    to_location: str
    qty: int
    from_days_of_cover_before: float
    to_days_of_cover_before: float
    from_days_of_cover_after: float
    to_days_of_cover_after: float
    rationale: str


class TransferRecommendationsResponse(ApiModel):
    transfers: list[TransferRecommendation]


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------

class PurchaseOrderLine(ApiModel):
    sku_id: str
    name: str
    qty: int
    unit_cost: float
    extended_cost: float


class PurchaseOrderDraft(ApiModel):
    po_id: str
    vendor: str
    created_at: datetime
    status: PurchaseOrderStatus
    lines: list[PurchaseOrderLine]
    total_cost: float
    expected_arrival_date: str
    rationale: str


class PurchaseOrderDraftsResponse(ApiModel):
    drafts: list[PurchaseOrderDraft]
    total_capital_required: float


# ---------------------------------------------------------------------------
# Dead stock / liquidation
# ---------------------------------------------------------------------------

class LiquidationSuggestion(ApiModel):
    sku_id: str
    name: str
    on_hand: int
    days_since_last_sale: int
    capital_tied_up: float
    suggested_markdown_pct: float
    suggested_price: float
    projected_recovered_capital: float
    tactic: Literal["markdown", "bundle", "wholesale", "donate_write_off"]
    rationale: str


class LiquidationResponse(ApiModel):
    total_capital_recoverable: float
    suggestions: list[LiquidationSuggestion]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertRule(ApiModel):
    id: str
    name: str
    trigger: AlertTrigger
    severity: AlertSeverity
    channels: list[NotificationChannel]
    threshold: float = Field(
        description="Interpretation depends on trigger; see alert service docs."
    )
    enabled: bool = True
    created_at: datetime
    last_fired_at: Optional[datetime] = None


class AlertEvent(ApiModel):
    id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    trigger: AlertTrigger
    sku_id: Optional[str] = None
    sku_name: Optional[str] = None
    message: str
    fired_at: datetime
    channels_sent: list[NotificationChannel]
    delivered: bool


class AlertListResponse(ApiModel):
    rules: list[AlertRule]


class AlertEventsResponse(ApiModel):
    events: list[AlertEvent]


class NotificationChannelConfig(ApiModel):
    channel: NotificationChannel
    enabled: bool
    target: str = Field(
        description="Email address, phone number, Slack webhook URL, or generic webhook URL."
    )
    verified: bool = False


class NotificationChannelsResponse(ApiModel):
    channels: list[NotificationChannelConfig]


class CreateAlertRuleRequest(ApiModel):
    name: str = Field(min_length=1)
    trigger: AlertTrigger
    severity: AlertSeverity
    channels: list[NotificationChannel]
    threshold: float
    enabled: bool = True


class UpdateNotificationChannelRequest(ApiModel):
    channel: NotificationChannel
    enabled: bool
    target: str


class TestAlertRequest(ApiModel):
    channel: NotificationChannel
    target: str


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------

class DashboardKpi(ApiModel):
    label: str
    value: float
    unit: Literal["currency", "count", "percent", "days"]
    delta_pct: Optional[float] = None
    tone: Literal["positive", "negative", "neutral"] = "neutral"


class DashboardSeriesPoint(ApiModel):
    label: str
    value: float


class DashboardResponse(ApiModel):
    kpis: list[DashboardKpi]
    revenue_trend_30d: list[DashboardSeriesPoint]
    stock_health_breakdown: list[DashboardSeriesPoint]
    top_movers: list[DashboardSeriesPoint]
    abc_distribution: list[DashboardSeriesPoint]
    cash_at_risk_by_vendor: list[DashboardSeriesPoint]
    forecast_vs_actual_7d: list[DashboardSeriesPoint]
    alert_counts_by_severity: list[DashboardSeriesPoint]
    generated_at: datetime
