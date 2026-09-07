"""Atomic, duplicate-safe ShipStation ingestion with explicit source evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, text

from app.db.models import OrderLineItem, Product, ShipmentImportBatchRecord, ShipmentImportRowRecord, Shop
from app.db.session import session_scope
from app.services.shop_settings import ShopSettingsInputError, normalize_shopify_domain

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": ("orderid",),
    "order_number": ("ordernumber", "ordernum", "orderno"),
    "shipment_id": ("shipmentid",),
    # Generic ItemId may identify a catalog product, not a shipment line.
    "line_item_id": ("orderitemid", "orderlineitemid", "lineitemid"),
    "shipment_item_id": ("shipmentitemid", "shipmentlineitemid"),
    "shopify_order_id": ("shopifyorderid",),
    "store_id": ("storeid",),
    "ship_date": ("shipdate", "shippeddate", "datedelivered", "datesent"),
    "order_date": ("orderdate", "datepurchased", "createddate"),
    "sku": ("sku", "itemsku", "productsku", "variantsku"),
    "name": ("itemname", "productname", "name", "title", "description"),
    "quantity": ("quantity", "qty", "qtyshipped", "shipped"),
    "unit_price": ("unitprice", "itemprice", "price", "lineprice"),
}
SOURCE_COLUMNS = {"store", "storename", "marketplace", "sellingchannel", "saleschannel", "channel", "storetype", "source"}
EXTERNAL_CHANNEL = re.compile(r"\b(?:amazon|etsy|ebay|walmart|bigcommerce|woocommerce|magento|square|bigcartel|bonanza|rakuten|newegg)\b", re.I)
MAX_ROWS = 100_000


class ShipStationImportError(ValueError):
    pass


@dataclass
class SkuVelocity:
    sku: str
    units_30d: int = 0
    units_90d: int = 0
    units_180d: int = 0
    days_in_dataset: int = 180
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
    batch_id: str | None = None
    source_scope: str = "unknown"
    replayed: bool = False
    duplicate_rows: int = 0
    rows_held: int = 0
    shopify_rows_excluded: int = 0
    invalid_rows: int = 0
    hold_reasons: list[str] = field(default_factory=list)


@dataclass
class ParsedRow:
    row_number: int
    facts: dict
    error: str | None = None


def _norm(value: str) -> str:
    return "".join(c for c in value.lower() if c.isalnum())


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_csv(csv_bytes: bytes) -> list[ParsedRow]:
    if not csv_bytes or len(csv_bytes) > 50 * 1024 * 1024:
        raise ShipStationImportError("Choose a non-empty CSV no larger than 50 MB.")
    try:
        decoded = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = csv_bytes.decode("latin-1")
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        header = next(reader)
        normalized = [_norm(value) for value in header]
        if len(normalized) != len(set(normalized)):
            raise ShipStationImportError("CSV column names must be unique.")
        indices = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            matches = [i for i, value in enumerate(normalized) if value in aliases]
            if len(matches) > 1:
                raise ShipStationImportError(f"Use one {canonical.replace('_', ' ')} column so values are unambiguous.")
            if matches:
                indices[canonical] = matches[0]
        if "sku" not in indices or "quantity" not in indices or not {"ship_date", "order_date"}.intersection(indices):
            raise ShipStationImportError("CSV must include SKU, Quantity and a ship or order date column.")
        source_indices = [i for i, value in enumerate(normalized) if value in SOURCE_COLUMNS]
        parsed = []
        for row_number, row in enumerate(reader, start=2):
            if not any(cell.strip() for cell in row):
                continue
            if len(parsed) >= MAX_ROWS:
                raise ShipStationImportError("CSV has more than 100,000 rows. Export a smaller date range.")
            cells = {key: (row[indices[key]].strip() if key in indices and indices[key] < len(row) else "") for key in COLUMN_ALIASES}
            sources = sorted({row[i].strip().casefold() for i in source_indices if i < len(row) and row[i].strip()})
            facts = {**cells, "source_labels": sources}
            error = None
            if len(row) != len(header):
                error = "column count does not match the header"
            elif not cells.get("sku") or len(cells["sku"]) > 128:
                error = "SKU is missing or longer than 128 characters"
            elif any(len(value) > 255 for key, value in cells.items() if key not in {"sku", "quantity", "unit_price"}) or any(len(value) > 255 for value in sources):
                error = "a shipment identifier or product name is longer than 255 characters"
            try:
                quantity = Decimal(cells.get("quantity", "").replace(",", ""))
                if not quantity.is_finite() or quantity != quantity.to_integral_value() or not 0 < quantity <= 2_147_483_647:
                    raise ValueError()
                facts["quantity"] = int(quantity)
            except (InvalidOperation, ValueError):
                error = error or "quantity must be a positive whole number"
            try:
                price = Decimal(re.sub(r"[$£€,]", "", cells.get("unit_price", "")) or "0")
                if not price.is_finite() or not 0 <= price <= Decimal("99999999.99") or price != price.quantize(Decimal("0.01")):
                    raise ValueError()
                facts["unit_price"] = format(price, ".2f")
            except (InvalidOperation, ValueError):
                error = error or "unit price must be a finite non-negative amount with at most two decimal places"
            date = _parse_date(cells.get("ship_date", "")) or _parse_date(cells.get("order_date", ""))
            if date is None:
                error = error or "ship or order date could not be read"
            else:
                facts["date"] = date.isoformat()
                facts.pop("ship_date", None)
                facts.pop("order_date", None)
            parsed.append(ParsedRow(row_number, facts, error))
    except StopIteration:
        raise ShipStationImportError("CSV file is empty.") from None
    except csv.Error as exc:
        raise ShipStationImportError("CSV could not be read. Check quoting and export it again.") from exc
    if not parsed:
        raise ShipStationImportError("CSV contains no shipment rows.")
    return parsed


def _namespace(facts: dict) -> str:
    return f"store:{facts['store_id']}" if facts.get("store_id") else "source:" + "|".join(facts.get("source_labels") or ["confirmed-external"])


def _source_identity(facts: dict) -> str | None:
    kind, identifier = _line_identity(facts)
    if facts.get("shipment_id") and identifier:
        return _hash([_namespace(facts), facts["shipment_id"], kind, identifier])
    return None


def _line_identity(facts: dict) -> tuple[str, str | None]:
    return ("order-line", facts["line_item_id"]) if facts.get("line_item_id") else ("shipment-line", facts.get("shipment_item_id"))


def _demand_facts(facts: dict):
    return [facts.get(key) for key in ("sku", "quantity", "unit_price", "date")]


def _order_refs(facts: dict) -> set[str]:
    return {facts[key] for key in ("order_id", "order_number") if facts.get(key)}


def _row_identities(parsed: list[ParsedRow], file_hash: str) -> dict[int, str]:
    identities = {}
    occurrences: dict[str, int] = defaultdict(int)
    for row in parsed:
        if row.error:
            continue
        fingerprint = _hash(row.facts)
        occurrences[fingerprint] += 1
        # Without shipment IDs, identity is only proven inside this exact
        # canonical file, including multiplicity. A scope correction can reuse
        # already accepted rows while a different overlapping file is held.
        identities[row.row_number] = _source_identity(row.facts) or _hash(
            ["file-row", file_hash, fingerprint, occurrences[fingerprint]])
    return identities


def _ambiguous_overlap(new: dict, old: dict) -> bool:
    if _source_identity(new) and _source_identity(old) and _namespace(new) == _namespace(old):
        if new["shipment_id"] != old["shipment_id"]:
            return False
        new_kind, new_id = _line_identity(new)
        old_kind, old_id = _line_identity(old)
        return new_kind != old_kind or new_id == old_id
    if new.get("store_id") and old.get("store_id") and new["store_id"] != old["store_id"]:
        return False
    new_channels = {match.group().casefold() for label in new.get("source_labels", []) for match in EXTERNAL_CHANNEL.finditer(label)}
    old_channels = {match.group().casefold() for label in old.get("source_labels", []) for match in EXTERNAL_CHANNEL.finditer(label)}
    if new_channels and old_channels and new_channels.isdisjoint(old_channels):
        return False
    new_refs, old_refs = _order_refs(new), _order_refs(old)
    if new_refs and old_refs:
        return bool(new_refs.intersection(old_refs))
    # Missing order references cannot distinguish a corrected quantity/price
    # from a new shipment of the same SKU on that day.
    return new.get("date", "")[:10] == old.get("date", "")[:10]


def _skip(result: ShipStationImportResult, row: ParsedRow, status: str, reason: str):
    result.rows_skipped += 1
    key = {"duplicate": "duplicate_rows", "held": "rows_held", "shopify_excluded": "shopify_rows_excluded", "invalid": "invalid_rows"}[status]
    setattr(result, key, getattr(result, key) + 1)
    detail = f"Row {row.row_number}: {reason}"
    if len(result.skip_reasons) < 10:
        result.skip_reasons.append(detail)
    if status == "held" and len(result.hold_reasons) < 10:
        result.hold_reasons.append(detail)


def _replay(batch: ShipmentImportBatchRecord) -> ShipStationImportResult:
    result = ShipStationImportResult(**{**batch.result, "top_skus_by_velocity": []})
    result.replayed = True
    result.duplicate_rows += result.line_items_inserted
    result.rows_skipped += result.line_items_inserted
    result.line_items_inserted = result.distinct_skus = 0
    result.earliest_ship_date = result.latest_ship_date = None
    result.skip_reasons = ["This file and source selection were already checked; no new shipment rows were added.", *result.skip_reasons][:10]
    return result


def import_shipstation_csv(*, shopify_domain: str, csv_bytes: bytes, source_scope: str = "unknown", shop_id: int | None = None) -> ShipStationImportResult:
    if source_scope not in {"unknown", "non_shopify"}:
        raise ShipStationImportError("Choose an unknown/mixed export or confirm that the export excludes Shopify orders.")
    try:
        domain = normalize_shopify_domain(shopify_domain)
    except ShopSettingsInputError as exc:
        raise ShipStationImportError("Your workspace's shop domain could not be validated. Connect your store on Store Sync, then retry.") from exc
    if not domain:
        raise ShipStationImportError("Shopify domain is required.")
    parsed = _parse_csv(csv_bytes)
    # Preserve row multiplicity, ignoring order, BOM and customer/address columns.
    file_hash = _hash(sorted(_hash([row.facts, row.error]) for row in parsed))
    content_hash = _hash(["v1", source_scope, file_hash])
    row_identities = _row_identities(parsed, file_hash)
    result = ShipStationImportResult(shop_id=0, shopify_domain=domain, source_scope=source_scope, rows_processed=len(parsed))
    imported: list[dict] = []
    with session_scope() as session:
        if session.bind.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        shop = session.scalar(select(Shop).where(Shop.shopify_domain == domain).with_for_update().execution_options(populate_existing=True))
        if shop is None or (shop_id is not None and shop.id != shop_id):
            raise ShipStationImportError("Workspace shop not found. Sign in to the intended workspace before importing.")
        result.shop_id = shop.id
        existing_batch = session.scalar(select(ShipmentImportBatchRecord).where(
            ShipmentImportBatchRecord.shop_id == shop.id, ShipmentImportBatchRecord.content_hash == content_hash))
        if existing_batch:
            return _replay(existing_batch)
        batch = ShipmentImportBatchRecord(id=str(uuid.uuid4()), shop_id=shop.id, content_hash=content_hash, source_scope=source_scope)
        session.add(batch)
        session.flush()
        result.batch_id = batch.id
        products: dict[str, list[Product]] = defaultdict(list)
        for product in session.scalars(select(Product).where(Product.shop_id == shop.id)).all():
            if product.sku:
                products[product.sku].append(product)
        prior: dict[str, list[dict]] = defaultdict(list)
        strong: dict[str, dict] = {}
        identities = sorted(set(row_identities.values()))
        for start in range(0, len(identities), 400):
            for receipt in session.scalars(select(ShipmentImportRowRecord).where(ShipmentImportRowRecord.shop_id == shop.id,
                ShipmentImportRowRecord.source_identity.in_(identities[start:start + 400]))).all():
                strong[receipt.source_identity] = receipt.facts
        skus = sorted({row.facts["sku"] for row in parsed if not row.error})
        for start in range(0, len(skus), 400):
            sku_chunk = skus[start:start + 400]
            receipts = session.scalars(select(ShipmentImportRowRecord).where(ShipmentImportRowRecord.shop_id == shop.id,
                ShipmentImportRowRecord.status == "imported", ShipmentImportRowRecord.sku.in_(sku_chunk))).all()
            for receipt in receipts:
                prior[receipt.sku].append(receipt.facts)
                if receipt.source_identity:
                    strong[receipt.source_identity] = receipt.facts
            logged_lines = select(ShipmentImportRowRecord.order_line_item_id).where(
                ShipmentImportRowRecord.shop_id == shop.id, ShipmentImportRowRecord.order_line_item_id.is_not(None))
            legacy = session.scalars(select(OrderLineItem).where(OrderLineItem.shop_id == shop.id,
                OrderLineItem.sku.in_(sku_chunk), OrderLineItem.shopify_order_id.like("shipstation:%"),
                OrderLineItem.id.not_in(logged_lines))).all()
            for line in legacy:
                when = line.created_at.replace(tzinfo=timezone.utc) if line.created_at.tzinfo is None else line.created_at.astimezone(timezone.utc)
                prior[line.sku].append({"sku": line.sku, "quantity": line.quantity, "unit_price": format(line.price, ".2f"),
                    "date": when.isoformat(), "order_number": line.shopify_order_id.removeprefix("shipstation:")})
        for row in parsed:
            facts = row.facts
            status, reason, line_id = "imported", None, None
            identity = row_identities.get(row.row_number)
            if row.error:
                status, reason = "invalid", row.error
            elif facts.get("shopify_order_id") or any("shopify" in value for value in facts["source_labels"]):
                status, reason = "shopify_excluded", "Shopify-sourced order excluded to avoid counting Shopify sales twice"
            elif source_scope != "non_shopify" and not any(EXTERNAL_CHANNEL.search(value) for value in facts["source_labels"]):
                status, reason = "held", "sales channel is unclear; only confirm a non-Shopify export if it excludes every Shopify order"
            elif identity and identity in strong:
                if _demand_facts(facts) == _demand_facts(strong[identity]):
                    status, reason = "duplicate", "shipment line was already imported"
                else:
                    status, reason = "held", "shipment line identity already exists with different SKU, date, quantity or price; review the correction"
            elif any(_ambiguous_overlap(facts, old) for old in prior[facts["sku"]]):
                status, reason = "held", "possible overlap with earlier shipment history; include stable Shipment ID and line-item IDs or contact support for review"
            elif len(products.get(facts["sku"], [])) > 1:
                status, reason = "held", "SKU matches multiple catalog products; resolve the catalog mapping before importing"
            if status == "imported":
                product = next(iter(products.get(facts["sku"], [])), None)
                if product is None:
                    product = Product(shop_id=shop.id, shopify_product_id=f"shipstation:{facts['sku']}",
                        shopify_variant_id=f"shipstation:{facts['sku']}", sku=facts["sku"], name=facts.get("name") or facts["sku"],
                        price=Decimal(facts["unit_price"]))
                    session.add(product)
                    session.flush()
                    products[facts["sku"]].append(product)
                order_key = _hash([_namespace(facts), facts.get("order_id") or facts.get("order_number") or [batch.id, row.row_number]])
                line = OrderLineItem(shop_id=shop.id, shopify_order_id=f"shipstation:v2:{order_key}", product_id=product.id,
                    sku=facts["sku"], quantity=facts["quantity"], price=Decimal(facts["unit_price"]), created_at=datetime.fromisoformat(facts["date"]))
                session.add(line)
                session.flush()
                line_id = line.id
                imported.append(facts)
                result.line_items_inserted += 1
                if identity:
                    strong[identity] = facts
                # Weak identical rows within a new file retain multiplicity.
                # Only previously committed imports are overlap candidates.
            else:
                _skip(result, row, status, reason)
            session.add(ShipmentImportRowRecord(shop_id=shop.id, batch_id=batch.id, row_number=row.row_number,
                source_identity=identity if status == "imported" else None, sku=facts.get("sku", "")[:128] or None,
                status=status, reason=reason, facts=facts if not row.error else {"fingerprint": _hash(facts)}, order_line_item_id=line_id))
        _summarize_imported(result, imported)
        batch.result = asdict(result)
        session.flush()
    return result


def _summarize_imported(result: ShipStationImportResult, imported: list[dict]):
    if not imported:
        return
    latest = max(datetime.fromisoformat(row["date"]) for row in imported)
    earliest = min(datetime.fromisoformat(row["date"]) for row in imported)
    result.earliest_ship_date, result.latest_ship_date = earliest.date().isoformat(), latest.date().isoformat()
    by_sku: dict[str, SkuVelocity] = {}
    for row in imported:
        value = by_sku.setdefault(row["sku"], SkuVelocity(sku=row["sku"]))
        for days in (30, 90, 180):
            if datetime.fromisoformat(row["date"]) >= latest - timedelta(days=days):
                setattr(value, f"units_{days}d", getattr(value, f"units_{days}d") + row["quantity"])
    for value in by_sku.values():
        value.daily_average_180d = round(value.units_180d / 180, 3)
    result.distinct_skus = len(by_sku)
    result.top_skus_by_velocity = sorted(by_sku.values(), key=lambda value: value.units_180d, reverse=True)[:10]
