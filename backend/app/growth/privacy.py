"""Erase merchant-linked growth data in the existing signed shop-redaction transaction."""
import hashlib
import json

from sqlalchemy import delete, or_, select

from .models import Contact, Evidence, Memory, Message, Usage, Work


def redact_growth(db, shop_id, emails):
    # No model summaries or raw correspondence are exempt from merchant erasure.
    contacts = list(db.scalars(select(Contact).where(or_(Contact.shop_id == shop_id, Contact.email.in_(emails)))))
    contact_ids = {c.id for c in contacts}
    message_ids = set(db.scalars(select(Message.id).where(Message.contact_id.in_(contact_ids)))) if contact_ids else set()
    subjects = {f"shop:{shop_id}", *contact_ids, *("customer:" + c for c in contact_ids), f"attribution:shop:{shop_id}", f"economics:shop:{shop_id}"}
    # Remove anonymous history connected to this tenant by the authenticated bridge.
    links = list(db.scalars(select(Evidence).where(Evidence.kind == "IDENTITY_LINK")))
    subjects.update(e.subject for e in links if e.data.get("shop_id") == shop_id)
    db.execute(delete(Evidence).where(Evidence.subject.in_(subjects)))
    for item in db.scalars(select(Work)):
        if item.payload.get("contact_id") in contact_ids or item.payload.get("message_id") in message_ids:
            db.delete(item)
    for item in db.scalars(select(Memory).where(Memory.namespace.in_(["customer", "attribution", "economics"]))):
        if item.key in contact_ids or item.key == f"shop:{shop_id}" or item.value.get("shop_id") == shop_id:
            db.delete(item)
    # Provider payloads may include mailbox addresses; discard matching raw delivery records.
    for item in db.scalars(select(Evidence).where(Evidence.kind == "PROVIDER_EVENT")):
        raw = json.dumps(item.data).lower()
        if any(email.lower() in raw for email in emails):
            db.delete(item)
    db.execute(delete(Message).where(Message.contact_id.in_(contact_ids)))
    db.execute(delete(Contact).where(Contact.id.in_(contact_ids)))
    # Scrub linked raw summaries too; preserve spend totals without model output.
    identifiers = [*emails, *contact_ids, *message_ids]
    for entity, field in ((Evidence, "data"), (Memory, "value"), (Usage, "result"), (Work, "result")):
        for item in db.scalars(select(entity)):
            raw = json.dumps(getattr(item, field)).lower()
            if any(identifier.lower() in raw for identifier in identifiers) or json.dumps(f"shop:{shop_id}") in raw:
                if entity is Usage:
                    item.result = {"redacted": True}
                else:
                    db.delete(item)
