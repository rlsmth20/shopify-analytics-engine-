from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.config.lead_time import MOCK_LEAD_TIME_CONFIG
from app.db.models import Inventory, OrderLineItem, Product, Shop
from app.db.session import session_scope
from app.mock_data import list_skus
from app.schemas import (
    ActionDataSource,
    DataQualityConfidence,
    InventoryAction,
    SkuDetail,
)
from app.services.inventory_engine import build_inventory_actions
from app.services.shop_settings import (
    ResolvedShopSettings,
    build_default_shop_settings,
    load_effective_shop_settings_map,
)


UNKNOWN_VENDOR = "Unknown Vendor"
UNKNOWN_CATEGORY = "uncategorized"
NEVER_SOLD_DAYS = 999
DEFAULT_COST_RATIO = Decimal("0.40")
MISSING_SKU_WARNING = "Missing Shopify SKU; using variant ID fallback."
MISSING_VENDOR_WARNING = "Missing vendor; vendor lead-time overrides unavailable."
MISSING_CATEGORY_WARNING = (
    "Missing category; category lead-time overrides unavailable."
)
MISSING_PRICE_WARNING = "Missing price; profitability estimates may be unreliable."


class ActionFeedUnavailableError(RuntimeError):
    """Raised when DB-backed actions are unavailable and mock fallback is disabled."""


@dataclass(frozen=True)
class InventoryActionFeed:
    actions: list[InventoryAction]
    source: ActionDataSource


@dataclass(frozen=True)
class PreparedSkuRecord:
    shop_id: int
    sku: SkuDetail
    data_quality_confidence: DataQualityConfidence
    data_quality_warnings: tuple[str, ...]


@dataclass(frozen=True)
class PersistedSkuSnapshot:
    records: list[PreparedSkuRecord]
    shop_count: int
    product_count: int
    inventory_row_count: int
    order_line_item_count: int
    settings_by_shop: dict[int, ResolvedShopSettings]


@dataclass(frozen=True)
class ActionDataHealthSummary:
    shops: int
    products: int
    inventory_rows: int
    order_line_items: int
    distinct_skus_with_usable_action_data: int


def build_inventory_action_feed() -> InventoryActionFeed:
    snapshot = load_persisted_sku_snapshot()
    if _should_use_db_actions(snapshot):
        return InventoryActionFeed(
            actions=_build_db_backed_actions(snapshot),
            source="db",
        )

    if not _is_mock_fallback_allowed(snapshot):
        raise ActionFeedUnavailableError(_build_unavailable_message(snapshot))

    return InventoryActionFeed(
        actions=_apply_action_explanations(build_inventory_actions(list_skus())),
        source="mock",
    )


def list_persisted_skus() -> list[SkuDetail]:
    snapshot = load_persisted_sku_snapshot()
    if snapshot is None:
        return []

    return [record.sku for record in snapshot.records]


def load_persisted_sku_snapshot() -> PersistedSkuSnapshot | None:
    now = datetime.now(timezone.utc)
    sales_30_day_cutoff = now - timedelta(days=30)
    sales_7_day_cutoff = now - timedelta(days=7)

    try:
        with session_scope() as session:
            shop_count = _load_shop_count(session)
            product_rows = session.execute(
                select(Product, Shop.id, Shop.shopify_domain)
                .join(Shop, Product.shop_id == Shop.id)
                .order_by(Product.id)
            ).all()
            inventory_row_count = _load_inventory_row_count(session)
            inventory_by_product = _load_inventory_by_product(session)
            sales_30_by_product = _load_sales_by_product(session, sales_30_day_cutoff)
            sales_7_by_product = _load_sales_by_product(session, sales_7_day_cutoff)
            last_sale_by_product = _load_last_sale_by_product(session)
            order_line_item_count = _load_order_line_item_count(session)
            settings_by_shop = load_effective_shop_settings_map(session)
    except SQLAlchemyError:
        return None

    records = [
        _build_prepared_sku_record(
            product=product,
            shop_id=shop_id,
            shopify_domain=shopify_domain,
            inventory=inventory_by_product.get(product.id, 0),
            last_30_day_sales=sales_30_by_product.get(product.id, 0),
            last_7_day_sales=sales_7_by_product.get(product.id, 0),
            last_sale_at=last_sale_by_product.get(product.id),
            now=now,
        )
        for product, shop_id, shopify_domain in product_rows
    ]

    return PersistedSkuSnapshot(
        records=records,
        shop_count=shop_count,
        product_count=len(product_rows),
        inventory_row_count=inventory_row_count,
        order_line_item_count=order_line_item_count,
        settings_by_shop=settings_by_shop,
    )


