"""Dedicated business email outbox. Ambiguous effects are never blindly replayed."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import requests
from email.utils import parseaddr

from sqlalchemy import func, select, update

from .model_router import reserve
from .models import Contact, Evidence, Experiment, Message, Usage, Work
from .policy import GrowthError, Policy, classify_reply
from .skills import active_skill
from .store import digest, enqueue, insert_once, record, require_lease


def resend_request(path, *, data=None, key=None):
    token = os.getenv("GROWTH_RESEND_API_KEY", "")
    if not token:
        raise GrowthError("Dedicated Resend key missing", "configuration")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
               "User-Agent": "SkubaseGrowth/1.0 (info@skubase.io)"}
    if key:
        headers["Idempotency-Key"] = key
    try:
        # Use the same requests transport as the provider SDK, with a per-request
        # dedicated key instead of mutating the transactional SDK's global key.
        with requests.request("POST" if data else "GET", "https://api.resend.com/" + path,
                              json=data, headers=headers, timeout=20, stream=True, allow_redirects=False) as response:
            if response.status_code >= 300:
                raise GrowthError(f"Resend HTTP {response.status_code}",
                                  "configuration" if response.status_code in (401, 403) else "transient")
            raw = response.raw.read(256001, decode_content=True)
            if len(raw) > 256000:
                raise GrowthError("Resend response exceeds bounded read", "permanent")
            return json.loads(raw)
    except (requests.RequestException, TimeoutError, ValueError):
        raise GrowthError("Resend transport result unknown", "ambiguous") from None


def draft_first_contact(db, contact, experiment, variant):
    if contact.suppressed or not contact.qualification.get("qualified"):
        raise GrowthError("Contact declined or is not qualified")
    facts = [f for f in contact.facts if f.get("verified") is True and f.get("source") and 5 <= len(f.get("text", "")) <= 180]
    if not facts:
        raise GrowthError("No verified personalization fact")
    fact = facts[0]["text"].replace("\n", " ").replace("\r", " ")
    # Affiliation is explicit. Quotation preserves what is actually known.
    problem = "cash tied up in slow-moving stock" if variant == "cash" else "what to reorder before stock runs out"
    body = (f"Hi,\n\nI'm Skubase's automated growth assistant. Your public information says: “{fact}”.\n\n"
            f"If {problem} is on your mind, Skubase offers a free Shopify Inventory Health Check "
            "to help identify reorder priorities and excess-stock risks from data you choose to share.\n\n"
            "Would a free check be useful for your store?\n\nSkubase | https://skubase.io\n"
            "Reply 'no thanks' and I won't follow up.")
    if contact.contact_basis == "requested_health_check":
        body = ("Hi,\n\nI'm Skubase's automated assistant. You requested a free inventory health check. "
                "You can start by connecting your Shopify store to Skubase; its initial analysis is read-only. "
                "Please do not email customer data, passwords or access tokens.\n\n"
                "Would you like help getting your store connected?\n\nSkubase | https://skubase.io/store-sync\n"
                "Reply 'no thanks' to stop these messages.")
    skill = active_skill(db, "email_outreach")
    message, fresh = insert_once(db, Message, key="first-contact:" + contact.id,
        contact_id=contact.id, experiment_id=experiment.id, direction="out", variant=variant,
        subject="Your Shopify inventory health check", body=body, skill_version=skill.version)
    if fresh:
        record(db, f"draft:{message.id}", "EMAIL_DRAFTED", contact.id,
               {"message_id": message.id, "experiment_id": experiment.id, "variant": variant,
                "fact_sources": [f["source"] for f in facts], "skill_version": skill.version})
    return message


def send(factory, work, *, policy=None, provider=resend_request):
    policy = policy or Policy.from_env()
    policy.check_mailbox()
    message_id = work.payload["message_id"]
    # Reserve before entering the send transaction. A crash leaves a conservative cost.
    usage, _ = reserve(factory, f"email:{message_id}", "email", "resend", policy.email_unit_usd, policy, "email")
    with factory() as db:
        require_lease(db, work)
        message = db.get(Message, message_id)
        if not message:
            raise GrowthError("Message missing", "permanent")
        if message.status in ("sent", "delivered", "replied"):
            return {"already_sent": True, "provider_id": message.provider_id}
        if message.status != "draft":
            raise GrowthError("Prior send is unresolved or rejected; no automatic resend", "ambiguous")
        contact = db.get(Contact, message.contact_id)
        if not contact or contact.suppressed or contact.status in ("declined", "unsubscribed", "delivery_failure"):
            raise GrowthError("Contact is suppressed")
        if not contact.email or contact.contact_basis not in ("public_business_contact", "requested_health_check", "requested_reply"):
            raise GrowthError("No verified legitimate business contact basis")
        if not contact.qualification.get("qualified"):
            raise GrowthError("Contact is not qualified")
        # Shared lock serializes caps and suppression with concurrent sends.
        db.execute(update(Contact).where(Contact.id == contact.id).values(status=Contact.status))
        db.refresh(contact)
        if contact.suppressed:
            raise GrowthError("Contact is suppressed")
        day_start = int(time.time() // 86400) * 86400
        # Budget row locks in reserve are released; acquire global dispatch row here.
        from .models import Memory
        db.execute(update(Memory).where(Memory.namespace == "working", Memory.key == "dispatch_lock")
                   .values(version=Memory.version + 1))
        attempted = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "SEND_INTENT", Evidence.occurred_at >= day_start)) or 0
        if attempted >= policy.daily_emails:
            raise GrowthError("Daily outbound limit reached", "configuration")
        if message.reply_to_id:
            parent = db.get(Message, message.reply_to_id)
            if not parent or parent.classification not in ("SUBSTANTIVE_POSITIVE", "QUESTION", "SUBSTANTIVE_NEUTRAL"):
                raise GrowthError("Follow-up requires substantive engagement")
        else:
            prior = db.scalar(select(Message.id).where(Message.contact_id == contact.id,
                              Message.direction == "out", Message.id != message.id, Message.sent_at.is_not(None)))
            if prior:
                raise GrowthError("First-contact deduplication blocked a repeat")
        body = message.body + "\n" + policy.postal_address
        payload = {"from": "Skubase <" + policy.sender + ">", "to": [contact.email], "reply_to": policy.sender,
                   "subject": message.subject, "text": body,
                   "headers": {"X-Skubase-Message": message.id},
                   "tags": [{"name": "growth_message", "value": message.id}]}
        message.status = "sending"
        record(db, f"intent:{message.id}", "SEND_INTENT", contact.id,
               {"message_id": message.id, "payload_hash": digest(payload), "sender": policy.sender,
                "body": body, "recipient": contact.email, "experiment_id": message.experiment_id})
        db.commit()
    # A durable intent can be dispatched once. Any crash from here requires reconciliation.
    try:
        result = provider("emails", data=payload, key="skubase-growth/" + message_id)
        if not isinstance(result.get("id"), str):
            raise GrowthError("Provider returned no receipt", "ambiguous")
    except Exception:
        with factory() as db:
            message = db.get(Message, message_id)
            if message.status == "sending":
                message.status = "unknown"
            record(db, f"unknown:{message_id}", "SEND_UNKNOWN", message.contact_id, {"message_id": message_id})
            db.commit()
        raise GrowthError("Send outcome uncertain; reconcile receipt before further contact", "ambiguous") from None
    with factory() as db:
        message = db.get(Message, message_id)
        message.provider_id = result["id"]
        if message.status in ("sending", "unknown"):
            message.status = "sent"
        message.sent_at = time.time()
        cost = db.get(Usage, usage.id)
        cost.estimated_usd, cost.outcome = policy.email_unit_usd, "completed"
        record(db, f"receipt:{message_id}", "EMAIL_SENT", message.contact_id,
               {"message_id": message_id, "provider_id": result["id"], "experiment_id": message.experiment_id}, source="resend")
        # Silence is observed after a seven-day window, never auto-chased.
        enqueue(db, f"evaluate:{message.experiment_id}:{message_id}", "evaluate", {"experiment_id": message.experiment_id},
                priority=30, due_at=time.time() + 7 * 86400)
        db.commit()
    return {"provider_id": result["id"]}


def ingest_reply(db, *, provider_id, sender, recipients, text, subject="", headers=None, occurred_at=None):
    mailbox = Policy.from_env().sender
    if mailbox not in [parseaddr(x)[1].lower() for x in recipients] or parseaddr(sender)[1].lower() == mailbox:
        raise GrowthError("Reply is not addressed to the dedicated growth mailbox")
    address = parseaddr(sender)[1].lower()
    contact = db.scalar(select(Contact).where(Contact.email == address))
    if not contact:
        # Unsolicited inbound is preserved as an unqualified contact, never an auto-send target.
        contact = Contact(identity="email:" + address, email=address, source="resend_inbound",
                          contact_basis="research_only", status="inbound_unqualified")
        db.add(contact)
        db.flush()
    original = db.scalar(select(Message).where(Message.contact_id == contact.id, Message.direction == "out",
                          Message.sent_at.is_not(None)).order_by(Message.sent_at.desc()))
    classification = classify_reply(text, headers)
    message, fresh = insert_once(db, Message, key="inbound:" + provider_id, contact_id=contact.id,
        experiment_id=original.experiment_id if original else None, direction="in", body=text[:12000], subject=subject[:200],
        provider_id=provider_id, classification=classification, status="received", reply_to_id=original.id if original else None,
        created_at=occurred_at or time.time())
    if not fresh:
        return message
    if classification in ("UNSUBSCRIBE", "SUBSTANTIVE_NEGATIVE", "DELIVERY_FAILURE"):
        contact.suppressed = True
        contact.status = {"UNSUBSCRIBE": "unsubscribed", "SUBSTANTIVE_NEGATIVE": "declined", "DELIVERY_FAILURE": "delivery_failure"}[classification]
        for draft in db.scalars(select(Message).where(Message.contact_id == contact.id, Message.status == "draft")):
            draft.status = "suppressed"
    elif classification in ("SUBSTANTIVE_POSITIVE", "QUESTION", "SUBSTANTIVE_NEUTRAL"):
        contact.status = "active_conversation"
        if original:
            original.status = "replied"
    event = record(db, "reply:" + provider_id, "REPLY_RECEIVED", contact.id,
        {"message_id": message.id, "classification": classification, "experiment_id": message.experiment_id,
         "variant": original.variant if original else None, "quoted_text": text[:12000]}, source="resend_inbound")
    enqueue(db, f"reply-work:{message.id}", "reply", {"message_id": message.id, "evidence_id": event.id}, priority=100)
    return message


def poll_replies(factory, provider=resend_request):
    from .store import get_memory, remember
    from .funnel import timestamp
    from datetime import datetime
    if os.getenv("GROWTH_INBOUND_ENABLED") != "true":
        raise GrowthError("Dedicated inbound mailbox not connected", "configuration")
    with factory() as db:
        state = get_memory(db, "working", "inbound_cursor")
    # A bounded page per wake; oldest unseen pages drain before restarting at the head.
    suffix = "?limit=20" + ("&after=" + urllib.parse.quote(state["after"], safe="") if state.get("after") else "")
    result = provider("emails/receiving" + suffix)
    rows = result.get("data", [])
    count = 0
    for row in rows:
        with factory() as db:
            if db.scalar(select(Evidence.id).where(Evidence.key == "inbound-seen:" + row["id"])):
                continue
        mailbox = Policy.from_env().sender
        if mailbox not in [parseaddr(x)[1].lower() for x in row.get("to", [])]:
            continue
        if parseaddr(row.get("from", ""))[1].lower() == mailbox:
            # Internal setup checks and support notifications aren't merchant replies.
            continue
        full = provider("emails/receiving/" + urllib.parse.quote(row["id"], safe=""))
        with factory() as db:
            # HTML is retained only as text; no links/attachments are automatically fetched.
            from .discovery import clean_text
            ingest_reply(db, provider_id=row["id"], sender=full["from"], recipients=full.get("to", []),
                         subject=full.get("subject", ""), text=full.get("text") or clean_text(full.get("html", "")),
                         headers=full.get("headers", {}),
                         occurred_at=timestamp(datetime.fromisoformat(full["created_at"].replace("Z", "+00:00"))))
            record(db, "inbound-seen:" + row["id"], "INBOUND_PROCESSED", "mailbox", {"provider_id": row["id"]})
            db.commit()
            count += 1
    with factory() as db:
        remember(db, "working", "inbound_cursor", {"after": rows[-1]["id"] if rows and result.get("has_more") else None})
        db.commit()
    return {"replies_ingested": count}
