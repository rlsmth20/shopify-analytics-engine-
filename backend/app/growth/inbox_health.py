"""Mailbox transport evidence, separate from merchant engagement and send authority."""
import math
import os
import time
from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy import select

from .models import Evidence, Memory
from .outbound import lock
from .policy import Policy
from .store import digest, insert_once, remember

MAILBOX = "info@skubase.io"
POLL_STALE_SECONDS = 900
VERIFICATION_REVIEW_SECONDS = 7 * 86400


def _state_key():
    return "inbox_transport:" + digest(MAILBOX)[:16]


def _state(db):
    # Select the value directly: a cached ORM instance must not defeat the lock.
    return dict(db.scalar(select(Memory.value).where(
        Memory.namespace == "working", Memory.key == _state_key())) or {})


def _save(db, value):
    db.scalar(select(Memory).where(Memory.namespace == "working", Memory.key == _state_key())
              .execution_options(populate_existing=True))
    remember(db, "working", _state_key(), value, source="inbox_transport")


def record_poll(db, *, completed_at, replies_ingested=None, failure_class=None):
    lock(db)
    state = _state(db)
    if (completed_at > state.get("last_poll_at", 0)
            or (completed_at == state.get("last_poll_at") and failure_class)):
        state.update(last_poll_at=completed_at,
                     last_poll_status="failed" if failure_class else "success",
                     latest_poll_replies_ingested=None if failure_class else replies_ingested,
                     last_poll_failure_class=failure_class)
    if not failure_class and completed_at > state.get("last_successful_poll_at", 0):
        state["last_successful_poll_at"] = completed_at
    _save(db, state)


def observe_receipt(db, row, *, observed_at):
    """Retain approved-recipient metadata once, including excluded self checks."""
    from email.utils import parseaddr
    # Observation precedes the existing ingestion dedupe. Malformed metadata on
    # an already-processed row must not prevent later replies being ingested.
    # New malformed messages still pass to the unchanged ingestion validation.
    if not isinstance(row, Mapping):
        return False
    provider_id = row.get("id")
    recipients = row.get("to")
    sender = row.get("from", "")
    if (not isinstance(provider_id, str) or not provider_id.strip() or len(provider_id) > 200
            or not isinstance(recipients, list) or not all(isinstance(value, str) for value in recipients)
            or not isinstance(sender, str)):
        return False
    if MAILBOX not in [parseaddr(value)[1].lower() for value in recipients]:
        return False
    if db.scalar(select(Evidence.id).where(Evidence.key == "inbound-transport:" + provider_id)):
        return False
    received_at = None
    try:
        parsed = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        received_at = parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
        if not math.isfinite(received_at) or received_at <= 0 or received_at > observed_at + 300:
            received_at = None
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        pass
    lock(db)
    receipt, fresh = insert_once(db, Evidence, key="inbound-transport:" + provider_id,
        kind="INBOUND_TRANSPORT_RECEIPT", subject=MAILBOX, source="resend_receiving_api",
        epistemic="OBSERVATION", occurred_at=received_at or observed_at,
        data={"provider_id": provider_id, "mailbox": MAILBOX, "received_at": received_at,
              "observed_at": observed_at, "provider_created_at": str(row.get("created_at", ""))[:100],
              "self_check": parseaddr(sender)[1].lower() == MAILBOX})
    if not fresh:
        return False
    state = _state(db)
    state["last_approved_receipt_observed_at"] = max(state.get("last_approved_receipt_observed_at", 0), observed_at)
    if received_at and received_at > state.get("last_approved_receipt_at", 0):
        state.update(last_approved_receipt_at=received_at, last_receipt_evidence_id=receipt.id)
    _save(db, state)
    return True


def record_bridge_verification(db, evidence_id, *, now=None):
    """Trusted operator use only; polling and incoming messages cannot call this.

    The retained FACT must independently verify the Google-to-Resend path. A
    Resend receipt alone, especially pre-migration mail, is insufficient proof.
    """
    now = time.time() if now is None else now
    evidence = db.get(Evidence, evidence_id)
    if (not evidence or evidence.kind != "MAILBOX_BRIDGE_VERIFIED"
            or evidence.source != "owner_verified_transport" or evidence.epistemic != "FACT"
            or evidence.subject != MAILBOX or evidence.data.get("mailbox") != MAILBOX
            or evidence.data.get("verified") is not True
            or not isinstance(evidence.data.get("receipt_ids"), list)
            or not evidence.data["receipt_ids"]
            or not all(isinstance(value, str) and value.strip() for value in evidence.data["receipt_ids"])
            or not math.isfinite(evidence.occurred_at) or not 0 < evidence.occurred_at <= now):
        raise ValueError("Retained independent business-mailbox verification is required")
    lock(db)
    state = _state(db)
    if evidence.occurred_at > state.get("last_bridge_verified_at", 0):
        state.update(last_bridge_verified_at=evidence.occurred_at, bridge_evidence_id=evidence.id)
        _save(db, state)


def projection(db, *, now=None):
    now = time.time() if now is None else now
    state = _state(db)
    poll_at = state.get("last_poll_at")
    proof_at = state.get("last_bridge_verified_at")
    if os.getenv("GROWTH_INBOUND_ENABLED") != "true":
        status, label = "disabled", "Inbox monitoring is off"
        explanation = "The growth worker is not checking incoming business mail."
    elif Policy.from_env().sender != MAILBOX or not os.getenv("GROWTH_RESEND_API_KEY"):
        status, label = "configuration_required", "Inbox connection needs attention"
        explanation = "The approved business mailbox and its receiving connection must be configured."
    elif not poll_at:
        status, label = "not_checked", "Waiting for the first inbox check"
        explanation = "No completed inbox check has been recorded yet."
    elif state.get("last_poll_status") == "failed":
        status, label = "poll_failed", "The latest inbox check failed"
        explanation = "Incoming replies may be delayed. Check the agent's recorded errors; prior delivery evidence is preserved."
    elif now - poll_at > POLL_STALE_SECONDS:
        status, label = "poll_stale", "Inbox checks are overdue"
        explanation = "No successful check has completed in the past 15 minutes. Replies may be waiting."
    elif not proof_at:
        status, label = "verification_unrecorded", "Inbox checks work; delivery path unverified"
        explanation = "Resend polling succeeds, but independent proof that Gmail copies reach the agent has not been recorded. An empty check is normal and does not verify forwarding."
    elif now - proof_at > VERIFICATION_REVIEW_SECONDS:
        status, label = "verification_stale", "Inbox checks work; review the delivery path"
        explanation = "The last independent Gmail-to-agent verification is over seven days old. This is a verification reminder, not evidence of lost mail; a quiet inbox is normal."
    else:
        status, label = "verified", "Inbox checks work; delivery path recently verified"
        explanation = "A recent independent check verified the Gmail-to-agent path. A successful check with no new messages is normal; polling alone does not prove future delivery."
    return {"mailbox": MAILBOX, "status": status, "label": label, "explanation": explanation,
            **{key: state.get(key) for key in (
                "last_poll_at", "last_poll_status", "last_successful_poll_at", "latest_poll_replies_ingested",
                "last_approved_receipt_at", "last_approved_receipt_observed_at", "last_bridge_verified_at")},
            "verification_due_after_seconds": VERIFICATION_REVIEW_SECONDS,
            "poll_stale_after_seconds": POLL_STALE_SECONDS}
