"""Shopify ingestion runner — pulls products / inventory / orders via Admin GraphQL.

Designed for the live OAuth-connected case. Reuses the existing Product /
Inventory / OrderLineItem persistence so dashboard / forecast / actions
read the same shape regardless of whether data came from CSV or API.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
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

# Shopify retired non-expiring offline tokens in June 2026; stores connected
# before the cutover hold a token Shopify now rejects with 403 on every call.
LEGACY_TOKEN_HELP = (
    "Shopify retired this store's old-style access token (403). Click "
    "Reconnect to re-authorize skubase - the new connection uses Shopify's "
    "expiring tokens and renews itself automatically."
)

ORDER_SCOPE_RECONNECT_MESSAGE = (
    "Reconnect Shopify to approve the updated order access scope."
)


@dataclass
class ShopifyApiHTTPError(RuntimeError):
    status_code: int
    reason: str
    sanitized_message: str
    request_type: str
    shop_domain: str

    def __str__(self) -> str:
        return f"Shopify HTTP error: {self.status_code} {self.reason}"


@dataclass
class ProductIngestStats:
    products_scanned: int = 0
    variants_imported: int = 0


@dataclass
class OrderIngestStats:
    orders_scanned: int = 0
    line_items_scanned: int = 0
    line_items_imported: int = 0
    line_items_skipped: int = 0
    line_items_with_variant_id: int = 0
    line_items_with_product_id: int = 0
    skip_reasons: Counter[str] = field(default_factory=Counter)
    shopify_order_query: str = ""
    days_back: int = 60
    token_lacks_read_orders: bool = False
    no_eligible_recent_orders_found: bool = False

    def add_skip(self, reason: str) -> None:
        self.line_items_skipped += 1
        self.skip_reasons[reason] += 1

    @property
    def top_skip_reason(self) -> str | None:
        if not self.skip_reasons:
            return None
        return self.skip_reasons.most_common(1)[0][0]

    def to_response(self) -> dict:
        return {
            "orders_scanned": self.orders_scanned,
            "line_items_scanned": self.line_items_scanned,
            "line_items_imported": self.line_items_imported,
            "line_items_skipped": self.line_items_skipped,
            "line_items_with_variant_id": self.line_items_with_variant_id,
            "line_items_with_product_id": self.line_items_with_product_id,
            "top_skip_reason": self.top_skip_reason,
            "skip_reasons": dict(self.skip_reasons),
            "shopify_order_query": self.shopify_order_query,
            "days_back": self.days_back,
            "token_lacks_read_orders": self.token_lacks_read_orders,
            "no_eligible_recent_orders_found": self.no_eligible_recent_orders_found,
        }


def _sanitize_shopify_error_message(raw: str) -> str:
    """Keep API logs useful without access tokens or customer contact data."""
    message = raw[:1000] if raw else "<empty response>"
    try:
        payload = json.loads(message)
        if isinstance(payload, dict):
            candidate = payload.get("errors") or payload.get("error_description") or payload.get("error")
            message = json.dumps(candidate) if candidate is not None else json.dumps(payload)
    except Exception:
        pass

    message = re.sub(r"shp[a-zA-Z_]*_[A-Za-z0-9_\-]+", "[redacted-token]", message)
    message = re.sub(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        "[redacted-email]",
        message,
    )
    message = re.sub(r"\+?\d[\d\s().-]{7,}\d", "[redacted-phone]", message)
    return message[:500]


def _gql(
    domain: str,
    token: str,
    query: str,
    variables: Optional[dict] = None,
    *,
    request_type: str,
) -> dict:
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body_preview = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_preview = "<unavailable>"
        sanitized = _sanitize_shopify_error_message(body_preview)
        logger.error(
            "shopify_api_error shop=%s request_type=%s status_code=%s message=%s",
            domain,
            request_type,
            exc.code,
            sanitized,
        )
        raise ShopifyApiHTTPError(
            status_code=exc.code,
            reason=str(exc.reason),
            sanitized_message=sanitized,
            request_type=request_type,
            shop_domain=domain,
        ) from exc


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

ACCESS_SCOPES_QUERY = """
query CurrentAppInstallationAccessScopes {
  currentAppInstallation {
    accessScopes {
      handle
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


def _log_graphql_errors(
    *,
    domain: str,
    request_type: str,
    gql_errors: object,
) -> None:
    logger.error(
        "shopify_graphql_error shop=%s request_type=%s message=%s",
        domain,
        request_type,
        _sanitize_shopify_error_message(json.dumps(gql_errors)),
    )


def fetch_token_access_scopes(*, domain: str, token: str) -> set[str]:
    """Return live access scope handles granted to the current app token."""
    result = _gql(
        domain,
        token,
        ACCESS_SCOPES_QUERY,
        request_type="access_scopes",
    )
    gql_errors = result.get("errors")
    if gql_errors:
        _log_graphql_errors(
            domain=domain,
            request_type="access_scopes",
            gql_errors=gql_errors,
        )
        raise RuntimeError(f"Shopify access scopes query failed: {gql_errors}")

    installation = ((result.get("data") or {}).get("currentAppInstallation")) or {}
    scopes = installation.get("accessScopes") or []
    return {
        str(scope.get("handle"))
        for scope in scopes
        if isinstance(scope, dict) and scope.get("handle")
    }


def _ingest_products(
    db: DbSession,
    *,
    shop_id: int,
    domain: str,
    token: str,
) -> ProductIngestStats:
    """Pull products + variants + inventory snapshot."""
    cursor = None
    stats = ProductIngestStats()
    while True:
        result = _gql(
            domain,
            token,
            PRODUCTS_QUERY,
            {"cursor": cursor},
            request_type="products",
        )
        # Surface GraphQL-level errors so we can see scope / permission failures.
        gql_errors = result.get("errors")
        if gql_errors:
            _log_graphql_errors(domain=domain, request_type="products", gql_errors=gql_errors)
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
            stats.products_scanned += 1
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
                stats.variants_imported += 1
        db.commit()
        page_info = (((result.get("data") or {}).get("products") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return stats


def _unique_mapping_value(mapping: dict[str, list[int]], key: str) -> tuple[int | None, bool]:
    matches = mapping.get(key) or []
    if len(matches) == 1:
        return matches[0], False
    return None, len(matches) > 1


def _resolve_line_item_product_id(
    *,
    variant_id: str,
    shopify_product_id: str,
    sku: str | None,
    variant_to_product: dict[str, int],
    shopify_product_to_products: dict[str, list[int]],
    sku_to_products: dict[str, list[int]],
) -> tuple[int | None, str | None]:
    if variant_id:
        product_id = variant_to_product.get(variant_id)
        if product_id is not None:
            return product_id, None
        return None, "unknown_variant_id"

    if sku:
        product_id, ambiguous = _unique_mapping_value(sku_to_products, sku)
        if product_id is not None:
            return product_id, None
        if ambiguous:
            return None, "ambiguous_sku_mapping"

    if shopify_product_id:
        product_id, ambiguous = _unique_mapping_value(
            shopify_product_to_products,
            shopify_product_id,
        )
        if product_id is not None:
            return product_id, None
        if ambiguous:
            return None, "ambiguous_product_mapping"

    if sku or shopify_product_id:
        return None, "missing_variant_id_no_unique_fallback"
    return None, "missing_variant_id"


def _ingest_orders(
    db: DbSession,
    *,
    shop_id: int,
    domain: str,
    token: str,
    days_back: int = 60,
) -> OrderIngestStats:
    """Pull paid orders within the last `days_back` days."""
    # Shopify's search-query language wants ISO 8601 without microseconds and
    # ideally with a Z suffix (not +00:00). datetime.isoformat() produces
    # the latter, which Shopify silently rejects → zero orders returned.
    since_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"created_at:>={since} financial_status:paid status:any"
    cursor = None
    pages_seen = 0
    stats = OrderIngestStats(shopify_order_query=query, days_back=days_back)

    # Pre-build local product maps for fast, explicit line-item joins.
    variant_to_product: dict[str, int] = {}
    shopify_product_to_products: dict[str, list[int]] = {}
    sku_to_products: dict[str, list[int]] = {}
    rows = db.execute(
        select(
            Product.id,
            Product.shopify_variant_id,
            Product.shopify_product_id,
            Product.sku,
        ).where(Product.shop_id == shop_id)
    ).all()
    for pid, vid, shopify_product_id, sku in rows:
        product_id = int(pid)
        if vid:
            variant_to_product[str(vid)] = product_id
        if shopify_product_id:
            shopify_product_to_products.setdefault(str(shopify_product_id), []).append(product_id)
        normalized_sku = (sku or "").strip()
        if normalized_sku:
            sku_to_products.setdefault(normalized_sku, []).append(product_id)

    logger.info(
        "shopify_orders_ingest_start shop=%s shop_id=%s query=%s products_indexed=%s",
        domain,
        shop_id,
        query,
        len(variant_to_product),
    )

    while True:
        result = _gql(
            domain,
            token,
            ORDERS_QUERY,
            {"cursor": cursor, "query": query},
            request_type="orders",
        )
        # Surface GraphQL-level errors (invalid query syntax, bad scope, etc.)
        # so we know WHY orders are missing instead of silently getting zero.
        gql_errors = result.get("errors")
        if gql_errors:
            _log_graphql_errors(domain=domain, request_type="orders", gql_errors=gql_errors)
            raise RuntimeError(f"Shopify orders query failed: {gql_errors}")
        data = result.get("data") or {}
        orders = data.get("orders") or {}
        edges = orders.get("edges") or []
        pages_seen += 1
        logger.info(
            "shopify_orders_page shop=%s page=%s orders=%s cursor_present=%s",
            domain,
            pages_seen,
            len(edges),
            bool(cursor),
        )
        for edge in edges:
            order = edge.get("node") or {}
            if not order:
                continue
            stats.orders_scanned += 1
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
            line_items_page_info = line_items.get("pageInfo") or {}
            order_line_items_scanned = 0
            order_line_items_with_variant_id = 0
            order_line_items_with_product_id = 0
            skipped_before_order = stats.line_items_skipped
            if line_items_page_info.get("hasNextPage"):
                logger.warning(
                    "shopify_order_line_items_truncated shop=%s order_id=%s fetched=%s",
                    domain,
                    order_id,
                    len(li_edges),
                )
            for liedge in li_edges:
                li = liedge.get("node") or {}
                if not li:
                    continue
                stats.line_items_scanned += 1
                order_line_items_scanned += 1
                variant = li.get("variant") or {}
                variant_id = _shopify_id_to_str(variant.get("id") or "")
                if variant_id:
                    stats.line_items_with_variant_id += 1
                    order_line_items_with_variant_id += 1
                shopify_product = li.get("product") or {}
                shopify_product_id = _shopify_id_to_str(shopify_product.get("id") or "")
                if shopify_product_id:
                    stats.line_items_with_product_id += 1
                    order_line_items_with_product_id += 1
                sku = (li.get("sku") or "").strip() or None
                product_id, skip_reason = _resolve_line_item_product_id(
                    variant_id=variant_id,
                    shopify_product_id=shopify_product_id,
                    sku=sku,
                    variant_to_product=variant_to_product,
                    shopify_product_to_products=shopify_product_to_products,
                    sku_to_products=sku_to_products,
                )
                if product_id is None:
                    stats.add_skip(skip_reason or "missing_product_mapping")
                    continue
                qty = int(li.get("quantity") or 0)
                if qty <= 0:
                    stats.add_skip("non_positive_quantity")
                    continue
                price_set = li.get("originalUnitPriceSet") or {}
                shop_money = price_set.get("shopMoney") or {}
                amount = shop_money.get("amount") or "0"
                try:
                    price = Decimal(str(amount))
                except Exception:
                    price = Decimal("0")

                # Idempotency: avoid double-inserting the same line item
                # by anchoring on the Shopify line item id encoded into
                # shopify_order_id field for now.
                line_id = _shopify_id_to_str(li.get("id") or "")
                if not line_id:
                    stats.add_skip("missing_line_item_id")
                    continue
                exists = db.scalar(
                    select(OrderLineItem.id).where(
                        OrderLineItem.shop_id == shop_id,
                        OrderLineItem.shopify_order_id == f"{order_id}:{line_id}",
                    )
                )
                if exists is not None:
                    stats.add_skip("already_imported")
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
                stats.line_items_imported += 1
            logger.info(
                "shopify_order_line_items shop=%s order_id=%s total=%s with_variant_id=%s with_product_id=%s skipped=%s",
                domain,
                order_id,
                order_line_items_scanned,
                order_line_items_with_variant_id,
                order_line_items_with_product_id,
                stats.line_items_skipped - skipped_before_order,
            )
        db.commit()
        page_info = (((result.get("data") or {}).get("orders") or {}).get("pageInfo")) or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    stats.no_eligible_recent_orders_found = stats.orders_scanned == 0
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
    from app.services.shopify_oauth import ensure_fresh_access_token, missing_required_scopes

    token = ensure_fresh_access_token(db, conn)
    stored_missing_scopes = missing_required_scopes(conn.scope)
    stored_token_has_read_orders = "read_orders" not in stored_missing_scopes
    live_token_has_read_orders: bool | None = None
    token_scope_check_error: str | None = None
    try:
        live_access_scopes = fetch_token_access_scopes(
            domain=conn.shopify_domain,
            token=token,
        )
        live_token_has_read_orders = "read_orders" in live_access_scopes
        logger.info(
            "shopify_token_scope_check shop=%s has_read_orders=%s missing_required_scopes=%s",
            conn.shopify_domain,
            live_token_has_read_orders,
            [scope for scope in ("read_orders",) if scope not in live_access_scopes],
        )
    except Exception as exc:
        token_scope_check_error = _friendly_sync_error(exc)
        logger.warning(
            "shopify_token_scope_check_failed shop=%s message=%s",
            conn.shopify_domain,
            token_scope_check_error,
        )

    started_at = datetime.now(timezone.utc)
    try:
        product_stats = _ingest_products(
            db, shop_id=shop_id, domain=conn.shopify_domain, token=token
        )
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
    order_stats = OrderIngestStats()
    orders_error: str | None = None
    token_lacks_read_orders = (
        live_token_has_read_orders is False
        or (live_token_has_read_orders is None and not stored_token_has_read_orders)
    )
    if token_lacks_read_orders:
        order_stats.token_lacks_read_orders = True
        orders_error = f"{ORDER_SCOPE_RECONNECT_MESSAGE} Products and inventory still synced."
        logger.warning(
            "shopify_order_sync_skipped_missing_scope shop=%s stored_has_read_orders=%s live_has_read_orders=%s",
            conn.shopify_domain,
            stored_token_has_read_orders,
            live_token_has_read_orders,
        )
    else:
        try:
            order_stats = _ingest_orders(
                db, shop_id=shop_id, domain=conn.shopify_domain, token=token
            )
        except Exception as exc:
            orders_error = _friendly_sync_error(exc) + " Products and inventory still synced."
            logger.exception(
                "Shopify order sync failed for shop_id=%s shop=%s",
                shop_id,
                conn.shopify_domain,
            )

    run.products_count = product_stats.variants_imported
    run.order_line_items_count = order_stats.line_items_imported
    run.status = "succeeded" if orders_error is None else "partial"
    run.error_message = orders_error[:1000] if orders_error else None
    run.finished_at = datetime.now(timezone.utc)
    conn.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    order_details = order_stats.to_response()
    return {
        "status": run.status,
        "products_count": product_stats.variants_imported,
        "products_scanned": product_stats.products_scanned,
        "variants_imported": product_stats.variants_imported,
        "order_line_items_count": order_stats.line_items_imported,
        "orders_scanned": order_stats.orders_scanned,
        "line_items_scanned": order_stats.line_items_scanned,
        "line_items_imported": order_stats.line_items_imported,
        "line_items_skipped": order_stats.line_items_skipped,
        "line_items_with_variant_id": order_stats.line_items_with_variant_id,
        "line_items_with_product_id": order_stats.line_items_with_product_id,
        "top_skip_reason": order_stats.top_skip_reason,
        "skip_reasons": dict(order_stats.skip_reasons),
        "token_lacks_read_orders": order_stats.token_lacks_read_orders,
        "stored_token_has_read_orders": stored_token_has_read_orders,
        "live_token_has_read_orders": live_token_has_read_orders,
        "token_scope_check_error": token_scope_check_error,
        "no_eligible_recent_orders_found": order_stats.no_eligible_recent_orders_found,
        "shopify_order_query": order_stats.shopify_order_query,
        "order_details": order_details,
        "orders_error": orders_error,
        "duration_seconds": (run.finished_at - started_at).total_seconds(),
    }


def _friendly_sync_error(exc: Exception) -> str:
    """Translate raw Shopify failures into something a merchant can act on."""
    if isinstance(exc, ShopifyApiHTTPError):
        if exc.status_code == 403:
            if "non-expiring access tokens" in exc.sanitized_message.lower():
                return LEGACY_TOKEN_HELP
            return PROTECTED_DATA_HELP
        if exc.status_code == 401:
            return (
                "Shopify rejected the store's access token (401). "
                "Re-authorize skubase from the Billing or Store Sync page."
            )
        if exc.status_code == 429:
            return "Shopify rate-limited the sync (429). Try again in a minute."
        return f"Shopify HTTP error: {exc.status_code} {exc.reason}"
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body_preview = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body_preview = "<unavailable>"
        body_preview = _sanitize_shopify_error_message(body_preview)
        logger.error(
            "shopify_api_error shop=%s request_type=%s status_code=%s message=%s",
            "<unknown>",
            "unknown",
            exc.code,
            body_preview,
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
    message = str(exc)
    if "ACCESS_DENIED" in message or "not approved" in message.lower():
        return PROTECTED_DATA_HELP
    return f"Sync failed: {message}"
