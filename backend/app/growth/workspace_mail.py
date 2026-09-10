"""Google Workspace browser transport using the shared send ledger and mailbox.

No OAuth app, paid provider or alternate mailbox is needed. The authenticated
browser executor submits once and retains the Gmail Sent-thread receipt.
"""
import time
import re
from html import escape
from urllib.parse import urlparse

from sqlalchemy import select

from .models import Contact, Evidence, FirstContact, Memory, Message
from .policy import GrowthError
from .store import digest, get_memory, record, remember

SENDER = "info@skubase.io"
PROVIDER = "google_workspace"


def defer_capped_tasks(db, now=None):
    """Wait without a model turn or retry; caller holds the dispatch lock.

    Only explicit email first-contact tasks with no prior intent are deferred.
    Legacy task text uses the controlled channel=email field. Replies and
    receipt recovery remain independent.
    """
    if not selected(db):
        return 0
    now = time.time() if now is None else now
    from .email_ramp import status as ramp_status
    ramp = ramp_status(db, SENDER, now)
    if ramp['remaining']:
        return 0
    count = 0
    for row in db.scalars(select(Memory).where(Memory.namespace == 'operator_task',
            Memory.value['status'].as_string() == 'pending',
            Memory.value['stage'].as_string().in_(['send', 'outreach']))):
        task = row.value
        if (task.get('retry_at', 0) >= ramp['resets_at'] or task.get('lease_until', 0) > now
                or not (task.get('channel') == 'email' or re.search(r'\bchannel\s*=\s*email\b', task.get('decision', ''), re.I))):
            continue
        if task.get('contact_id') and db.scalar(select(FirstContact.id).where(FirstContact.contact_id == task['contact_id'])):
            continue
        event = record(db, f"email-ramp-defer:{task['id']}:{ramp['day']}", 'EMAIL_SEND_DEFERRED', task['id'],
            {'reason': 'EMAIL_DAILY_CAP_REACHED', 'resume_at': ramp['resets_at'],
             'actual_email_first_contacts': ramp['actual_first_contacts_today'], 'ceiling': ramp['daily_ceiling']})
        remember(db, 'operator_task', task['id'], {**task, 'channel': 'email',
            'retry_at': ramp['resets_at'], 'defer_reason': 'EMAIL_DAILY_CAP_REACHED',
            'defer_evidence_id': event.id, 'next_step': 'Resume after the email ramp resets; use other permitted channels meanwhile.'})
        count += 1
    return count


def format_message(body, business):
    """Keep the approved words, add readable paragraphs and a separate footer."""
    paragraphs = []
    for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n").strip()):
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", block)
        paragraph = ""
        for sentence in sentences:
            if paragraph and (len(paragraph) + len(sentence) > 260 or sentence.rstrip().endswith("?")):
                paragraphs.append(paragraph)
                paragraph = ""
            paragraph = (paragraph + " " + sentence).strip()
        if paragraph:
            paragraphs.append(paragraph)
    text = "\n\n".join(paragraphs)
    text += "\n\nRainer\n" + business["name"] + "\n\n" + business["postal_address"] + "\n\nTo opt out, reply unsubscribe."
    # Gmail rich-text editors collapse raw newline characters inserted with
    # setValue. Clipboard HTML uses explicit blocks; escape all merchant text.
    html = '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5">'
    html += "".join("<div>" + (escape(line) if line else "<br>") + "</div>" for line in text.split("\n"))
    return text, html + "</div>"


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
    body, html_body = format_message(body, business)
    return {"sender": SENDER, "recipient": recipient, "subject": subject, "body": body,
            "html_body": html_body, "format_version": "paragraphs_v1", "email_source": payload["email_source"]}


def retain_intent(db, reservation_id, contact, experiment_id, prepared, cohort):
    row = Message(key="workspace:" + reservation_id, contact_id=contact.id,
        experiment_id=experiment_id, direction="out", subject=prepared["subject"],
        body=prepared["body"], status="draft")
    db.add(row); db.flush()
    remember(db, "outreach_email", row.id, {"provider": PROVIDER, "sender": SENDER,
        "kind": "first_contact", "safe_test": False, "actual_recipient": prepared["recipient"],
        "recipient": prepared["recipient"], "reservation_id": reservation_id, "cohort": cohort,
        "email_source": prepared["email_source"], "wire_body": prepared["body"],
        "html_body": prepared["html_body"], "format_version": prepared["format_version"]})
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
