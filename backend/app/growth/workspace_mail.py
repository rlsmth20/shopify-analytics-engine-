"""Google Workspace browser transport using the shared send ledger and mailbox.

No OAuth app, paid provider or alternate mailbox is needed. The authenticated
browser executor submits once and retains the Gmail Sent-thread receipt.
"""
import time
from urllib.parse import urlparse

from sqlalchemy import select

from .models import Contact, Evidence, Message
from .policy import GrowthError
from .store import digest, get_memory, remember

SENDER = "info@skubase.io"
PROVIDER = "google_workspace"


def selected(db):
    return get_memory(db, "strategic", "email_transport").get("provider") == PROVIDER


def status(db):
    from .email_ramp import status as ramp_status
    cfg = get_memory(db, "strategic", "email_transport")
    business = get_memory(db, "strategic", "email_business_identity")
    ramp = ramp_status(db, SENDER)
    blockers = []
    if not selected(db) or cfg.get("enabled") is not True or cfg.get("sender") != SENDER:
        blockers.append("WORKSPACE_TRANSPORT_DISABLED")
    if not ramp["authentication"]["verified"]:
        blockers.append("EMAIL_AUTHENTICATION_NOT_VERIFIED")
    if not business.get("name") or not business.get("postal_address"):
        blockers.append("BUSINESS_POSTAL_IDENTITY_REQUIRED")
    proof = cfg.get("transport_test_evidence_id")
    if not isinstance(proof, int) or not db.get(Evidence, proof) or ramp["authentication"]["evidence"].get("evidence_id") != proof:
        blockers.append("WORKSPACE_TRANSPORT_TEST_REQUIRED")
    health = get_memory(db, "working", "outreach_email_health")
    if health.get("paused"):
        blockers.append(health.get("reason", "DELIVERABILITY_HOLD"))
    return {"provider": PROVIDER, "sender": SENDER, "transport": "authenticated_browser",
            "ready": not blockers, "blockers": blockers, "safe_test_mode": False,
            "daily_limit": ramp["daily_ceiling"], "ramp": ramp, "health": health,
            "all_channel_daily_limit": get_memory(db, "strategic", "outreach_policy").get("daily_new_contact_limit")}


def require_send(db, recipient, *, advance=True):
    from .outreach_email import address
    from .email_ramp import status as ramp_status
    ready = status(db)
    if not ready["ready"]:
        raise GrowthError(",".join(ready["blockers"]), "configuration")
    recipient = address(recipient)
    if recipient.rsplit("@", 1)[1] == "skubase.io" or get_memory(db, "email_suppression", digest(recipient)):
        raise GrowthError("SUPPRESSED_OR_INTERNAL_RECIPIENT")
    ramp = ramp_status(db, SENDER, persist=True, advance=advance)
    if not ramp["remaining"]:
        raise GrowthError("EMAIL_RAMP_DAILY_CEILING; use other channels until the next Pacific day", "capacity")
    return recipient


def prepare(db, contact, payload):
    recipient = require_send(db, payload.get("recipient"))
    if payload.get("sender", SENDER) != SENDER:
        raise GrowthError("Only the approved Skubase Workspace mailbox may send")
    subject = payload.get("subject", "").strip()
    if not subject or len(subject) > 200 or any(c in subject for c in "\r\n"):
        raise GrowthError("A concise single-line email subject is required")
    source = urlparse(payload.get("email_source", ""))
    if source.scheme != "https" or not source.hostname:
        raise GrowthError("Recipient requires its actual published business-contact source")
    if contact.email and contact.email.lower() != recipient:
        raise GrowthError("Resolve the merchant contact identity before changing address")
    existing = db.scalar(select(Contact).where(Contact.email == recipient, Contact.id != contact.id))
    if existing:
        raise GrowthError("Resolve the existing merchant email identity before contact")
    other = db.scalar(select(Message.id).where(Message.direction == "out",
        Message.contact_id == contact.id, Message.sent_at.is_not(None)).limit(1))
    if other:
        raise GrowthError("Previously contacted merchant; use its existing conversation")
    contact.email = recipient
    body = payload["body"].strip()
    if not body or len(body) > 2500 or "\u2014" in body + subject:
        raise GrowthError("Use concise outreach without em dashes")
    business = get_memory(db, "strategic", "email_business_identity")
    body += "\n\n" + business["name"] + "\n" + business["postal_address"] + "\nTo opt out, reply unsubscribe."
    return {"sender": SENDER, "recipient": recipient, "subject": subject, "body": body,
            "email_source": payload["email_source"]}


def retain_intent(db, reservation_id, contact, experiment_id, prepared, cohort):
    row = Message(key="workspace:" + reservation_id, contact_id=contact.id,
        experiment_id=experiment_id, direction="out", subject=prepared["subject"],
        body=prepared["body"], status="draft")
    db.add(row); db.flush()
    remember(db, "outreach_email", row.id, {"provider": PROVIDER, "sender": SENDER,
        "kind": "first_contact", "safe_test": False, "actual_recipient": prepared["recipient"],
        "recipient": prepared["recipient"], "reservation_id": reservation_id, "cohort": cohort,
        "email_source": prepared["email_source"], "wire_body": prepared["body"]})
    return row


def authorize(db, reservation):
    row = db.scalar(select(Message).where(Message.key == "workspace:" + reservation.id))
    if not row or digest(row.body) != reservation.body_hash:
        raise GrowthError("Workspace message does not match its reserved body")
    meta = get_memory(db, "outreach_email", row.id)
    require_send(db, meta.get("actual_recipient"))
    row.status = "sending"


def receipt(db, reservation, outcome, url):
    row = db.scalar(select(Message).where(Message.key == "workspace:" + reservation.id))
    if not row:
        raise GrowthError("Workspace message intent is missing")
    if outcome == "sent":
        parsed = urlparse(url or "")
        if parsed.scheme != "https" or parsed.hostname != "mail.google.com" or not parsed.fragment or "/" not in parsed.fragment:
            raise GrowthError("Retain the actual Gmail Sent-thread URL after matching recipient, subject and body")
        row.sent_at = reservation.sent_at
        row.status = "sent"
        row.provider_id = "gmail:" + digest(url)
        contact = db.get(Contact, row.contact_id)
        if contact and not contact.suppressed:
            contact.status = "contacted"
        from .email_ramp import status as ramp_status
        db.flush()
        ramp_status(db, SENDER, persist=True, confirmed_at=reservation.sent_at, advance=False)
    else:
        row.status = "unknown"
    meta = get_memory(db, "outreach_email", row.id)
    remember(db, "outreach_email", row.id, {**meta, "state": row.status, "receipt_url": url,
        "attempted_at": reservation.reserved_at})
