"""Persisted purchase order lifecycle and receipt observations."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from app.db.models import (
    PurchaseOrderLineRecord,
    PurchaseOrderReceiptRecord,
    PurchaseOrderReceiptSubmissionRecord,
    PurchaseOrderRecord,
)
from app.schemas_v2 import PurchaseOrderDraft, PurchaseOrderLine, PurchaseOrderReceipt
from app.services.supplier_scoring import SupplierObservation
from app.services.shop_skus import AmbiguousSkuError, build_sku_alias_index
from app.services.audit_log import record_audit_event


class PurchaseOrderIdentityError(ValueError):
    """A requested write cannot identify one purchase-order line safely."""


class PurchaseOrderReceiptError(ValueError):
    """A receipt cannot be applied to the saved remaining quantities."""


class ReceiptSubmissionNotAppliedError(PurchaseOrderReceiptError):
    """A keyed submission failed preflight before any receipt was applied."""


@dataclass(frozen=True)
class ReceiptSubmissionResult:
    po: PurchaseOrderDraft
    replayed: bool = False
    request_id: str | None = None


def list_saved_purchase_orders(db: DbSession, shop_id: int) -> list[PurchaseOrderDraft]:
    rows = db.scalars(
        select(PurchaseOrderRecord)
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .order_by(PurchaseOrderRecord.updated_at.desc())
    ).all()
    index = build_sku_alias_index(db, shop_id)
    return [_record_to_schema(db, row, index=index) for row in rows]


def save_purchase_order(
    db: DbSession,
    *,
    shop_id: int,
    draft: PurchaseOrderDraft,
) -> PurchaseOrderDraft:
    if not draft.financial_values_known or any(not line.financial_values_known for line in draft.lines):
        raise ValueError("Record explicit unit costs for every purchase-order line before saving.")
    record = db.scalar(
        select(PurchaseOrderRecord)
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .where(PurchaseOrderRecord.po_id == draft.po_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    old_lines = db.scalars(select(PurchaseOrderLineRecord).where(
        PurchaseOrderLineRecord.purchase_order_id == record.id).execution_options(populate_existing=True)).all() if record else []
    old_groups, new_groups = _line_groups(old_lines), _line_groups(draft.lines)
    changed_aliases = [alias for alias in dict.fromkeys([*old_groups, *new_groups])
                       if Counter(_line_state(line) for line in old_groups.get(alias, [])) !=
                          Counter(_line_state(line) for line in new_groups.get(alias, []))]
    index = build_sku_alias_index(db, shop_id)
    # Preflight the whole change before creating the PO or touching any line.
    # Unchanged legacy lines may remain while a merchant edits unrelated text
    # or an unambiguous line; their identities, receipts and amounts stay intact.
    for alias in changed_aliases:
        if len(old_groups.get(alias, [])) > 1 or len(new_groups.get(alias, [])) > 1:
            raise PurchaseOrderIdentityError(
                f"SKU '{alias}' identifies multiple purchase-order lines. Review those lines before changing them; the purchase order was not changed."
            )
        _check_catalog_alias(index, alias)
        old_line = next(iter(old_groups.get(alias, [])), None)
        new_line = next(iter(new_groups.get(alias, [])), None)
        if old_line is not None and old_line.received_qty > 0 and (new_line is None or new_line.qty < old_line.received_qty):
            raise PurchaseOrderReceiptError(
                f"SKU '{alias}' already has {old_line.received_qty} received units. Keep this line and an ordered quantity at least that large; no purchase-order data was changed.")
    has_receipts = record is not None and db.scalar(select(PurchaseOrderReceiptRecord.id).where(
        PurchaseOrderReceiptRecord.purchase_order_id == record.id).limit(1)) is not None
    if record is None:
        record = PurchaseOrderRecord(shop_id=shop_id, po_id=draft.po_id, vendor=draft.vendor)
        db.add(record)
        db.flush()

    record.vendor = draft.vendor
    if not has_receipts:
        record.status = draft.status
    record.subtotal_cost = Decimal(str(draft.subtotal_cost or sum(line.extended_cost for line in draft.lines)))
    record.shipping_cost = Decimal(str(draft.shipping_cost))
    record.total_cost = Decimal(str(draft.total_cost))
    record.expected_arrival_date = draft.expected_arrival_date
    record.rationale = draft.rationale
    record.sent_at = draft.sent_at
    if not has_receipts:
        record.received_at = draft.received_at

    for alias in changed_aliases:
        old_line = next(iter(old_groups.get(alias, [])), None)
        line = next(iter(new_groups.get(alias, [])), None)
        if line is None:
            db.delete(old_line)
            continue
        if old_line is None:
            old_line = PurchaseOrderLineRecord(shop_id=shop_id, purchase_order_id=record.id,
                                               sku_id=line.sku_id, received_qty=0)
            db.add(old_line)
        old_line.name = line.name
        old_line.qty = line.qty
        old_line.unit_cost = Decimal(str(line.unit_cost))
        old_line.extended_cost = Decimal(str(line.extended_cost))
        # Receipt counts come only from receiving, never from a stale/editable draft.
    db.commit()
    db.refresh(record)
    return _record_to_schema(db, record, index=index)


def update_purchase_order_status(
    db: DbSession,
    *,
    shop_id: int,
    po_id: str,
    status: str,
    user_id: int | None = None,
) -> PurchaseOrderDraft | None:
    record = _get_record(db, shop_id, po_id)
    if record is None:
        return None
    record.status = status
    if status == "approved" and record.approved_at is None:
        record.approved_at = datetime.now(timezone.utc)
        record.approved_by_user_id = user_id
    if status == "sent" and record.sent_at is None:
        record.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _record_to_schema(db, record)


def receive_purchase_order(
    db: DbSession,
    *,
    shop_id: int,
    po_id: str,
    received_lines: dict[str, tuple[int, float | None]],
    received_at: datetime | None = None,
) -> PurchaseOrderDraft | None:
    """Legacy internal entrypoint; HTTP receipt writes use the protected entrypoint."""
    result = _receive_purchase_order(db, shop_id=shop_id, po_id=po_id,
        received_lines=received_lines, received_at=received_at)
    return result.po if result else None


def receive_purchase_order_submission(
    db: DbSession, *, shop_id: int, po_id: str, request_id: UUID | str,
    received_lines: dict[str, tuple[int, float | None]],
    received_at: datetime | None = None, user_id: int | None = None,
) -> ReceiptSubmissionResult | None:
    """Commit submission, quantities, receipt rows and audit together, or none."""
    normalized_id = str(UUID(str(request_id)))
    try:
        # SQLite lacks row locks. Reserve its writer before reading the PO.
        # The API may already have an auth read transaction, but no writes.
        if db.get_bind().dialect.name == "sqlite":
            connection = db.connection()
            if not connection.connection.driver_connection.in_transaction:
                db.execute(text("BEGIN IMMEDIATE"))
            else:
                db.execute(text("UPDATE purchase_orders SET id = id WHERE shop_id = :shop_id AND po_id = :po_id"),
                           {"shop_id": shop_id, "po_id": po_id})
        return _receive_purchase_order(db, shop_id=shop_id, po_id=po_id,
            received_lines=received_lines, received_at=received_at,
            request_id=normalized_id, user_id=user_id)
    except Exception:
        db.rollback()
        raise


def _receipt_payload_hash(received_lines, received_at):
    normalized_date = (received_at.replace(tzinfo=timezone.utc) if received_at.tzinfo is None
                       else received_at.astimezone(timezone.utc)) if received_at is not None else None
    payload = {"received_at": normalized_date.isoformat() if normalized_date else None,
               "lines": [[sku, qty, str(Decimal(str(cost)).normalize()) if cost is not None else None]
                         for sku, (qty, cost) in sorted(received_lines.items())]}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _receive_purchase_order(
    db: DbSession, *, shop_id: int, po_id: str,
    received_lines: dict[str, tuple[int, float | None]], received_at: datetime | None,
    request_id: str | None = None, user_id: int | None = None,
) -> ReceiptSubmissionResult | None:
    record = _get_record(db, shop_id, po_id, for_update=True)
    if record is None:
        return None
    payload_hash = _receipt_payload_hash(received_lines, received_at) if request_id else None
    if request_id:
        previous = db.scalar(select(PurchaseOrderReceiptSubmissionRecord).where(
            PurchaseOrderReceiptSubmissionRecord.shop_id == shop_id,
            PurchaseOrderReceiptSubmissionRecord.purchase_order_id == record.id,
            PurchaseOrderReceiptSubmissionRecord.request_id == request_id))
        if previous is not None:
            if previous.payload_hash != payload_hash:
                raise PurchaseOrderReceiptError("This receipt submission ID was already used with different details. Review the recorded receipt before starting a separate delivery.")
            # A retry remains successful even if the PO is now fully received
            # or the catalog has since changed. Return current saved evidence.
            db.expire_all()
            result = ReceiptSubmissionResult(_record_to_schema(db, record), True, request_id)
            db.commit()
            return result
    received_at = received_at or datetime.now(timezone.utc)
    lines = db.scalars(
        select(PurchaseOrderLineRecord).where(PurchaseOrderLineRecord.purchase_order_id == record.id)
        .execution_options(populate_existing=True)
    ).all()
    index = build_sku_alias_index(db, shop_id)
    try:
        requested = _validate_receipt(lines, index, received_lines)
    except (PurchaseOrderIdentityError, PurchaseOrderReceiptError) as exc:
        if request_id:
            raise ReceiptSubmissionNotAppliedError(str(exc)) from None
        raise
    for line in lines:
        if line.sku_id not in requested:
            continue
        qty, received_unit_cost = requested[line.sku_id]
        line.received_qty += qty
        unit_cost = float(line.unit_cost)
        db.add(
            PurchaseOrderReceiptRecord(
                shop_id=shop_id,
                purchase_order_id=record.id,
                vendor=record.vendor,
                sku_id=line.sku_id,
                ordered_qty=line.qty,
                received_qty=qty,
                ordered_unit_cost=line.unit_cost,
                received_unit_cost=Decimal(str(received_unit_cost if received_unit_cost is not None else unit_cost)),
                expected_arrival_date=record.expected_arrival_date,
                received_at=received_at,
            )
        )
    record.received_at = received_at
    record.status = "received" if all(line.received_qty >= line.qty for line in lines) else "partially_received"
    if request_id:
        db.add(PurchaseOrderReceiptSubmissionRecord(shop_id=shop_id, purchase_order_id=record.id,
            request_id=request_id, payload_hash=payload_hash))
        record_audit_event(db, shop_id=shop_id, user_id=user_id, event_type="purchase_order_received",
            entity_type="purchase_order", entity_id=record.po_id,
            summary=f"Receipt recorded for purchase order {record.po_id}.",
            metadata={"vendor": record.vendor, "request_id": request_id,
                      "received_lines": [{"sku_id": sku, "received_qty": values[0], "received_unit_cost": values[1]}
                                         for sku, values in requested.items()], "status": record.status}, commit=False)
    db.commit()
    db.refresh(record)
    return ReceiptSubmissionResult(_record_to_schema(db, record, index=index), False, request_id)


def _validate_receipt(lines, index, received_lines):
    requested = {alias: values for alias, values in received_lines.items() if values[0] > 0}
    if not requested:
        raise PurchaseOrderReceiptError("Enter a positive received quantity for a saved line; no receipt was recorded.")
    groups = _line_groups(lines)
    for alias in requested:
        if len(groups.get(alias, [])) != 1:
            raise PurchaseOrderIdentityError(
                f"SKU '{alias}' does not identify exactly one saved purchase-order line. Review the receipt; no receipt was recorded.")
        _check_catalog_alias(index, alias)
        line = groups[alias][0]
        remaining = max(line.qty - line.received_qty, 0)
        if requested[alias][0] > remaining:
            raise PurchaseOrderReceiptError(
                f"SKU '{alias}' has only {remaining} unreceived units on this purchase order. Refresh the receipt quantities; no receipt was recorded.")
    return requested


def receipt_lines_by_sku(lines):
    """Reject duplicate request aliases before a dict can discard a receipt."""
    result = {}
    for line in lines:
        if line.sku_id in result:
            raise PurchaseOrderIdentityError(
                f"SKU '{line.sku_id}' appears more than once in this receipt. Submit each saved line once; no receipt was recorded."
            )
        result[line.sku_id] = (line.received_qty, line.received_unit_cost)
    return result


def _line_groups(lines):
    groups = defaultdict(list)
    for line in lines:
        groups[line.sku_id].append(line)
    return groups


def _line_state(line):
    return (line.name, line.qty, Decimal(str(line.unit_cost)), Decimal(str(line.extended_cost)))


def _check_catalog_alias(index, alias):
    try:
        index.resolve(alias)
    except AmbiguousSkuError:
        raise PurchaseOrderIdentityError(
            f"SKU '{alias}' matches multiple current products. Review its identity before changing quantities, costs or receipts; no purchase-order data was changed."
        ) from None


def load_supplier_observations(db: DbSession, shop_id: int) -> list[SupplierObservation]:
    rows = db.scalars(
        select(PurchaseOrderReceiptRecord).where(PurchaseOrderReceiptRecord.shop_id == shop_id)
    ).all()
    observations: list[SupplierObservation] = []
    for row in rows:
        expected = _parse_date(row.expected_arrival_date)
        received = row.received_at
        if received.tzinfo is not None:
            received_naive = received.replace(tzinfo=None)
        else:
            received_naive = received
        expected_lead = 14
        actual_lead = 14
        if expected is not None:
            expected_lead = 14
            actual_lead = max(1, expected_lead + (received_naive.date() - expected).days)
        observations.append(
            SupplierObservation(
                vendor=row.vendor,
                expected_lead_time_days=expected_lead,
                actual_lead_time_days=actual_lead,
                ordered_qty=row.ordered_qty,
                received_qty=row.received_qty,
                ordered_unit_cost=float(row.ordered_unit_cost),
                received_unit_cost=float(row.received_unit_cost),
            )
        )
    return observations


def _get_record(db: DbSession, shop_id: int, po_id: str, *, for_update=False) -> PurchaseOrderRecord | None:
    query = select(PurchaseOrderRecord)
    query = (query
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .where(PurchaseOrderRecord.po_id == po_id)
    )
    return db.scalar(query.with_for_update().execution_options(populate_existing=True) if for_update else query)


def _record_to_schema(db: DbSession, record: PurchaseOrderRecord, *, index=None) -> PurchaseOrderDraft:
    index = index or build_sku_alias_index(db, record.shop_id)
    lines = db.scalars(
        select(PurchaseOrderLineRecord).where(PurchaseOrderLineRecord.purchase_order_id == record.id)
    ).all()
    duplicate_aliases = {alias for alias, group in _line_groups(lines).items() if len(group) > 1}
    receipts = db.scalars(
        select(PurchaseOrderReceiptRecord)
        .where(PurchaseOrderReceiptRecord.purchase_order_id == record.id)
        .order_by(PurchaseOrderReceiptRecord.received_at.desc(), PurchaseOrderReceiptRecord.id.desc())
    ).all()
    return PurchaseOrderDraft(
        po_id=record.po_id,
        vendor=record.vendor,
        created_at=record.created_at,
        status=record.status,
        source="saved",
        lines=[
            PurchaseOrderLine(
                sku_id=line.sku_id,
                name=line.name,
                qty=line.qty,
                unit_cost=float(line.unit_cost),
                extended_cost=float(line.extended_cost),
                received_qty=line.received_qty,
                **_line_identity_view(index, line.sku_id, duplicate_aliases),
            )
            for line in lines
        ],
        subtotal_cost=float(record.subtotal_cost),
        shipping_cost=float(record.shipping_cost),
        total_cost=float(record.total_cost),
        expected_arrival_date=record.expected_arrival_date,
        rationale=record.rationale,
        approved_at=record.approved_at,
        approved_by_user_id=record.approved_by_user_id,
        sent_at=record.sent_at,
        received_at=record.received_at,
        receipts=[
            PurchaseOrderReceipt(
                id=receipt.id,
                sku_id=receipt.sku_id,
                ordered_qty=receipt.ordered_qty,
                received_qty=receipt.received_qty,
                ordered_unit_cost=float(receipt.ordered_unit_cost),
                received_unit_cost=float(receipt.received_unit_cost),
                expected_arrival_date=receipt.expected_arrival_date,
                received_at=receipt.received_at,
                created_at=receipt.created_at,
            )
            for receipt in receipts
        ],
    )


def _line_identity_view(index, alias, duplicate_aliases):
    try:
        product = index.resolve(alias)
    except AmbiguousSkuError:
        return dict(product_id=None, identity_ambiguous=True,
                    identity_warning="This SKU matches multiple products. Existing purchase-order data is preserved; review identity before changing this line or recording a receipt.")
    return dict(product_id=product.id if product else None, identity_ambiguous=alias in duplicate_aliases,
                identity_warning="This SKU identifies multiple saved lines. Existing amounts are preserved; a receipt cannot choose a line by SKU alone."
                    if alias in duplicate_aliases else None)


def _parse_date(value: str):
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None
