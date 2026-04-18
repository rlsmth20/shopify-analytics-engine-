from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ShopifyProductRecord:
    shop_id: int
    shopify_product_id: str
    shopify_variant_id: str
    sku: str | None
    name: str
    variant_name: str | None
    vendor: str | None
    category: str | None
    price: Decimal


@dataclass(frozen=True)
class ShopifyInventoryRecord:
    shop_id: int
    shopify_variant_id: str
    shopify_location_id: str
    quantity: int
    updated_at: datetime


@dataclass(frozen=True)
class ShopifyOrderLineItemRecord:
    shop_id: int
    shopify_order_id: str
    shopify_variant_id: str
    sku: str | None
    quantity: int
    price: Decimal
    created_at: datetime


def build_inventory_item_to_variant_map(
    products_payload: list[dict[str, Any]],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for product in products_payload:
        for variant in product.get("variants", []):
            inventory_item_id = variant.get("inventory_item_id")
            variant_id = variant.get("id")
            if inventory_item_id is None or variant_id is None:
                continue

            mapping[str(inventory_item_id)] = str(variant_id)

    return mapping


def map_products(
    shop_id: int, products_payload: list[dict[str, Any]]
) -> list[ShopifyProductRecord]:
    records: list[ShopifyProductRecord] = []
    for product in products_payload:
        product_id = product.get("id")
        if product_id is None:
            continue

        product_name = _clean_string(product.get("title")) or "Untitled Product"
        vendor = _clean_string(product.get("vendor"))
        category = _normalize_category(product)

        for variant in product.get("variants", []):
            variant_id = variant.get("id")
            if variant_id is None:
                continue

            variant_name = _normalize_variant_name(variant.get("title"))
            records.append(
                ShopifyProductRecord(
                    shop_id=shop_id,
                    shopify_product_id=str(product_id),
                    shopify_variant_id=str(variant_id),
                    sku=_clean_string(variant.get("sku")),
                    name=product_name,
                    variant_name=variant_name,
                    vendor=vendor,
                    category=category,
                    price=_to_decimal(variant.get("price")),
                )
            )

    return records


def map_inventory_levels(
    shop_id: int,
    inventory_levels_payload: list[dict[str, Any]],
    inventory_item_to_variant_map: dict[str, str],
) -> list[ShopifyInventoryRecord]:
    records: list[ShopifyInventoryRecord] = []
    for inventory_level in inventory_levels_payload:
        inventory_item_id = inventory_level.get("inventory_item_id")
        location_id = inventory_level.get("location_id")
        if inventory_item_id is None or location_id is None:
            continue

        variant_id = inventory_item_to_variant_map.get(str(inventory_item_id))
        if variant_id is None:
            continue

        quantity = inventory_level.get("available", inventory_level.get("quantity", 0))
        updated_at = _to_datetime(
            inventory_level.get("updated_at"), fallback=datetime.now(timezone.utc)
        )
        records.append(
            ShopifyInventoryRecord(
                shop_id=shop_id,
                shopify_variant_id=variant_id,
                shopify_location_id=str(location_id),
                quantity=int(quantity),
                updated_at=updated_at,
            )
        )

    return records


def map_order_line_items(
    shop_id: int, orders_payload: list[dict[str, Any]]
) -> list[ShopifyOrderLineItemRecord]:
    records: list[ShopifyOrderLineItemRecord] = []
    for order in orders_payload:
        if order.get("cancelled_at"):
            continue

        order_id = order.get("id")
        created_at = _to_datetime(
            order.get("created_at"), fallback=datetime.now(timezone.utc)
        )
        if order_id is None:
            continue

        for line_item in order.get("line_items", []):
            variant_id = line_item.get("variant_id")
            if variant_id is None:
                continue

            records.append(
                ShopifyOrderLineItemRecord(
                    shop_id=shop_id,
                    shopify_order_id=str(order_id),
                    shopify_variant_id=str(variant_id),
                    sku=_clean_string(line_item.get("sku")),
                    quantity=int(line_item.get("quantity", 0)),
                    price=_to_decimal(line_item.get("price")),
                    created_at=created_at,
                )
            )

    return records


def _normalize_category(product_payload: dict[str, Any]) -> str | None:
    product_type = _clean_string(product_payload.get("product_type"))
    if product_type:
        return product_type

    category = product_payload.get("category")
    if isinstance(category, dict):
        return _clean_string(category.get("name"))

    return _clean_string(category)


def _normalize_variant_name(value: Any) -> str | None:
    variant_name = _clean_string(value)
    if variant_name in {None, "", "Default Title"}:
        return None

    return variant_name


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None


def _to_decimal(value: Any) -> Decimal:
    if value in {None, ""}:
        return Decimal("0.00")

    return Decimal(str(value))


def _to_datetime(value: Any, *, fallback: datetime) -> datetime:
    if not value:
        return fallback

    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
