"""Per-shop SKU loader — replaces MOCK_SKUS with real database rows.

Every dashboard / forecast / supplier / etc. service was originally
designed against `MOCK_SKUS: list[SkuDetail]`. To stay surgical we keep
that shape and add this single loader, which queries Product / Inventory
/ OrderLineItem for one shop_id and returns the equivalent list.

A shop with no imported data returns an empty list — every consumer
must handle that case (typically by returning an empty response and
letting the frontend render a "no data yet" state).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Inventory, OrderLineItem, Product
from app.schemas import SkuDetail

DEFAULT_COST_RATIO = Decimal("0.40")


def _now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slugify(*parts: str | None) -> str:
    """Stable SKU id from product fields when no native SKU is set."""
    bits = []
    for p in parts:
        if p is None:
            continue
        s = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(p))
        s = "-".join(filter(None, s.split("-")))
        if s:
            bits.append(s)
    return "-".join(bits) or "sku-unknown"


def load_skus_for_shop(db: Session, shop_id: int) -> List[SkuDetail]:
    """Build the SkuDetail list for a single shop from the database.

    Sales aggregates are computed in two trips for clarity (one for the
    30-day window, one for the 7-day window, one for last-sale date).
    All windows are anchored on `now()` rather than the latest order date —
    if a shop hasn't imported recent orders we want their dashboard to
    reflect that staleness rather than silently shifting the window.
    """
    products = db.scalars(
        select(Product).where(Product.shop_id == shop_id)
    ).all()
    if not products:
        return []

    # Aggregate inventory across locations, per product.
    inv_rows = db.execute(
        select(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.quantity), 0).label("on_hand"),
        )
        .where(Inventory.shop_id == shop_id)
        .group_by(Inventory.product_id)
    ).all()
    on_hand_by_product: dict[int, int] = {row.product_id: int(row.on_hand) for row in inv_rows}

    now = _now_naive_utc()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Sum quantities sold per product in 30 / 7 day windows, plus latest sale date.
    sales_rows = db.execute(
        select(
            OrderLineItem.product_id,
            func.coalesce(
                func.sum(
                    case((OrderLineItem.created_at >= thirty_days_ago, OrderLineItem.quantity), else_=0)
                ),
                0,
            ).label("sales_30d"),
            func.coalesce(
                func.sum(
                    case((OrderLineItem.created_at >= seven_days_ago, OrderLineItem.quantity), else_=0)
                ),
                0,
            ).label("sales_7d"),
            func.max(OrderLineItem.created_at).label("last_sale_at"),
        )
        .where(OrderLineItem.shop_id == shop_id)
        .group_by(OrderLineItem.product_id)
    ).all()

    sales_by_product: dict[int, dict] = {
        row.product_id: {
            "sales_30d": int(row.sales_30d or 0),
            "sales_7d": int(row.sales_7d or 0),
            "last_sale_at": row.last_sale_at,
        }
        for row in sales_rows
    }

    skus: list[SkuDetail] = []
    for p in products:
        if p.id not in on_hand_by_product:
            continue

        sales = sales_by_product.get(p.id, {})
        last_sale = sales.get("last_sale_at")
        if last_sale is None:
            days_since = 999  # Treat "never sold" as very stale.
        else:
            ls = last_sale.replace(tzinfo=None) if last_sale.tzinfo is not None else last_sale
            days_since = max(0, (now - ls).days)

        sku_id = (p.sku or _slugify(p.name, p.variant_name, str(p.id)))[:128]

        skus.append(
            SkuDetail(
                sku_id=sku_id,
                name=p.name + (f" / {p.variant_name}" if p.variant_name else ""),
                vendor=p.vendor or "Unassigned",
                category=p.category or "uncategorized",
                price=float(p.price or 0),
                cost=_resolve_unit_cost(p),
                inventory=on_hand_by_product.get(p.id, 0),
                last_30_day_sales=sales.get("sales_30d", 0),
                last_7_day_sales=sales.get("sales_7d", 0),
                days_since_last_sale=days_since,
                sku_lead_time_days=p.sku_lead_time_days,
            )
        )

    return skus


def _resolve_unit_cost(product: Product) -> float:
    if product.cost is not None and product.cost > 0:
        return float(product.cost)

    if product.price is not None and product.price > 0:
        return float((product.price * DEFAULT_COST_RATIO).quantize(Decimal("0.01")))

    return 0.0


def _slugified_sku_id_for_product(p: Product) -> str:
    """Mirror the SKU-id rule used in load_skus_for_shop so callers that
    receive a sku_id from the API can map back to a product row.
    """
    return (p.sku or _slugify(p.name, p.variant_name, str(p.id)))[:128]


def _resolve_product_id_for_sku(db: Session, shop_id: int, sku_id: str) -> int | None:
    """Find the Product row id for a given external sku_id within one shop.

    Looks up by Product.sku first, then falls back to the slugified id.
    Returns None if no product matches — callers should treat that as
    "no history" rather than crashing.
    """
    direct = db.scalar(
        select(Product.id)
        .where(Product.shop_id == shop_id)
        .where(Product.sku == sku_id)
    )
    if direct is not None:
        return int(direct)

    # Fallback: scan products for one whose slug matches.
    products = db.scalars(
        select(Product).where(Product.shop_id == shop_id)
    ).all()
    for p in products:
        if _slugified_sku_id_for_product(p) == sku_id:
            return int(p.id)
    return None


def load_daily_history_for_shop_sku(
    db: Session,
    shop_id: int,
    sku_id: str,
    days: int = 90,
) -> List[int]:
    """Return a list of `days` daily quantities sold (oldest first).

    The returned list always has length `days`. Days with no orders are
    zero. The window ends at "today" — `_now_naive_utc()` — so a fresh
    shop with no recent imports gets a list of all zeros (which the
    forecasting engine treats as "no demand signal").
    """
    if days <= 0:
        return []

    product_id = _resolve_product_id_for_sku(db, shop_id, sku_id)
    if product_id is None:
        return [0] * days

    now = _now_naive_utc()
    start = now - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(OrderLineItem.created_at).label("day"),
            func.coalesce(func.sum(OrderLineItem.quantity), 0).label("qty"),
        )
        .where(OrderLineItem.shop_id == shop_id)
        .where(OrderLineItem.product_id == product_id)
        .where(OrderLineItem.created_at >= start)
        .group_by(func.date(OrderLineItem.created_at))
    ).all()
    qty_by_day: dict[str, int] = {str(row.day): int(row.qty or 0) for row in rows}

    history: list[int] = []
    for offset in range(days, 0, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        history.append(qty_by_day.get(day, 0))
    return history


def load_daily_history_for_shop_skus(
    db: Session,
    shop_id: int,
    sku_ids: list[str],
    days: int = 90,
) -> dict[str, List[int]]:
    """Return daily histories for many SKUs with one aggregate query.

    This avoids the per-SKU query loop on forecast, analytics, dashboard, and
    reorder endpoints. Unknown SKUs still receive an all-zero history so callers
    can treat the result exactly like repeated load_daily_history_for_shop_sku.
    """
    if days <= 0 or not sku_ids:
        return {sku_id: [] for sku_id in sku_ids}

    products = db.scalars(
        select(Product).where(Product.shop_id == shop_id)
    ).all()
    product_id_by_sku: dict[str, int] = {}
    for product in products:
        product_id_by_sku[_slugified_sku_id_for_product(product)] = int(product.id)
        if product.sku:
            product_id_by_sku[product.sku] = int(product.id)

    product_ids = {
        product_id_by_sku[sku_id]
        for sku_id in sku_ids
        if sku_id in product_id_by_sku
    }
    empty_history = [0] * days
    if not product_ids:
        return {sku_id: list(empty_history) for sku_id in sku_ids}

    now = _now_naive_utc()
    start = now - timedelta(days=days)
    rows = db.execute(
        select(
            OrderLineItem.product_id,
            func.date(OrderLineItem.created_at).label("day"),
            func.coalesce(func.sum(OrderLineItem.quantity), 0).label("qty"),
        )
        .where(OrderLineItem.shop_id == shop_id)
        .where(OrderLineItem.product_id.in_(product_ids))
        .where(OrderLineItem.created_at >= start)
        .group_by(OrderLineItem.product_id, func.date(OrderLineItem.created_at))
    ).all()

    qty_by_product_day: dict[int, dict[str, int]] = {}
    for row in rows:
        qty_by_product_day.setdefault(int(row.product_id), {})[str(row.day)] = int(row.qty or 0)

    histories: dict[str, List[int]] = {}
    day_keys = [
        (now - timedelta(days=offset)).date().isoformat()
        for offset in range(days, 0, -1)
    ]
    for sku_id in sku_ids:
        product_id = product_id_by_sku.get(sku_id)
        if product_id is None:
            histories[sku_id] = list(empty_history)
            continue
        qty_by_day = qty_by_product_day.get(product_id, {})
        histories[sku_id] = [qty_by_day.get(day, 0) for day in day_keys]

    return histories


def load_recent_daily_revenue_for_shop(
    db: Session,
    shop_id: int,
    days: int = 30,
) -> List[tuple[int, float]]:
    """List of (offset_days, revenue) tuples, oldest first.

    Mirrors mock_data_v2.recent_daily_revenue. Revenue is per-line-item
    price * quantity summed by day; same window rule as above.
    """
    if days <= 0:
        return []

    now = _now_naive_utc()
    start = now - timedelta(days=days)
    rows = db.execute(
        select(
            func.date(OrderLineItem.created_at).label("day"),
            func.coalesce(
                func.sum(OrderLineItem.quantity * OrderLineItem.price), 0
            ).label("rev"),
        )
        .where(OrderLineItem.shop_id == shop_id)
        .where(OrderLineItem.created_at >= start)
        .group_by(func.date(OrderLineItem.created_at))
    ).all()
    rev_by_day: dict[str, float] = {str(row.day): float(row.rev or 0) for row in rows}

    points: list[tuple[int, float]] = []
    for offset in range(days, 0, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        points.append((offset, rev_by_day.get(day, 0.0)))
    return points


def start_weekday_for_shop_history(
    db: Session,
    shop_id: int,
    days: int = 90,
) -> int:
    """Return the weekday (0=Monday..6=Sunday) of the first day in the
    history window. Used by forecasting for seasonality alignment.
    """
    now = _now_naive_utc()
    start = now - timedelta(days=days)
    return start.weekday()
