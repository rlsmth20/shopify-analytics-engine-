"""Co-purchase bundle opportunity scoring.

This is intentionally lightweight: it mines historical order lines for products
that appear together often enough to test as bundles, kits, or cross-sells. It
does not create Shopify bundles or discounts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OrderLineItem, Product
from app.schemas_v2 import BundleOpportunity


def recommend_bundle_opportunities(
    db: Session,
    shop_id: int,
    min_co_purchase_count: int = 3,
    limit: int = 25,
) -> tuple[list[BundleOpportunity], int]:
    rows = db.execute(
        select(
            OrderLineItem.shopify_order_id,
            OrderLineItem.product_id,
            OrderLineItem.quantity,
            OrderLineItem.price,
            Product.name,
            Product.sku,
            Product.category,
        )
        .join(Product, Product.id == OrderLineItem.product_id)
        .where(OrderLineItem.shop_id == shop_id)
        .where(Product.shop_id == shop_id)
    ).all()

    orders: dict[str, dict[int, dict[str, object]]] = defaultdict(dict)
    product_meta: dict[int, dict[str, object]] = {}

    for row in rows:
        product_id = int(row.product_id)
        line_revenue = float(row.quantity or 0) * float(row.price or 0)
        product_meta[product_id] = {
            "name": row.name,
            "sku": row.sku,
            "category": row.category,
        }
        current = orders[str(row.shopify_order_id)].setdefault(
            product_id,
            {"quantity": 0, "revenue": 0.0},
        )
        current["quantity"] = int(current["quantity"]) + int(row.quantity or 0)
        current["revenue"] = float(current["revenue"]) + line_revenue

    orders_analyzed = len(orders)
    if orders_analyzed == 0:
        return [], 0

    product_order_counts: Counter[int] = Counter()
    pair_counts: Counter[tuple[int, int]] = Counter()
    pair_revenue: Counter[tuple[int, int]] = Counter()

    for order_products in orders.values():
        product_ids = sorted(order_products)
        for product_id in product_ids:
            product_order_counts[product_id] += 1
        for left, right in combinations(product_ids, 2):
            pair = (left, right)
            pair_counts[pair] += 1
            pair_revenue[pair] += float(order_products[left]["revenue"]) + float(
                order_products[right]["revenue"]
            )

    opportunities: list[BundleOpportunity] = []
    for (left, right), count in pair_counts.items():
        if count < min_co_purchase_count:
            continue

        left_count = product_order_counts[left]
        right_count = product_order_counts[right]
        if left_count == 0 or right_count == 0:
            continue

        support = count / orders_analyzed
        confidence_a_to_b = count / left_count
        confidence_b_to_a = count / right_count
        baseline_b = right_count / orders_analyzed
        lift = confidence_a_to_b / baseline_b if baseline_b > 0 else None
        combined_revenue = float(pair_revenue[(left, right)])
        average_impact = combined_revenue / count if count else None
        opportunity_type = _opportunity_type(count, confidence_a_to_b, confidence_b_to_a, lift)
        left_meta = product_meta[left]
        right_meta = product_meta[right]

        opportunities.append(
            BundleOpportunity(
                id=f"{left}-{right}",
                product_a_id=left,
                product_a_name=str(left_meta["name"]),
                product_a_sku=left_meta.get("sku"),
                product_a_category=left_meta.get("category"),
                product_b_id=right,
                product_b_name=str(right_meta["name"]),
                product_b_sku=right_meta.get("sku"),
                product_b_category=right_meta.get("category"),
                co_purchase_count=count,
                support=round(support, 4),
                confidence_a_to_b=round(confidence_a_to_b, 4),
                confidence_b_to_a=round(confidence_b_to_a, 4),
                lift=round(lift, 2) if lift is not None else None,
                combined_revenue=round(combined_revenue, 2),
                average_order_value_impact=round(average_impact, 2)
                if average_impact is not None
                else None,
                opportunity_type=opportunity_type,
                suggested_action=_suggested_action(opportunity_type),
                explanation=(
                    f"Customers who buy {left_meta['name']} also bought "
                    f"{right_meta['name']} in {count} orders. "
                    f"Confidence: {confidence_a_to_b:.0%} of orders containing "
                    f"{left_meta['name']} also contained {right_meta['name']}."
                ),
            )
        )

    opportunities.sort(
        key=lambda item: (
            item.co_purchase_count,
            max(item.confidence_a_to_b, item.confidence_b_to_a),
            item.combined_revenue,
        ),
        reverse=True,
    )
    return opportunities[:limit], orders_analyzed


def _opportunity_type(
    count: int,
    confidence_a_to_b: float,
    confidence_b_to_a: float,
    lift: float | None,
) -> str:
    confidence = max(confidence_a_to_b, confidence_b_to_a)
    if count >= 20 and confidence >= 0.25:
        return "Bundle"
    if lift is not None and lift >= 1.5:
        return "Cross-sell"
    if confidence >= 0.15:
        return "Promo test"
    return "Watch"


def _suggested_action(opportunity_type: str) -> str:
    if opportunity_type == "Bundle":
        return "Create bundle"
    if opportunity_type == "Cross-sell":
        return "Add cross-sell"
    if opportunity_type == "Promo test":
        return "Test promo"
    return "Watch"


# ---------------------------------------------------------------------------
# Dead-stock pairings — clear slow stock by attaching it to a fast mover
# ---------------------------------------------------------------------------

DEAD_STOCK_DAYS = 45
MIN_ANCHOR_MONTHLY_UNITS = 5
DEAD_ITEM_DISCOUNT = 0.20
ATTACH_RATE = 0.20  # assumed share of anchor orders that take the bundle


def recommend_dead_stock_pairings(db: Session, shop_id: int, limit: int = 12):
    """Pair dead-stock SKUs with fast movers to clear them as bundles.

    Match preference: same category, then same vendor, then the overall
    fastest mover. The attach-rate assumption (20% of anchor volume) is stated
    in the explanation so merchants can judge the projection.
    """
    from app.schemas_v2 import DeadStockPairing, DeadStockPairingsResponse
    from app.services.shop_skus import load_skus_for_shop

    skus = load_skus_for_shop(db, shop_id)
    dead = [
        sku for sku in skus
        if sku.inventory > 0 and sku.days_since_last_sale >= DEAD_STOCK_DAYS
    ]
    anchors = sorted(
        (
            sku for sku in skus
            if sku.inventory > 0
            and sku.last_30_day_sales >= MIN_ANCHOR_MONTHLY_UNITS
            and sku.days_since_last_sale < DEAD_STOCK_DAYS
        ),
        key=lambda sku: sku.last_30_day_sales,
        reverse=True,
    )
    dead_capital = round(sum(sku.inventory * sku.cost for sku in dead), 2)
    if not dead or not anchors:
        return DeadStockPairingsResponse(
            pairings=[],
            dead_stock_sku_count=len(dead),
            dead_stock_capital=dead_capital,
        )

    dead.sort(key=lambda sku: sku.inventory * sku.cost, reverse=True)
    pairings: list[DeadStockPairing] = []
    for dead_sku in dead[: limit * 2]:
        anchor, reason = _best_anchor(dead_sku, anchors)
        if anchor is None:
            continue

        bundle_price = round(anchor.price + dead_sku.price * (1 - DEAD_ITEM_DISCOUNT), 2)
        bundle_cost = round(anchor.cost + dead_sku.cost, 2)
        margin_pct = (
            round((bundle_price - bundle_cost) / bundle_price * 100, 1)
            if bundle_price > 0
            else 0.0
        )
        monthly_bundles = max(1, int(anchor.last_30_day_sales * ATTACH_RATE))
        months_to_clear = (
            round(dead_sku.inventory / monthly_bundles, 1) if monthly_bundles else None
        )
        capital = round(dead_sku.inventory * dead_sku.cost, 2)
        recovered = round(
            min(dead_sku.inventory, monthly_bundles * 3)
            * dead_sku.price
            * (1 - DEAD_ITEM_DISCOUNT),
            2,
        )

        pairings.append(
            DeadStockPairing(
                id=f"{anchor.sku_id}+{dead_sku.sku_id}",
                anchor_product_name=anchor.name,
                anchor_sku=anchor.sku_id,
                anchor_monthly_units=anchor.last_30_day_sales,
                anchor_price=round(anchor.price, 2),
                anchor_cost=round(anchor.cost, 2),
                dead_product_name=dead_sku.name,
                dead_sku=dead_sku.sku_id,
                dead_on_hand=dead_sku.inventory,
                dead_days_since_last_sale=dead_sku.days_since_last_sale,
                dead_price=round(dead_sku.price, 2),
                dead_cost=round(dead_sku.cost, 2),
                dead_capital_tied_up=capital,
                match_reason=reason,
                suggested_bundle_price=bundle_price,
                bundle_unit_cost=bundle_cost,
                bundle_margin_pct=margin_pct,
                estimated_monthly_bundles=monthly_bundles,
                estimated_months_to_clear=months_to_clear,
                projected_cash_recovered=recovered,
                explanation=(
                    f"{dead_sku.name} has not sold in {dead_sku.days_since_last_sale} days "
                    f"with ${capital:,.0f} tied up in {dead_sku.inventory} units. "
                    f"{anchor.name} sells {anchor.last_30_day_sales} units/month ({reason}). "
                    f"Bundled at ${bundle_price:,.2f} ({int(DEAD_ITEM_DISCOUNT * 100)}% off the slow item), "
                    f"a {int(ATTACH_RATE * 100)}% attach rate moves ~{monthly_bundles} bundles/month "
                    f"at {margin_pct:.0f}% margin - projected ${recovered:,.0f} recovered in the first quarter."
                ),
            )
        )
        if len(pairings) >= limit:
            break

    pairings.sort(key=lambda p: p.dead_capital_tied_up, reverse=True)
    return DeadStockPairingsResponse(
        pairings=pairings,
        dead_stock_sku_count=len(dead),
        dead_stock_capital=dead_capital,
    )


def _best_anchor(dead_sku, anchors):
    """Pick the strongest anchor, preferring catalog affinity over raw speed."""
    for anchor in anchors:
        if anchor.sku_id == dead_sku.sku_id:
            continue
        if dead_sku.category and anchor.category == dead_sku.category:
            return anchor, f"same category: {anchor.category}"
    for anchor in anchors:
        if anchor.sku_id == dead_sku.sku_id:
            continue
        if dead_sku.vendor and anchor.vendor == dead_sku.vendor:
            return anchor, f"same vendor: {anchor.vendor}"
    for anchor in anchors:
        if anchor.sku_id != dead_sku.sku_id:
            return anchor, "store's fastest mover"
    return None, ""
