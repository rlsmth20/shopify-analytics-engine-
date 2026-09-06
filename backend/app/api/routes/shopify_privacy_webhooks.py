"""Verified Shopify privacy webhooks and merchant-only privacy exports."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session as DbSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import SessionLocal, get_db_session
from app.services import shopify_privacy as privacy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["shopify-webhooks"])


def verify_shopify_webhook_hmac(raw_body: bytes, hmac_header: str | None) -> bool:
    secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    try:
        return hmac.compare_digest(expected, hmac_header)
    except TypeError:
        return False


async def _verified_payload(request: Request, hmac_header: str | None) -> tuple[dict[str, Any], str]:
    raw_body = await request.body()
    if not verify_shopify_webhook_hmac(raw_body, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook HMAC.")
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")
        # Route tenancy comes from the signed body, never an unsigned header
        # or Shopify's unrelated numeric shop ID.
        domain = privacy.normalize_shop_domain(
            payload.get("shop_domain") or payload.get("myshopify_domain") or payload.get("shop")
        )
        header_domain = request.headers.get("x-shopify-shop-domain")
        if header_domain and privacy.normalize_shop_domain(header_domain) != domain:
            raise ValueError("Shopify shop domain does not match the signed payload.")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return payload, domain


def _triggered_at(request: Request) -> datetime | None:
    value = request.headers.get("x-shopify-triggered-at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError()
        return parsed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Shopify event timestamp.") from exc


def _process(topic: str, *, payload: dict, domain: str, webhook_id: str | None,
             triggered_at: datetime | None = None) -> None:
    # Commit before acknowledging; failures remain retryable by Shopify.
    # Database work runs off the async event loop and never logs payload PII.
    with SessionLocal() as db:
        if topic == "customers/data_request":
            result = privacy.record_customer_data_request(db, shop_domain=domain, payload=payload, webhook_id=webhook_id)
        elif topic == "customers/redact":
            result = privacy.redact_customer_orders(db, shop_domain=domain, payload=payload)
        elif topic == "shop/redact":
            result = privacy.redact_shop(db, shop_domain=domain, triggered_at=triggered_at)
        elif topic == "app/uninstalled":
            result = privacy.mark_shop_uninstalled(db, shop_domain=domain, triggered_at=triggered_at)
        else:
            raise ValueError("Unsupported Shopify privacy topic.")
    logger.info("shopify_privacy_processed topic=%s counts=%s", topic, result)


async def _handle(request: Request, *, topic: str, hmac_header: str | None) -> dict[str, str]:
    payload, domain = await _verified_payload(request, hmac_header)
    try:
        await run_in_threadpool(
            _process, topic, payload=payload, domain=domain,
            webhook_id=request.headers.get("x-shopify-webhook-id"),
            triggered_at=_triggered_at(request) if topic in ("shop/redact", "app/uninstalled") else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "accepted"}


@router.post("/customers/data_request")
async def customers_data_request(request: Request, x_shopify_hmac_sha256: str | None = Header(default=None)):
    return await _handle(request, topic="customers/data_request", hmac_header=x_shopify_hmac_sha256)


@router.post("/customers/redact")
async def customers_redact(request: Request, x_shopify_hmac_sha256: str | None = Header(default=None)):
    return await _handle(request, topic="customers/redact", hmac_header=x_shopify_hmac_sha256)


@router.post("/shop/redact")
async def shop_redact(request: Request, x_shopify_hmac_sha256: str | None = Header(default=None)):
    return await _handle(request, topic="shop/redact", hmac_header=x_shopify_hmac_sha256)


@router.post("/app/uninstalled")
async def app_uninstalled(request: Request, x_shopify_hmac_sha256: str | None = Header(default=None)):
    return await _handle(request, topic="app/uninstalled", hmac_header=x_shopify_hmac_sha256)


@router.get("/customer-data-requests")
def customer_data_requests(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
):
    response.headers["Cache-Control"] = "no-store"
    return {"items": privacy.list_customer_data_requests(db, shop_id=user.shop_id)}


@router.get("/customer-data-requests/{request_id}")
def customer_data_export(
    request_id: int,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
):
    result = privacy.export_customer_data_request(db, shop_id=user.shop_id, request_id=request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Privacy request not found.")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = f'attachment; filename="skubase-privacy-request-{request_id}.json"'
    return result


# Keep existing registered aliases compatible.
router.add_api_route("/customers_data_request", customers_data_request, methods=["POST"])
router.add_api_route("/customers_redact", customers_redact, methods=["POST"])
router.add_api_route("/shop_redact", shop_redact, methods=["POST"])
router.add_api_route("/app_uninstalled", app_uninstalled, methods=["POST"])
