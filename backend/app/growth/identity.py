"""Compare historical community identities without rewriting their audit history."""
from sqlalchemy import func, select

from .models import Contact

INELIGIBLE = {"declined", "unsubscribed", "delivery_failure", "bounced", "ineligible"}


def canonical_identity(identity):
    value = identity.strip().lower()
    if value.startswith("shopify_community:"):
        value = "shopify-community:" + value.split(":", 1)[1]
    return value


def identity_match(identity):
    canonical = canonical_identity(identity)
    variants = [canonical]
    if canonical.startswith("shopify-community:"):
        variants.append("shopify_community:" + canonical.split(":", 1)[1])
    return func.lower(Contact.identity).in_(variants)


def matching_contacts(db, identity):
    return list(db.scalars(select(Contact).where(identity_match(identity)).order_by(Contact.created_at, Contact.id)))


def existing_contact(db, identity):
    rows = matching_contacts(db, identity)
    # A suppressed legacy row must never be hidden by a newer spelling.
    return next((row for row in rows if row.suppressed or row.status in INELIGIBLE),
                next((row for row in rows if row.identity == canonical_identity(identity)), rows[0] if rows else None))
