from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


Classification = Literal["urgent", "optimize", "dead", "healthy"]
ActionableStatus = Literal["urgent", "optimize", "dead"]
UrgencyLevel = Literal["critical", "high", "medium"]
LeadTimeSource = Literal["sku_override", "vendor", "category", "global_default"]
ActionDataSource = Literal["db", "mock"]
DataQualityConfidence = Literal["high", "medium", "low"]
ShopifySyncStatus = Literal["running", "succeeded", "failed"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class VendorLeadTimeSettingsResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    items: list[VendorLeadTimeEntry]


class CategoryLeadTimeSettingsResponse(ApiModel):
    shop_id: int | None = None
    shopify_domain: str
    items: list[CategoryLeadTimeEntry]


class UpdateVendorLeadTimesRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    items: list[VendorLeadTimeEntry] = Field(default_factory=list)


class UpdateCategoryLeadTimesRequest(ApiModel):
    shopify_domain: str = Field(min_length=1)
    items: list[CategoryLeadTimeEntry] = Field(default_factory=list)


class BaseInventoryAction(ApiModel):
    sku_id: str = Field(description="Internal SKU identifier.")
    name: str
    status: ActionableStatus
    recommended_action: str
    explanation: str | None = None
    days_of_inventory: float
    lead_time_days_used: int
    safety_buffer_days: int
    lead_time_source: LeadTimeSource
    target_coverage_days: int
    priority_score: float
    data_quality_confidence: DataQualityConfidence = "high"
    data_quality_warnings: list[str] = Field(default_factory=list)


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
    data_source: ActionDataSource
    actions: list[InventoryAction]


class ActionDataHealthSummaryResponse(ApiModel):
    shops: int
    products: int
    inventory_rows: int
    order_line_items: int
    distinct_skus_with_usable_action_data: int


class SkuDetail(ApiModel):
    sku_id: str = Field(description="Internal SKU identifier.")
    name: str
    vendor: str
    category: str
    price: float
    cost: float
    inventory: int
    last_30_day_sales: int
    last_7_day_sales: int
    days_since_last_sale: int
    sku_lead_time_days: int | None = None
