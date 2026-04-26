"""ShipStation CSV importer."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from app.db.models import OrderLineItem, Product, Shop
from app.db.session import session_scope
from app.services.shop_settings import normalize_shopify_domain


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": ("ordernumber", "orderid", "ordernum", "orderno"),
    "ship_date": ("shipdate", "shippeddate", "datedelivered", "datesent"),
    "order_date": ("orderdate", "datepurchased", "createddate"),
    "sku": ("sku", "itemsku", "productsku", "variantsku"),
    "name": ("itemname", "productname", "name", "title", "description"),
    "quantity": ("quantity", "qty", "qtyshipped", "shipped"),
    "unit_price": ("unitprice", "itemprice", "price", "lineprice"),
}


class ShipStationImportError(ValueError):
    pass


@dataclass
class SkuVelocity:
    sku: str
    units_30d: int = 0
    units_90d: int = 0
    units_180d: int = 0
    days_in_dataset: int = 0
    daily_average_180d: float = 0.0


@dataclass
class ShipStationImportResult:
    shop_id: int
    shopify_domain: str
    rows_processed: int = 0
    line_items_inserted: int = 0
    rows_skipped: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    distinct_skus: int = 0
    earliest_ship_date: str | None = None
    latest_ship_date: str | None = None
    top_skus_by_velocity: list[SkuVelocity] = field(default_factory=list)


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _resolve_columns(header: list[str]) -> dict[str, str]:
    normalized = {_norm(h): h for h in header}
    out: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in normalized:
                out[canonical] = normalized[a]
                break
    return out


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


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
    "%d/%m/%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _parse_date(raw: Any) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def import_shipstation_csv(
    *,
    shopify_domain: str,
    csv_bytes: bytes,
) -> ShipStationImportResult:
    domain = normalize_shopify_domain(shopify_domain)
    if not domain:
        raise ShipStationImportError("Shopify domain is required.")

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = csv_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ShipStationImportError(f"Could not decode CSV: {exc}") from exc

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ShipStationImportError("CSV file is empty.") from None

    cols = _resolve_columns(header)
    missing = [k for k in ("sku", "quantity") if k not in cols]
    if missing:
        raise ShipStationImportError(
            "CSV must include SKU and Quantity columns. Missing: " + ", ".join(missing)
        )

    name_to_index = {h: i for i, h in enumerate(header)}
    idx = {canonical: name_to_index[h] for canonical, h in cols.items()}

    result = ShipStationImportResult(shop_id=0, shopify_domain=domain)
    by_sku: dict[str, list[tuple[datetime, int, Decimal]]] = defaultdict(list)
    earliest: datetime | None = None
    latest: datetime | None = None

    with session_scope() as session:
        shop = session.scalar(select(Shop).where(Shop.shopify_domain == domain))
        if shop is None:
            shop = Shop(shopify_domain=domain)
            session.add(shop)
            session.flush()
        result.shop_id = shop.id

        existing_by_sku: dict[str, Product] = {}
        for p in session.scalars(select(Product).where(Product.shop_id == shop.id)).all():
            if p.sku:
                existing_by_sku[p.sku] = p

        for row_num, row in enumerate(reader, start=2):
            if not any((cell or "").strip() for cell in row):
                continue
            result.rows_processed += 1

            def cell(canonical: str) -> str:
                i = idx.get(canonical)
                if i is None or i >= len(row):
                    return ""
                return (row[i] or "").strip()

            sku = cell("sku")
            qty = _to_int(cell("quantity"))
            if not sku:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: missing SKU")
                continue
            if qty <= 0:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: non-positive quantity")
                continue

            ship_dt = _parse_date(cell("ship_date")) or _parse_date(cell("order_date"))
            if ship_dt is None:
                result.rows_skipped += 1
                if len(result.skip_reasons) < 10:
                    result.skip_reasons.append(f"Row {row_num}: unparseable date")
                continue

            unit_price = _to_decimal(cell("unit_price"))
            order_id = cell("order_id") or f"shipstation:{row_num}"
            product_name = cell("name") or sku

            product = existing_by_sku.get(sku)
            if product is None:
                product = Product(
                    shop_id=shop.id,
                    shopify_product_id=f"shipstation:{sku}",
                    shopify_variant_id=f"shipstation:{sku}",
                    sku=sku,
                    name=product_name,
                    price=unit_price,
                )
                session.add(product)
                session.flush()
                existing_by_sku[sku] = product

            session.add(
                OrderLineItem(
                    shop_id=shop.id,
                    shopify_order_id=f"shipstation:{order_id}",
                    product_id=product.id,
                    sku=sku,
                    quantity=qty,
                    price=unit_price,
                    created_at=ship_dt,
                )
            )
            result.line_items_inserted += 1

            by_sku[sku].append((ship_dt, qty, unit_price))
            if earliest is None or ship_dt < earliest:
                earliest = ship_dt
            if latest is None or ship_dt > latest:
                latest = ship_dt

    if earliest:
        result.earliest_ship_date = earliest.date().isoformat()
    if latest:
        result.latest_ship_date = latest.date().isoformat()
    result.distinct_skus = len(by_sku)

    if latest is not None:
        cutoff_30 = latest - timedelta(days=30)
        cutoff_90 = latest - timedelta(days=90)
        cutoff_180 = latest - timedelta(days=180)
        velocities: list[SkuVelocity] = []
        for sku, rows in by_sku.items():
            v = SkuVelocity(sku=sku)
            for dt, qty, _price in rows:
                if dt >= cutoff_180:
                    v.units_180d += qty
                if dt >= cutoff_90:
                    v.units_90d += qty
                if dt >= cutoff_30:
                    v.units_30d += qty
            v.days_in_dataset = max(1, (latest - cutoff_180).days)
            v.daily_average_180d = round(v.units_180d / v.days_in_dataset, 3)
            velocities.append(v)
        velocities.sort(key=lambda x: x.units_180d, reverse=True)
        result.top_skus_by_velocity = velocities[:10]

    return result
