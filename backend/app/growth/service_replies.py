"""Narrow requested-service fulfillment. Never relabel marketing as support."""
import re
import time

from sqlalchemy import select, func

from .models import Contact, Evidence, Message
from .policy import GrowthError
from .store import digest, enqueue, insert_once, record
from .skills import active_skill

SERVICE_KNOWLEDGE = {
    "connection": {
        "patterns": (r"(?:help|how|where|cannot|can't|unable).{0,70}(?:connect|install|log in|login)",),
        "answer": "To continue your requested inventory analysis, sign in at https://skubase.io/login, then open https://skubase.io/store-sync and choose Connect Shopify. Review Shopify's permission screen and return to Store sync to start an import. If a step fails, reply with the step and error text, without passwords or access tokens.",
        "sources": ["frontend/app/(app-shell)/store-sync/page.tsx", "backend/app/api/routes/shopify_ingestion.py"],
    },
    "read_only": {
        "patterns": (r"(?:will|can|does|do).{0,70}(?:change|edit|write|modify).{0,40}(?:inventory|store|stock)", r"read.only"),
        "answer": "The connected-store inventory analysis reads the store data needed for analysis. It does not automatically place supplier orders or change Shopify inventory quantities. Review the permission screen when connecting, and keep purchasing decisions under your control.",
        "sources": ["backend/app/services/shopify_oauth.py", "backend/app/services/shopify_sync.py"],
    },
    "data_safety": {
        "patterns": (r"(?:send|share|email).{0,50}(?:password|token|customer data)",),
        "answer": "Please do not email passwords, access tokens or customer records. Use the Shopify connection flow at https://skubase.io/store-sync for your requested analysis. If you already sent a credential, revoke it in the issuing service; this assistant cannot revoke it for you.",
        "sources": ["frontend/app/privacy/page.tsx"],
    },
}


def current_request(db, contact_id):
    return db.scalar(select(Evidence).where(Evidence.subject == contact_id, Evidence.kind == "ACCESS_REQUESTED",
                     Evidence.source == "skubase_form", Evidence.occurred_at >= time.time() - 14 * 86400)
                     .order_by(Evidence.id.desc()).limit(1))


def permit(db, message, request_event, scope, sources):
    record(db, "service-permit:" + message.id, "SERVICE_RESPONSE_AUTHORIZED", message.id,
           {"request_evidence_id": request_event.id, "contact_id": message.contact_id, "scope": scope,
            "body_hash": digest([message.subject, message.body]), "knowledge_sources": sources},
           source="service_fulfillment_policy", epistemic="FACT")


def validate_permit(db, message, contact):
    authority = db.scalar(select(Evidence).where(Evidence.key == "service-permit:" + message.id,
                                                Evidence.source == "service_fulfillment_policy"))
    if not authority or authority.data.get("body_hash") != digest([message.subject, message.body]):
        raise GrowthError("Resend dispatch requires a recorded, unchanged requested-service response; promotional outreach is disabled")
    request = db.get(Evidence, authority.data.get("request_evidence_id"))
    if not request or request.subject != contact.id or request.kind not in {"ACCESS_REQUESTED", "REPLY_RECEIVED", "CONTACT_FORM_RECEIVED"}:
        raise GrowthError("The original service request is missing")
    if request.occurred_at < time.time() - 14 * 86400:
        raise GrowthError("Service request is stale; do not revive an old conversation automatically")
    if authority.data.get("scope") not in {"health_check", *SERVICE_KNOWLEDGE}:
        raise GrowthError("Unknown service response scope")
    return authority


def draft_requested_check(db, contact, experiment, variant):
    request = current_request(db, contact.id)
    if not request:
        raise GrowthError("No recent inventory-health-check request; no unsolicited Resend outreach")
    focus = "cash tied up in slow-moving inventory" if variant == "cash" else "stockout risks and reorder priorities"
    message, fresh = insert_once(db, Message, key="first-contact:" + contact.id, contact_id=contact.id,
        experiment_id=experiment.id, direction="out", variant=variant, subject="Next step for your requested inventory check",
        body=("Hi,\n\nI'm Skubase's automated assistant, following up on the inventory check you requested. "
              f"For that check, we can review {focus} using the data you choose to connect. "
              "Sign in at https://skubase.io/login, then connect your store and start an import at https://skubase.io/store-sync. "
              "The initial analysis is read-only. Please do not email passwords, access tokens or customer records.\n\n"
              "Reply if you need help with the connection step.\n\nSkubase | info@skubase.io\nReply 'stop' to stop automated responses."))
    if fresh:
        message.skill_version = active_skill(db, "requested_service").version
        permit(db, message, request, "health_check", ["backend/app/api/routes/inventory_risk_snapshot.py"])
        record(db, "draft:" + message.id, "EMAIL_DRAFTED", contact.id,
               {"message_id": message.id, "experiment_id": experiment.id, "variant": variant, "purpose": "requested_service"})
    return message


def answer_request(db, contact, event, text, parent=None):
    """One response per request, exact knowledge match, no private account data."""
    if contact.suppressed:
        return None
    lower = text.lower().split("\non ")[0].split("\n>")[0][:4000]
    # Automated headers and negative intent are checked by the calling ingestion path.
    matches = [key for key, spec in SERVICE_KNOWLEDGE.items() if any(re.search(p, lower, re.S) for p in spec["patterns"])]
    if len(matches) != 1:
        return None
    key = matches[0]
    recent = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "SERVICE_REPLY_DRAFTED",
                      Evidence.subject == contact.id, Evidence.occurred_at > time.time() - 7 * 86400)) or 0
    if recent >= 3:
        return None
    # Match a user's service question, not an unrelated sales pitch or quoted document.
    if not (contact.shop_id or current_request(db, contact.id) or any(t in lower for t in ("my shopify", "my store", "our store", "my account", "health check", "skubase"))):
        return None
    spec = SERVICE_KNOWLEDGE[key]
    message, fresh = insert_once(db, Message, key=f"service-answer:{event.id}", contact_id=contact.id,
        experiment_id=parent.experiment_id if parent else None, direction="out", variant="service:" + key,
        reply_to_id=parent.id if parent else None, subject="Help with your Skubase request",
        body="I'm Skubase's automated assistant.\n\n" + spec["answer"] + "\n\nSkubase | info@skubase.io\nReply 'stop' to stop automated responses.")
    if fresh:
        message.skill_version = active_skill(db, "requested_service").version
        permit(db, message, event, key, spec["sources"])
        record(db, "service-reply:" + message.id, "SERVICE_REPLY_DRAFTED", contact.id,
               {"message_id": message.id, "request_evidence_id": event.id, "topic": key})
        enqueue(db, "send:" + message.id, "send", {"message_id": message.id}, priority=95)
    return message
