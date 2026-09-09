"""One merchant, one first contact; atomic Pacific-day admission across channels.

Confirmed receipts alone consume the calendar-day quota. Short-lived send permits
serialize dispatch; expired/uncertain contacts retain permanent duplicate fences.
"""
import time

from sqlalchemy import func, or_, select, update

from .models import Contact, Evidence, Experiment, FirstContact, Memory, Message
from .identity import INELIGIBLE, canonical_identity, prospect_identity, existing_contact, identity_match, matching_contacts, owned_identity
from .policy import GrowthError
from .store import digest, get_memory, record
from .review_calendar import review_day

LIMIT = 20  # Legacy default only; owner policy may explicitly remove the ceiling.
PERMIT_SECONDS = 600
MAX_IN_FLIGHT = 1
# Independent incident circuit breaker, not part of the confirmed outreach quota.
# Prevent a broken channel from accumulating unlimited possibly-sent messages.
MAX_UNCERTAIN = 10
CHANNELS = {"email", "contact_form", "shopify_community", "reddit", "public_community", "social_dm"}


def lock(db):
    changed = db.execute(update(Memory).where(Memory.namespace == "working", Memory.key == "dispatch_lock")
                         .values(version=Memory.version + 1)).rowcount
    if not changed:
        raise GrowthError("Dispatch lock missing; initialize growth before outreach", "configuration")


def status(db, now=None):
    now = time.time() if now is None else now
    day = review_day(now)
    rows = list(db.scalars(select(FirstContact).where(or_(
        FirstContact.status.in_(["reserved", "uncertain"]),
        (FirstContact.sent_at >= day.start) & (FirstContact.sent_at < day.end)))
        .execution_options(populate_existing=True)))
    unresolved = sum(r.status in {"reserved", "uncertain"} for r in rows)
    in_flight = sum(r.status == "reserved" and r.reserved_at + PERMIT_SECONDS > now for r in rows)
    uncertain = unresolved - in_flight
    sent = sum(r.status == "sent" and r.sent_at is not None and day.start <= r.sent_at < day.end for r in rows)
    limit = get_memory(db, "strategic", "outreach_policy").get("daily_new_contact_limit", LIMIT)
    if limit is not None and (type(limit) is not int or limit < 0):
        raise GrowthError("Invalid owner outreach ceiling", "configuration")
    remaining = None if limit is None else max(0, limit - sent)
    blocker = ("DAILY_CAP_REACHED" if remaining == 0 else
               "OUTREACH_UNCERTAINTY_SAFETY_HOLD" if uncertain >= MAX_UNCERTAIN else
               "SEND_IN_FLIGHT" if in_flight >= MAX_IN_FLIGHT or limit is not None and sent + in_flight >= limit else None)
    return {"policy": "uncapped_confirmed_outreach_v1" if limit is None else "confirmed_outreach_pacific_day_v3", "limit": limit,
            "window_hours": (day.end - day.start) / 3600, "day_timezone": "America/Los_Angeles",
            "day": day.day, "day_start_at": day.start, "resets_at": day.end, "used": sent, "sent": sent,
            "confirmed_sent_count": sent, "remaining_confirmed_capacity": remaining,
            "in_flight_send_count": in_flight, "uncertain_contact_count": uncertain,
            "uncertain_contacts_protected": uncertain, "uncertainty_safety_limit": MAX_UNCERTAIN,
            "late_confirmation_overage": 0 if limit is None else max(0, sent - limit),
            "blocker": blocker, "remaining": remaining,
            "dispatch_remaining": 0 if blocker else MAX_IN_FLIGHT - in_flight if limit is None else min(MAX_IN_FLIGHT - in_flight, remaining - in_flight),
            "unresolved": unresolved, "next_slot_at": day.end if remaining == 0 else None,
            "is_target": False, "scope": "new merchants across email, forms and public replies", "continue_non_outbound": True}


