"""Preserve acknowledged support requests without treating them as sales consent."""
import logging
import os
import time

from sqlalchemy import select

from app.db.session import SessionLocal
from .models import Contact
from .store import digest, record


def observe_contact_form(*, email, contact_type, message, receipt_id, factory=SessionLocal):
    if os.getenv("GROWTH_ENABLED") != "true" or email.lower().endswith("@skubase.io"):
        return
    try:
        with factory() as db:
            contact = db.scalar(select(Contact).where(Contact.email == email.lower()))
            if not contact:
                contact = Contact(identity="email:" + email.lower(), email=email.lower(), source="skubase_contact_form",
                                  contact_basis="research_only", status="inbound_unqualified")
                db.add(contact); db.flush()
            key = digest([email.lower(), contact_type, message, int(time.time() // 86400)])
            event = record(db, "form:" + key, "CONTACT_FORM_RECEIVED", contact.id,
                           {"type": contact_type, "message": message, "provider_receipt": receipt_id}, source="skubase_contact_form")
            record(db, "form-obligation:" + key, "OWNER_ATTENTION", contact.id,
                   {"priority": "high" if contact_type in ("billing", "bug") else "normal",
                    "reason": "Answer a contact form request; this is not marketing consent", "evidence_id": event.id})
            db.commit()
    except Exception:
        # Delivery already succeeded; never invite a duplicate support submission.
        logging.error("Growth contact-form observation failed; original remains in info inbox")
