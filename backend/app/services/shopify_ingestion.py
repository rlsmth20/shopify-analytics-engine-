from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Inventory, OrderLineItem, Product, Shop, ShopifySyncRun
from app.db.session import session_scope
from app.integrations.shopify_client import (
    ShopifyClient,
    ShopifyClientConfig,
)
from app.integrations.shopify_mapper import (
    ShopifyProductRecord,
    build_inventory_item_to_variant_map,
    map_inventory_levels,
    map_order_line_items,
    map_products,
)
from app.services.shop_settings import normalize_shopify_domain


DEFAULT_ORDER_LOOKBACK_DAYS = 365
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_SUCCEEDED = "succeeded"
SYNC_STATUS_FAILED = "failed"


class ShopifyIngestionInputError(ValueError):
    """Raised when manual Shopify ingestion input is invalid."""


@dataclass(frozen=True)
class IngestionResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ProcessedCounts:
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ShopifyIngestionSummary:
    shops: ProcessedCounts
    products: ProcessedCounts
    inventory_rows: ProcessedCounts
    order_line_items: ProcessedCounts


@dataclass(frozen=True)
class LatestShopifySyncStatus:
    shop_id: int | None
    shopify_domain: str
    latest_run: ShopifySyncRun | None


class ShopifyIngestionService:
    def __init__(self, client: ShopifyClient):
        self.client = client

    def ensure_shop(self) -> int:
        shop_id, _ = self.ensure_shop_with_result()
        return shop_id

    def ensure_shop_with_result(self) -> tuple[int, ProcessedCounts]:
        with session_scope() as session:
            shop = session.scalar(
                select(Shop).where(Shop.shopify_domain == self.client.shopify_domain)
            )
            if shop is None:
                shop = Shop(shopify_domain=self.client.shopify_domain)
                session.add(shop)
                session.flush()
                return shop.id, ProcessedCounts(processed=1, inserted=1)

            return shop.id, ProcessedCounts(processed=1, updated=1)

    def sync_products(self, *, limit: int = 250) -> IngestionResult:
        shop_id = self.ensure_shop()
        products_payload = self.client.get_products(limit=limit)
        return self.ingest_products(shop_id, products_payload)

    def sync_inventory(
        self,
        *,
        inventory_item_to_variant_map: dict[str, str] | None = None,
        location_ids: list[str] | None = None,
        limit: int = 250,
    ) -> IngestionResult:
        shop_id = self.ensure_shop()
        mapping = inventory_item_to_variant_map
        if mapping is None:
            products_payload = self.client.get_products(limit=limit)
            mapping = build_inventory_item_to_variant_map(products_payload)

        inventory_levels_payload = self.client.get_inventory_levels(
            inventory_item_ids=list(mapping.keys()),
            location_ids=location_ids,
            limit=limit,
        )
        return self.ingest_inventory_levels(shop_id, inventory_levels_payload, mapping)

    def sync_orders(
        self,
        *,
        created_at_min: datetime | None = None,
        limit: int = 250,
        status: str = "any",
    ) -> IngestionResult:
        shop_id = self.ensure_shop()
        orders_payload = self.client.get_orders(
            created_at_min=created_at_min,
            limit=limit,
            status=status,
        )
        return self.ingest_orders(shop_id, orders_payload)

    def run_initial_sync(
        self,
        *,
        created_at_min: datetime | None = None,
        product_limit: int = 250,
        order_limit: int = 250,
    ) -> ShopifyIngestionSummary:
        shop_id, shop_result = self.ensure_shop_with_result()
        sync_run_id = self.create_sync_run(shop_id)

        try:
            products_payload = self.client.get_products(limit=product_limit)
            product_result = self.ingest_products(shop_id, products_payload)

            inventory_mapping = build_inventory_item_to_variant_map(products_payload)
            inventory_payload = self.client.get_inventory_levels(
                inventory_item_ids=list(inventory_mapping.keys()),
                limit=product_limit,
            )
            inventory_result = self.ingest_inventory_levels(
                shop_id, inventory_payload, inventory_mapping
            )

            order_payload = self.client.get_orders(
                created_at_min=created_at_min,
                limit=order_limit,
                status="any",
            )
            order_result = self.ingest_orders(shop_id, order_payload)
        except Exception as exc:
            self.mark_sync_run_failed(sync_run_id, str(exc))
            raise

        summary = ShopifyIngestionSummary(
            shops=shop_result,
            products=_to_processed_counts(product_result),
            inventory_rows=_to_processed_counts(inventory_result),
            order_line_items=_to_processed_counts(order_result),
        )
        self.mark_sync_run_succeeded(sync_run_id, summary)
        return summary

    def create_sync_run(self, shop_id: int) -> int:
        with session_scope() as session:
            sync_run = ShopifySyncRun(
                shop_id=shop_id,
                status=SYNC_STATUS_RUNNING,
                error_message=None,
                products_count=0,
                inventory_rows_count=0,
                order_line_items_count=0,
            )
            session.add(sync_run)
            session.flush()
            return sync_run.id

    def mark_sync_run_succeeded(
        self,
        sync_run_id: int,
        summary: ShopifyIngestionSummary,
    ) -> None:
        with session_scope() as session:
            sync_run = session.get(ShopifySyncRun, sync_run_id)
            if sync_run is None:
                return

            sync_run.status = SYNC_STATUS_SUCCEEDED
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.error_message = None
            sync_run.products_count = summary.products.processed
            sync_run.inventory_rows_count = summary.inventory_rows.processed
            sync_run.order_line_items_count = summary.order_line_items.processed

    def mark_sync_run_failed(self, sync_run_id: int, error_message: str) -> None:
        with session_scope() as session:
            sync_run = session.get(ShopifySyncRun, sync_run_id)
            if sync_run is None:
                return

            sync_run.status = SYNC_STATUS_FAILED
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.error_message = error_message[:1000]

    def ingest_products(
        self, shop_id: int, products_payload: list[dict[str, Any]]
    ) -> IngestionResult:
        records = map_products(shop_id, products_payload)
        if not records:
            return IngestionResult(skipped=0)

        variant_ids = [record.shopify_variant_id for record in records]
        inserted = 0
        updated = 0

        with session_scope() as session:
            existing_products = {
                product.shopify_variant_id: product
                for product in session.scalars(
                    select(Product).where(
                        Product.shop_id == shop_id,
                        Product.shopify_variant_id.in_(variant_ids),
                    )
                )
            }

            for record in records:
                product = existing_products.get(record.shopify_variant_id)
                if product is None:
                    session.add(self._build_product_model(record))
                    inserted += 1
                    continue

                self._update_product_model(product, record)
                updated += 1

        return IngestionResult(inserted=inserted, updated=updated)

    def ingest_inventory_levels(
        self,
        shop_id: int,
        inventory_levels_payload: list[dict[str, Any]],
        inventory_item_to_variant_map: dict[str, str],
    ) -> IngestionResult:
        records = map_inventory_levels(
            shop_id, inventory_levels_payload, inventory_item_to_variant_map
        )
        if not records:
            return IngestionResult(skipped=0)

        variant_ids = [record.shopify_variant_id for record in records]
        inserted = 0
        updated = 0
        skipped = 0

        with session_scope() as session:
            product_lookup = {
                product.shopify_variant_id: product
                for product in session.scalars(
                    select(Product).where(
                        Product.shop_id == shop_id,
                        Product.shopify_variant_id.in_(variant_ids),
                    )
                )
            }

            existing_inventory = {
                (row.product_id, row.shopify_location_id): row
                for row in session.scalars(
                    select(Inventory).where(Inventory.shop_id == shop_id)
                )
            }

            for record in records:
                product = product_lookup.get(record.shopify_variant_id)
                if product is None:
                    skipped += 1
                    continue

                inventory_row = existing_inventory.get(
                    (product.id, record.shopify_location_id)
                )
                if inventory_row is None:
                    session.add(
                        Inventory(
                            shop_id=shop_id,
                            product_id=product.id,
                            shopify_location_id=record.shopify_location_id,
                            quantity=record.quantity,
                            updated_at=record.updated_at,
                        )
                    )
                    inserted += 1
                    continue

                inventory_row.quantity = record.quantity
                inventory_row.updated_at = record.updated_at
                updated += 1

        return IngestionResult(inserted=inserted, updated=updated, skipped=skipped)

    def ingest_orders(
        self, shop_id: int, orders_payload: list[dict[str, Any]]
    ) -> IngestionResult:
        records = map_order_line_items(shop_id, orders_payload)
        if not records:
            return IngestionResult(skipped=0)

        variant_ids = [record.shopify_variant_id for record in records]
        inserted = 0
        skipped = 0

        with session_scope() as session:
            product_lookup = {
                product.shopify_variant_id: product
                for product in session.scalars(
                    select(Product).where(
                        Product.shop_id == shop_id,
                        Product.shopify_variant_id.in_(variant_ids),
                    )
                )
            }

            existing_rows = {
                (
                    row.shopify_order_id,
                    row.product_id,
                    row.sku,
                    row.quantity,
                    row.price,
                    row.created_at,
                )
                for row in session.scalars(
                    select(OrderLineItem).where(
                        OrderLineItem.shop_id == shop_id,
                        OrderLineItem.shopify_order_id.in_(
                            [record.shopify_order_id for record in records]
                        ),
                    )
                )
            }

            for record in records:
                product = product_lookup.get(record.shopify_variant_id)
                if product is None:
                    skipped += 1
                    continue

                dedupe_key = (
                    record.shopify_order_id,
                    product.id,
                    record.sku,
                    record.quantity,
                    record.price,
                    record.created_at,
                )
                if dedupe_key in existing_rows:
                    skipped += 1
                    continue

                session.add(
                    OrderLineItem(
                        shop_id=shop_id,
                        shopify_order_id=record.shopify_order_id,
                        product_id=product.id,
                        sku=record.sku,
                        quantity=record.quantity,
                        price=record.price,
                        created_at=record.created_at,
                    )
                )
                inserted += 1
                existing_rows.add(dedupe_key)

        return IngestionResult(inserted=inserted, skipped=skipped)

    def _build_product_model(self, record: ShopifyProductRecord) -> Product:
        return Product(
            shop_id=record.shop_id,
            shopify_product_id=record.shopify_product_id,
            shopify_variant_id=record.shopify_variant_id,
            sku=record.sku,
            name=record.name,
            variant_name=record.variant_name,
            vendor=record.vendor,
            category=record.category,
            price=record.price,
        )

    def _update_product_model(self, product: Product, record: ShopifyProductRecord) -> None:
        product.shopify_product_id = record.shopify_product_id
        product.sku = record.sku
        product.name = record.name
        product.variant_name = record.variant_name
        product.vendor = record.vendor
        product.category = record.category
        product.price = record.price