def reserve_contact(db, contact, *, action_key, channel, experiment_id, body, cohort, now=None):
    now = time.time() if now is None else now
    lock(db)  # PostgreSQL row lock / SQLite write lock serializes competing callers.
    control = get_memory(db, "working", "control")
    if control.get("paused") and not control.get("deployment_drain"):
        raise GrowthError("Acquisition is paused")
    db.refresh(contact)
    if owned_identity(contact.identity):
        raise GrowthError("Owned business account is not an acquisition prospect")
    identity_aliases = matching_contacts(db, contact.identity)
    if any(row.suppressed or row.status in INELIGIBLE for row in identity_aliases):
        raise GrowthError("Contact is suppressed or ineligible")
    if get_memory(db, "working", "acquisition_hold"):
        raise GrowthError("Product/funnel hold blocks new acquisition, not existing conversations")
    from .eligibility import POLICY
    if get_memory(db, "strategic", "qualification_policy").get("version") == POLICY:
        if contact.qualification.get("policy") != POLICY or contact.qualification.get("eligible") is not True:
            raise GrowthError("Basic merchant eligibility required")
        cohort = {**cohort, "qualification_policy": POLICY}
    if not contact.qualification.get("qualified") or not any(f.get("verified") and f.get("source") for f in contact.facts):
        raise GrowthError("Verified merchant relevance and a sourced fact are required")
    experiment = db.get(Experiment, experiment_id)
    if not experiment or experiment.status != "active" or experiment.stop_at <= now:
        raise GrowthError("An active, unexpired experiment is required. Run operator-export for a real active ID; never invent an experiment ID.")
    if channel not in CHANNELS or not body.strip() or not all(cohort.get(k) for k in ("icp", "offer", "message_version")):
        raise GrowthError("Channel, exact message and immutable cohort labels are required")
    prior = db.scalar(select(FirstContact).where(FirstContact.contact_id == contact.id))
    aliases = [Contact.id.in_([row.id for row in identity_aliases]), identity_match(contact.identity)]
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
    if current["dispatch_remaining"] == 0:
        raise GrowthError(current["blocker"] + "; continue replies, research and receipt reconciliation", "capacity")
    row = FirstContact(contact_id=contact.id, action_key=action_key, channel=channel, experiment_id=experiment_id,
        cohort={**cohort, "characteristics": contact.characteristics, "qualification": contact.qualification,
                "fact_sources": contact.facts}, body_hash=digest(body), reserved_at=now)
    db.add(row); db.flush()
    record(db, "first-contact-intent:" + row.id, "FIRST_CONTACT_RESERVED", contact.id,
           {"reservation_id": row.id, "body": body, "channel": channel, "experiment_id": experiment_id,
            "cohort": row.cohort, "submit_before": now + PERMIT_SECONDS}, occurred_at=now)
    return {"reservation_id": row.id, "submit_before": now + PERMIT_SECONDS,
            "remaining": current["remaining"], "authorize_before_submit": True}


def authorize_submission(db, reservation_id, now=None):
    """One-use final fence immediately before an external submission; never replay."""
    now = time.time() if now is None else now
    lock(db)
    row = db.get(FirstContact, reservation_id)
    if row:
        db.refresh(row)
    if not row or row.status != "reserved" or row.reserved_at + PERMIT_SECONDS <= now:
        raise GrowthError("Send permit expired or uncertain; reconcile without retry", "ambiguous")
    if db.scalar(select(Evidence.id).where(Evidence.key == "first-contact-authorized:" + row.id)):
        raise GrowthError("Submission was already authorized; reconcile without retry", "ambiguous")
    current = status(db, now)
    if (current["limit"] is not None and current["sent"] >= current["limit"]) or current["uncertain_contact_count"] >= MAX_UNCERTAIN:
        raise GrowthError("Confirmed ceiling or uncertainty safety hold; do not submit", "capacity")
    if current["in_flight_send_count"] > MAX_IN_FLIGHT:
        raise GrowthError("Competing legacy permits; wait for receipt reconciliation", "capacity")
    contact = db.get(Contact, row.contact_id)
    if not contact or any(c.suppressed or c.status in INELIGIBLE for c in matching_contacts(db, contact.identity)):
        raise GrowthError("Contact is suppressed or ineligible")
    control = get_memory(db, "working", "control")
    if (control.get("paused") and not control.get("deployment_drain")) or get_memory(db, "working", "acquisition_hold"):
        raise GrowthError("Acquisition is paused or held")
    record(db, "first-contact-authorized:" + row.id, "FIRST_CONTACT_SUBMISSION_AUTHORIZED", row.contact_id,
           {"reservation_id": row.id, "confirmed_count": current["sent"],
            "submit_before": min(now + 30, row.reserved_at + PERMIT_SECONDS)}, occurred_at=now)
    return {"reservation_id": row.id, "submit_before": min(now + 30, row.reserved_at + PERMIT_SECONDS),
            "instruction": "Submit once before this deadline. Never retry an expired or consumed authorization."}


