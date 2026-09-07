"""Tenant-scoped processing of Shopify privacy requests.

Only the existing merchant analytics are exported. Shopify customer names,
emails, telephone numbers and addresses in webhook payloads are never stored.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.db.models import (
    AuditLogRecord, Base, InventoryRiskSnapshotLead, MagicLinkToken,
    NotificationChannelRecord, OrderLineItem, Session as LoginSession, Shop,
    ShopifyConnection, Subscription, User, WaitlistSignup,
)
from app.services.shopify_oauth import shopify_connection_lock

DATA_REQUEST_EVENT = "shopify_customer_data_request"


def normalize_shop_domain(value: Any) -> str:
    domain = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", domain):
        raise ValueError("A valid Shopify shop domain is required.")
    return domain


def requested_order_ids(payload: dict, field: str) -> list[str]:
    values = payload.get(field, [])
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list of Shopify order IDs.")
    ids = set()
    for value in values:
        text = str(value)
        if not re.fullmatch(r"[1-9][0-9]*", text):
            raise ValueError(f"{field} contains an invalid Shopify order ID.")
        ids.add(text)
    return sorted(ids)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _shops(db: DbSession, domain: str) -> list[Shop]:
    # Resolve the signed domain to local tenant IDs. Shopify's numeric shop_id
    # is external and must never be interpreted as a local primary key.
    return list(db.scalars(select(Shop).where(Shop.shopify_domain == domain)))


def _clear_runtime_data(shop_ids: list[int]) -> None:
    from app.services import alerts
    from app.services.shopify_billing import invalidate_shopify_billing_cache

    for shop_id in shop_ids:
        invalidate_shopify_billing_cache(shop_id)
    alerts._EVENTS[:] = [entry for entry in alerts._EVENTS if entry[0] not in shop_ids]


def _newer_install(conn: ShopifyConnection, triggered_at: datetime | None, *, redact: bool) -> bool:
    if conn.uninstalled_at is not None or not conn.access_token:
        return False
    if triggered_at is None:
        # Older webhook deliveries lack event time. Never erase an active
        # reinstall on ambiguous delivery metadata.
        return True
    installed = _utc(conn.installed_at)
    threshold = _utc(triggered_at) - (timedelta(hours=48) if redact else timedelta())
    # shop/redact describes an uninstall 48 hours before the original event,
    # not an uninstall at the retry delivery time.
    return installed >= threshold


def mark_shop_uninstalled(
    db: DbSession, *, shop_domain: str, triggered_at: datetime | None,
) -> dict[str, int]:
    domain = normalize_shop_domain(shop_domain)
    affected = []
    preserved = 0
    with shopify_connection_lock(db, domain):
        for conn in db.scalars(select(ShopifyConnection).where(ShopifyConnection.shopify_domain == domain)):
            if _newer_install(conn, triggered_at, redact=False):
                preserved += 1
                continue
            conn.access_token = ""
            conn.refresh_token = None
            conn.access_token_expires_at = None
            conn.refresh_token_expires_at = None
            # A retry must not move the original uninstall timestamp.
            conn.uninstalled_at = conn.uninstalled_at or triggered_at or datetime.now(timezone.utc)
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == conn.shop_id))
            if sub is not None and str(sub.stripe_subscription_id or "").startswith("shopify:"):
                sub.status, sub.plan = "inactive", "none"
            affected.append(conn.shop_id)
        db.commit()
    _clear_runtime_data(affected)
    return {"connections_revoked": len(affected), "active_installations_preserved": preserved}


def redact_shop(
    db: DbSession, *, shop_domain: str, triggered_at: datetime | None,
) -> dict[str, int]:
    domain = normalize_shop_domain(shop_domain)
    purged = []
    preserved = 0
    with shopify_connection_lock(db, domain):
        for shop in _shops(db, domain):
            conn = db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == shop.id))
            if conn is not None and _newer_install(conn, triggered_at, redact=True):
                preserved += 1
                continue
            users = list(db.execute(select(User.id, User.email).where(User.shop_id == shop.id)))
            from app.growth.privacy import redact_growth
            redact_growth(db, shop.id, [user.email for user in users])
            if users:
                db.execute(delete(LoginSession).where(LoginSession.user_id.in_([user.id for user in users])))
                db.execute(delete(MagicLinkToken).where(MagicLinkToken.email.in_([user.email for user in users])))
            # These legacy tables predate the shop_id foreign key convention.
            db.execute(delete(NotificationChannelRecord).where(NotificationChannelRecord.channel.like(f"{shop.id}:%")))
            # Delete all tenant-owned tables in FK dependency order, including
            # settings, orders, reports, audit history, billing and auth users.
            # Explicit SQL works with both PostgreSQL and SQLite; it does not
            # depend on ORM relationships or SQLite's optional FK cascades.
            for table in reversed(Base.metadata.sorted_tables):
                if "shop_id" in table.c:
                    db.execute(delete(table).where(table.c.shop_id == shop.id))
            db.execute(delete(Shop).where(Shop.id == shop.id))
            purged.append(shop.id)
        # Also remove shop-associated signups, including when the tenant has
        # already been deleted by an earlier delivery.
        if purged or not _shops(db, domain):
            db.execute(delete(WaitlistSignup).where(func.lower(WaitlistSignup.shopify_domain) == domain))
            urls = [domain, f"https://{domain}", f"http://{domain}"]
            db.execute(delete(InventoryRiskSnapshotLead).where(or_(
                func.lower(InventoryRiskSnapshotLead.store_url).in_(urls),
                *[func.lower(InventoryRiskSnapshotLead.store_url).like(url + "/%") for url in urls],
            )))
        db.commit()
    _clear_runtime_data(purged)
    return {"shops_redacted": len(purged), "active_installations_preserved": preserved}


def _order_matches(order_ids: list[str]):
    # Historical imports used a bare order ID; current sync stores order:line.
    return or_(OrderLineItem.shopify_order_id.in_(order_ids), *[
        OrderLineItem.shopify_order_id.like(order_id + ":%") for order_id in order_ids
    ])


def redact_customer_orders(db: DbSession, *, shop_domain: str, payload: dict) -> dict[str, int]:
    domain = normalize_shop_domain(shop_domain)
    order_ids = requested_order_ids(payload, "orders_to_redact")
    count = 0
    with shopify_connection_lock(db, domain):
        for shop in _shops(db, domain):
            # Chunk conditions so a large privacy request stays under SQLite
            # and PostgreSQL expression/parameter limits.
            for start in range(0, len(order_ids), 200):
                result = db.execute(delete(OrderLineItem).where(
                    OrderLineItem.shop_id == shop.id, _order_matches(order_ids[start:start + 200]),
                ))
                count += result.rowcount or 0
            for event in db.scalars(select(AuditLogRecord).where(
                AuditLogRecord.shop_id == shop.id, AuditLogRecord.event_type == DATA_REQUEST_EVENT,
            )):
                metadata = dict(event.event_metadata or {})
                remaining = [item for item in metadata.get("orders_requested", []) if item not in order_ids]
                if remaining != metadata.get("orders_requested", []):
                    metadata["orders_requested"] = remaining
                    metadata["redacted"] = True
                    event.event_metadata = metadata
        db.commit()
    return {"order_line_items_redacted": count}


def record_customer_data_request(
    db: DbSession, *, shop_domain: str, payload: dict, webhook_id: str | None,
) -> dict[str, int]:
    domain = normalize_shop_domain(shop_domain)
    order_ids = requested_order_ids(payload, "orders_requested")
    raw_id = (payload.get("data_request") or {}).get("id") if isinstance(payload.get("data_request", {}), dict) else None
    request_id = str(raw_id or webhook_id or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
    if len(request_id) > 128:
        request_id = hashlib.sha256(request_id.encode()).hexdigest()
    created = 0
    with shopify_connection_lock(db, domain):
        for shop in _shops(db, domain):
            existing = db.scalar(select(AuditLogRecord).where(
                AuditLogRecord.shop_id == shop.id, AuditLogRecord.event_type == DATA_REQUEST_EVENT,
                AuditLogRecord.entity_id == request_id,
            ))
            if existing is None:
                db.add(AuditLogRecord(
                    shop_id=shop.id, event_type=DATA_REQUEST_EVENT, entity_type="privacy_request",
                    entity_id=request_id, summary="Customer data request ready to download in Settings.",
                    event_metadata={"orders_requested": order_ids},
                ))
                created += 1
        db.commit()
    return {"requests_recorded": created}


def list_customer_data_requests(db: DbSession, *, shop_id: int) -> list[dict]:
    return [{"id": item.id, "request_id": item.entity_id, "created_at": item.created_at,
             "order_count": len((item.event_metadata or {}).get("orders_requested", []))}
            for item in db.scalars(select(AuditLogRecord).where(
                AuditLogRecord.shop_id == shop_id, AuditLogRecord.event_type == DATA_REQUEST_EVENT,
            ).order_by(AuditLogRecord.created_at.desc()))]


def export_customer_data_request(db: DbSession, *, shop_id: int, request_id: int) -> dict | None:
    event = db.scalar(select(AuditLogRecord).where(
        AuditLogRecord.id == request_id, AuditLogRecord.shop_id == shop_id,
        AuditLogRecord.event_type == DATA_REQUEST_EVENT,
    ))
    if event is None:
        return None
    order_ids = (event.event_metadata or {}).get("orders_requested", [])
    lines = []
    for start in range(0, len(order_ids), 200):
        for row in db.scalars(select(OrderLineItem).where(
            OrderLineItem.shop_id == shop_id, _order_matches(order_ids[start:start + 200]),
        ).order_by(OrderLineItem.id)):
            lines.append({"order_id": row.shopify_order_id.split(":", 1)[0],
                          "order_line_reference": row.shopify_order_id, "sku": row.sku,
                          "quantity": row.quantity, "unit_price": str(row.price),
                          "created_at": row.created_at})
    return {"request_id": event.entity_id, "received_at": event.created_at,
            "customer_profile_stored": False,
            "note": "SKUbase stores order-line analytics, but no customer profiles, names, addresses, emails or telephone numbers.",
            "order_line_items": lines}
