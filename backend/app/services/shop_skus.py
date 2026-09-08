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
from typing import List

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Inventory, OrderLineItem, Product, ShopifySyncRun
from app.schemas import SkuDetail, SkuIdentityIssue
from app.services.transfers import LocationStock
from app.services.cost_provenance import unit_cost_details

MIN_OBSERVED_HISTORY_DAYS = 30
MAX_ORDER_SYNC_AGE = timedelta(days=2)


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


IDENTITY_WARNING = "Multiple current products share this SKU code. Review and assign distinct SKU codes in the source catalog before forecasting, purchasing, or clearing this stock; recorded stock and sales are preserved."


class AmbiguousSkuError(ValueError):
    def __init__(self, sku_id: str, product_ids: list[int]):
        self.sku_id = sku_id
        self.product_ids = sorted(product_ids)
        super().__init__(f"SKU '{sku_id}' matches multiple products. Review the SKU mapping before changing this item.")


class SkuAliasIndex:
    """Resolve aliases without merging product history or choosing an arbitrary row."""
    def __init__(self, products: list[Product], active_product_ids: set[int]):
        self._candidates: dict[str, list[Product]] = {}
        self._alias_by_product = {product.id: _slugified_sku_id_for_product(product) for product in products}
        for product in products:
            for alias in {_slugified_sku_id_for_product(product), product.sku} - {None, ""}:
                self._candidates.setdefault(alias, []).append(product)
        # Filter each alias once, including when many variants reuse one code.
        for alias, candidates in self._candidates.items():
            active = [product for product in candidates if product.id in active_product_ids]
            self._candidates[alias] = active or candidates

    def _eligible(self, sku_id: str) -> list[Product]:
        return self._candidates.get(sku_id, [])

    def is_ambiguous(self, sku_id: str) -> bool:
        return len(self._eligible(sku_id)) > 1

    def is_authoritative_product(self, product_id: int) -> bool:
        """Whether this row owns its alias (including a unique history-only row)."""
        alias = self._alias_by_product.get(product_id)
        candidates = self._eligible(alias) if alias is not None else []
        return len(candidates) == 1 and candidates[0].id == product_id

    def resolve(self, sku_id: str) -> Product | None:
        candidates = self._eligible(sku_id)
        if len(candidates) > 1:
            raise AmbiguousSkuError(sku_id, [product.id for product in candidates])
        return candidates[0] if candidates else None


def build_sku_alias_index(db: Session, shop_id: int) -> SkuAliasIndex:
    products = list(db.scalars(select(Product).where(Product.shop_id == shop_id)).all())
    active_ids = set(db.scalars(select(Inventory.product_id).where(Inventory.shop_id == shop_id).distinct()).all())
    return SkuAliasIndex(products, active_ids)


