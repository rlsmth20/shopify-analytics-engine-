"""Acknowledge durable receipt quickly; retry idempotent privacy work off-request."""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import hashlib
import json
import logging
import time
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.webhook_models import ShopifyWebhookJob
from app.services import shopify_privacy as privacy

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
LEASE_SECONDS = 300
_task = None
_wake = None


def enqueue(factory, *, topic, domain, payload, webhook_id, triggered_at=None):
    # Keep only identifiers needed for the requested operation, never customer
    # names, email, addresses, headers, HMAC signatures or the original body.
    minimal = {}
    if topic in {"customers/redact", "customers/data_request"}:
        field = "orders_to_redact" if topic == "customers/redact" else "orders_requested"
        minimal[field] = privacy.requested_order_ids(payload, field)
        if topic == "customers/data_request":
            request = payload.get("data_request")
            if isinstance(request, dict) and request.get("id"):
                minimal["data_request"] = {"id": str(request["id"])}
    timestamp = triggered_at.timestamp() if triggered_at else None
    # Include signed content/tenancy: a reused delivery header cannot suppress a
    # different tenant's operation. Stable retries map to the same receipt.
    key = hashlib.sha256(json.dumps([topic, domain, minimal, timestamp, webhook_id],
                                   sort_keys=True).encode()).hexdigest()
    with factory() as db:
        if db.get(ShopifyWebhookJob, key) is None:
            db.add(ShopifyWebhookJob(id=key, topic=topic, domain=domain,
                                    payload=minimal, triggered_at=timestamp))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if db.get(ShopifyWebhookJob, key) is None:
                    raise
    return key


def process_one(factory=SessionLocal, *, now=None):
    now = time.time() if now is None else now
    eligible = or_(ShopifyWebhookJob.status == "pending",
                   (ShopifyWebhookJob.status == "running") & (ShopifyWebhookJob.lease_until <= now))
    with factory() as db:
        # A process crash consumes the same bounded retry allowance.
        db.execute(update(ShopifyWebhookJob).where(ShopifyWebhookJob.status == "running",
            ShopifyWebhookJob.lease_until <= now, ShopifyWebhookJob.attempts >= MAX_ATTEMPTS)
            .values(status="failed", error="lease_expired", lease_token=None))
        candidates = list(db.scalars(select(ShopifyWebhookJob.id).where(eligible,
            ShopifyWebhookJob.due_at <= now, ShopifyWebhookJob.attempts < MAX_ATTEMPTS)
            .order_by(ShopifyWebhookJob.received_at).limit(4)))
        job = None
        for key in candidates:
            token = uuid.uuid4().hex
            changed = db.execute(update(ShopifyWebhookJob).where(ShopifyWebhookJob.id == key,
                eligible, ShopifyWebhookJob.due_at <= now, ShopifyWebhookJob.attempts < MAX_ATTEMPTS)
                .values(status="running", lease_token=token, lease_until=now + LEASE_SECONDS,
                        attempts=ShopifyWebhookJob.attempts + 1)).rowcount
            if changed:
                db.commit()
                job = db.get(ShopifyWebhookJob, key)
                break
        db.commit()
        if job is None:
            return False
        data = (job.topic, job.domain, dict(job.payload), job.triggered_at, job.attempts, job.id, job.lease_token)
    topic, domain, payload, timestamp, attempts, key, token = data
    try:
        triggered = datetime.fromtimestamp(timestamp, timezone.utc) if timestamp is not None else None
        with factory() as db:
            if topic == "customers/data_request":
                result = privacy.record_customer_data_request(db, shop_domain=domain, payload=payload, webhook_id=key)
            elif topic == "customers/redact":
                result = privacy.redact_customer_orders(db, shop_domain=domain, payload=payload)
            elif topic == "shop/redact":
                result = privacy.redact_shop(db, shop_domain=domain, triggered_at=triggered)
            elif topic == "app/uninstalled":
                result = privacy.mark_shop_uninstalled(db, shop_domain=domain, triggered_at=triggered)
            else:
                raise ValueError("Unsupported webhook topic")
        with factory() as db:
            db.execute(update(ShopifyWebhookJob).where(ShopifyWebhookJob.id == key,
                ShopifyWebhookJob.lease_token == token).values(status="done", completed_at=time.time(),
                    payload={}, domain="", error=None, lease_until=0, lease_token=None))
            db.commit()
        logger.info("shopify_webhook_completed receipt=%s topic=%s counts=%s", key, topic, result)
    except Exception as exc:
        # Never log the exception message: database errors can contain payloads.
        error = type(exc).__name__
        with factory() as db:
            db.execute(update(ShopifyWebhookJob).where(ShopifyWebhookJob.id == key,
                ShopifyWebhookJob.lease_token == token).values(
                    status="failed" if attempts >= MAX_ATTEMPTS else "pending", error=error,
                    due_at=now + min(3600, 30 * 2 ** (attempts - 1)), lease_until=0, lease_token=None))
            db.commit()
        logger.error("shopify_webhook_processing_failed receipt=%s topic=%s attempt=%s code=%s",
                     key, topic, attempts, error)
    return True


def wake():
    if _wake is not None:
        _wake.set()


async def _loop():
    while True:
        _wake.clear()
        try:
            for _ in range(10):
                if not await asyncio.to_thread(process_one):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("shopify_webhook_worker_unavailable code=%s", type(exc).__name__)
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(_wake.wait(), timeout=5)


def start():
    global _task, _wake
    if _task is None or _task.done():
        _wake = asyncio.Event()
        _task = asyncio.create_task(_loop())


async def stop():
    global _task, _wake
    if _task is not None:
        _task.cancel()
        with suppress(asyncio.CancelledError):
            await _task
        _task = None
        _wake = None