def build_action_data_health_summary() -> ActionDataHealthSummary:
    snapshot = load_persisted_sku_snapshot()
    if snapshot is None:
        return ActionDataHealthSummary(
            shops=0,
            products=0,
            inventory_rows=0,
            order_line_items=0,
            distinct_skus_with_usable_action_data=0,
        )

    return ActionDataHealthSummary(
        shops=snapshot.shop_count,
        products=snapshot.product_count,
        inventory_rows=snapshot.inventory_row_count,
        order_line_items=snapshot.order_line_item_count,
        distinct_skus_with_usable_action_data=len(snapshot.records),
    )


def _should_use_db_actions(snapshot: PersistedSkuSnapshot | None) -> bool:
    if snapshot is None:
        return False

    # Mock fallback is only for an empty or not-yet-ingested database.
    # Once a real shop catalog exists, sparse inventory or order history should
    # still produce DB-backed actions with zero/default derived values.
    return (
        snapshot.shop_count > 0
        and snapshot.product_count > 0
        and bool(snapshot.records)
    )


def _is_mock_fallback_allowed(snapshot: PersistedSkuSnapshot | None) -> bool:
    if snapshot is None:
        return MOCK_LEAD_TIME_CONFIG.allow_mock_fallback
    if not snapshot.settings_by_shop:
        return MOCK_LEAD_TIME_CONFIG.allow_mock_fallback

    return all(
        settings.allow_mock_fallback
        for settings in snapshot.settings_by_shop.values()
    )


def _build_unavailable_message(snapshot: PersistedSkuSnapshot | None) -> str:
    if snapshot is None:
        return (
            "Action data could not be loaded and mock fallback is disabled. "
            "Run a Shopify ingest or re-enable mock fallback in shop settings."
        )
    if snapshot.shop_count == 0:
        return (
            "No persisted Shopify shop data is available and mock fallback is disabled. "
            "Run a Shopify ingest or re-enable mock fallback in shop settings."
        )
    if snapshot.product_count == 0:
        return (
            "Mock fallback is disabled, but no persisted product catalog is available yet. "
            "Run a Shopify ingest or re-enable mock fallback in shop settings."
        )
    return (
        "DB-backed action data is not usable and mock fallback is disabled. "
        "Run a Shopify ingest or re-enable mock fallback in shop settings."
    )


def _build_db_backed_actions(snapshot: PersistedSkuSnapshot) -> list[InventoryAction]:
    records_by_shop: dict[int, list[PreparedSkuRecord]] = defaultdict(list)
    for record in snapshot.records:
        records_by_shop[record.shop_id].append(record)

    actions: list[InventoryAction] = []
    for shop_id, shop_records in records_by_shop.items():
        settings = snapshot.settings_by_shop.get(shop_id)
        if settings is None:
            settings = build_default_shop_settings()

        shop_actions = build_inventory_actions(
            [record.sku for record in shop_records],
            lead_time_config=settings.to_lead_time_config(),
        )
        quality_by_sku = {record.sku.sku_id: record for record in shop_records}
        actions.extend(
            _apply_action_explanations(
                _apply_data_quality(shop_actions, quality_by_sku)
            )
        )

    return sorted(actions, key=lambda action: action.priority_score, reverse=True)


def _load_shop_count(session) -> int:
    return int(session.scalar(select(func.count()).select_from(Shop)) or 0)


def _load_order_line_item_count(session) -> int:
    return int(session.scalar(select(func.count()).select_from(OrderLineItem)) or 0)


def _load_inventory_row_count(session) -> int:
    return int(session.scalar(select(func.count()).select_from(Inventory)) or 0)


def _load_inventory_by_product(session) -> dict[int, int]:
    rows = session.execute(
        select(Inventory.product_id, func.coalesce(func.sum(Inventory.quantity), 0))
        .group_by(Inventory.product_id)
    ).all()
    return {product_id: int(quantity) for product_id, quantity in rows}


def _load_sales_by_product(session, created_at_min: datetime) -> dict[int, int]:
    rows = session.execute(
        select(
            OrderLineItem.product_id,
            func.coalesce(func.sum(OrderLineItem.quantity), 0),
        )
        .where(OrderLineItem.created_at >= created_at_min)
        .group_by(OrderLineItem.product_id)
    ).all()
    return {product_id: int(quantity) for product_id, quantity in rows}