def complete(db, reservation_id, *, receipt=None, outcome="sent", now=None):
    now = time.time() if now is None else now
    lock(db)
    row = db.get(FirstContact, reservation_id)
    if row:
        db.refresh(row)
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
    capacity = status(db, now)
    if capacity["late_confirmation_overage"]:
        record(db, "late-confirmation-overage:" + row.id, "OUTREACH_LATE_CONFIRMATION_OVERAGE", "outbound",
               {"reservation_id": row.id, "confirmed_count": capacity["sent"], "limit": capacity["limit"],
                "action": "Block new dispatch until confirmations age out; retain every real receipt"}, occurred_at=now)
    return {"reservation_id": row.id, "status": row.status, "capacity": capacity}


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
    authenticated = False
    if evidence and evidence.source == "authenticated_browser_executor":
        task = get_memory(db, "operator_task", evidence.data.get("task_id", ""))
        authenticated = (task.get("status") == "running" and task.get("lease_token") == evidence.data.get("lease_token")
                         and task.get("lease_until", 0) > time.time() and row and task.get("contact_id") == row.contact_id)
    if (not row or row.status == "sent" or not evidence or evidence.kind != "OUTREACH_NOT_SENT_VERIFIED"
        or (evidence.source != "owner_operator" and not authenticated) or evidence.subject != reservation_id
        or evidence.data.get("no_external_effect") is not True or not evidence.data.get("reason")):
        raise GrowthError("Retained operator verification of no external send is required; uncertainty cannot release capacity")
    record(db, "first-contact-released:"+row.id, "FIRST_CONTACT_RELEASED", row.contact_id,
           {"reservation_id":row.id, "action_key":row.action_key, "evidence_id":evidence_id, "cohort":row.cohort})
    # A fresh admission gets a new ID. The old reservation cannot be reused.
    db.delete(row); db.flush()
    return {"released":reservation_id, "capacity":status(db)}


def require_browser_safety(db):
    executor = get_memory(db, "working", "browser_executor")
    if executor.get("owner"):
        safety = get_memory(db, "working", "browser_safety_check")
        evidence = db.get(Evidence, safety.get("evidence_id")) if safety.get("evidence_id") else None
        invalidated = evidence and db.scalar(select(Evidence.id).where(Evidence.kind == "EVIDENCE_INVALIDATED",
            Evidence.subject == str(evidence.id)).limit(1))
        if invalidated or safety.get("requires_attention") or time.time() - safety.get("checked_at", 0) > 300 or not evidence or evidence.kind != "CHANNEL_MONITOR" or time.time() - evidence.occurred_at > 300:
            raise GrowthError("Fresh essential browser reply/safety checks required before first contact")


def operator_action(db, action, payload):
    """Trusted owner CLI only; does not dispatch mail or authorize channel use."""
    if action == "outreach-status":
        return status(db)
    if action == "outreach-backfill":
        return backfill(db)
    if action == "outreach-authorize":
        require_browser_safety(db)
        return authorize_submission(db, payload["reservation_id"])
    if action == "outreach-complete":
        return complete(db, payload["reservation_id"], receipt=payload.get("receipt"), outcome=payload["outcome"])
    if action == "outreach-reconcile":
        return reconcile_not_sent(db,payload["reservation_id"],payload["evidence_id"])
    if action != "outreach-reserve":
        raise GrowthError("Unknown outreach operation")
    require_browser_safety(db)
    # Channel rules are reviewed by the authenticated operator, not guessed from keywords.
    if not payload.get("channel_rules_source") or not payload.get("relevance_evidence"):
        raise GrowthError("Current channel-rule and merchant relevance evidence required")
    if payload.get("channel") == "email":
        raise GrowthError("Promotional email transport remains disabled; use permitted channels")
    identity = prospect_identity(payload["identity"], payload.get("source"))
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
    from .eligibility import POLICY, assess
    if payload.get("checks"):
        assess(db, payload)
    baseline = contact.qualification.get("policy") == POLICY
    if get_memory(db, "strategic", "qualification_policy").get("version") == POLICY and not baseline:
        raise GrowthError("Basic merchant eligibility assessment required")
    if baseline:
        if contact.qualification.get("eligible") is not True:
            raise GrowthError(contact.qualification.get("reason") or "Basic merchant evidence required")
        if contact.qualification.get("priority") == "LOW" and not payload.get("exploration_hypothesis"):
            raise GrowthError("Low-priority outreach requires a deliberate exploration hypothesis")
    elif payload.get("qualified") is not True:
        raise GrowthError("Verified basic merchant relevance required")
    contact.facts = facts
    contact.qualification = {**contact.qualification, "qualified": True,
                             "qualified_user": contact.qualification.get("qualified_user", False), "evidence": payload["relevance_evidence"],
                             "verified_at": time.time()}
    db.flush()
    result = reserve_contact(db, contact, action_key=payload["action_key"], channel=payload["channel"],
        experiment_id=payload["experiment_id"], body=payload["body"], cohort=payload["cohort"])
    record(db, "channel-check:"+result["reservation_id"], "OUTREACH_CHANNEL_REVIEW", contact.id,
           {"channel_rules_source": payload["channel_rules_source"], "source": payload["source"],
            "relevance_evidence": payload["relevance_evidence"]}, source="owner_operator")
    return result
