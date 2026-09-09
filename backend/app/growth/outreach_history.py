"""Read-only, bounded owner projection of original outreach evidence."""
import re
from urllib.parse import urlsplit

from sqlalchemy import select

from .models import Contact, Evidence, FirstContact, Message
from .store import digest


def public_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {'https', 'http'} and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def history(db, *, before=None, status='sent', limit=25, search='', method=None):
    query = select(FirstContact).outerjoin(Contact, Contact.id == FirstContact.contact_id).where(FirstContact.status == status)
    if method:
        query = query.where(FirstContact.channel == method)
    if search.strip():
        pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.where(Contact.organization.ilike(pattern, escape='\\') |
                            Contact.identity.ilike(pattern, escape='\\') |
                            Contact.email.ilike(pattern, escape='\\'))
    if before:
        # IDs are opaque; cursor uses the immutable reservation ordering.
        anchor = db.get(FirstContact, before)
        if anchor is None:
            return {'items': [], 'next_cursor': None}
        query = query.where((FirstContact.reserved_at < anchor.reserved_at) |
                            ((FirstContact.reserved_at == anchor.reserved_at) & (FirstContact.id < anchor.id)))
    rows = list(db.scalars(query.order_by(FirstContact.reserved_at.desc(), FirstContact.id.desc()).limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    contact_ids = [r.contact_id for r in rows]
    contacts = {c.id: c for c in db.scalars(select(Contact).where(Contact.id.in_(contact_ids)))}
    keys = ['first-contact-intent:' + r.id for r in rows] + ['channel-check:' + r.id for r in rows]
    evidence = {e.key: e for e in db.scalars(select(Evidence).where(Evidence.key.in_(keys)))}
    legacy_ids = [r.cohort.get('source_evidence_id') for r in rows if isinstance(r.cohort.get('source_evidence_id'), int)]
    legacy = {e.id: e for e in db.scalars(select(Evidence).where(Evidence.id.in_(legacy_ids)))}
    messages = list(db.scalars(select(Message).where(Message.contact_id.in_(contact_ids),
        Message.direction == 'outbound', Message.sent_at.is_not(None)).order_by(Message.sent_at.desc())))
    items = []
    for row in rows:
        contact = contacts.get(row.contact_id)
        intent = evidence.get('first-contact-intent:' + row.id) or legacy.get(row.cohort.get('source_evidence_id'))
        retained = intent.data if intent and intent.subject == row.contact_id else {}
        body = retained.get('body') or retained.get('body_normalized_whitespace')
        message_basis = 'Historical text; original spacing was not retained.' if not retained.get('body') and retained.get('body_normalized_whitespace') else None
        # Never substitute a current draft for a historical sent message.
        if not isinstance(body, str) or digest(body) != row.body_hash:
            body = None
        matched = next((m for m in messages if m.contact_id == row.contact_id and digest(m.body) == row.body_hash), None)
        if body is None and matched:
            body = matched.body
        review = evidence.get('channel-check:' + row.id)
        source = review.data.get('source') if review else None
        source = public_url(source) or public_url(contact.source if contact else None)
        links = []
        for candidate in re.findall(r'https?://[^\s<>"\x00-\x1f]+', row.receipt or ''):
            url = public_url(candidate.rstrip('.,;'))
            if url and url not in links:
                links.append(url)
        items.append({'id': row.id, 'contact': contact.organization if contact else 'Historical contact',
            'identity': contact.identity if contact else None, 'email': contact.email if contact else None,
            'method': row.channel, 'status': row.status, 'sent_at': row.sent_at, 'reserved_at': row.reserved_at,
            'timestamp_basis': row.cohort.get('timestamp_basis'), 'message': body,
            'subject': matched.subject if matched else None, 'source_url': source, 'message_basis': message_basis,
            'receipt': row.receipt, 'receipt_urls': links, 'experiment_id': row.experiment_id,
            'message_version': row.cohort.get('message_version'),
            'qualification_policy': row.cohort.get('qualification_policy'),
            'suppressed': contact.suppressed if contact else None})
    return {'items': items, 'next_cursor': rows[-1].id if more else None}
