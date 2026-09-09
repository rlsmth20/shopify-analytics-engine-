"""Compare historical community identities without rewriting their audit history."""
from urllib.parse import urlparse
from sqlalchemy import func, select, or_, and_

from .models import Contact, Memory
from .store import digest, get_memory

INELIGIBLE = {"declined", "unsubscribed", "delivery_failure", "bounced", "ineligible"}


def canonical_identity(identity):
    value = identity.strip().lower()
    if value.startswith("email:"):
        value = value.removeprefix("email:")
    if value.startswith("shopify_community:"):
        value = "shopify-community:" + value.split(":", 1)[1]
    return value


def owned_identity(identity):
    return canonical_identity(identity) in {"shopify-community:skubase", "reddit:skubase",
        "info@skubase.io", "support@skubase.io", "email:info@skubase.io", "email:support@skubase.io"}


def prospect_identity(identity, source):
    value = canonical_identity(identity)
    host = urlparse(source or "").hostname or ""
    if ":" not in value and "@" not in value:
        if host == "community.shopify.com":
            value = "shopify-community:" + value
        elif host in {"reddit.com", "www.reddit.com"}:
            value = "reddit:" + value.removeprefix("u/")
    return value


def identity_match(identity):
    canonical = canonical_identity(identity)
    variants = [canonical]
    if "@" in canonical:
        variants.append("email:" + canonical)
    if canonical.startswith("shopify-community:"):
        variants.append("shopify_community:" + canonical.split(":", 1)[1])
    exact = func.lower(Contact.identity).in_(variants)
    for prefix, host in (("shopify-community:", "community.shopify.com"), ("reddit:", "reddit.com")):
        if canonical.startswith(prefix):
            bare = canonical.split(":", 1)[1]
            return or_(exact, and_(func.lower(Contact.identity) == bare,
                or_(Contact.source.like("https://" + host + "/%"), Contact.source.like("https://www." + host + "/%"))))
    return exact


def matching_contacts(db, identity):
    mapping = get_memory(db, "merchant_alias", digest(canonical_identity(identity)))
    merchant = get_memory(db, "merchant", mapping.get("merchant_key", "")) if mapping else {}
    aliases = {canonical_identity(identity), *(a["identity"] for a in merchant.get("routes", []))}
    return list(db.scalars(select(Contact).where(or_(*(identity_match(a) for a in aliases)))
                           .order_by(Contact.created_at, Contact.id)))


def link_merchant(db, payload):
    """Explicit public evidence links identities; names and email domains alone do not."""
    from .outbound import lock
    from .policy import GrowthError
    from .store import record, remember
    lock(db)
    key = payload.get("merchant_key", "").strip().lower()
    if not key or len(key) > 180 or owned_identity(key):
        raise GrowthError("A stable merchant key is required")
    routes = payload.get("routes", [])
    if not 1 <= len(routes) <= 12:
        raise GrowthError("Link only the merchant routes actually discovered")
    current = get_memory(db, "merchant", key)
    merged = {r["identity"]: r for r in current.get("routes", [])}
    for route in routes:
        identity = canonical_identity(route.get("identity", ""))
        source = route.get("source", "")
        parsed = urlparse(source)
        if (not identity or len(identity) > 320 or owned_identity(identity) or parsed.scheme != "https"
                or not parsed.hostname or parsed.username or parsed.password
                or not route.get("relationship") or len(route["relationship"]) > 400
                or route.get("channel") not in {"email", "contact_form", "shopify_community", "reddit", "public_community", "social_dm"}):
            raise GrowthError("Each route needs identity, channel, source and verified relationship")
        prior = get_memory(db, "merchant_alias", digest(identity))
        if prior and prior["merchant_key"] != key:
            raise GrowthError("Conflicting merchant association; retain uncertainty instead of merging")
        merged[identity] = {"identity": identity, "channel": route["channel"], "source": source,
                            "relationship": route["relationship"], "person": route.get("person")}
    if len(merged) > 30:
        raise GrowthError("Merchant route list exceeds bounded context")
    value = {"merchant_key": key, "name": payload.get("name") or current.get("name"), "routes": list(merged.values())}
    event = record(db, "merchant-linked:" + digest(value), "MERCHANT_IDENTITIES_LINKED", key, value)
    remember(db, "merchant", key, {**value, "evidence_id": event.id})
    for identity in merged:
        remember(db, "merchant_alias", digest(identity), {"identity": identity, "merchant_key": key, "evidence_id": event.id})
    db.flush()
    contacts = matching_contacts(db, next(iter(merged)))
    emails = [r["identity"] for r in merged.values() if r["channel"] == "email"]
    if contacts and emails and not any(c.email for c in contacts):
        from .outreach_email import address
        verified_email = address(emails[0])
        prior_email = db.scalar(select(Contact).where(func.lower(Contact.email) == verified_email))
        if prior_email and prior_email.id not in {c.id for c in contacts}:
            raise GrowthError("Business email is associated with another prospect; resolve identity first")
        contacts[0].email = verified_email
        db.flush()
    return merchant_view(db, next(iter(merged)))


def merchant_view(db, identity):
    from .models import Evidence, FirstContact, Message
    rows = matching_contacts(db, identity)
    ids = [r.id for r in rows]
    mapping = get_memory(db, "merchant_alias", digest(canonical_identity(identity)))
    merchant = get_memory(db, "merchant", mapping.get("merchant_key", "")) if mapping else {}
    first = list(db.scalars(select(FirstContact).where(FirstContact.contact_id.in_(ids))))
    messages = list(db.scalars(select(Message).where(Message.contact_id.in_(ids)).order_by(Message.created_at.desc()).limit(12)))
    touches = [r.value for r in db.scalars(select(Memory).where(Memory.namespace == "merchant_touch",
                Memory.value["contact_id"].as_string().in_(ids)).order_by(Memory.updated_at.desc()).limit(12))]
    suppressed = any(c.suppressed or c.status in INELIGIBLE for c in rows)
    return {"merchant": merchant or {"routes": [{"identity": identity}]}, "contact_ids": ids,
        "suppressed": suppressed, "first_contacts": [{"id": r.id, "channel": r.channel, "status": r.status,
            "receipt": r.receipt, "sent_at": r.sent_at, "cohort": r.cohort} for r in first],
        "recent_messages": [{"id": m.id, "direction": m.direction, "classification": m.classification, "subject": m.subject,
                            "campaign_id": m.experiment_id, "reply_to_id": m.reply_to_id,
                            "body": m.body, "status": m.status} for m in messages], "subsequent_contacts": touches,
        "next_action": "SUPPRESSED" if suppressed else "RECONCILE_ONLY" if any(r.status != "sent" for r in first)
            or any(t["status"] in {"reserved", "authorized", "uncertain"} for t in touches)
            else "REVIEW_CONVERSATION" if first else "LIGHT_QUALIFICATION"}


def existing_contact(db, identity):
    rows = matching_contacts(db, identity)
    # A suppressed legacy row must never be hidden by a newer spelling.
    return next((row for row in rows if row.suppressed or row.status in INELIGIBLE),
                next((row for row in rows if row.identity == canonical_identity(identity)), rows[0] if rows else None))
