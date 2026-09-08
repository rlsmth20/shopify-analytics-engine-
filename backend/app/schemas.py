from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


Classification = Literal["urgent", "optimize", "dead", "healthy"]
ActionableStatus = Literal["urgent", "optimize", "dead"]
UrgencyLevel = Literal["critical", "high", "medium"]
LeadTimeSource = Literal["sku_override", "vendor", "category", "global_default"]
ActionDataSource = Literal["db", "mock"]
DataQualityConfidence = Literal["high", "medium", "low"]
CostSource = Literal["recorded", "estimated_from_price", "missing"]
ShopifySyncStatus = Literal["running", "succeeded", "failed", "partial"]
AiChatRole = Literal["user", "assistant"]
AiChatMode = Literal["ai", "local"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkuIdentityProjection(ApiModel):
    product_id: int | None = None
    identity_ambiguous: bool = False
    identity_warning: str | None = None


class SkuIdentityIssue(ApiModel):
    product_id: int
    sku_id: str
    name: str
    current_on_hand: int
    message: str


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: str


class ProcessedCountsResponse(ApiModel):
    processed: int
    inserted: int
    updated: int
    skipped: int


class ShopifyIngestionRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    access_token: str = Field(min_length=1)


class ShopifyIngestionResponse(ApiModel):
    shops: ProcessedCountsResponse
    products: ProcessedCountsResponse
    inventory_rows: ProcessedCountsResponse
    order_line_items: ProcessedCountsResponse


class ShopifySyncRunResponse(ApiModel):
    id: int
    shop_id: int
    started_at: datetime
    finished_at: datetime | None = None
    status: ShopifySyncStatus
    error_message: str | None = None
    products_count: int
    inventory_rows_count: int
    order_line_items_count: int


class LatestShopifySyncStatusResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    latest_run: ShopifySyncRunResponse | None = None


class ShopSettingsResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    global_default_lead_time_days: int
    global_safety_buffer_days: int
    allow_mock_fallback: bool
    is_persisted: bool


class UpdateShopSettingsRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    global_default_lead_time_days: int = Field(ge=1)
    global_safety_buffer_days: int = Field(ge=0)
    allow_mock_fallback: bool


class VendorLeadTimeEntry(ApiModel):
    vendor: str = Field(min_length=1)
    lead_time_days: int = Field(ge=1)


class CategoryLeadTimeEntry(ApiModel):
    category: str = Field(min_length=1)
    lead_time_days: int = Field(ge=1)


class SkuLeadTimeEntry(ApiModel):
    sku_id: str = Field(min_length=1)
    lead_time_days: int | None = Field(default=None, ge=1)


class VendorLeadTimeSettingsResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    items: list[VendorLeadTimeEntry]


class CategoryLeadTimeSettingsResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    items: list[CategoryLeadTimeEntry]


class SkuLeadTimeSettingsResponse(ApiModel):
    warnings: list[str] = Field(default_factory=list)
    shop_id: int | None = None
    shopify_domain: str
    items: list[SkuLeadTimeEntry]


class UpdateVendorLeadTimesRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    items: list[VendorLeadTimeEntry] = Field(default_factory=list)


class UpdateCategoryLeadTimesRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    items: list[CategoryLeadTimeEntry] = Field(default_factory=list)


class UpdateSkuLeadTimesRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    items: list[SkuLeadTimeEntry] = Field(default_factory=list)


class BaseInventoryAction(SkuIdentityProjection):
    planning_values_known: bool = True
    planning_values: dict[str, float | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def canonical_planning_values(self):
        self.planning_values_known = self.planning_values_known and not self.identity_ambiguous
        fields = ("safety_stock_units", "target_inventory_units", "reorder_point_units",
                  "days_of_inventory", "lead_time_days_used", "target_coverage_days")
        self.planning_values = {key: getattr(self, key) if self.planning_values_known else None for key in fields}
        return self

    sku_id: str = Field(description="Internal SKU identifier.")
    name: str
    status: ActionableStatus
    recommended_action: str
    explanation: str | None = None
    current_on_hand: int
    daily_velocity: float
    safety_stock_units: int
    target_inventory_units: int
    reorder_point_units: int
    days_of_inventory: float
    lead_time_days_used: int
    safety_buffer_days: int
    lead_time_source: LeadTimeSource
    target_coverage_days: int
    priority_score: float
    sales_history_complete: bool = True
    data_quality_confidence: DataQualityConfidence = "high"
    data_quality_warnings: list[str] = Field(default_factory=list)
    cost_source: CostSource = "recorded"
    financial_values_known: bool = True
    financial_values: dict[str, float | None] = Field(default_factory=dict)


class UrgentInventoryAction(BaseInventoryAction):
    status: Literal["urgent"]
    urgency_level: UrgencyLevel
    days_until_stockout: float
    estimated_profit_impact: float


class OptimizeInventoryAction(BaseInventoryAction):
    status: Literal["optimize"]
    excess_units: int
    cash_tied_up: float


class DeadInventoryAction(BaseInventoryAction):
    status: Literal["dead"]
    excess_units: int
    cash_tied_up: float


InventoryAction: TypeAlias = Annotated[
    UrgentInventoryAction | OptimizeInventoryAction | DeadInventoryAction,
    Field(discriminator="status"),
]


class ActionFeedResponse(ApiModel):
    identity_issues: list[SkuIdentityIssue] = Field(default_factory=list)
    data_source: ActionDataSource
    actions: list[InventoryAction]


class ActionDataHealthSummaryResponse(ApiModel):
    shops: int
    products: int
    inventory_rows: int
    order_line_items: int
    distinct_skus_with_usable_action_data: int


class AiChatMessage(ApiModel):
    role: AiChatRole
    content: str = Field(min_length=1, max_length=2000)


class AiChatRequest(ApiModel):
    messages: list[AiChatMessage] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def user_question_required(self):
        if self.messages[-1].role != "user" or not self.messages[-1].content.strip():
            raise ValueError("End the conversation with a nonempty user question.")
        return self


class AiChatRelatedLink(ApiModel):
    label: str
    href: str


class AiChatResponse(ApiModel):
    answer: str
    mode: AiChatMode
    data_source: ActionDataSource
    context_summary: str
    related_links: list[AiChatRelatedLink] = Field(default_factory=list)
    model: str | None = None
    fallback_reason: str | None = None


class SkuDetail(SkuIdentityProjection):
    sku_id: str = Field(description="Internal SKU identifier.")
    name: str
    vendor: str
    category: str
    price: float
    cost: float
    cost_source: CostSource = "recorded"
    inventory: int
    last_30_day_sales: int
    last_7_day_sales: int
    days_since_last_sale: int
    sku_lead_time_days: int | None = None
    observed_history_days: int | None = Field(default=None, ge=0,
        description="Days since the first recorded sale; zero means no completed observed history, null means legacy provenance unavailable.")
    sales_history_complete: bool = Field(
        default=True,
        description="Whether available order history supports stale/excess-stock conclusions; legacy inputs default to known history.",
    )
    sales_history_warnings: list[str] = Field(default_factory=list)
