"""Shopify ingestion runner — pulls products / inventory / orders via Admin GraphQL.

Designed for the live OAuth-connected case. Reuses the existing Product /
Inventory / OrderLineItem persistence so dashboard / forecast / actions
read the same shape regardless of whether data came from CSV or API.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Inventory, OrderLineItem, Product, ShopifyConnection, ShopifySyncRun

logger = logging.getLogger(__name__)


# Shopify supports each API version for 12 months; a sunset version silently
# falls back to the oldest supported one. Keep this current (matches billing).
GRAPHQL_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-04")

# The message shown when Shopify denies access to order data. This is the
# "Protected customer data" gate: the app must be approved for order-level
# data in the Partner Dashboard (Apps -> skubase -> API access).
PROTECTED_DATA_HELP = (
    "Shopify denied access to order data (403). The app needs 'Protected "
    "customer data' access approved in the Shopify Partner Dashboard "
    "(Apps -> skubase -> API access -> Protected customer data: select "
    "order-level data only)."
)

RECONNECT_SCOPE_HELP = "Reconnect Shopify to approve the updated order access scope."

# Shopify retired non-expiring offline tokens in June 2026; stores connected
# before the cutover hold a token Shopify now rejects with 403 on every call.
LEGACY_TOKEN_HELP = (
    "Shopify retired this store's old-style access token (403). Click "
    "Reconnect to re-authorize skubase - the new connection uses Shopify's "
    "expiring tokens and renews itself automatically."
)


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
        displayFinancialStatus
        displayFulfillmentStatus
        lineItems(first: 250) {
          pageInfo { hasNextPage endCursor }
          edges {
            node {
              id
              title
              sku
              quantity
              product { id }
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


def _scope_set(scope: str | None) -> set[str]:
    return {part.strip() for part in re.split(r"[\s,]+", scope or "") if part.strip()}


def _sanitize_error_message(message: str) -> str:
    text = re.sub(r"shp[a-z]_[A-Za-z0-9_]+", "[redacted]", message)
    text = re.sub(
        r'("access_token"\s*:\s*")[^"]+',
        r'\1[redacted]',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(access_token=)[^&\s]+",
        r"\1[redacted]",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _http_error_preview(exc: urllib.error.HTTPError) -> str:
    cached = getattr(exc, "_skubase_body_preview", None)
    if cached is not None:
        return str(cached)
    try:
        body_preview = exc.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        body_preview = "<unavailable>"
    sanitized = _sanitize_error_message(body_preview)
    setattr(exc, "_skubase_body_preview", sanitized)
    return sanitized


def _top_skip_reason(skip_reasons: Counter) -> str | None:
    if not skip_reasons:
        return None
    reason, _ = skip_reasons.most_common(1)[0]
    return str(reason)


def _ingest_products(db: DbSession, *, shop_id: int, domain: str, token: str) -> dict:
    """Pull products + variants + inventory snapshot."""
    cursor = None
    products_scanned = 0
    variants_imported = 0
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
            products_scanned += 1
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
                variants_imported += 1
        db.commit()
        page_info = (((result.get("data") or {}).get("products") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return {
        "products_scanned": products_scanned,
        "variants_imported": variants_imported,
    }


def _resolve_line_item_product_id(
    li: dict,
    *,
    variant_to_product: dict[str, int],
    shopify_product_to_products: dict[str, list[int]],
    sku_to_products: dict[str, list[int]],
) -> tuple[int | None, str | None]:
    variant = li.get("variant") or {}
    variant_gid = _shopify_id_to_str(variant.get("id") or "")
    if variant_gid:
        product_id = variant_to_product.get(variant_gid)
        if product_id:
            return product_id, None
        return None, "unknown_variant_id"

    product = li.get("product") or {}
    shopify_product_id = _shopify_id_to_str(product.get("id") or "")
    sku = (li.get("sku") or "").strip().lower()

    if shopify_product_id:
        product_candidates = shopify_product_to_products.get(shopify_product_id, [])
        if len(product_candidates) == 1:
            return product_candidates[0], None
        if len(product_candidates) > 1:
            if sku:
                sku_candidates = [
                    product_id
                    for product_id in sku_to_products.get(sku, [])
                    if product_id in product_candidates
                ]
                if len(sku_candidates) == 1:
                    return sku_candidates[0], None
            return None, "ambiguous_product_id_without_variant"

    if sku:
        sku_candidates = sku_to_products.get(sku, [])
        if len(sku_candidates) == 1:
            return sku_candidates[0], None
        if len(sku_candidates) > 1:
            return None, "ambiguous_sku_without_variant"
        return None, "unknown_sku_without_variant"

    if shopify_product_id:
        return None, "unknown_product_id_without_variant"
    return None, "missing_variant_product_and_sku"


def _ingest_orders(db: DbSession, *, shop_id: int, domain: str, token: str, days_back: int = 60) -> dict:
    """Pull recent paid orders. Returns line item import diagnostics."""
    # Shopify's search-query language wants ISO 8601 without microseconds and
    # ideally with a Z suffix (not +00:00). datetime.isoformat() produces
    # the latter, which Shopify silently rejects → zero orders returned.
    since_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"created_at:>={since} financial_status:paid status:any"
    cursor = None
    stats = {
        "orders_query": query,
        "orders_scanned": 0,
        "line_items_scanned": 0,
        "line_items_with_variant_id": 0,
        "line_items_with_product_id": 0,
        "line_items_imported": 0,
        "line_items_skipped": 0,
        "line_item_skip_reasons": {},
        "top_skip_reason": None,
        "no_eligible_recent_orders_found": False,
    }
    skip_reasons: Counter = Counter()
    pages_seen = 0

    # Pre-build lookup maps for line item joins. Customer data is intentionally
    # not part of forecasting imports.
    variant_to_product: dict[str, int] = {}
    shopify_product_to_products: dict[str, list[int]] = defaultdict(list)
    sku_to_products: dict[str, list[int]] = defaultdict(list)
    rows = db.execute(
        select(
            Product.id,
            Product.shopify_variant_id,
            Product.shopify_product_id,
            Product.sku,
        ).where(Product.shop_id == shop_id)
    ).all()
    for pid, vid, shopify_product_id, sku in rows:
        if vid:
            variant_to_product[str(vid)] = int(pid)
        if shopify_product_id:
            shopify_product_to_products[str(shopify_product_id)].append(int(pid))
        normalized_sku = (sku or "").strip().lower()
        if normalized_sku:
            sku_to_products[normalized_sku].append(int(pid))

    logger.info(
        "Shopify order ingest start: shop_domain=%s request_type=orders_graphql since=%s query=%s products_indexed=%s",
        domain, since, query, len(variant_to_product),
    )

    while True:
        try:
            result = _gql(domain, token, ORDERS_QUERY, {"cursor": cursor, "query": query})
        except urllib.error.HTTPError as exc:
            logger.error(
                "Shopify order API error: shop_domain=%s request_type=orders_graphql status_code=%s message=%s",
                domain,
                exc.code,
                _http_error_preview(exc),
            )
            raise
        # Surface GraphQL-level errors (invalid query syntax, bad scope, etc.)
        # so we know WHY orders are missing instead of silently getting zero.
        gql_errors = result.get("errors")
        if gql_errors:
            logger.error(
                "Shopify order GraphQL errors: shop_domain=%s request_type=orders_graphql errors=%s",
                domain,
                _sanitize_error_message(str(gql_errors))[:500],
            )
            raise RuntimeError(f"Shopify orders query failed: {gql_errors}")
        data = result.get("data") or {}
        orders = data.get("orders") or {}
        edges = orders.get("edges") or []
        pages_seen += 1
        logger.info(
            "Shopify orders page: shop_domain=%s request_type=orders_graphql page=%s edges=%s cursor=%s",
            domain, pages_seen, len(edges), cursor,
        )
        for edge in edges:
            order = edge.get("node") or {}
            if not order:
                continue
            order_id = _shopify_id_to_str(order.get("id") or "")
            if not order_id:
                continue
            stats["orders_scanned"] += 1
            try:
                created_at_raw = order.get("createdAt") or ""
                created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            except Exception:
                created_at = datetime.now(timezone.utc)
            line_items = order.get("lineItems") or {}
            li_edges = line_items.get("edges") or []
            order_counts = Counter()
            if (line_items.get("pageInfo") or {}).get("hasNextPage"):
                skip_reasons["line_items_page_truncated"] += 1
                logger.warning(
                    "Shopify order has more line items than fetched: shop_domain=%s request_type=orders_graphql order_id=%s fetched_line_items=%s",
                    domain,
                    order_id,
                    len(li_edges),
                )
            for liedge in li_edges:
                li = liedge.get("node") or {}
                if not li:
                    continue
                stats["line_items_scanned"] += 1
                order_counts["line_items_scanned"] += 1
                variant = li.get("variant") or {}
                variant_gid = _shopify_id_to_str(variant.get("id") or "")
                if variant_gid:
                    stats["line_items_with_variant_id"] += 1
                    order_counts["line_items_with_variant_id"] += 1
                product = li.get("product") or {}
                if _shopify_id_to_str(product.get("id") or ""):
                    stats["line_items_with_product_id"] += 1
                    order_counts["line_items_with_product_id"] += 1

                product_id, skip_reason = _resolve_line_item_product_id(
                    li,
                    variant_to_product=variant_to_product,
                    shopify_product_to_products=shopify_product_to_products,
                    sku_to_products=sku_to_products,
                )
                if not product_id:
                    reason = skip_reason or "unmapped_line_item"
                    skip_reasons[reason] += 1
                    stats["line_items_skipped"] += 1
                    order_counts["line_items_skipped"] += 1
                    continue
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
                    skip_reasons["missing_line_item_id"] += 1
                    stats["line_items_skipped"] += 1
                    order_counts["line_items_skipped"] += 1
                    continue
                exists = db.scalar(
                    select(OrderLineItem.id).where(
                        OrderLineItem.shop_id == shop_id,
                        OrderLineItem.shopify_order_id == f"{order_id}:{line_id}",
                    )
                )
                if exists is not None:
                    skip_reasons["already_imported"] += 1
                    stats["line_items_skipped"] += 1
                    order_counts["line_items_skipped"] += 1
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
                stats["line_items_imported"] += 1
            logger.info(
                "Shopify order line item mapping: shop_domain=%s request_type=orders_graphql order_id=%s financial_status=%s fulfillment_status=%s line_items=%s with_variant_id=%s with_product_id=%s skipped=%s top_skip_reason=%s",
                domain,
                order_id,
                order.get("displayFinancialStatus"),
                order.get("displayFulfillmentStatus"),
                order_counts["line_items_scanned"],
                order_counts["line_items_with_variant_id"],
                order_counts["line_items_with_product_id"],
                order_counts["line_items_skipped"],
                _top_skip_reason(skip_reasons),
            )
        db.commit()
        page_info = (((result.get("data") or {}).get("orders") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    stats["line_item_skip_reasons"] = dict(skip_reasons)
    stats["top_skip_reason"] = _top_skip_reason(skip_reasons)
    stats["no_eligible_recent_orders_found"] = stats["orders_scanned"] == 0
    logger.info(
        "Shopify order ingest complete: shop_domain=%s request_type=orders_graphql orders_scanned=%s line_items_scanned=%s line_items_imported=%s line_items_skipped=%s top_skip_reason=%s",
        domain,
        stats["orders_scanned"],
        stats["line_items_scanned"],
        stats["line_items_imported"],
        stats["line_items_skipped"],
        stats["top_skip_reason"],
    )
    return stats


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

    # Access tokens expire after ~1h; renew through the refresh token before
    # the sync so a long-lived connection keeps working unattended.
    from app.services.shopify_oauth import ensure_fresh_access_token

    token = ensure_fresh_access_token(db, conn)

    started_at = datetime.now(timezone.utc)
    try:
        product_stats = _ingest_products(
            db, shop_id=shop_id, domain=conn.shopify_domain, token=token
        )
        products_count = int(product_stats.get("variants_imported") or 0)
    except Exception as exc:
        run.status = "failed"
        run.error_message = _friendly_sync_error(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Shopify product sync failed for shop_id=%s", shop_id)
        raise RuntimeError(run.error_message) from exc

    # Orders are ingested separately so an order-permission failure (the
    # Protected Customer Data gate) does not throw away a good product +
    # inventory sync — the app stays useful and the error stays actionable.
    line_items_count = 0
    orders_error: str | None = None
    order_stats = {
        "orders_query": None,
        "orders_scanned": 0,
        "line_items_scanned": 0,
        "line_items_with_variant_id": 0,
        "line_items_with_product_id": 0,
        "line_items_imported": 0,
        "line_items_skipped": 0,
        "line_item_skip_reasons": {},
        "top_skip_reason": None,
        "no_eligible_recent_orders_found": False,
    }
    stored_token_has_read_orders = "read_orders" in _scope_set(conn.scope)
    token_lacks_read_orders = not stored_token_has_read_orders
    if token_lacks_read_orders:
        orders_error = f"{RECONNECT_SCOPE_HELP} Products and inventory still synced."
        logger.warning(
            "Shopify order sync skipped: shop_domain=%s request_type=orders_graphql reason=missing_read_orders_scope",
            conn.shopify_domain,
        )
    else:
        try:
            order_stats = _ingest_orders(
                db, shop_id=shop_id, domain=conn.shopify_domain, token=token
            )
            line_items_count = int(order_stats.get("line_items_imported") or 0)
        except Exception as exc:
            orders_error = _friendly_sync_error(exc) + " Products and inventory still synced."
            logger.exception("Shopify order sync failed for shop_id=%s", shop_id)

    run.products_count = products_count
    run.order_line_items_count = line_items_count
    run.status = "succeeded" if orders_error is None else "partial"
    run.error_message = orders_error[:1000] if orders_error else None
    run.finished_at = datetime.now(timezone.utc)
    conn.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": run.status,
        "products_count": products_count,
        "products_scanned": int(product_stats.get("products_scanned") or 0),
        "variants_imported": products_count,
        "order_line_items_count": line_items_count,
        "orders_scanned": int(order_stats.get("orders_scanned") or 0),
        "line_items_scanned": int(order_stats.get("line_items_scanned") or 0),
        "line_items_imported": int(order_stats.get("line_items_imported") or 0),
        "line_items_skipped": int(order_stats.get("line_items_skipped") or 0),
        "line_items_with_variant_id": int(order_stats.get("line_items_with_variant_id") or 0),
        "line_items_with_product_id": int(order_stats.get("line_items_with_product_id") or 0),
        "line_item_skip_reasons": order_stats.get("line_item_skip_reasons") or {},
        "top_skip_reason": order_stats.get("top_skip_reason"),
        "stored_token_has_read_orders": stored_token_has_read_orders,
        "token_lacks_read_orders": token_lacks_read_orders,
        "no_eligible_recent_orders_found": bool(order_stats.get("no_eligible_recent_orders_found")),
        "orders_query": order_stats.get("orders_query"),
        "orders_error": orders_error,
        "duration_seconds": (run.finished_at - started_at).total_seconds(),
    }


def _friendly_sync_error(exc: Exception) -> str:
    """Translate raw Shopify failures into something a merchant can act on."""
    if isinstance(exc, urllib.error.HTTPError):
        body_preview = _http_error_preview(exc)
        logger.error(
            "Shopify HTTP error: code=%s reason=%s body=%s",
            exc.code, exc.reason, body_preview,
        )
        if exc.code == 403:
            if "non-expiring access tokens" in body_preview.lower():
                return LEGACY_TOKEN_HELP
            return PROTECTED_DATA_HELP
        if exc.code == 401:
            return (
                "Shopify rejected the store's access token (401). "
                "Re-authorize skubase from the Billing or Store Sync page."
            )
        if exc.code == 429:
            return "Shopify rate-limited the sync (429). Try again in a minute."
        return f"Shopify HTTP error: {exc.code} {exc.reason}"
    message = _sanitize_error_message(str(exc))
    if "ACCESS_DENIED" in message or "not approved" in message.lower():
        return PROTECTED_DATA_HELP
    return f"Sync failed: {message}"
