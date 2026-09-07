"""Durable per-incident/channel acceptance, bounded retries, and crash evidence."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db.models import AlertDeliveryAttemptRecord, AlertEventRecord, AlertRuleRecord, NotificationChannelRecord
from app.db.session import SessionLocal
from app.schemas_v2 import AlertEvent
from app.services.notifications import deliver
from app.services.audit_log import record_audit_event

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def target_fingerprint(target: str) -> str:
    return hashlib.sha256(target.strip().encode()).hexdigest()


def _event_view(event, deliveries):
    accepted = sorted({row.channel for row in deliveries if row.status == "accepted"})
    errors = {row.channel: row.last_error for row in deliveries if row.last_error and row.status != "accepted"}
    statuses = {row.status for row in deliveries}
    status = ("partial" if accepted and statuses != {"accepted"} else "accepted" if accepted
              else "unknown" if "unknown" in statuses else "pending" if "pending" in statuses
              else "failed" if deliveries else "skipped")
    return AlertEvent(**event.payload, channels_sent=accepted, delivered=bool(accepted),
                      preview=False, delivery_status=status, delivery_errors=errors, resolved=event.resolved_at is not None,
                      uncertain_channels=sorted({row.channel for row in deliveries if row.status == "unknown"}))


def resolve_absent_incidents(shop_id: int, rule_id: str, active_subjects: set[str], now: datetime) -> None:
    with SessionLocal() as db:
        statement = update(AlertEventRecord).where(AlertEventRecord.shop_id == shop_id,
                    AlertEventRecord.rule_id == rule_id, AlertEventRecord.resolved_at.is_(None),
                    AlertEventRecord.created_at <= now)
        if active_subjects:
            statement = statement.where(AlertEventRecord.subject_key.not_in(active_subjects))
        db.execute(statement.values(resolved_at=now))
        db.commit()


def queue_uncertain_retry(*, shop_id: int, user_id: int, event_id: str, channel: str,
                         acknowledge_possible_duplicate: bool) -> None:
    if not acknowledge_possible_duplicate:
        raise ValueError("Check the destination and acknowledge that retrying may send a duplicate.")
    with SessionLocal() as db:
        event = db.scalar(select(AlertEventRecord).where(AlertEventRecord.id == event_id,
                          AlertEventRecord.shop_id == shop_id).with_for_update())
        if event is None:
            raise LookupError("Alert event not found.")
        if event.resolved_at is not None:
            raise ValueError("This inventory condition has resolved; no retry is needed.")
        config = db.get(NotificationChannelRecord, f"{shop_id}:{channel}")
        if not config or not config.enabled:
            raise ValueError("Enable the saved destination before retrying.")
        row = db.scalar(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.event_id == event_id,
                        AlertDeliveryAttemptRecord.channel == channel,
                        AlertDeliveryAttemptRecord.target_fingerprint == target_fingerprint(config.target)).with_for_update())
        if row is None or row.status != "unknown":
            raise ValueError("Only an uncertain send to the current saved destination can be retried.")
        row.status, row.attempts, row.lease_until, row.next_attempt_at = "pending", 0, None, None
        row.lease_token = None
        row.last_error = None
        record_audit_event(db, shop_id=shop_id, user_id=user_id, event_type="alert_retry_requested",
                           entity_type="alert_delivery", entity_id=row.id,
                           summary=f"A merchant requested retry of uncertain {channel} delivery after acknowledging duplicate risk.",
                           metadata={"event_id": event_id, "channel": channel, "acknowledged_possible_duplicate": True}, commit=False)
        db.commit()


def list_persisted_events(shop_id: int, limit: int = 50) -> list[AlertEvent]:
    with SessionLocal() as db:
        events = db.scalars(select(AlertEventRecord).where(AlertEventRecord.shop_id == shop_id)
                           .order_by(AlertEventRecord.created_at.desc()).limit(max(1, min(limit, 500)))).all()
        if not events:
            return []
        deliveries = db.scalars(select(AlertDeliveryAttemptRecord)
                                .where(AlertDeliveryAttemptRecord.event_id.in_([event.id for event in events]))).all()
        grouped = {}
        for row in deliveries:
            grouped.setdefault(row.event_id, []).append(row)
        return [_event_view(event, grouped.get(event.id, [])) for event in reversed(events)]


def dispatch_alert(*, rule, sku_id, sku_name, message, now, allowed_channels, cooldown_seconds):
    """Retry only while a fresh evaluation still finds this incident relevant.

    PostgreSQL row locking on the rule serializes incident creation across workers.
    A committed channel lease precedes provider I/O. Lost acceptance stays unknown.
    """
    now = utc_now()
    subject_key = target_fingerprint(sku_id or sku_name or "storewide")
    with SessionLocal() as db:
        stored_rule = db.scalar(select(AlertRuleRecord).where(AlertRuleRecord.id == rule.id).with_for_update())
        if stored_rule is None or not stored_rule.enabled or stored_rule.shop_id is None:
            return None
        configs = db.scalars(select(NotificationChannelRecord)
                             .where(NotificationChannelRecord.channel.like(f"{stored_rule.shop_id}:%"))).all()
        destinations = [(config.channel.split(":", 1)[1], config) for config in configs
                        if config.enabled and config.target.strip()]
        destinations = [(channel, config) for channel, config in destinations
                        if channel in stored_rule.channels and channel != "sms"
                        and (allowed_channels is None or channel in allowed_channels)]
        if not destinations:
            return None
        event = db.scalar(select(AlertEventRecord).where(AlertEventRecord.shop_id == stored_rule.shop_id,
                          AlertEventRecord.rule_id == rule.id, AlertEventRecord.subject_key == subject_key)
                          .order_by(AlertEventRecord.created_at.desc()).limit(1))
        if event is None and stored_rule.last_fired_at and now < _utc(stored_rule.last_fired_at) + timedelta(seconds=cooldown_seconds):
            # Migration cannot reconstruct old per-SKU receipts. Preserve the
            # existing cooldown once; after the first ledger event use SKU scope.
            has_ledger_history = db.scalar(select(AlertEventRecord.id).where(AlertEventRecord.rule_id == rule.id).limit(1))
            if has_ledger_history is None:
                return None
        rows = db.scalars(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.event_id == event.id)).all() if event else []
        recovered_uncertainty = False
        for row in rows:
            if row.lease_until and _utc(row.lease_until) <= now:
                row.status = "unknown"
                row.last_error = "The worker stopped before provider acceptance was recorded. Review the destination before retrying."
                row.lease_until = None
                row.lease_token = None
                history = list(row.attempt_history or [])
                if history:
                    history[-1] = {**history[-1], "status": "unknown", "error": row.last_error}
                    row.attempt_history = history
                recovered_uncertainty = True
        anchor = max([_utc(event.created_at), *[_utc(row.accepted_at) for row in rows if row.accepted_at]]) if event else now
        # Ambiguous attempts need review; a normal retry must not duplicate a
        # Slack/webhook message accepted just before a process or network failure.
        uncertain = any(row.status == "unknown" or row.lease_until is not None for row in rows)
        if event is None or event.resolved_at is not None or (not uncertain and now >= anchor + timedelta(seconds=max(cooldown_seconds, 60))):
            event_id = str(uuid.uuid4())
            event = AlertEventRecord(id=event_id, shop_id=stored_rule.shop_id, rule_id=rule.id,
                    subject_key=subject_key, created_at=now,
                    payload=dict(id=event_id, rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                                 trigger=rule.trigger, sku_id=sku_id, sku_name=sku_name, message=message,
                                 fired_at=now.isoformat()))
            db.add(event)
            db.flush()
            rows = []
        pending_ids = []
        for channel, config in destinations:
            fingerprint = target_fingerprint(config.target)
            row = next((item for item in rows if item.channel == channel and item.target_fingerprint == fingerprint), None)
            if row is None:
                row = AlertDeliveryAttemptRecord(id=str(uuid.uuid4()), event_id=event.id, channel=channel,
                                                target_fingerprint=fingerprint, status="pending", attempts=0)
                db.add(row)
            if row.status in {"pending", "failed", "unavailable"}:
                pending_ids.append(row.id)
        event_id = event.id
        db.commit()
    attempted = recovered_uncertainty
    for delivery_id in pending_ids:
        attempted = _attempt(delivery_id) or attempted
    if not attempted:
        return None
    with SessionLocal() as db:
        event = db.get(AlertEventRecord, event_id)
        rows = db.scalars(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.event_id == event_id)).all()
        return _event_view(event, rows)


def _attempt(delivery_id: str) -> bool:
    now = utc_now()
    with SessionLocal() as db:
        row = db.scalar(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.id == delivery_id).with_for_update())
        if row is None or row.status in {"accepted", "unknown"} or row.attempts >= MAX_ATTEMPTS:
            return False
        if row.next_attempt_at and _utc(row.next_attempt_at) > now:
            return False
        if row.lease_until:
            if _utc(row.lease_until) > now:
                return False
            row.status, row.last_error = "unknown", "The worker stopped before provider acceptance was recorded. Review the destination before retrying."
            row.lease_until = None
            row.lease_token = None
            db.commit()
            return True
        event = db.get(AlertEventRecord, row.event_id)
        if event is None or event.resolved_at is not None:
            return False
        rule = db.get(AlertRuleRecord, event.rule_id)
        config = db.get(NotificationChannelRecord, f"{event.shop_id}:{row.channel}")
        if (not rule or not rule.enabled or row.channel not in rule.channels or not config or not config.enabled
                or target_fingerprint(config.target) != row.target_fingerprint):
            return False
        target, channel = config.target, row.channel
        payload = dict(event.payload)
        row.attempts += 1
        row.status = "pending"
        token = str(uuid.uuid4())
        row.lease_token = token
        row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        row.attempt_history = [*(row.attempt_history or []), {"attempt": row.attempts, "started_at": now.isoformat(), "status": "pending"}]
        db.commit()
    record = deliver(channel=channel, target=target,
                     subject=f"[{payload['severity'].upper()}] {payload['rule_name']}", body=payload["message"],
                     idempotency_key=f"alert-{delivery_id}")
    finished_at = utc_now()
    with SessionLocal() as db:
        row = db.scalar(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.id == delivery_id).with_for_update())
        if row is None or row.lease_token != token:
            return False
        row.status = record.status
        row.provider_receipt = record.provider_receipt
        row.last_error = record.error
        row.lease_until = None
        row.lease_token = None
        row.accepted_at = finished_at if record.delivered else None
        row.next_attempt_at = finished_at + timedelta(seconds=min(3600, 60 * 2 ** (row.attempts - 1))) if record.status in {"failed", "unavailable"} else None
        history = list(row.attempt_history or [])
        history[-1] = {**history[-1], "status": record.status, "finished_at": finished_at.isoformat(),
                       "provider_receipt": record.provider_receipt, "error": record.error}
        row.attempt_history = history
        if record.delivered:
            event = db.get(AlertEventRecord, row.event_id)
            rule = db.get(AlertRuleRecord, event.rule_id)
            if rule:
                rule.last_fired_at = finished_at
        db.commit()
    return True
