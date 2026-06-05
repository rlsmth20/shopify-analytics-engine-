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
