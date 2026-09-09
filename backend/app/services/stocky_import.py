"""Stocky CSV importer."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from app.db.models import Inventory, Product, Shop, ShopifyConnection
from app.db.session import session_scope
from app.services.shop_settings import ShopSettingsInputError, normalize_shopify_domain
from app.services.shopify_oauth import shopify_connection_lock


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "variantsku", "skucode", "barcode"),
    "name": ("product", "productname", "title", "name", "producttitle"),
    "variant": ("variant", "variantname", "varianttitle", "option1value"),
    "vendor": ("vendor", "supplier", "brand"),
    "category": ("type", "category", "producttype", "productcategory"),
    "cost": ("cost", "unitcost", "supplyprice", "wholesale"),
    "price": ("price", "retailprice", "sellprice", "listprice"),
    "inventory": ("inventory", "onhand", "available", "stockonhand", "qty", "quantity"),
    "lead_time_days": ("leadtime", "leadtimedays", "leaddays"),
}


class StockyImportError(ValueError):
    """Raised when Stocky CSV input is invalid."""


@dataclass
class StockyImportResult:
    shop_id: int
    shopify_domain: str
    products_processed: int = 0
    products_inserted: int = 0
    products_updated: int = 0
    inventory_rows_inserted: int = 0
    rows_skipped: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    inventory_source: str = "csv"
    inventory_rows_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def _norm_key(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _resolve_columns(header: list[str]) -> dict[str, str]:
    normalized = {_norm_key(h): h for h in header}
    resolved: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[canonical] = normalized[alias]
                break
    return resolved


def _to_decimal(raw: Any, default: str = "0") -> Decimal:
    if raw is None:
        return Decimal(default)
    s = str(raw).strip()
    if not s:
        return Decimal(default)
    s = s.replace("$", "").replace(",", "").replace("£", "").replace("€", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _to_int(raw: Any, default: int = 0) -> int:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        value = Decimal(s.replace(",", ""))
        if not value.is_finite() or value != value.to_integral_value() or not -2_147_483_648 <= value <= 2_147_483_647:
            return default
        return int(value)
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return default


def _optional_inventory(raw: str) -> int | None:
    if not raw:
        return None
    try:
        value = Decimal(raw.replace(",", ""))
        if not value.is_finite() or value != value.to_integral_value() or not -2_147_483_648 <= value <= 2_147_483_647:
            raise ValueError()
        return int(value)
    except (InvalidOperation, ValueError, OverflowError):
        raise ValueError("inventory must be a finite whole number within the supported stock range") from None


def _optional_price(raw: str) -> Decimal | None:
    if not raw:
        return None
    value = _to_decimal(raw, default="NaN")
    if (not value.is_finite() or not 0 <= value <= Decimal("99999999.99")
            or value != value.quantize(Decimal("0.01"))):
        raise ValueError("price must be a finite non-negative amount with at most two decimal places")
    return value


def import_stocky_products_csv(
    *,
    shopify_domain: str,
    csv_bytes: bytes,
    location_label: str = "stocky-import",
) -> StockyImportResult:
    try:
        domain = normalize_shopify_domain(shopify_domain)
    except ShopSettingsInputError as exc:
        # Pre-existing workspaces can hold placeholder domains that fail
        # normalization; surface a 400 instead of a 500.
        raise StockyImportError(
            "Your workspace's shop domain could not be validated. "
            "Connect your Shopify store on the Store Sync page, then retry the import."
        ) from exc
    if not domain:
        raise StockyImportError("Shopify domain is required.")

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = csv_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise StockyImportError(f"Could not decode CSV file: {exc}") from exc

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise StockyImportError("CSV file is empty.") from None

    cols = _resolve_columns(header)
    if "sku" not in cols and "name" not in cols:
        raise StockyImportError(
            "CSV must include either an SKU or product name column."
        )

    name_to_index = {h: i for i, h in enumerate(header)}
    idx = {canonical: name_to_index[h] for canonical, h in cols.items()}

    result = StockyImportResult(shop_id=0, shopify_domain=domain)

    with session_scope() as session, shopify_connection_lock(session, domain):
        shop = session.scalar(select(Shop).where(Shop.shopify_domain == domain))
        if shop is None:
            shop = Shop(shopify_domain=domain)
            session.add(shop)
            session.flush()
        result.shop_id = shop.id

        existing_by_sku: dict[str, list[Product]] = defaultdict(list)
        products = session.scalars(select(Product).where(Product.shop_id == shop.id)).all()
        existing_by_variant = {p.shopify_variant_id: p for p in products}
        for p in products:
            if p.sku:
                existing_by_sku[p.sku].append(p)
        connected = session.scalar(select(ShopifyConnection.id).where(
            ShopifyConnection.shop_id == shop.id, ShopifyConnection.uninstalled_at.is_(None),
            ShopifyConnection.access_token != "").limit(1)) is not None
        shopify_owned = connected or any(str(p.shopify_variant_id).isdigit() for p in products)
        if shopify_owned:
            result.inventory_source = "shopify"
            result.warnings.append(
                "Shopify remains the inventory source: CSV quantities are ignored. Only costs and lead times "
                "can update an unambiguous Shopify variant. Sync Shopify first for missing products; "
                "duplicate SKUs require mapping review. No historical products or sales are merged."
            )

        for row_num, row in enumerate(reader, start=2):
            if not any((cell or "").strip() for cell in row):
                continue
            result.products_processed += 1

            def cell(canonical: str) -> str:
                i = idx.get(canonical)
                if i is None or i >= len(row):
                    return ""
                return (row[i] or "").strip()

            sku = cell("sku")
            name = cell("name")
            if not sku and not name:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: missing SKU and product name")
                continue

            variant = cell("variant")
            vendor = cell("vendor") or None
            category = cell("category") or None
            if shopify_owned and cell("inventory"):
                result.inventory_rows_skipped += 1
            try:
                price = _optional_price(cell("price"))
                inventory_qty = _optional_inventory(cell("inventory"))
            except ValueError as exc:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: {exc}")
                continue
            cost = _to_decimal(cell("cost"), default="NaN")
            cost_value = cost if (cost.is_finite() and 0 <= cost <= Decimal("99999999.99")
                                  and cost == cost.quantize(Decimal("0.01"))) else None
            lead_time = _to_int(cell("lead_time_days"))
            lead_time_value = lead_time if lead_time > 0 else None

            display_name = name or sku
            shopify_variant_id = f"stocky:{sku or display_name}"
            shopify_product_id = f"stocky:{display_name}"

            candidates = existing_by_sku.get(sku, []) if sku else []
            if len(candidates) > 1:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: SKU matches multiple catalog products; review variant mapping before importing")
                continue
            existing = candidates[0] if candidates else None
            if not sku and not shopify_owned:
                existing = existing_by_variant.get(shopify_variant_id)
                if existing and (existing.sku or (existing.variant_name or "") != variant):
                    result.rows_skipped += 1
                    if len(result.skip_reasons) < 10:
                        result.skip_reasons.append(f"Row {row_num}: product name matches another variant; add a unique SKU before importing")
                    continue
            if shopify_owned:
                if existing is None or not str(existing.shopify_variant_id).isdigit():
                    result.rows_skipped += 1
                    if len(result.skip_reasons) < 10:
                        result.skip_reasons.append(f"Row {row_num}: no unambiguous Shopify variant for this SKU; sync Shopify and review the mapping")
                    continue
                changed = False
                if cost_value is not None and existing.cost != cost_value:
                    existing.cost, changed = cost_value, True
                if lead_time_value is not None and existing.sku_lead_time_days != lead_time_value:
                    existing.sku_lead_time_days, changed = lead_time_value, True
                result.products_updated += int(changed)
                continue
            if existing is not None:
                existing.name = display_name
                existing.variant_name = variant or existing.variant_name
                existing.vendor = vendor or existing.vendor
                existing.category = category or existing.category
                if price is not None:
                    existing.price = price
                if cost_value is not None:
                    existing.cost = cost_value
                if lead_time_value is not None:
                    existing.sku_lead_time_days = lead_time_value
                product = existing
                result.products_updated += 1
            else:
                product = Product(
                    shop_id=shop.id,
                    shopify_product_id=shopify_product_id,
                    shopify_variant_id=shopify_variant_id,
                    sku=sku or None,
                    name=display_name,
                    variant_name=variant or None,
                    vendor=vendor,
                    category=category,
                    price=price if price is not None else Decimal("0"),
                    cost=cost_value,
                    sku_lead_time_days=lead_time_value,
                )
                session.add(product)
                session.flush()
                existing_by_variant[shopify_variant_id] = product
                if sku:
                    existing_by_sku[sku].append(product)
                result.products_inserted += 1

            if inventory_qty is None:
                warning = "Rows without an inventory quantity update catalog details only; existing stock counts are unchanged."
                if warning not in result.warnings:
                    result.warnings.append(warning)
                continue
            inv = session.scalar(
                select(Inventory).where(
                    Inventory.shop_id == shop.id,
                    Inventory.product_id == product.id,
                    Inventory.shopify_location_id == location_label,
                )
            )
            if inv is None:
                session.add(
                    Inventory(
                        shop_id=shop.id,
                        product_id=product.id,
                        shopify_location_id=location_label,
                        quantity=inventory_qty,
                    )
                )
                result.inventory_rows_inserted += 1
            else:
                inv.quantity = inventory_qty
        # The connection lock also protects first install. Commit before its
        # process lock is released, so a first sync sees this CSV snapshot.
        session.commit()

    return result