def sku_identity_issues(skus: list[SkuDetail]) -> list[SkuIdentityIssue]:
    return [SkuIdentityIssue(product_id=sku.product_id, sku_id=sku.sku_id, name=sku.name,
                current_on_hand=sku.inventory, message=sku.identity_warning or IDENTITY_WARNING)
            for sku in skus if sku.identity_ambiguous and sku.product_id is not None]


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
            func.min(OrderLineItem.created_at).label("first_sale_at"),
            func.max(OrderLineItem.created_at).label("last_sale_at"),
        )
        .where(OrderLineItem.shop_id == shop_id,
               OrderLineItem.quantity > 0,
               OrderLineItem.created_at <= now)
        .group_by(OrderLineItem.product_id)
    ).all()

    sales_by_product: dict[int, dict] = {
        row.product_id: {
            "sales_30d": int(row.sales_30d or 0),
            "sales_7d": int(row.sales_7d or 0),
            "first_sale_at": row.first_sale_at,
            "last_sale_at": row.last_sale_at,
        }
        for row in sales_rows
    }
    latest_finished_sync = db.scalar(
        select(ShopifySyncRun)
        .where(ShopifySyncRun.shop_id == shop_id, ShopifySyncRun.status != "running")
        .order_by(ShopifySyncRun.id.desc())
        .limit(1)
    )

    alias_index = SkuAliasIndex(list(products), set(on_hand_by_product))
    skus: list[SkuDetail] = []
    for p in products:
        if p.id not in on_hand_by_product:
            continue

        sales = sales_by_product.get(p.id, {})
        last_sale = sales.get("last_sale_at")
        if last_sale is None:
            # Retain the legacy numeric sentinel, but never treat it as proof of
            # age: sales_history_complete gates stale-stock recommendations.
            days_since = 999
        else:
            ls = last_sale.replace(tzinfo=None) if last_sale.tzinfo is not None else last_sale
            days_since = max(0, (now - ls).days)

        sku_id = (p.sku or _slugify(p.name, p.variant_name, str(p.id)))[:128]
        history_warnings = _sales_history_warnings(sales.get("first_sale_at"), now, latest_finished_sync)
        first_sale = sales.get("first_sale_at")
        if first_sale is not None and first_sale.tzinfo is not None:
            first_sale = first_sale.astimezone(timezone.utc)
        # Daily forecast buckets end yesterday in UTC. A sale yesterday evening
        # is one observed bucket even when fewer than 24 hours have elapsed.
        observed_days = max(0, (now.date() - first_sale.date()).days) if first_sale is not None else 0

        skus.append(
            SkuDetail(
                sku_id=sku_id,
                product_id=p.id,
                identity_ambiguous=alias_index.is_ambiguous(sku_id),
                identity_warning=IDENTITY_WARNING if alias_index.is_ambiguous(sku_id) else None,
                name=p.name + (f" / {p.variant_name}" if p.variant_name else ""),
                vendor=p.vendor or "Unassigned",
                category=p.category or "uncategorized",
                price=float(p.price or 0),
                cost=_resolve_unit_cost(p),
                cost_source=unit_cost_details(p)[1],
                inventory=on_hand_by_product.get(p.id, 0),
                last_30_day_sales=sales.get("sales_30d", 0),
                last_7_day_sales=sales.get("sales_7d", 0),
                days_since_last_sale=days_since,
                sku_lead_time_days=p.sku_lead_time_days,
                observed_history_days=observed_days,
                sales_history_complete=not history_warnings,
                sales_history_warnings=history_warnings,
            )
        )

    return skus


def _sales_history_warnings(first_sale: datetime | None, now: datetime,
                            latest_sync: ShopifySyncRun | None) -> list[str]:
    """Use observed history conservatively without requiring sync metadata for CSVs.

    A first sale is evidence of observation, not product age. Missing or less than
    30 days of observed sales cannot justify excess/dead-stock conclusions. A
    completed Shopify sync also needs to be successful and no more than two days
    old. Established imported history with no Shopify run keeps its prior behavior.
    """
    warnings: list[str] = []
    if first_sale is None:
        warnings.append("No sales are recorded for this SKU; missing order history does not establish that stock is stale.")
    else:
        first_sale = first_sale.replace(tzinfo=None)
        history_days = max(0, (now - first_sale).days)
        if history_days < MIN_OBSERVED_HISTORY_DAYS:
            warnings.append(f"Only {history_days} days since the first recorded sale; demand estimates use limited history.")
    if latest_sync is not None:
        if latest_sync.status != "succeeded" or latest_sync.finished_at is None:
            warnings.append("The latest Shopify sync did not complete successfully; verify order-history coverage.")
        elif now - latest_sync.finished_at.replace(tzinfo=None) > MAX_ORDER_SYNC_AGE:
            warnings.append("Shopify order history has not been refreshed in more than two days; sync before clearing stock.")
    return warnings


def _resolve_unit_cost(product: Product) -> float:
    return unit_cost_details(product)[0]


