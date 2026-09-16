"""Rules for the bounded commercial validation experiment, using existing ledgers."""
from urllib.parse import urlencode
import re

from sqlalchemy import func, select

from .models import FirstContact
from .policy import GrowthError
from .store import get_memory

VERSION = "focused_validation_v1"
KEY = "reorder-po-validation-v1"
LABELS = {
    "icp": "shopify_physical_inventory_complexity",
    "offer": "reorder_recommendations_exportable_purchase_orders",
    "message_version": "reorder_po_v1",
    "message_variant": "reorder_po_v1",
    "positioning": "practical_purchasing_decisions",
    "cta": "Would you be interested in seeing what Skubase recommends for your store?",
}


def policy(db):
    value = get_memory(db, "strategic", "focused_validation")
    return value if value.get("version") == VERSION and value.get("active") else {}


def tagged_url(contact_id, channel, campaign=KEY):
    return "https://www.skubase.io/?" + urlencode({
        "utm_source": channel, "utm_medium": "outreach", "utm_campaign": campaign,
        "utm_content": "outreach-" + contact_id})


def admission(db, experiment, channel, cohort, body):
    """Called under the send lock. Old receipts/intents are never rewritten."""
    focus = policy(db)
    if not focus:
        return cohort
    if experiment.id != focus.get("experiment_id"):
        raise GrowthError("Use the active focused validation experiment for new first contacts", "configuration")
    spec = experiment.specification
    labels = spec["cohort_labels"]
    confirmed = db.scalar(select(func.count()).select_from(FirstContact).where(
        FirstContact.experiment_id == experiment.id, FirstContact.status == "sent")) or 0
    if confirmed >= spec.get("max_contacts", 50):
        raise GrowthError("FOCUSED_VALIDATION_REVIEW_DUE: review outcomes before extending this experiment; continue conversations and discovery", "capacity")
    # Forms remain a deliberate fallback, not spillover when email hits its ramp.
    if channel not in spec.get("primary_channels", []):
        raise GrowthError("Focused validation uses email or relevant Shopify Community; retain other opportunities for a later experiment", "configuration")
    if not (re.search(r"reorder", body, re.I) and re.search(r"export", body, re.I)
            and re.search(r"purchase orders?|\bPOs?\b", body, re.I)):
        raise GrowthError("Focused message must explain reorder recommendations and exportable purchase orders; do not relabel an old pitch", "configuration")
    return {**cohort, **labels, "cohort_policy": VERSION}


def cohort_key(dimensions, cohort):
    if cohort.get("cohort_policy") == VERSION:
        return {k: dimensions[k] for k in ("experiment_id", "icp_segment", "offer", "channel", "message")}
    return {k: v for k, v in dimensions.items() if k not in {"source", "shopify_confidence"}}


def summarize(experiment, block, records, evidence, now):
    """A 50-contact decision threshold is not a claim of statistical certainty."""
    n = block["metrics"]["confirmed_contacts"]
    replies = block["metrics"]["substantive_responses"]
    positive = block["metrics"]["positive_responses"]
    ids = {r["row"].contact_id: r["row"].sent_at for r in records if r["row"].status == "sent"}
    requests = {e.subject for e in evidence if e.kind == "ACCESS_REQUESTED" and e.data.get("verified") is True
                and e.subject in ids and e.occurred_at >= ids[e.subject]
                and e.data.get("experiment_id") in (None, experiment.id)}
    strong = {r["merchant"] for r in records if r["row"].contact_id in requests
              or any(r["stages"][s] for s in ("SHOPIFY_CONNECTED", "ACTIVATED", "PAID"))}
    target = experiment.specification.get("max_contacts", 50)
    latest = max(ids.values(), default=now)
    waiting = n >= target and now < latest + 7 * 86400
    achieved = replies >= 3 and positive >= 2 and len(strong) >= 1
    decision = ("CONTINUE_CAREFULLY" if achieved else
                "OBSERVE_RESPONSES" if waiting else
                "CHANGE_ONE_MAJOR_VARIABLE" if n >= target and replies <= 1 else
                "DIAGNOSE_FUNNEL" if n >= target else "ACCUMULATING")
    return {"experiment_id": experiment.id, "campaign": experiment.key,
            "metrics": block["metrics"], "funnel": block["funnel"], "rates": block["rates"],
            "health_check_requests": len(requests) or None, "strong_activation_events": len(strong) or None,
            "targets": {"confirmed_contacts": target, "substantive_responses": 3, "positive_responses": 2, "strong_activation_events": 1},
            "remaining": max(0, target - n), "decision": decision,
            "next_decision_at": latest + 7 * 86400 if waiting else None,
            "guidance": "At 50 confirmed contacts stop enrollment and review delivery/reply coverage. Allow seven days for the last contact to respond before treating silence as negative. Keep useful conversations and discovery running. If weak, change one major variable; never infer absent demand or fabricate conversions."}


def attributed_touches(rows, experiments, evidence, visitor_links):
    """Campaign links attribute traffic, not a visitor's claimed merchant identity.

    Only confirmed send/campaign matches qualify. First observed touch wins per
    visitor and authenticated shop. A public link is not proof of merchant identity.
    """
    campaigns = {e.id: e.key for e in experiments}
    sends = {"outreach-" + r.contact_id: r for r in rows if r.status == "sent" and r.sent_at is not None}
    visits, shops, first_visitors, first_shops = {}, {}, set(), set()
    for e in sorted(evidence, key=lambda e: (e.occurred_at, e.id)):
        if e.kind != "VISITOR" or e.source != "first_party_browser" or not e.subject.startswith("visitor:"):
            continue
        tags = e.data.get("attribution", {})
        row = sends.get(tags.get("utm_content"))
        if (not row or e.occurred_at < row.sent_at or tags.get("utm_campaign") != campaigns.get(row.experiment_id)
                or tags.get("utm_medium") != "outreach" or tags.get("utm_source") != row.channel):
            continue
        if e.subject in first_visitors:
            continue
        first_visitors.add(e.subject)
        visits.setdefault(row.id, []).append(e)
        shop = visitor_links.get(e.subject)
        if shop and shop not in first_shops:
            first_shops.add(shop)
            shops.setdefault(row.id, {})[shop] = e.occurred_at
    return visits, shops
