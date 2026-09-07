"""Notification drivers report provider acceptance, never guaranteed inbox delivery."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.schemas_v2 import NotificationChannel
from app.services.notification_targets import NotificationHttpError, post_public_json, validate_target

logger = logging.getLogger(__name__)


@dataclass
class DeliveryRecord:
    channel: NotificationChannel
    target: str
    subject: str
    body: str
    delivered: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "accepted"
    provider_receipt: str | None = None


def channel_availability(channel: str) -> tuple[bool, str]:
    if channel == "sms":
        return False, "SMS is planned and is not available yet. Use email or Slack."
    if channel == "email" and not os.getenv("RESEND_API_KEY"):
        return False, "The email provider is not configured on the server. Contact support."
    return True, "Email provider configured; send a test to confirm acceptance." if channel == "email" else "Add your own destination and send a test."


def deliver(*, channel: NotificationChannel, target: str, subject: str, body: str,
            idempotency_key: str | None = None) -> DeliveryRecord:
    record = DeliveryRecord(channel, target, subject, body, delivered=False, status="failed")
    available, reason = channel_availability(channel)
    if not available:
        record.status, record.error = "unavailable", reason
        return record
    try:
        target = validate_target(channel, target)
        if channel == "email":
            from app.services.transactional_email import send_alert_email_receipt
            record.provider_receipt = send_alert_email_receipt(to=target, subject=subject, body=body,
                                                               idempotency_key=idempotency_key)
        elif channel == "slack":
            post_public_json(target, {"text": f"*{subject}*\n{body}"})
        else:
            try:
                timeout = int(os.getenv("GENERIC_WEBHOOK_TIMEOUT", "10"))
            except ValueError:
                timeout = 10
            post_public_json(target, {"subject": subject, "body": body,
                             "emitted_at": datetime.now(timezone.utc).isoformat(), "source": "skubase"}, timeout=timeout)
        record.delivered, record.status = True, "accepted"
    except ValueError:
        record.status, record.error = "unavailable", "The destination or provider request is invalid. Review the channel settings."
    except NotificationHttpError as exc:
        record.status = "failed" if exc.status == 429 or exc.status >= 500 else "unavailable"
        record.error = str(exc)
    except Exception as exc:
        # A lost response can follow acceptance. Never silently replay an
        # uncertain non-idempotent Slack/webhook send.
        status_code = getattr(exc, "status_code", getattr(exc, "code", None))
        try:
            status_code = int(status_code)
        except (TypeError, ValueError):
            status_code = None
        if getattr(exc, "error_type", None) == "HttpClientError":
            record.status, record.error = "unknown", "Email provider acceptance could not be confirmed. Check the destination before retrying."
        elif isinstance(status_code, int):
            record.status = "failed" if status_code == 429 or status_code >= 500 else "unavailable"
            record.error = f"Email provider returned HTTP {status_code}."
        elif isinstance(exc, ConnectionRefusedError):
            record.status, record.error = "failed", "The notification endpoint could not be reached."
        else:
            record.status, record.error = "unknown", "Provider acceptance could not be confirmed. Check the destination before retrying."
        logger.warning("Notification acceptance not confirmed; channel=%s status=%s", channel, record.status)
    return record
