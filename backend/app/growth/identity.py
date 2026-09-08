"""Compare historical community identities without rewriting their audit history."""
from urllib.parse import urlparse
from sqlalchemy import func, select, or_, and_

from .models import Contact

INELIGIBLE = {"declined", "unsubscribed", "delivery_failure", "bounced", "ineligible"}


def canonical_identity(identity):
    value = identity.strip().lower()
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
    return list(db.scalars(select(Contact).where(identity_match(identity)).order_by(Contact.created_at, Contact.id)))


def existing_contact(db, identity):
    rows = matching_contacts(db, identity)
    # A suppressed legacy row must never be hidden by a newer spelling.
    return next((row for row in rows if row.suppressed or row.status in INELIGIBLE),
                next((row for row in rows if row.identity == canonical_identity(identity)), rows[0] if rows else None))