def _load_last_sale_by_product(session) -> dict[int, datetime]:
    rows = session.execute(
        select(OrderLineItem.product_id, func.max(OrderLineItem.created_at))
        .group_by(OrderLineItem.product_id)
    ).all()
    return {
        product_id: last_sale_at
        for product_id, last_sale_at in rows
        if last_sale_at is not None
    }


def _build_prepared_sku_record(
    *,
    product: Product,
    shop_id: int,
    shopify_domain: str,
    inventory: int,
    last_30_day_sales: int,
    last_7_day_sales: int,
    last_sale_at: datetime | None,
    now: datetime,
) -> PreparedSkuRecord:
    warnings = _build_data_quality_warnings(product)
    return PreparedSkuRecord(
        shop_id=shop_id,
        sku=SkuDetail(
            sku_id=_build_sku_id(product, shopify_domain),
            name=_build_product_name(product),
            vendor=product.vendor or UNKNOWN_VENDOR,
            category=product.category or UNKNOWN_CATEGORY,
            price=float(product.price),
            cost=_resolve_cost(product),
            inventory=inventory,
            last_30_day_sales=last_30_day_sales,
            last_7_day_sales=last_7_day_sales,
            days_since_last_sale=_calculate_days_since_last_sale(last_sale_at, now),
            sku_lead_time_days=product.sku_lead_time_days,
        ),
        data_quality_confidence=_determine_data_quality_confidence(warnings),
        data_quality_warnings=warnings,
    )


def _build_sku_id(product: Product, shopify_domain: str) -> str:
    base_identifier = product.sku or product.shopify_variant_id
    return f"{shopify_domain}:{base_identifier}"


def _build_product_name(product: Product) -> str:
    if product.variant_name:
        return f"{product.name} / {product.variant_name}"
    return product.name


def _resolve_cost(product: Product) -> float:
    if product.cost is not None:
        return float(product.cost)

    # Persisted ingest does not store landed cost yet, so use a stable fallback.
    return float((product.price * DEFAULT_COST_RATIO).quantize(Decimal("0.01")))


def _calculate_days_since_last_sale(
    last_sale_at: datetime | None, now: datetime
) -> int:
    if last_sale_at is None:
        return NEVER_SOLD_DAYS

    return max((now - last_sale_at).days, 0)


def _build_data_quality_warnings(product: Product) -> tuple[str, ...]:
    warnings: list[str] = []
    if not product.sku:
        warnings.append(MISSING_SKU_WARNING)
    if not product.vendor:
        warnings.append(MISSING_VENDOR_WARNING)
    if not product.category:
        warnings.append(MISSING_CATEGORY_WARNING)
    if product.price <= 0:
        warnings.append(MISSING_PRICE_WARNING)

    return tuple(warnings)


def _determine_data_quality_confidence(
    warnings: tuple[str, ...],
) -> DataQualityConfidence:
    if not warnings:
        return "high"
    if MISSING_PRICE_WARNING in warnings or len(warnings) >= 2:
        return "low"
    return "medium"


def _apply_data_quality(
    actions: list[InventoryAction],
    quality_by_sku: dict[str, PreparedSkuRecord],
) -> list[InventoryAction]:
    enriched_actions: list[InventoryAction] = []
    for action in actions:
        quality = quality_by_sku.get(action.sku_id)
        if quality is None:
            enriched_actions.append(action)
            continue

        enriched_actions.append(
            action.model_copy(
                update={
                    "data_quality_confidence": quality.data_quality_confidence,
                    "data_quality_warnings": list(quality.data_quality_warnings),
                }
            )
        )

    return enriched_actions


def _apply_action_explanations(
    actions: list[InventoryAction],
) -> list[InventoryAction]:
    return [
        action.model_copy(update={"explanation": _build_action_explanation(action)})
        for action in actions
    ]


def _build_action_explanation(action: InventoryAction) -> str:
    if action.status == "urgent":
        return (
            f"Stockout in {action.days_until_stockout:.1f} days; "
            f"estimated profit at risk {_format_currency(action.estimated_profit_impact)}."
        )

    if action.status == "optimize":
        return (
            f"Cash tied up {_format_currency(action.cash_tied_up)}; "
            f"inventory cover is far above the {action.target_coverage_days}-day target."
        )

    return (
        f"No recent sales; capital tied up {_format_currency(action.cash_tied_up)} "
        "in stale inventory."
    )


def _format_currency(value: float) -> str:
    return f"${value:,.0f}"
