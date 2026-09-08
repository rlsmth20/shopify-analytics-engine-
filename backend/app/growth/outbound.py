"""One merchant, one first contact; atomic rolling admission across channels.

An unresolved reservation consumes capacity until reconciled, even after 24h.
No timeout silently grants another send. Browser operators must reserve just
before submission and record the result; this is admission, not channel authority.
"""
import time

from sqlalchemy import func, or_, select, update

from .models import Contact, Evidence, Experiment, FirstContact, Memory, Message
from .identity import INELIGIBLE, canonical_identity, existing_contact, identity_match, matching_contacts, owned_identity
from .policy import GrowthError
from .store import digest, get_memory, record

LIMIT = 20
WINDOW = 86400
CHANNELS = {"email", "contact_form", "shopify_community", "reddit"}


def lock(db):
    changed = db.execute(update(Memory).where(Memory.namespace == "working", Memory.key == "dispatch_lock")
                         .values(version=Memory.version + 1)).rowcount
    if not changed:
        raise GrowthError("Dispatch lock missing; initialize growth before outreach", "configuration")


def status(db, now=None):
    now = time.time() if now is None else now
    rows = list(db.scalars(select(FirstContact).where(or_(
        FirstContact.status.in_(["reserved", "uncertain"]), FirstContact.sent_at > now - WINDOW))))
    unresolved = sum(r.status in {"reserved", "uncertain"} for r in rows)
    releases = sorted(r.sent_at + WINDOW for r in rows if r.sent_at is not None and r.status == "sent")
    needed = max(1, len(rows) - LIMIT + 1)
    return {"limit": LIMIT, "window_hours": 24, "used": len(rows), "remaining": max(0, LIMIT-len(rows)),
            "unresolved": unresolved, "next_slot_at": releases[needed-1] if len(rows) >= LIMIT and len(releases) >= needed else None,
            "is_target": False, "scope": "new merchants across email, forms and public replies", "continue_non_outbound": True}


def reserve_contact(db, contact, *, action_key, channel, experiment_id, body, cohort, now=None):
    now = time.time() if now is None else now
    lock(db)  # PostgreSQL row lock / SQLite write lock serializes competing callers.
    db.refresh(contact)
    if owned_identity(contact.identity):
        raise GrowthError("Owned business account is not an acquisition prospect")
    identity_aliases = matching_contacts(db, contact.identity)
    if any(row.suppressed or row.status in INELIGIBLE for row in identity_aliases):
        raise GrowthError("Contact is suppressed or ineligible")
    if get_memory(db, "working", "acquisition_hold"):
        raise GrowthError("Product/funnel hold blocks new acquisition, not existing conversations")
    if not contact.qualification.get("qualified") or not any(f.get("verified") and f.get("source") for f in contact.facts):
        raise GrowthError("Verified merchant relevance and a sourced fact are required")
    experiment = db.get(Experiment, experiment_id)
    if not experiment or experiment.status != "active" or experiment.stop_at <= now:
        raise GrowthError("An active, unexpired experiment is required")
    if channel not in CHANNELS or not body.strip() or not all(cohort.get(k) for k in ("icp", "offer", "message_version")):
        raise GrowthError("Channel, exact message and immutable cohort labels are required")
    prior = db.scalar(select(FirstContact).where(FirstContact.contact_id == contact.id))
    aliases = [Contact.id == contact.id, identity_match(contact.identity)]
    if contact.email:
        aliases.append(func.lower(Contact.email) == contact.email.lower())
    if contact.organization.lower() not in {"unknown", ""}:
        aliases.append(func.lower(Contact.organization) == contact.organization.lower())
    alias_contact = db.scalar(select(FirstContact.id).join(Contact, Contact.id == FirstContact.contact_id).where(or_(*aliases)))
    prior_mail = db.scalar(select(Message.id).where(Message.contact_id.in_([row.id for row in identity_aliases]), Message.direction == "out",
                           or_(Message.sent_at.is_not(None), Message.status.in_(["sending", "unknown"]))))
    if prior or prior_mail or alias_contact:
        raise GrowthError("Merchant was already contacted or has an unresolved intent; reconcile, never resend", "ambiguous")
    current = status(db, now)
    if current["remaining"] == 0:
        raise GrowthError("Rolling 24-hour first-contact ceiling reached; continue replies/research", "capacity")
    row = FirstContact(contact_id=contact.id, action_key=action_key, channel=channel, experiment_id=experiment_id,
        cohort={**cohort, "characteristics": contact.characteristics, "qualification": contact.qualification,
                "fact_sources": contact.facts}, body_hash=digest(body), reserved_at=now)
    db.add(row); db.flush()
    record(db, "first-contact-intent:" + row.id, "FIRST_CONTACT_RESERVED", contact.id,
           {"reservation_id": row.id, "body": body, "channel": channel, "experiment_id": experiment_id,
            "cohort": row.cohort, "submit_before": now + 600}, occurred_at=now)
    return {"reservation_id": row.id, "submit_before": now + 600, "remaining": current["remaining"]-1}


