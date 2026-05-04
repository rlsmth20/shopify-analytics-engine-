"""Notification delivery abstraction.

Provides a single `deliver()` entry point that routes to the configured channel.
Real credentials are read from environment variables — when they're absent the
service falls back to an in-memory sink so dev + test runs succeed without
side effects.

Env vars:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
    SLACK_WEBHOOK_URL        (default, can be overridden per-alert)
    GENERIC_WEBHOOK_TIMEOUT  (seconds)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

from app.schemas_v2 import NotificationChannel

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


# In-memory sink used for dev / test when credentials aren't configured.
_DEV_SINK: list[DeliveryRecord] = []


def recent_deliveries(limit: int = 50) -> list[DeliveryRecord]:
    return list(_DEV_SINK[-limit:])


def deliver(
    *,
    channel: NotificationChannel,
    target: str,
    subject: str,
    body: str,
) -> DeliveryRecord:
    """Route a notification to the right channel driver.

    Returns a DeliveryRecord regardless of success so callers can log the attempt.
    """
    try:
        if channel == "email":
            _send_email(target, subject, body)
        elif channel == "sms":
            _send_sms(target, body)
        elif channel == "slack":
            _send_slack(target, subject, body)
        elif channel == "webhook":
            _send_webhook(target, subject, body)
        else:
            raise ValueError(f"Unknown notification channel: {channel}")

        record = DeliveryRecord(
            channel=channel,
            target=target,
            subject=subject,
            body=body,
            delivered=True,
        )
    except Exception as exc:  # noqa: BLE001 — we deliberately capture any driver failure
        logger.exception("Notification delivery failed on channel=%s target=%s", channel, target)
        record = DeliveryRecord(
            channel=channel,
            target=target,
            subject=subject,
            body=body,
            delivered=False,
            error=str(exc),
        )

    _DEV_SINK.append(record)
    return record


# ---------------------------------------------------------------------------
# Channel drivers
# ---------------------------------------------------------------------------

def _send_email(target: str, subject: str, body: str) -> None:
    from app.services.transactional_email import send_alert_email

    sent = send_alert_email(to=target, subject=subject, body=body)
    if not sent:
        # Resend not configured — fall back to dev-log so alerts don't crash.
        logger.info("[dev-email] to=%s subject=%s", target, subject)


def _send_sms(target: str, body: str) -> None:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    sender = os.getenv("TWILIO_FROM")
    if not (sid and token and sender):
        logger.info("[dev-sms] to=%s body=%s", target, body[:80])
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = f"From={sender}&To={target}&Body={body[:1400]}".encode("utf-8")
    req = urllib_request.Request(url, data=data, method="POST")
    basic = f"{sid}:{token}".encode("utf-8")
    import base64

    req.add_header("Authorization", b"Basic " + base64.b64encode(basic))
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib_request.urlopen(req, timeout=10):
            pass
    except URLError as exc:
        raise RuntimeError(f"Twilio request failed: {exc}") from exc


def _send_slack(webhook_url: str, subject: str, body: str) -> None:
    if not webhook_url:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.info("[dev-slack] subject=%s", subject)
        return

    payload = {
        "text": f"*{subject}*\n{body}",
        "attachments": [
            {
                "color": "#e43d3d",
                "fields": [{"title": subject, "value": body, "short": False}],
            }
        ],
    }
    req = urllib_request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(req, timeout=10):
            pass
    except URLError as exc:
        raise RuntimeError(f"Slack webhook failed: {exc}") from exc


def _send_webhook(target: str, subject: str, body: str) -> None:
    payload = {
        "subject": subject,
        "body": body,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "source": "inventory-command",
    }
    timeout = int(os.getenv("GENERIC_WEBHOOK_TIMEOUT", "10"))
    req = urllib_request.Request(
        target,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout):
            pass
    except URLError as exc:
        raise RuntimeError(f"Webhook delivery failed: {exc}") from exc
