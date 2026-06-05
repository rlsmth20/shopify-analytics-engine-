"""Shopify mandatory customer privacy webhooks.

These endpoints are required for Shopify App Store compliance. They verify the
Shopify webhook HMAC, acknowledge quickly, and avoid logging customer payload
contents. Skubase stores product, inventory, order-line analytics, and Shopify
connection metadata; it does not store Shopify customer profiles, addresses, or
customer emails in the inventory analytics tables.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.db.models import ShopifyConnection
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["shopify-webhooks"])


def verify_shopify_webhook_hmac(raw_body: bytes, hmac_header: str | None) -> bool:
    """Return True when Shopify's HMAC header matches the raw request body.

    Shopify sends X-Shopify-Hmac-Sha256 as base64(HMAC-SHA256(raw_body,
    SHOPIFY_CLIENT_SECRET)). compare_digest prevents timing leaks.
    """
    secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    if not secret:
        logger.error("shopify_privacy_webhook_secret_missing")
        return False
    if not hmac_header:
        return False

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, hmac_header)


async def _verified_payload(
    request: Request,
    *,
    topic: str,
    hmac_header: str | None,
    shop_domain: str | None,
    webhook_id: str | None,
) -> dict[str, Any]:
    raw_body = await request.body()
    if not verify_shopify_webhook_hmac(raw_body, hmac_header):
        logger.warning(
            "shopify_privacy_webhook_hmac_failed topic=%s shop=%s webhook_id=%s",
            topic,
            _safe_shop(shop_domain),
            webhook_id or "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Shopify webhook HMAC.",
        )

    logger.info(
        "shopify_privacy_webhook_verified topic=%s shop=%s webhook_id=%s",
        topic,
        _safe_shop(shop_domain),
        webhook_id or "unknown",
    )
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


@router.post("/customers/data_request")
async def customers_data_request(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
    x_shopify_webhook_id: str | None = Header(default=None),
) -> dict[str, str]:
    """Acknowledge a customer data access request.

    Skubase does not store customer profiles, addresses, or customer emails in
    its inventory analytics data. Order-line analytics are keyed to products,
    SKUs, quantities, prices, and order IDs for merchant inventory planning.
    """
    await _verified_payload(
        request,
        topic="customers/data_request",
        hmac_header=x_shopify_hmac_sha256,
        shop_domain=x_shopify_shop_domain,
        webhook_id=x_shopify_webhook_id,
    )
    return {"status": "accepted"}


@router.post("/customers/redact")
async def customers_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
    x_shopify_webhook_id: str | None = Header(default=None),
) -> dict[str, str]:
    """Acknowledge a customer redaction request.

    No customer profile table exists in Skubase today, so there is no customer
    PII to delete. We still verify and acknowledge the webhook for compliance.
    """
    await _verified_payload(
        request,
        topic="customers/redact",
        hmac_header=x_shopify_hmac_sha256,
        shop_domain=x_shopify_shop_domain,
        webhook_id=x_shopify_webhook_id,
    )
    return {"status": "accepted"}


@router.post("/shop/redact")
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
    x_shopify_webhook_id: str | None = Header(default=None),
) -> dict[str, str]:
    """Handle a shop redaction request after uninstall.

    We do not perform long-running deletion inline. The compliance-safe immediate
    action is to revoke local Shopify API usage by clearing stored access tokens
    and marking the connection uninstalled. Any fuller data retention/deletion
    policy can run asynchronously without blocking Shopify's webhook response.
    """
    payload = await _verified_payload(
        request,
        topic="shop/redact",
        hmac_header=x_shopify_hmac_sha256,
        shop_domain=x_shopify_shop_domain,
        webhook_id=x_shopify_webhook_id,
    )
    shop = _extract_shop_domain(payload, x_shopify_shop_domain)
    if shop:
        _mark_shop_connection_redacted(shop)
    return {"status": "accepted"}


# Shopify examples sometimes use topic-style paths without slashes. Keep these
# aliases so either registration style reaches the same compliance handlers.
router.add_api_route("/customers_data_request", customers_data_request, methods=["POST"])
router.add_api_route("/customers_redact", customers_redact, methods=["POST"])
router.add_api_route("/shop_redact", shop_redact, methods=["POST"])


def _mark_shop_connection_redacted(shop_domain: str) -> None:
    normalized = shop_domain.strip().lower()
    if not normalized:
        return
    with SessionLocal() as session:
        records = session.scalars(
            select(ShopifyConnection).where(ShopifyConnection.shopify_domain == normalized)
        ).all()
        for record in records:
            record.access_token = ""
            record.uninstalled_at = datetime.now(timezone.utc)
        if records:
            session.commit()
    logger.info(
        "shopify_privacy_shop_redact_marked shop=%s connection_count=%s",
        _safe_shop(normalized),
        len(records),
    )


def _extract_shop_domain(payload: dict[str, Any], header_shop: str | None) -> str | None:
    value = header_shop or payload.get("shop_domain") or payload.get("shop")
    return str(value).strip().lower() if value else None


def _safe_shop(shop_domain: str | None) -> str:
    if not shop_domain:
        return "unknown"
    return shop_domain.strip().lower()[:255]
