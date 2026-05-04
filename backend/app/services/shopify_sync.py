"""Shopify ingestion runner — pulls products / inventory / orders via Admin GraphQL.

Designed for the live OAuth-connected case. Reuses the existing Product /
Inventory / OrderLineItem persistence so dashboard / forecast / actions
read the same shape regardless of whether data came from CSV or API.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Inventory, OrderLineItem, Product, ShopifyConnection, ShopifySyncRun

logger = logging.getLogger(__name__)


GRAPHQL_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-01")


def _gql(domain: str, token: str, query: str, variables: Optional[dict] = None) -> dict:
    """Call Shopify Admin GraphQL and return the parsed JSON response."""
    url = f"https://{domain}/admin/api/{GRAPHQL_VERSION}/graphql.json"
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


PRODUCTS_QUERY = """
query Products($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        vendor
        productType
        variants(first: 50) {
          edges {
            node {
              id
              sku
              title
              price
              inventoryItem { unitCost { amount } }
              inventoryQuantity
            }
          }
        }
      }
    }
  }
}
"""

ORDERS_QUERY = """
query Orders($cursor: String, $query: String) {
  orders(first: 100, after: $cursor, query: $query) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        createdAt
        lineItems(first: 50) {
          edges {
            node {
              id
              sku
              quantity
              variant { id }
              originalUnitPriceSet { shopMoney { amount } }
            }
          }
        }
      }
    }
  }
}
"""


def _shopify_id_to_str(gid: str) -> str:
    return gid.split("/")[-1] if gid else gid


def _ingest_products(db: DbSession, *, shop_id: int, domain: str, token: str) -> int:
    """Pull products + variants + inventory snapshot. Returns count of variants."""
    cursor = None
    count = 0
    while True:
        result = _gql(domain, token, PRODUCTS_QUERY, {"cursor": cursor})
        # Surface GraphQL-level errors so we can see scope / permission failures.
        gql_errors = result.get("errors")
        if gql_errors:
            logger.error("Shopify products GraphQL errors: %s", gql_errors)
            raise RuntimeError(f"Shopify products query failed: {gql_errors}")
        # Use `or {}` after every .get() because Shopify's GraphQL can return
        # explicit nulls that dict.get() does NOT replace with its default.
        data = result.get("data") or {}
        products = data.get("products") or {}
        edges = products.get("edges") or []
        for edge in edges:
            node = edge.get("node") or {}
            if not node:
                continue
            shopify_product_id = _shopify_id_to_str(node.get("id") or "")
            if not shopify_product_id:
                continue
            vendor = (node.get("vendor") or "").strip() or None
            category = (node.get("productType") or "").strip() or None
            base_name = node.get("title") or "Untitled product"
            variants = node.get("variants") or {}
            v_edges = variants.get("edges") or []
            for vedge in v_edges:
                v = vedge.get("node") or {}
                if not v:
                    continue
                shopify_variant_id = _shopify_id_to_str(v.get("id") or "")
                if not shopify_variant_id:
                    continue
                sku = (v.get("sku") or "").strip() or None
                variant_title = (v.get("title") or "").strip() or None
                if variant_title and variant_title.lower() == "default title":
                    variant_title = None
                price_raw = v.get("price") or "0"
                try:
                    price = Decimal(str(price_raw))
                except Exception:
                    price = Decimal("0")
                cost_amount = (
                    (v.get("inventoryItem") or {}).get("unitCost") or {}
                ).get("amount")
                try:
                    cost = Decimal(str(cost_amount)) if cost_amount is not None else None
                except Exception:
                    cost = None
                qty = int(v.get("inventoryQuantity") or 0)

                product = db.scalar(
                    select(Product).where(
                        Product.shop_id == shop_id,
                        Product.shopify_variant_id == shopify_variant_id,
                    )
                )
                if product is None:
                    product = Product(
                        shop_id=shop_id,
                        shopify_product_id=shopify_product_id,
                        shopify_variant_id=shopify_variant_id,
                        sku=sku,
                        name=base_name,
                        variant_name=variant_title,
                        vendor=vendor,
                        category=category,
                        price=price,
                        cost=cost,
                    )
                    db.add(product)
                    db.flush()
                else:
                    product.shopify_product_id = shopify_product_id
                    product.sku = sku
                    product.name = base_name
                    product.variant_name = variant_title
                    product.vendor = vendor
                    product.category = category
                    product.price = price
                    if cost is not None:
                        product.cost = cost

                # Inventory: store an aggregate row per variant. Multi-location
                # split lands when we wire InventoryLevel per location below.
                inv = db.scalar(
                    select(Inventory).where(
                        Inventory.shop_id == shop_id,
                        Inventory.product_id == product.id,
                        Inventory.shopify_location_id == "aggregate",
                    )
                )
                if inv is None:
                    inv = Inventory(
                        shop_id=shop_id,
                        product_id=product.id,
                        shopify_location_id="aggregate",
                        quantity=qty,
                    )
                    db.add(inv)
                else:
                    inv.quantity = qty
                count += 1
        db.commit()
        page_info = (((result.get("data") or {}).get("products") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return count


def _ingest_orders(db: DbSession, *, shop_id: int, domain: str, token: str, days_back: int = 180) -> int:
    """Pull orders within the last `days_back` days. Returns count of line items."""
    # Shopify's search-query language wants ISO 8601 without microseconds and
    # ideally with a Z suffix (not +00:00). datetime.isoformat() produces
    # the latter, which Shopify silently rejects → zero orders returned.
    since_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"created_at:>={since}"
    cursor = None
    count = 0
    pages_seen = 0

    # Pre-build a variant -> product_id map for fast joins.
    variant_to_product: dict[str, int] = {}
    rows = db.execute(
        select(Product.id, Product.shopify_variant_id).where(Product.shop_id == shop_id)
    ).all()
    for pid, vid in rows:
        if vid:
            variant_to_product[str(vid)] = int(pid)

    logger.info(
        "orders ingest start: shop_id=%s since=%s products_indexed=%s",
        shop_id, since, len(variant_to_product),
    )

    while True:
        result = _gql(domain, token, ORDERS_QUERY, {"cursor": cursor, "query": query})
        # Surface GraphQL-level errors (invalid query syntax, bad scope, etc.)
        # so we know WHY orders are missing instead of silently getting zero.
        gql_errors = result.get("errors")
        if gql_errors:
            logger.error("Shopify orders GraphQL errors: %s", gql_errors)
            raise RuntimeError(f"Shopify orders query failed: {gql_errors}")
        data = result.get("data") or {}
        orders = data.get("orders") or {}
        edges = orders.get("edges") or []
        pages_seen += 1
        logger.info(
            "orders page %s: edges=%s cursor=%s",
            pages_seen, len(edges), cursor,
        )
        for edge in edges:
            order = edge.get("node") or {}
            if not order:
                continue
            order_id = _shopify_id_to_str(order.get("id") or "")
            if not order_id:
                continue
            try:
                created_at_raw = order.get("createdAt") or ""
                created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            except Exception:
                created_at = datetime.now(timezone.utc)
            line_items = order.get("lineItems") or {}
            li_edges = line_items.get("edges") or []
            for liedge in li_edges:
                li = liedge.get("node") or {}
                if not li:
                    continue
                variant = li.get("variant") or {}
                variant_gid = _shopify_id_to_str(variant.get("id") or "")
                product_id = variant_to_product.get(variant_gid)
                if not product_id:
                    continue  # Skip line items we can't map to a known product.
                qty = int(li.get("quantity") or 0)
                price_set = li.get("originalUnitPriceSet") or {}
                shop_money = price_set.get("shopMoney") or {}
                amount = shop_money.get("amount") or "0"
                try:
                    price = Decimal(str(amount))
                except Exception:
                    price = Decimal("0")
                sku = (li.get("sku") or "").strip() or None

                # Idempotency: avoid double-inserting the same line item
                # by anchoring on the Shopify line item id encoded into
                # shopify_order_id field for now.
                line_id = _shopify_id_to_str(li.get("id") or "")
                if not line_id:
                    continue
                exists = db.scalar(
                    select(OrderLineItem.id).where(
                        OrderLineItem.shop_id == shop_id,
                        OrderLineItem.shopify_order_id == f"{order_id}:{line_id}",
                    )
                )
                if exists is not None:
                    continue

                db.add(
                    OrderLineItem(
                        shop_id=shop_id,
                        shopify_order_id=f"{order_id}:{line_id}",
                        product_id=product_id,
                        sku=sku,
                        quantity=qty,
                        price=price,
                        created_at=created_at,
                    )
                )
                count += 1
        db.commit()
        page_info = (((result.get("data") or {}).get("orders") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return count


def sync_shop_now(db: DbSession, *, shop_id: int) -> dict:
    """Run a full sync: products + inventory + recent orders. Returns a summary."""
    conn = db.scalar(
        select(ShopifyConnection).where(ShopifyConnection.shop_id == shop_id)
    )
    if conn is None or not conn.access_token or conn.uninstalled_at is not None:
        logger.error(
            "Shopify sync precondition failed: shop_id=%s conn_exists=%s has_token=%s uninstalled_at=%s shopify_domain=%s",
            shop_id,
            conn is not None,
            bool(conn and conn.access_token),
            conn.uninstalled_at if conn else None,
            conn.shopify_domain if conn else None,
        )
        raise RuntimeError("No active Shopify connection for this workspace.")

    run = ShopifySyncRun(shop_id=shop_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    started_at = datetime.now(timezone.utc)
    try:
        products_count = _ingest_products(
            db, shop_id=shop_id, domain=conn.shopify_domain, token=conn.access_token
        )
        line_items_count = _ingest_orders(
            db, shop_id=shop_id, domain=conn.shopify_domain, token=conn.access_token
        )
        run.products_count = products_count
        run.order_line_items_count = line_items_count
        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        conn.last_sync_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "succeeded",
            "products_count": products_count,
            "order_line_items_count": line_items_count,
            "duration_seconds": (run.finished_at - started_at).total_seconds(),
        }
    except urllib.error.HTTPError as exc:
        # Log Shopify HTTP errors loudly so 401/403/429 are visible in Railway
        # logs immediately, not just propagated as a 400 response message.
        try:
            body_preview = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body_preview = "<unavailable>"
        logger.error(
            "Shopify HTTP error for shop_id=%s: code=%s reason=%s body=%s",
            shop_id, exc.code, exc.reason, body_preview,
        )
        run.status = "failed"
        run.error_message = f"Shopify HTTP error: {exc.code} {exc.reason}"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise RuntimeError(run.error_message) from exc
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Shopify sync failed for shop_id=%s", shop_id)
        raise RuntimeError(f"Sync failed: {exc}") from exc