def complete(db, reservation_id, *, receipt=None, outcome="sent", now=None):
    now = time.time() if now is None else now
    lock(db)
    row = db.get(FirstContact, reservation_id)
    if not row or outcome not in {"sent", "uncertain"}:
        raise GrowthError("Known reservation and sent/uncertain outcome required")
    if row.status == "sent":
        if receipt != row.receipt:
            raise GrowthError("Receipt differs from the recorded send")
        return {"already_recorded": True, "reservation_id": row.id}
    if outcome == "sent" and not receipt:
        raise GrowthError("Publication/provider receipt required")
    row.status = outcome
    if outcome == "sent":
        row.sent_at, row.receipt = now, receipt
    record(db, f"first-contact-result:{row.id}:{outcome}", "FIRST_CONTACT_RESULT", row.contact_id,
           {"reservation_id": row.id, "outcome": outcome, "receipt": receipt,
            "channel": row.channel, "experiment_id": row.experiment_id, "cohort": row.cohort}, occurred_at=now)
    db.flush()
    return {"reservation_id": row.id, "status": row.status, "capacity": status(db, now)}


def backfill(db):
    """Retain existing public/form receipts once, using conservative import times.

    Do not manufacture delivery confirmation for a form or mail readership.
    Old recipient identity stays in this table even after its window expires.
    """
    lock(db)
    added = 0
    for event in db.scalars(select(Evidence).where(Evidence.kind.in_(["COMMUNITY_REPLY_SENT", "CONTACT_FORM_ACCEPTED"]))
                           .order_by(Evidence.occurred_at)):
        if not db.get(Contact, event.subject) or db.scalar(select(FirstContact.id).where(FirstContact.contact_id == event.subject)):
            continue
        data = event.data
        contact = db.get(Contact, event.subject)
        db.add(FirstContact(contact_id=event.subject, action_key="historical:"+str(event.id),
            channel="shopify_community" if event.kind == "COMMUNITY_REPLY_SENT" else "contact_form",
            experiment_id=data.get("experiment_id") or "historical_unknown", body_hash=digest(data.get("body", "")),
            cohort={"message_version": data.get("messaging_revision", 1), "icp": contact.qualification,
                    "offer": "inventory_health_check", "source_evidence_id": event.id,
                    "timestamp_basis": "conservative receipt import time; exact send time unknown"},
            status="sent", reserved_at=event.occurred_at, sent_at=event.occurred_at,
            receipt=data.get("receipt_url") or data.get("receipt") or event.source))
        db.flush(); added += 1
    record(db, "first-contact-backfill:v1", "FIRST_CONTACT_BACKFILL", "outbound", {"added": added})
    return {"imported": added, "capacity": status(db)}


