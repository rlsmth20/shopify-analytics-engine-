"""Narrow requested-service fulfillment. Never relabel marketing as support."""
import re
import time

from sqlalchemy import select, func

from .models import Contact, Evidence, Message
from .policy import GrowthError
from .store import digest, enqueue, insert_once, record
from .skills import active_skill

APP_REVIEW_DISCLOSURE = "Skubase is currently in Shopify's review process and is not yet listed in the Shopify App Store."
HEALTH_CHECK_URL = "https://skubase.io/tools/inventory-health-check"
SERVICE_TEMPLATE_REVISION = "browser-health-check-v1"
HEALTH_CHECK_SOURCES = [
    "frontend/app/tools/inventory-health-check/page.tsx",
    "frontend/lib/inventory-health-check.ts",
    "frontend/components/inventory-health-checker.tsx",
]


def service_body(answer):
    return (answer + "\n\n" + APP_REVIEW_DISCLOSURE +
            "\n\nSkubase | info@skubase.io\nReply 'stop' if you don't want further replies.")


SERVICE_KNOWLEDGE = {
    "connection": {
        "patterns": (r"(?:help|how|where|cannot|can't|unable).{0,70}(?:connect|install|log in|login)",),
        "answer": f"You can start your requested inventory check without a Shopify installation or account at {HEALTH_CHECK_URL}. "
                  "Add a SKU summary of on-hand units and units sold over your chosen sales period. "
                  "The check runs in your browser; your SKU entries are not sent to Skubase. "
                  "If you need help with an existing Skubase account or connection, reply with the step and error text, without passwords or access tokens.",
        "sources": HEALTH_CHECK_SOURCES,
    },
    "read_only": {
        "patterns": (r"(?:will|can|does|do).{0,70}(?:change|edit|write|modify).{0,40}(?:inventory|store|stock)", r"read.only"),
        "answer": f"For your requested check, the free tool at {HEALTH_CHECK_URL} processes a SKU summary in your browser. "
                  "It does not connect to your store, send your SKU entries to Skubase, change Shopify inventory or place supplier orders. "
                  "Its stock-cover estimates and reorder triggers depend on the sales period and assumptions you enter. "
                  "A trigger is not an order quantity; check incoming orders and current demand before purchasing. Reply if you need help interpreting a result.",
        "sources": HEALTH_CHECK_SOURCES,
    },
    "data_safety": {
        "patterns": (r"(?:send|share|email).{0,50}(?:password|token|customer data)",),
        "answer": f"Please do not email passwords, access tokens or customer records. For your requested analysis, use {HEALTH_CHECK_URL} "
                  "with a SKU summary of stock and units sold; no customer details are needed. "
                  "Your SKU entries stay in your browser and are not sent to Skubase. "
                  "If you already sent a credential, revoke it in the issuing service; Skubase cannot revoke it for you. Reply if you need help preparing the summary.",
        "sources": [*HEALTH_CHECK_SOURCES, "frontend/app/privacy/page.tsx"],
    },
}


def current_request(db, contact_id):
    return db.scalar(select(Evidence).where(Evidence.subject == contact_id, Evidence.kind == "ACCESS_REQUESTED",
                     Evidence.source == "skubase_form", Evidence.occurred_at >= time.time() - 14 * 86400)
                     .order_by(Evidence.id.desc()).limit(1))


def permit(db, message, request_event, scope, sources):
    record(db, "service-permit:" + message.id, "SERVICE_RESPONSE_AUTHORIZED", message.id,
           {"request_evidence_id": request_event.id, "contact_id": message.contact_id, "scope": scope,
            "body_hash": digest([message.subject, message.body]), "knowledge_sources": sources,
            "template_revision": SERVICE_TEMPLATE_REVISION},
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
    focus = ("stock above your chosen coverage target and its cost when unit costs are provided"
             if variant == "cash" else "possible stockout risks and reorder triggers")
    message, fresh = insert_once(db, Message, key="first-contact:" + contact.id, contact_id=contact.id,
        experiment_id=experiment.id, direction="out", variant=variant, subject="Next step for your requested inventory check",
        body=service_body("Hi,\n\nThis is Skubase, following up on the free inventory check you requested.\n\n"
              f"Start at {HEALTH_CHECK_URL} — no account or Shopify installation needed. "
              "Add a SKU summary of on-hand units and units sold over a stated period; unit cost, supplier lead time and safety stock are optional. "
              "The check runs in your browser. Your SKU entries are not sent to Skubase.\n\n"
              f"It highlights {focus}. Results depend on the sales period and assumptions you enter; a reorder trigger is not an order quantity.\n\n"
              "If you want help interpreting 5–10 products, reply with the inventory question you want to solve. "
              "Please do not email passwords, access tokens or customer records."))
    if fresh:
        message.skill_version = active_skill(db, "requested_service").version
        permit(db, message, request, "health_check", ["backend/app/api/routes/inventory_risk_snapshot.py", *HEALTH_CHECK_SOURCES])
        record(db, "draft:" + message.id, "EMAIL_DRAFTED", contact.id,
               {"message_id": message.id, "experiment_id": experiment.id, "variant": variant, "purpose": "requested_service",
                "template_revision": SERVICE_TEMPLATE_REVISION})
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
        body=service_body(spec["answer"]))
    if fresh:
        message.skill_version = active_skill(db, "requested_service").version
        permit(db, message, event, key, spec["sources"])
        record(db, "service-reply:" + message.id, "SERVICE_REPLY_DRAFTED", contact.id,
               {"message_id": message.id, "request_evidence_id": event.id, "topic": key,
                "template_revision": SERVICE_TEMPLATE_REVISION})
        enqueue(db, "send:" + message.id, "send", {"message_id": message.id}, priority=95)
    return message
