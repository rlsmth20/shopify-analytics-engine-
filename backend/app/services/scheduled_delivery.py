"""Bounded scheduled-email delivery, with a frozen payload and durable unknown hold."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select, text

from app.db.models import DigestSendLog, ReportScheduleRecord, ScheduledEmailDeliveryRecord
from app.db.session import SessionLocal
from app.services.report_schedule_access import REPORT_CAPABILITIES, shop_may_send_scheduled_report
from app.services.transactional_email import EmailProviderUnavailable, send_prepared_email_receipt

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120
# Resend keys expire after 24h. Leave margin for clocks/network latency; an
# uncertain or old attempt must never be silently replayed beyond that window.
IDEMPOTENCY_WINDOW = timedelta(hours=23)


def utc_now():
    return datetime.now(timezone.utc)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def calendar_period(cadence: str, now: datetime):
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if cadence == "monthly":
        return f"monthly:{now:%Y-%m}", start.replace(day=1)
    start -= timedelta(days=start.weekday())
    return f"weekly:{start:%Y-%m-%d}", start


def _eligible(schedule) -> bool:
    return bool(schedule is not None and schedule.enabled and schedule.channel == "email"
                and schedule.report_type in REPORT_CAPABILITIES and schedule.cadence in {"weekly", "monthly"}
                and (schedule.report_type != "weekly_buy_list" or schedule.cadence == "weekly"))


def _due(cadence: str, now: datetime) -> bool:
    return now.day == 1 if cadence == "monthly" else now.weekday() == 0


def _failure(error: Exception):
    if isinstance(error, EmailProviderUnavailable):
        return "unavailable", "Email delivery is not configured. Contact info@skubase.io."
    if getattr(error, "error_type", None) == "HttpClientError":
        return "unknown", "Provider acceptance is uncertain. Check the recipient mailbox; this report is held to prevent duplicates."
    code = getattr(error, "status_code", getattr(error, "code", None))
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = None
    if code is not None:
        return ("failed" if code == 429 or code >= 500 else "unavailable"), f"Email provider returned HTTP {code}."
    if isinstance(error, ConnectionRefusedError):
        return "failed", "The email provider could not be reached."
    return "unknown", "Provider acceptance is uncertain. Check the recipient mailbox; this report is held to prevent duplicates."


def deliver_scheduled_email(schedule_id: int, build_payload, *, force: bool = False) -> bool:
    """Send at most one accepted email per schedule/calendar period.

    build_payload(db, schedule) runs only for a new period. Provider parameters
    (including recipient and rendered content) stay unchanged for every retry.
    """
    with SessionLocal() as db:
        schedule = db.get(ReportScheduleRecord, schedule_id)
        if not _eligible(schedule):
            return False
        authorized_identity = (schedule.shop_id, schedule.report_type)
        if not shop_may_send_scheduled_report(db, shop_id=schedule.shop_id, report_type=schedule.report_type):
            return False
        db.commit()  # Billing reconciliation may commit; claim only after it completes.
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        schedule = db.scalar(select(ReportScheduleRecord).where(ReportScheduleRecord.id == schedule_id)
                             .with_for_update().execution_options(populate_existing=True))
        if not _eligible(schedule) or (schedule.shop_id, schedule.report_type) != authorized_identity:
            return False
        now = utc_now()
        if not force and not _due(schedule.cadence, now):
            return False
        period_key, period_start = calendar_period(schedule.cadence, now)
        digest_type = "weekly_buy_list" if schedule.report_type == "weekly_buy_list" else f"report_{schedule.report_type}"
        row = db.scalar(select(ScheduledEmailDeliveryRecord).where(
            ScheduledEmailDeliveryRecord.schedule_id == schedule_id,
            ScheduledEmailDeliveryRecord.period_key == period_key,
        ).with_for_update())
        if row is None:
            # Preserve successful sends recorded before the durable ledger rollout.
            legacy = db.scalar(select(DigestSendLog.id).where(DigestSendLog.shop_id == schedule.shop_id,
                DigestSendLog.digest_type == digest_type, DigestSendLog.sent_at >= period_start).limit(1))
            if legacy is not None:
                return False
            payload = build_payload(db, schedule)
            if payload is None:
                return False
            # Building inventory reports can take time. Do not attach a new
            # request to an expired calendar period or start with a stale lease.
            now = utc_now()
            if calendar_period(schedule.cadence, now)[0] != period_key or (not force and not _due(schedule.cadence, now)):
                return False
            row = ScheduledEmailDeliveryRecord(id=str(uuid.uuid4()), schedule_id=schedule.id,
                shop_id=schedule.shop_id, report_type=schedule.report_type, period_key=period_key,
                payload=payload, status="pending", attempts=0, created_at=now)
            db.add(row)
            db.flush()
        now = utc_now()
        if calendar_period(schedule.cadence, now)[0] != period_key or (not force and not _due(schedule.cadence, now)):
            return False
        if row.status in {"accepted", "unknown"} or row.attempts >= MAX_ATTEMPTS:
            return False
        if row.lease_until:
            if _utc(row.lease_until) > now:
                return False
            row.status = "unknown"
            row.last_error = "The worker stopped before acceptance was recorded. Check the mailbox; this report is held to prevent duplicates."
            row.lease_until = row.lease_token = None
            history = list(row.attempt_history or [])
            if history:
                history[-1] = {**history[-1], "finished_at": now.isoformat(), "status": "unknown", "error": row.last_error}
                row.attempt_history = history
            db.commit()
            return False
        if row.first_attempt_at and now >= _utc(row.first_attempt_at) + IDEMPOTENCY_WINDOW:
            row.status = "unknown"
            row.last_error = "The safe provider retry window has ended. This report is held; contact info@skubase.io before resending."
            db.commit()
            return False
        if row.next_attempt_at and _utc(row.next_attempt_at) > now:
            return False
        if row.payload.get("to") != [schedule.recipient_email.strip()]:
            row.status = "unavailable"
            row.last_error = "The recipient changed after this period was prepared. Delivery is paused for this period; the next period will use the new recipient."
            db.commit()
            return False
        token = str(uuid.uuid4())
        row.lease_token, row.lease_until = token, now + timedelta(seconds=LEASE_SECONDS)
        row.first_attempt_at = row.first_attempt_at or now
        row.attempts += 1
        row.status, row.next_attempt_at = "pending", None
        row.attempt_history = [*(row.attempt_history or []), {"started_at": now.isoformat(), "status": "pending"}]
        delivery_id, payload = row.id, deepcopy(row.payload)
        db.commit()

    receipt, error, not_configured = None, None, False
    try:
        receipt = send_prepared_email_receipt(payload, idempotency_key=f"schedule-{delivery_id}")
        status = "accepted"
    except Exception as exc:
        status, error = _failure(exc)
        not_configured = isinstance(exc, EmailProviderUnavailable)
    finished = utc_now()
    with SessionLocal() as db:
        row = db.scalar(select(ScheduledEmailDeliveryRecord).where(ScheduledEmailDeliveryRecord.id == delivery_id).with_for_update())
        if row is None or row.lease_token != token:
            return False  # A stale worker must not overwrite a recovered/held attempt.
        row.status, row.provider_receipt, row.last_error = status, receipt, error
        row.lease_token = row.lease_until = None
        row.accepted_at = finished if status == "accepted" else None
        if not_configured:
            row.attempts -= 1  # No provider request occurred; a configuration check is not a send attempt.
            if row.attempts == 0:
                row.first_attempt_at = None
        row.next_attempt_at = (finished + timedelta(seconds=min(3600, 60 * 2 ** max(row.attempts - 1, 0)))
                               if status in {"failed", "unavailable"} and row.attempts < MAX_ATTEMPTS else None)
        if status in {"failed", "unavailable"} and row.attempts >= MAX_ATTEMPTS:
            row.last_error = error = f"{error} The retry limit for this report period has been reached."
        history = list(row.attempt_history or [])
        history[-1] = {**history[-1], "finished_at": finished.isoformat(), "status": status,
                       "provider_receipt": receipt, "error": error}
        row.attempt_history = history[-20:]
        if status == "accepted":
            db.add(DigestSendLog(shop_id=row.shop_id, digest_type=digest_type,
                                recipient_email=payload["to"][0], sent_at=finished))
        db.commit()
    return status == "accepted"


def schedule_delivery_summaries(db, schedule_ids: list[int]) -> dict[int, dict]:
    if not schedule_ids:
        return {}
    rows = db.scalars(select(ScheduledEmailDeliveryRecord).where(
        ScheduledEmailDeliveryRecord.schedule_id.in_(schedule_ids)).order_by(ScheduledEmailDeliveryRecord.created_at.desc())).all()
    summaries = {}
    now = utc_now()
    for row in rows:
        if row.schedule_id not in summaries:
            expired = row.status == "pending" and row.lease_until and _utc(row.lease_until) <= now
            summaries[row.schedule_id] = {
                "last_delivery_status": "unknown" if expired else row.status,
                "last_delivery_error": "A worker stopped before acceptance was recorded. This report is held for review." if expired else row.last_error,
                "last_sent_at": None, "delivery_attempts": row.attempts, "last_delivery_period": row.period_key,
            }
        if row.accepted_at and summaries[row.schedule_id]["last_sent_at"] is None:
            summaries[row.schedule_id]["last_sent_at"] = row.accepted_at
    return summaries
