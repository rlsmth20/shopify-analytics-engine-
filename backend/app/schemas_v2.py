"""Extended schemas for v2 engine features.

These live alongside the existing schemas.py so the v1 API contract is untouched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas import CostSource


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
PurchaseOrderStatus = Literal["draft", "ready", "approved", "sent", "partially_received", "received", "cancelled"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinancialProjection(ApiModel):
    """Canonical cost-derived values; legacy numeric fields remain compatible."""
    financial_values_known: bool = True
    financial_values: dict[str, float | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def canonical_financial_values(self):
        if getattr(self, "cost_source", "recorded") != "recorded":
            self.financial_values_known = False
        fields = {
            "profit_per_unit", "unit_cost", "extended_cost", "landed_extended_cost", "landed_unit_cost",
            "freight_share_pct", "total_extended_cost", "subtotal_cost", "total_cost", "estimated_cost",
            "total_capital_required", "total_estimated_cost", "capital_tied_up", "suggested_markdown_pct",
            "suggested_price", "projected_recovered_capital", "total_capital_recoverable",
            "total_component_value_at_risk", "anchor_cost", "dead_cost", "dead_capital_tied_up",
            "suggested_bundle_price", "bundle_unit_cost", "bundle_margin_pct", "projected_cash_recovered",
            "dead_stock_capital", "order_now_cost", "deferrable_cost",
        }
        self.financial_values = {key: getattr(self, key) if self.financial_values_known else None
                                 for key in fields if key in type(self).model_fields}
        return self


class CostedProjection(FinancialProjection):
    cost_source: CostSource = "recorded"


class KnownValueProjection(ApiModel):
    value: float
    value_known: bool = True
    known_value: float | None = None

    @model_validator(mode="after")
    def canonical_known_value(self):
        self.known_value = self.value if self.value_known else None
        return self


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
    history_days: int = Field(ge=0)
    adjusted_stockout_days: int = Field(
        ge=0,
        description="Recent zero-sales days adjusted because the SKU appears stockout-limited.",
    )
    data_quality_warnings: list[str] = Field(default_factory=list)
    backtest_mae_14d: Optional[float] = None
    backtest_mape_14d: Optional[float] = None
    forecast_bias_14d: Optional[Literal["over_forecast", "under_forecast", "balanced"]] = None
    trust_reasons: list[str] = Field(default_factory=list)


class ForecastFeedResponse(ApiModel):
    forecasts: list[ForecastResult]


# ---------------------------------------------------------------------------
# ABC / XYZ classification + scorecard
# ---------------------------------------------------------------------------

class SkuScorecard(CostedProjection):
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


class InventoryHealthKpi(KnownValueProjection):
    label: str
    unit: Literal["currency", "count", "percent", "days"]
    tone: Literal["positive", "negative", "neutral"] = "neutral"
    note: str


class InventoryHealthBucket(ApiModel):
    label: str
    value: float
    tone: Literal["positive", "negative", "neutral"] = "neutral"


class InventoryHealthSku(KnownValueProjection):
    sku_id: str
    name: str
    vendor: str
    note: str
    severity: Literal["critical", "warning", "info"]


class InventoryHealthInsight(ApiModel):
    title: str
    severity: Literal["critical", "warning", "info"]
    description: str
    metric_label: str
    metric_value: str


class InventoryHealthResponse(ApiModel):
    kpis: list[InventoryHealthKpi]
    health_buckets: list[InventoryHealthBucket]
    forecast_confidence: list[InventoryHealthBucket]
    top_cash_trapped: list[InventoryHealthSku]
    top_stockout_risk: list[InventoryHealthSku]
    insights: list[InventoryHealthInsight]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Reorder optimizer
# ---------------------------------------------------------------------------

class ReorderSuggestion(CostedProjection):
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
    order_cost: float = 0.0
    landed_extended_cost: float = 0.0
    landed_unit_cost: float = 0.0
    freight_share_pct: float = 0.0
    lead_time_days: int
    rationale: str


class ReorderFeedResponse(FinancialProjection):
    service_level: float
    suggestions: list[ReorderSuggestion]
    total_extended_cost: float
    vendor_totals: dict[str, float]
    known_vendor_totals: dict[str, float | None] = Field(default_factory=dict)


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


class BundleHealth(FinancialProjection):
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


class BundleOpportunity(ApiModel):
    id: str
    product_a_id: int
    product_a_name: str
    product_a_sku: str | None = None
    product_a_category: str | None = None
    product_b_id: int
    product_b_name: str
    product_b_sku: str | None = None
    product_b_category: str | None = None
    co_purchase_count: int
    support: float
    confidence_a_to_b: float
    confidence_b_to_a: float
    lift: float | None = None
    combined_revenue: float
    average_order_value_impact: float | None = None
    opportunity_type: str
    suggested_action: str
    explanation: str


class BundleOpportunitiesResponse(BundleHealthResponse):
    opportunities: list[BundleOpportunity]
    orders_analyzed: int


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

class PurchaseOrderLine(CostedProjection):
    sku_id: str
    name: str
    qty: int
    unit_cost: float
    extended_cost: float
    received_qty: int = 0


class PurchaseOrderReceipt(ApiModel):
    id: int
    sku_id: str
    ordered_qty: int
    received_qty: int
    ordered_unit_cost: float
    received_unit_cost: float
    expected_arrival_date: str
    received_at: datetime
    created_at: datetime


class PurchaseOrderDraft(FinancialProjection):
    po_id: str
    vendor: str
    created_at: datetime
    status: PurchaseOrderStatus
    source: Literal["recommended", "saved"] = "recommended"
    lines: list[PurchaseOrderLine]
    subtotal_cost: float = 0.0
    shipping_cost: float = 0.0
    total_cost: float
    expected_arrival_date: str
    rationale: str
    approved_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    receipts: list[PurchaseOrderReceipt] = Field(default_factory=list)


class PurchaseOrderDraftsResponse(FinancialProjection):
    drafts: list[PurchaseOrderDraft]
    total_capital_required: float


class BuyingCalendarLine(CostedProjection):
    sku_id: str
    name: str
    qty: int
    unit_cost: float
    extended_cost: float
    current_on_hand: int | None = None
    reorder_point: float | None = None
    daily_velocity: float | None = None
    lead_time_days: int | None = None


class BuyingCalendarEvent(FinancialProjection):
    event_id: str
    vendor: str
    source: Literal["recommended", "saved"]
    status: str
    order_by_date: str
    expected_arrival_date: str
    days_until_order: int
    lead_time_days: int
    line_count: int
    total_units: int
    estimated_cost: float
    urgency: Literal["due_now", "this_week", "future", "open"]
    rationale: str
    lines: list[BuyingCalendarLine]


class BuyingCalendarResponse(FinancialProjection):
    generated_at: datetime
    horizon_days: int
    events: list[BuyingCalendarEvent]
    total_estimated_cost: float
    due_now_count: int
    future_count: int
    saved_open_count: int


class SavePurchaseOrderRequest(ApiModel):
    draft: PurchaseOrderDraft


class ReceivePurchaseOrderLineRequest(ApiModel):
    sku_id: str
    received_qty: int = Field(ge=0)
    received_unit_cost: Optional[float] = Field(default=None, ge=0)


class ReceivePurchaseOrderRequest(ApiModel):
    lines: list[ReceivePurchaseOrderLineRequest]
    received_at: Optional[datetime] = None


class PurchaseOrderStatusResponse(ApiModel):
    po: PurchaseOrderDraft


class AuditLogEvent(ApiModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    summary: str
    metadata: dict
    created_at: datetime


class AuditLogResponse(ApiModel):
    events: list[AuditLogEvent]


class ReportSchedule(ApiModel):
    id: int
    report_type: str
    cadence: Literal["weekly", "monthly"]
    channel: Literal["email"]
    recipient_email: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ReportSchedulesResponse(ApiModel):
    schedules: list[ReportSchedule]


class UpsertReportScheduleRequest(ApiModel):
    report_type: Literal["actions", "stockout", "dead-stock", "reorder"]
    cadence: Literal["weekly", "monthly"] = "weekly"
    channel: Literal["email"] = "email"
    recipient_email: str = Field(min_length=3, max_length=320)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Dead stock / liquidation
# ---------------------------------------------------------------------------

class LiquidationSuggestion(CostedProjection):
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


class LiquidationResponse(FinancialProjection):
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
    scope: Literal["storewide", "custom"] = "storewide"
    match_mode: Literal["all", "any"] = "all"
    target_skus: list[str] = Field(default_factory=list)
    product_title_contains: str = ""
    categories: list[str] = Field(default_factory=list)
    suppliers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
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
    scope: Literal["storewide", "custom"] = "storewide"
    match_mode: Literal["all", "any"] = "all"
    target_skus: list[str] = Field(default_factory=list)
    product_title_contains: str = ""
    categories: list[str] = Field(default_factory=list)
    suppliers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
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

class DashboardKpi(KnownValueProjection):
    label: str
    unit: Literal["currency", "count", "percent", "days"]
    delta_pct: Optional[float] = None
    tone: Literal["positive", "negative", "neutral"] = "neutral"


class DashboardSeriesPoint(KnownValueProjection):
    label: str


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


# ---------------------------------------------------------------------------
# Dead-stock bundle pairings
# ---------------------------------------------------------------------------

class DeadStockPairing(FinancialProjection):
    """A fast mover paired with a dead-stock SKU to clear it as a bundle."""

    id: str
    anchor_product_name: str
    anchor_sku: str | None = None
    anchor_monthly_units: int
    anchor_price: float
    anchor_cost: float
    dead_product_name: str
    dead_sku: str | None = None
    dead_on_hand: int
    dead_days_since_last_sale: int
    dead_price: float
    dead_cost: float
    dead_capital_tied_up: float
    match_reason: str
    suggested_bundle_price: float
    bundle_unit_cost: float
    bundle_margin_pct: float
    estimated_monthly_bundles: int
    estimated_months_to_clear: float | None = None
    projected_cash_recovered: float
    explanation: str


class DeadStockPairingsResponse(FinancialProjection):
    pairings: list[DeadStockPairing]
    dead_stock_sku_count: int
    dead_stock_capital: float


# ---------------------------------------------------------------------------
# Open-to-buy cash plan
# ---------------------------------------------------------------------------

class CashPlanVendor(FinancialProjection):
    vendor: str
    order_now_cost: float
    deferrable_cost: float
    item_count: int
    max_lead_time_days: int


class CashPlanResponse(FinancialProjection):
    order_now_cost: float
    deferrable_cost: float
    total_cost: float
    order_now_items: int
    deferrable_items: int
    vendors: list[CashPlanVendor]
    explanation: str


# ---------------------------------------------------------------------------
# Inventory value history
# ---------------------------------------------------------------------------

class InventoryValuePoint(ApiModel):
    date: str
    total_units: int
    sku_count: int
    cost_value: float
    retail_value: float


class InventoryValueHistoryResponse(ApiModel):
    points: list[InventoryValuePoint]
    latest_cost_value: float
    latest_retail_value: float
    change_30d_pct: float | None = None