def get_latest_shopify_sync_status(
    shopify_domain: str,
) -> LatestShopifySyncStatus:
    normalized_domain = _normalize_shopify_domain(shopify_domain)

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            return LatestShopifySyncStatus(
                shop_id=None,
                shopify_domain=normalized_domain,
                latest_run=None,
            )

        latest_run = session.scalar(
            select(ShopifySyncRun)
            .where(ShopifySyncRun.shop_id == shop.id)
            .order_by(ShopifySyncRun.started_at.desc(), ShopifySyncRun.id.desc())
            .limit(1)
        )
        return LatestShopifySyncStatus(
            shop_id=shop.id,
            shopify_domain=shop.shopify_domain,
            latest_run=latest_run,
        )


def run_manual_shopify_ingestion(
    *,
    shopify_domain: str,
    access_token: str,
    order_lookback_days: int = DEFAULT_ORDER_LOOKBACK_DAYS,
) -> ShopifyIngestionSummary:
    if order_lookback_days < 1:
        raise ShopifyIngestionInputError("order_lookback_days must be at least 1.")

    client = ShopifyClient(
        ShopifyClientConfig(
            shopify_domain=_normalize_shopify_domain(shopify_domain),
            access_token=_normalize_access_token(access_token),
        )
    )
    service = ShopifyIngestionService(client)
    created_at_min = datetime.now(timezone.utc) - timedelta(days=order_lookback_days)
    return service.run_initial_sync(created_at_min=created_at_min)


def _to_processed_counts(result: IngestionResult) -> ProcessedCounts:
    return ProcessedCounts(
        processed=result.inserted + result.updated + result.skipped,
        inserted=result.inserted,
        updated=result.updated,
        skipped=result.skipped,
    )


def _normalize_shopify_domain(shopify_domain: str) -> str:
    try:
        return normalize_shopify_domain(shopify_domain)
    except ValueError as exc:
        raise ShopifyIngestionInputError(str(exc)) from exc


def _normalize_access_token(access_token: str) -> str:
    token = access_token.strip()
    if not token:
        raise ShopifyIngestionInputError("access_token must not be empty.")
    return token
