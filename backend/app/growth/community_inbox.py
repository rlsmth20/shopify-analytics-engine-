"""Bounded forum inbox checks and source-linked replies on the existing queue."""
import time

from sqlalchemy import select

from .community import location
from .identity import existing_contact, matching_contacts, owned_identity
from .models import Evidence, FirstContact, Message
from .outbound import lock
from .policy import GrowthError, REPLY_CLASSES, classify_reply
from .store import get_memory, insert_once, record, remember

INTERVAL = 3 * 3600
PREFIX = "community-inbox:"


def schedule(db, now=None):
    from .operator import offer, MAX_ATTEMPTS
    now = time.time() if now is None else now
    state = get_memory(db, "working", "community_inbox")
    if not state.get("enabled") or state.get("next_check_at", 0) > now:
        return None
    prior = get_memory(db, "operator_task", state.get("task_id", ""))
    if prior.get("status") in {"pending", "running"} and prior.get("attempts", 0) < MAX_ATTEMPTS:
        return None
    if prior.get("status") == "running" and prior.get("lease_until", 0) > now:
        return None
    seen = list(db.scalars(select(Evidence.data["url"].as_string()).where(
        Evidence.kind == "REPLY_RECEIVED", Evidence.data["channel"].as_string() == "shopify_community")
        .order_by(Evidence.id.desc()).limit(12)))
    event = record(db, PREFIX + str(int(now // INTERVAL)), "COMMUNITY_INBOX_DUE", "shopify-community",
        {"last_checked_at": state.get("checked_at"), "interval_seconds": INTERVAL, "seen_reply_urls": seen})
    task = offer(db, key=PREFIX + str(event.id), source="https://community.shopify.com/u/skubase/notifications",
        decision="Read docs/growth/community-inbox.md. Check the Skubase account notifications and at most three new reply threads. Record actual merchant replies with community-reply. No prospect research or sends during this check. Badges/likes/vendor pitches are not customer interest. Return compact observations and actual source URLs.",
        stage="monitor", priority=95, evidence_id=event.id)
    remember(db, "working", "community_inbox", {**state, "task_id": task["id"], "next_check_at": now + INTERVAL})
    return task


def complete_check(db, task, result, event):
    if not any(str(url).startswith("https://community.shopify.com/") for url in result.get("sources", [])):
        raise GrowthError("Forum inbox check requires actual Shopify Community source URLs")
    state = get_memory(db, "working", "community_inbox")
    remember(db, "working", "community_inbox", {**state,
        "checked_at": event.occurred_at if result["outcome"] == "done" else state.get("checked_at"),
        "evidence_id": event.id, "last_outcome": result["outcome"],
        "next_check_at": event.occurred_at + INTERVAL})


def ingest_reply(db, payload):
    """An observed reply is not a first contact, signup, or proven customer."""
    from .operator import offer
    lock(db)
    url, topic, post = location(payload["url"])
    _, parent_topic, parent_post = location(payload["parent_url"])
    author = str(payload.get("author", "")).strip().lower()
    identity = "shopify-community:" + author
    text = str(payload.get("text", "")).strip()
    classification = payload.get("classification")
    if (not author or owned_identity(identity) or not 1 <= len(text) <= 12000 or
            topic != parent_topic or int(post) <= int(parent_post) or classification not in REPLY_CLASSES):
        raise GrowthError("A real external reply, parent post, exact text and classification are required")
    contact = existing_contact(db, identity)
    if not contact:
        raise GrowthError("Match the forum author to retained prospect history first")
    contacts = matching_contacts(db, identity)
    firsts = list(db.scalars(select(FirstContact).where(FirstContact.contact_id.in_([c.id for c in contacts]),
        FirstContact.channel == "shopify_community", FirstContact.status == "sent")))
    first = next((f for f in firsts if f.receipt and location(f.receipt)[1] == topic), None)
    if not first:
        raise GrowthError("No confirmed Skubase conversation in this topic for this author")
    safety = classify_reply(text)
    if safety in {"UNSUBSCRIBE", "SUBSTANTIVE_NEGATIVE", "DELIVERY_FAILURE"}:
        classification = safety
    key = f"community-reply:{topic}:{post}"
    message, fresh = insert_once(db, Message, key=key, contact_id=first.contact_id,
        experiment_id=first.experiment_id, direction="in", body=text, subject="Shopify Community reply",
        provider_id=key, classification=classification, status="received")
    if not fresh:
        return {"message_id": message.id, "duplicate": True}
    event = record(db, key, "REPLY_RECEIVED", first.contact_id,
        {"message_id": message.id, "classification": classification, "quoted_text": text,
         "experiment_id": first.experiment_id, "channel": "shopify_community", "url": url,
         "parent_url": payload["parent_url"], "author": author, "first_contact_id": first.id}, source=url)
    negative = classification in {"UNSUBSCRIBE", "SUBSTANTIVE_NEGATIVE", "DELIVERY_FAILURE"}
    if negative:
        for item in contacts:
            item.suppressed = True
            item.status = "unsubscribed" if classification == "UNSUBSCRIBE" else "declined"
    elif classification in {"SUBSTANTIVE_POSITIVE", "SUBSTANTIVE_NEUTRAL", "QUESTION"}:
        if not any(c.suppressed for c in contacts):
            for item in contacts:
                item.status = "active_conversation"
            task = offer(db, key="answer:" + key, source=url, stage="reply", priority=100,
                contact_id=first.contact_id, evidence_id=event.id,
                decision="Handle the retained real Shopify Community reply, not a new first contact. Read docs/growth/community-inbox.md and the source conversation. Recheck that Skubase has not already answered this post before publishing once. Respond concisely to the actual interest/question with verified product facts and one useful next step. Preserve the existing campaign; record the exact answer and published permalink in your result. Do not reserve a new first contact or send another channel pitch.")
            return {"message_id": message.id, "evidence_id": event.id, "task_id": task["id"]}
    return {"message_id": message.id, "evidence_id": event.id}