def _slugified_sku_id_for_product(p: Product) -> str:
    """Mirror the SKU-id rule used in load_skus_for_shop so callers that
    receive a sku_id from the API can map back to a product row.
    """
    return (p.sku or _slugify(p.name, p.variant_name, str(p.id)))[:128]


def _resolve_product_id_for_sku(db: Session, shop_id: int, sku_id: str) -> int | None:
    """Use current inventory ownership; ambiguous aliases fail explicitly."""
    product = build_sku_alias_index(db, shop_id).resolve(sku_id)
    return product.id if product is not None else None


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

    This avoids per-SKU queries. Absent aliases keep legacy zero padding, while
    ambiguous aliases are omitted and must remain explicitly unavailable in the
    read projection. Single-alias lookup raises AmbiguousSkuError instead.
    """
    if days <= 0 or not sku_ids:
        return {sku_id: [] for sku_id in sku_ids}

    index = build_sku_alias_index(db, shop_id)
    # Ambiguous aliases are omitted, never presented as another variant's history
    # or as observed zero sales. Feed consumers expose an explicit review hold.
    eligible_ids = [sku_id for sku_id in dict.fromkeys(sku_ids) if not index.is_ambiguous(sku_id)]
    product_id_by_sku = {}
    for sku_id in eligible_ids:
        product = index.resolve(sku_id)
        if product is not None:
            product_id_by_sku[sku_id] = product.id
    sku_ids = eligible_ids

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


def load_location_stocks_for_shop(db: Session, shop_id: int) -> list[LocationStock]:
    """Build per-location stock snapshots for transfer recommendations.

    Shopify gives inventory by location, while order history is currently shop-wide.
    Until location-specific demand lands, allocate each SKU's recent velocity across
    locations in proportion to on-hand stock, with a small floor so low-stock
    locations can still be identified as transfer candidates.
    """
    products = db.scalars(select(Product).where(Product.shop_id == shop_id)).all()
    if not products:
        return []

    now = _now_naive_utc()
    thirty_days_ago = now - timedelta(days=30)
    sales_rows = db.execute(
        select(
            OrderLineItem.product_id,
            func.coalesce(func.sum(OrderLineItem.quantity), 0).label("sales_30d"),
        )
        .where(OrderLineItem.shop_id == shop_id)
        .where(OrderLineItem.created_at >= thirty_days_ago)
        .group_by(OrderLineItem.product_id)
    ).all()
    sales_by_product = {int(row.product_id): int(row.sales_30d or 0) for row in sales_rows}

    inventory_rows = db.scalars(
        select(Inventory).where(Inventory.shop_id == shop_id)
    ).all()
    by_product: dict[int, list[Inventory]] = {}
    for row in inventory_rows:
        by_product.setdefault(row.product_id, []).append(row)

    alias_index = SkuAliasIndex(list(products), set(by_product))
    snapshots: list[LocationStock] = []
    for product in products:
        if alias_index.is_ambiguous(_slugified_sku_id_for_product(product)):
            continue
        rows = [row for row in by_product.get(product.id, []) if row.quantity > 0]
        if len(rows) < 2:
            continue

        total_on_hand = sum(row.quantity for row in rows)
        total_velocity = sales_by_product.get(product.id, 0) / 30
        if total_velocity <= 0 or total_on_hand <= 0:
            continue

        sku_id = _slugified_sku_id_for_product(product)
        name = product.name + (f" / {product.variant_name}" if product.variant_name else "")
        location_count = len(rows)
        for row in rows:
            inventory_share = row.quantity / total_on_hand
            equal_share = 1 / location_count
            allocated_velocity = total_velocity * ((inventory_share + equal_share) / 2)
            snapshots.append(
                LocationStock(
                    sku_id=sku_id,
                    name=name,
                    location=row.shopify_location_id,
                    on_hand=row.quantity,
                    daily_velocity=max(allocated_velocity, 0.01),
                )
            )

    return snapshots


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
