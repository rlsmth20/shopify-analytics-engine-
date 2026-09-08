"""Cheap, evidence-backed market discovery. Optional ICP signals only rank."""
import time

from sqlalchemy import func, or_, select

from .identity import INELIGIBLE, prospect_identity, existing_contact, matching_contacts, owned_identity
from .models import Contact, FirstContact, Message
from .policy import GrowthError
from .store import digest, record

POLICY = "market_discovery_v1"
MAX_PAGES = 2
MAX_SEARCHES = 1
MAX_SECONDS = 120
CORE = {"merchant": "NOT_A_MERCHANT", "ecommerce": "NOT_ECOMMERCE",
        "physical_products": "DIGITAL_SERVICE_ONLY", "shopify": "CLEARLY_NOT_SHOPIFY",
        "contact_route": "NO_LEGITIMATE_CONTACT_ROUTE", "channel_permits_contact": "CHANNEL_RULE_PROHIBITS_CONTACT"}
RANKING = ("inventory_pain", "inventory_complexity", "apparel_beauty", "target_sku_range",
           "founder_led", "replenishable_products")


def evaluate(checks, signals=None):
    """Null core facts defer; null optional attributes never reject or lower rank."""
    signals = signals or {}
    for key, reason in CORE.items():
        fact = checks.get(key) or {}
        if fact.get("value") is False and fact.get("source") and fact.get("text"):
            return {"eligible": False, "priority": "REJECT", "confidence": "HIGH", "reason": reason}
    missing = [k for k in CORE if not ((checks.get(k) or {}).get("value") is True or
               k == "shopify" and (checks.get(k) or {}).get("value") == "probable") or
               not (checks.get(k) or {}).get("source") or not (checks.get(k) or {}).get("text")]
    if missing:
        return {"eligible": None, "priority": "DEFER", "confidence": "UNKNOWN",
                "reason": "BASIC_EVIDENCE_UNKNOWN", "unknown_basic_fields": missing}
    high = any(signals.get(k) is True for k in ("inventory_pain", "inventory_complexity"))
    return {"eligible": True, "priority": "HIGH" if high else
            "LOW" if signals.get("limited_inventory") is True else "MEDIUM",
            "confidence": "HIGH" if high and checks["shopify"]["value"] is True else "MEDIUM",
            "reason": None}


def exclusion(db, identity, organization=None):
    """Live safety checks override cached merchant facts, including aliases."""
    if owned_identity(identity):
        return "OBVIOUSLY_INAPPROPRIATE_TARGET"
    aliases = matching_contacts(db, identity)
    if organization and organization.lower() != "unknown":
        aliases += list(db.scalars(select(Contact).where(func.lower(Contact.organization) == organization.lower())))
    for c in aliases:
        if c.suppressed or c.status in INELIGIBLE:
            return {"declined": "DECLINED", "unsubscribed": "UNSUBSCRIBED"}.get(c.status, "BOUNCED_SUPPRESSED")
    ids = list({c.id for c in aliases})
    if ids and (db.scalar(select(FirstContact.id).where(FirstContact.contact_id.in_(ids)).limit(1)) or
                db.scalar(select(Message.id).where(Message.contact_id.in_(ids), Message.direction == "out",
                    or_(Message.sent_at.is_not(None), Message.status.in_(["sending", "unknown"]))).limit(1))):
        return "PREVIOUSLY_CONTACTED"
    return None


def assess(db, payload):
    from .outbound import lock
    lock(db)
    identity = prospect_identity(payload["identity"], payload.get("source"))
    if not identity or len(identity) > 320:
        raise GrowthError("Canonical merchant identity required")
    contact = existing_contact(db, identity)
    checks = payload.get("checks") or (contact.qualification.get("checks", {}) if contact else {})
    signals = payload.get("signals") or (contact.characteristics if contact else {})
    # Keep sourced facts compact; do not accept arbitrary research narratives.
    if len(str(checks)) > 8000 or len(str(signals)) > 2000:
        raise GrowthError("Eligibility evidence exceeds the compact research budget")
    organization = payload.get("organization") or (contact.organization if contact else "Unknown")
    reason = exclusion(db, identity, organization)
    result = {"eligible": False, "priority": "REJECT", "confidence": "HIGH", "reason": reason} if reason else evaluate(checks, signals)
    if not contact:
        contact = Contact(identity=identity, organization=organization,
                          source=payload.get("source") or next((f.get("source") for f in checks.values() if f.get("source")), "unknown"))
        db.add(contact)
        db.flush()
    assessment = {**result, "policy": POLICY, "checks": checks,
                  "qualified": result["eligible"] is True, "qualified_user": contact.qualification.get("qualified_user", False)}
    event = record(db, "eligibility:" + digest([identity, assessment, signals]), "PROSPECT_ELIGIBILITY", contact.id,
                   {**result, "policy": POLICY, "checks": checks, "signals": signals}, source=contact.source)
    contact.qualification = {**assessment, "evidence_id": event.id, "verified_at": event.occurred_at}
    contact.characteristics = signals
    contact.facts = [{"verified": True, "source": f["source"], "text": f["text"]}
                     for f in checks.values() if f.get("value") is True and f.get("source") and f.get("text")]
    db.flush()
    return {**result, "contact_id": contact.id, "evidence_id": event.id, "policy": POLICY,
            "cached": event.occurred_at < time.time() - 1,
            "research_budget": {"pages": MAX_PAGES, "searches": MAX_SEARCHES, "seconds": MAX_SECONDS}}
