"""Inventory value snapshots — capital tied up in stock over time.

Shopify can report what inventory is worth right now but not how that value
has changed, so merchants cannot tell whether their inventory investment is
growing or shrinking. We capture one roll-up per shop per UTC day; the chart
accrues history from the day a shop first syncs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Inventory, InventoryValueSnapshot, Product
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def capture_inventory_value_snapshot(db: DbSession, *, shop_id: int) -> InventoryValueSnapshot | None:
    """Upsert today's snapshot for one shop. Returns None for empty catalogs.

    Re-running on the same day refreshes the row, so the stored value reflects
    the last capture of the day.
    """
    row = db.execute(
        select(
            func.coalesce(func.sum(Inventory.quantity), 0),
            func.count(func.distinct(Inventory.product_id)),
            func.coalesce(func.sum(Inventory.quantity * func.coalesce(Product.cost, 0)), 0),
            func.coalesce(func.sum(Inventory.quantity * Product.price), 0),
        )
        .join(Product, Product.id == Inventory.product_id)
        .where(Inventory.shop_id == shop_id)
    ).one()
    total_units = int(row[0] or 0)
    sku_count = int(row[1] or 0)
    if sku_count == 0:
        return None

    today = _today_utc()
    snapshot = db.scalar(
        select(InventoryValueSnapshot).where(
            InventoryValueSnapshot.shop_id == shop_id,
            InventoryValueSnapshot.snapshot_date == today,
        )
    )
    if snapshot is None:
        snapshot = InventoryValueSnapshot(shop_id=shop_id, snapshot_date=today)
        db.add(snapshot)
    snapshot.total_units = total_units
    snapshot.sku_count = sku_count
    snapshot.total_cost_value = Decimal(str(round(float(row[2] or 0), 2)))
    snapshot.total_retail_value = Decimal(str(round(float(row[3] or 0), 2)))
    db.commit()
    return snapshot


def capture_all_inventory_snapshots() -> int:
    """Capture today's snapshot for every shop that has inventory rows."""
    captured = 0
    with SessionLocal() as db:
        shop_ids = [
            int(shop_id)
            for shop_id in db.scalars(select(Inventory.shop_id).distinct()).all()
        ]
        for shop_id in shop_ids:
            try:
                if capture_inventory_value_snapshot(db, shop_id=shop_id) is not None:
                    captured += 1
            except Exception:
                logger.exception("Inventory value snapshot failed for shop_id=%s", shop_id)
                db.rollback()
    return captured


def inventory_value_history(db: DbSession, *, shop_id: int, days: int = 90) -> list[dict]:
    rows = db.scalars(
        select(InventoryValueSnapshot)
        .where(InventoryValueSnapshot.shop_id == shop_id)
        .order_by(InventoryValueSnapshot.snapshot_date.desc())
        .limit(max(1, min(days, 365)))
    ).all()
    rows.reverse()
    return [
        {
            "date": snapshot.snapshot_date,
            "total_units": snapshot.total_units,
            "sku_count": snapshot.sku_count,
            "cost_value": float(snapshot.total_cost_value or 0),
            "retail_value": float(snapshot.total_retail_value or 0),
        }
        for snapshot in rows
    ]