def reconcile_not_sent(db, reservation_id, evidence_id):
    """Release only an explicitly reviewed no-effect result; never a timeout."""
    lock(db)
    row = db.get(FirstContact, reservation_id)
    evidence = db.get(Evidence, evidence_id)
    if (not row or row.status == "sent" or not evidence or evidence.kind != "OUTREACH_NOT_SENT_VERIFIED"
        or evidence.source != "owner_operator" or evidence.subject != reservation_id
        or evidence.data.get("no_external_effect") is not True or not evidence.data.get("reason")):
        raise GrowthError("Retained operator verification of no external send is required; uncertainty cannot release capacity")
    record(db, "first-contact-released:"+row.id, "FIRST_CONTACT_RELEASED", row.contact_id,
           {"reservation_id":row.id, "action_key":row.action_key, "evidence_id":evidence_id, "cohort":row.cohort})
    # A fresh admission gets a new ID. The old reservation cannot be reused.
    db.delete(row); db.flush()
    return {"released":reservation_id, "capacity":status(db)}


def operator_action(db, action, payload):
    """Trusted owner CLI only; does not dispatch mail or authorize channel use."""
    if action == "outreach-status":
        return status(db)
    if action == "outreach-backfill":
        return backfill(db)
    if action == "outreach-complete":
        return complete(db, payload["reservation_id"], receipt=payload.get("receipt"), outcome=payload["outcome"])
    if action == "outreach-reconcile":
        return reconcile_not_sent(db,payload["reservation_id"],payload["evidence_id"])
    if action != "outreach-reserve":
        raise GrowthError("Unknown outreach operation")
    executor = get_memory(db, "working", "browser_executor")
    if executor.get("owner"):
        safety = get_memory(db, "working", "browser_safety_check")
        evidence = db.get(Evidence, safety.get("evidence_id")) if safety.get("evidence_id") else None
        if safety.get("requires_attention") or time.time() - safety.get("checked_at", 0) > 300 or not evidence or evidence.kind != "CHANNEL_MONITOR" or time.time() - evidence.occurred_at > 300:
            raise GrowthError("Fresh essential browser reply/safety checks required before first contact")
    # Channel rules are reviewed by the authenticated operator, not guessed from keywords.
    if not payload.get("channel_rules_source") or not payload.get("relevance_evidence"):
        raise GrowthError("Current channel-rule and merchant relevance evidence required")
    if payload.get("channel") == "email":
        raise GrowthError("Promotional email transport remains disabled; use permitted channels")
    identity = canonical_identity(payload["identity"])
    if not identity or len(identity) > 320:
        raise GrowthError("Canonical merchant identity required")
    lock(db)
    contact = existing_contact(db, identity)
    if not contact:
        contact = Contact(identity=identity, organization=payload["organization"], source=payload["source"])
        db.add(contact); db.flush()
    if contact.suppressed or contact.status in INELIGIBLE:
        raise GrowthError("Suppressed contact")
    facts = payload["facts"]
    if not facts or not all(f.get("verified") is True and f.get("source") and f.get("text") for f in facts):
        raise GrowthError("At least one verified public personalization fact required")
    # This assertion must follow actual source review, not storefront fit alone.
    if payload.get("qualified") is not True:
        raise GrowthError("Do not contact weak or unverified prospects to fill capacity")
    contact.facts = facts
    contact.qualification = {"qualified": True, "qualified_user": False, "evidence": payload["relevance_evidence"],
                             "verified_at": time.time()}
    db.flush()
    result = reserve_contact(db, contact, action_key=payload["action_key"], channel=payload["channel"],
        experiment_id=payload["experiment_id"], body=payload["body"], cohort=payload["cohort"])
    record(db, "channel-check:"+result["reservation_id"], "OUTREACH_CHANNEL_REVIEW", contact.id,
           {"channel_rules_source": payload["channel_rules_source"], "source": payload["source"],
            "relevance_evidence": payload["relevance_evidence"]}, source="owner_operator")
    return result
