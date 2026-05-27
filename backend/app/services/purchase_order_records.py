"""Persisted purchase order lifecycle and receipt observations."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import (
    PurchaseOrderLineRecord,
    PurchaseOrderReceiptRecord,
    PurchaseOrderRecord,
)
from app.schemas_v2 import PurchaseOrderDraft, PurchaseOrderLine
from app.services.supplier_scoring import SupplierObservation


def list_saved_purchase_orders(db: DbSession, shop_id: int) -> list[PurchaseOrderDraft]:
    rows = db.scalars(
        select(PurchaseOrderRecord)
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .order_by(PurchaseOrderRecord.updated_at.desc())
    ).all()
    return [_record_to_schema(db, row) for row in rows]


def save_purchase_order(
    db: DbSession,
    *,
    shop_id: int,
    draft: PurchaseOrderDraft,
) -> PurchaseOrderDraft:
    record = db.scalar(
        select(PurchaseOrderRecord)
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .where(PurchaseOrderRecord.po_id == draft.po_id)
    )
    if record is None:
        record = PurchaseOrderRecord(shop_id=shop_id, po_id=draft.po_id)
        db.add(record)
        db.flush()
    else:
        old_lines = db.scalars(
            select(PurchaseOrderLineRecord).where(
                PurchaseOrderLineRecord.purchase_order_id == record.id
            )
        ).all()
        for line in old_lines:
            db.delete(line)
        db.flush()

    record.vendor = draft.vendor
    record.status = draft.status
    record.total_cost = Decimal(str(draft.total_cost))
    record.expected_arrival_date = draft.expected_arrival_date
    record.rationale = draft.rationale
    record.sent_at = draft.sent_at
    record.received_at = draft.received_at

    for line in draft.lines:
        db.add(
            PurchaseOrderLineRecord(
                shop_id=shop_id,
                purchase_order_id=record.id,
                sku_id=line.sku_id,
                name=line.name,
                qty=line.qty,
                unit_cost=Decimal(str(line.unit_cost)),
                extended_cost=Decimal(str(line.extended_cost)),
                received_qty=0,
            )
        )
    db.commit()
    db.refresh(record)
    return _record_to_schema(db, record)


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
    record = _get_record(db, shop_id, po_id)
    if record is None:
        return None
    received_at = received_at or datetime.now(timezone.utc)
    lines = db.scalars(
        select(PurchaseOrderLineRecord).where(PurchaseOrderLineRecord.purchase_order_id == record.id)
    ).all()
    for line in lines:
        if line.sku_id not in received_lines:
            continue
        qty, received_unit_cost = received_lines[line.sku_id]
        line.received_qty = max(line.received_qty, qty)
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
    record.status = "received" if all(line.received_qty >= line.qty for line in lines) else "sent"
    db.commit()
    db.refresh(record)
    return _record_to_schema(db, record)


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


def _get_record(db: DbSession, shop_id: int, po_id: str) -> PurchaseOrderRecord | None:
    return db.scalar(
        select(PurchaseOrderRecord)
        .where(PurchaseOrderRecord.shop_id == shop_id)
        .where(PurchaseOrderRecord.po_id == po_id)
    )


def _record_to_schema(db: DbSession, record: PurchaseOrderRecord) -> PurchaseOrderDraft:
    lines = db.scalars(
        select(PurchaseOrderLineRecord).where(PurchaseOrderLineRecord.purchase_order_id == record.id)
    ).all()
    return PurchaseOrderDraft(
        po_id=record.po_id,
        vendor=record.vendor,
        created_at=record.created_at,
        status=record.status,
        lines=[
            PurchaseOrderLine(
                sku_id=line.sku_id,
                name=line.name,
                qty=line.qty,
                unit_cost=float(line.unit_cost),
                extended_cost=float(line.extended_cost),
            )
            for line in lines
        ],
        total_cost=float(record.total_cost),
        expected_arrival_date=record.expected_arrival_date,
        rationale=record.rationale,
        approved_at=record.approved_at,
        approved_by_user_id=record.approved_by_user_id,
        sent_at=record.sent_at,
        received_at=record.received_at,
    )


def _parse_date(value: str):
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None
