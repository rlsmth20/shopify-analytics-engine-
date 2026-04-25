"""Stocky CSV importer.

Stocky is being end-of-life'd by Shopify on August 31, 2026. This service ingests
Stocky's product CSV export into slelfly's normalized tables so a Stocky merchant
can land in slelfly with their catalog already populated.

Stocky exports several CSVs. We accept the products export, which is the minimum
required to drive slelfly's action engine. Vendor lead times can be configured
afterwards on the Lead Times settings page.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from app.db.models import Inventory, Product, Shop
from app.db.session import session_scope
from app.services.shop_settings import normalize_shopify_domain


# Stocky's column names vary across export versions. We accept any of these.
# Match is case-insensitive and ignores whitespace/punctuation.
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


def _norm_key(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _resolve_columns(header: list[str]) -> dict[str, str]:
    """Return mapping of canonical name -> actual header in this CSV."""
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
    # Strip currency symbols and thousands separators
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
        return int(float(s.replace(",", "")))
    except (ValueError, TypeError):
        return default


def import_stocky_products_csv(
    *,
    shopify_domain: str,
    csv_bytes: bytes,
    location_label: str = "stocky-import",
) -> StockyImportResult:
    """Parse Stocky's products CSV and persist rows.

    Args:
      shopify_domain: the merchant's shop domain (will be normalized).
      csv_bytes: raw CSV file bytes.
      location_label: a label for the synthetic location row we attach
        inventory to. Real Shopify locations replace this on first sync.
    """
    domain = normalize_shopify_domain(shopify_domain)
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
            "CSV must include either an SKU or product name column. "
            "Recognized headers: " + ", ".join(sorted(set(a for v in COLUMN_ALIASES.values() for a in v)))
        )

    # Resolve column indices for fast lookup
    name_to_index = {h: i for i, h in enumerate(header)}
    idx = {canonical: name_to_index[h] for canonical, h in cols.items()}

    result = StockyImportResult(shop_id=0, shopify_domain=domain)

    with session_scope() as session:
        shop = session.scalar(select(Shop).where(Shop.shopify_domain == domain))
        if shop is None:
            shop = Shop(shopify_domain=domain)
            session.add(shop)
            session.flush()
        result.shop_id = shop.id

        # Build a quick lookup for existing products by SKU on this shop
        existing_by_sku: dict[str, Product] = {}
        for p in session.scalars(select(Product).where(Product.shop_id == shop.id)).all():
            if p.sku:
                existing_by_sku[p.sku] = p

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
            price = _to_decimal(cell("price"))
            cost = _to_decimal(cell("cost"))
            cost_value = cost if cost > 0 else None
            inventory_qty = _to_int(cell("inventory"))
            lead_time = _to_int(cell("lead_time_days"))
            lead_time_value = lead_time if lead_time > 0 else None

            display_name = name or sku
            shopify_variant_id = f"stocky:{sku or display_name}"
            shopify_product_id = f"stocky:{display_name}"

            existing = existing_by_sku.get(sku) if sku else None
            if existing is not None:
                existing.name = display_name
                existing.variant_name = variant or existing.variant_name
                existing.vendor = vendor or existing.vendor
                existing.category = category or existing.category
                existing.price = price if price > 0 else existing.price
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
                    price=price,
                    cost=cost_value,
                    sku_lead_time_days=lead_time_value,
                )
                session.add(product)
                session.flush()
                if sku:
                    existing_by_sku[sku] = product
                result.products_inserted += 1

            # Inventory row: write a single synthetic location for now;
            # real Shopify ingestion overrides this on first sync.
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

    return result
