"""Controlled mailbox diagnostics. Never creates a Contact, Message or FirstContact.

The existing browser executor supplies external effects; this module owns durable
timing, one-use send permits, threading and isolated evidence. Test success never
increases the merchant outreach ramp or becomes customer engagement.
"""
import re
import time
from email.utils import parseaddr
from html import escape
from urllib.parse import urlparse

from sqlalchemy import select

from .models import Evidence, Memory, uid
from .outbound import lock, status as outreach_status
from .policy import GrowthError
from .review_calendar import review_day
from .store import digest, get_memory, record, remember

NS = "warmup_message"
MARKER = r"\[sb-check:([a-f0-9]{32})\]"


def config(db):
    return get_memory(db, "strategic", "controlled_email_tests")


def messages(db):
    return [r.value for r in db.scalars(select(Memory).where(Memory.namespace == NS)
        .order_by(Memory.id.desc()).limit(200))]


def account(db, address):
    entry = config(db).get("accounts", {}).get(address)
    proof = db.get(Evidence, entry.get("evidence_id")) if entry else None
    if not entry or entry.get("enabled") is not True or not proof or proof.kind != "CONTROLLED_INBOX_VERIFIED" or proof.subject != address:
        raise GrowthError("CONTROLLED_INBOX_NOT_VERIFIED")
    parsed = urlparse(entry.get("url", ""))
    if parsed.scheme != "https" or parsed.hostname != "mail.google.com":
        raise GrowthError("CONTROLLED_INBOX_ROUTE_REQUIRED")
    return entry


def status(db, now=None):
    now = time.time() if now is None else now
    cfg = config(db)
    state = get_memory(db, "working", "controlled_email_tests")
    rows = messages(db)
    started = state.get("start_at")
    age = int((now - started) / 86400) if started else 0
    ceiling = min(int(cfg.get("daily_ceiling", 4)), 2 if age < 3 else 3 if age < 7 else 4)
    window = review_day(now)
    today = sum(window.start <= r.get("sent_at", 0) < window.end for r in rows)
    active = [r for r in rows if r.get("state") in {"queued", "authorized", "uncertain", "sent"}]
    hold = state.get("hold")
    if get_memory(db, "working", "outreach_email_health").get("paused"):
        hold = "PROVIDER_DELIVERABILITY_HOLD"
    return {"enabled": cfg.get("enabled") is True, "accounts": list(cfg.get("accounts", {})),
        "start_at": started, "phase": "complete" if age >= 14 else "controlled_testing",
        "daily_ceiling": max(0, ceiling), "sent_today": today,
        "remaining": max(0, ceiling - today), "hold": hold,
        "pending": active, "next_at": state.get("next_at"),
        "totals": {"sent": sum(bool(r.get("sent_at")) for r in rows),
            "received": sum(bool(r.get("received_at")) for r in rows),
            "read": sum(bool(r.get("read_at")) for r in rows),
            "threaded_replies": sum(bool(r.get("sent_at") and r.get("parent_id")) for r in rows),
            "initial_spam": sum(r.get("original_folder") == "spam" for r in rows),
            "moved_from_spam": sum(bool(r.get("moved_from_spam_at")) for r in rows),
            "failed": sum(r.get("state") == "failed" for r in rows)},
        "counts_toward_outreach": False, "proves_merchant_inbox_placement": False}


def _save(db, item):
    remember(db, NS, item["id"], item)


def _new(db, sender, recipient, due, parent=None):
    account(db, sender); account(db, recipient)
    item_id = uid()
    topics = [("Reply routing", "Could you reply in this thread so we can check the return route?"),
              ("Paragraph rendering", "This note checks that short paragraphs and the signature stay separate in the receiving inbox."),
              ("Mailbox delivery", "Please check the initial folder and authentication details for this delivery."),
              ("Sender details", "This check covers the displayed sender, reply address and message headers.")]
    topic, question = topics[int(item_id[:8], 16) % len(topics)]
    marker = f"[sb-check:{item_id}]"
    body = ("Hi,\n\nThis is a controlled Skubase email check. " + question if not parent else
            "Hi,\n\nReplying in the existing Skubase test thread to check return delivery and conversation routing.")
    body += "\n\nThese are internal infrastructure checks, not customer conversations.\n\nSkubase\n" + marker
    item = {"id": item_id, "sender": sender, "recipient": recipient,
        "subject": parent["subject"] if parent else f"Skubase {topic.lower()} check {marker}",
        "body": body, "html_body": ''.join('<div>'+ (escape(line) if line else '<br>')+'</div>' for line in body.split('\n')),
        "parent_id": parent["id"] if parent else None, "thread_url": parent.get("received_url") if parent else None,
        "state": "queued", "due_at": due, "created_at": time.time(), "checks": 0}
    _save(db, item)
    return item


def schedule(db, now=None):
    """At most one bounded operator task; no models or retrospective research."""
    now = time.time() if now is None else now
    lock(db)
    view = status(db, now)
    if not view["enabled"]:
        return None
    cfg = config(db)
    state = get_memory(db, "working", "controlled_email_tests")
    active = view["pending"]
    item = min(active, key=lambda r: r["created_at"]) if active else None
    if item and item["state"] == "authorized" and item["submit_before"] < now:
        item = {**item, "state": "uncertain"}; _save(db, item)
    if not item:
        if view["phase"] == "complete" or view["hold"] or not view["remaining"] or (state.get("next_at") or 0) > now:
            return None
        accounts = list(cfg.get("accounts", {}))
        if len(accounts) < 2:
            return None
        # No fake identities or provider/account rotation. Keep the real sender.
        item = _new(db, accounts[0], accounts[1], now)
    if item.get("next_check_at", item["due_at"]) > now or item["due_at"] > now:
        return None
    from .operator import offer
    mode = "send" if item["state"] == "queued" else "inspect"
    if mode == "send" and (view["phase"] == "complete" or view["hold"] or not view["remaining"]):
        return None
    key = f"controlled-test:{item['id']}:{mode}:{item['checks']}"
    evidence = record(db, key, "WARMUP_WORK_SCHEDULED", item["id"], {"mode": mode, "message_id": item["id"]})
    return offer(db, key=key, source=account(db, item["sender"] if mode == "send" else item["recipient"])["url"],
        stage="deliverability", priority=70, evidence_id=evidence.id,
        decision=f"Controlled inbox {mode} for warmup message {item['id']}. Read docs/growth/controlled-email-tests.md. Use warmup-status and warmup-prepare; only allowlisted accounts. Record actual receipts with warmup-record. No prospect/outreach actions in this task.")


def prepare(db, item_id, now=None):
    now = time.time() if now is None else now
    item = get_memory(db, NS, item_id)
    if not item:
        raise GrowthError("UNKNOWN_CONTROLLED_TEST")
    return {**item, "sender_account": account(db, item["sender"]), "recipient_account": account(db, item["recipient"]),
            "send_allowed": item["state"] == "queued" and item["due_at"] <= now}


def authorize(db, item_id, sender, now=None):
    now = time.time() if now is None else now
    lock(db)
    item = prepare(db, item_id, now)
    view = status(db, now)
    if not view["enabled"] or view["hold"] or view["phase"] == "complete" or not view["remaining"]:
        raise GrowthError("CONTROLLED_TEST_PAUSED_OR_CAPPED")
    if sender != item["sender"] or not item["send_allowed"]:
        raise GrowthError("CONTROLLED_TEST_SEND_NOT_AUTHORIZED")
    if get_memory(db, "working", "control").get("paused") or outreach_status(db)["in_flight_send_count"]:
        raise GrowthError("ANOTHER_SEND_OR_DEPLOYMENT_IN_PROGRESS", "capacity")
    if any(r["id"] != item_id and r["state"] in {"authorized", "uncertain"} for r in view["pending"]):
        raise GrowthError("CONTROLLED_TEST_UNRESOLVED")
    raw = get_memory(db, NS, item_id)
    _save(db, {**raw, "state": "authorized", "authorized_at": now, "submit_before": now+30})
    record(db, "warmup-authorize:"+item_id, "WARMUP_SEND_AUTHORIZED", item_id, {"sender": sender, "submit_before": now+30})
    return {"message_id": item_id, "submit_before": now+30, "single_use": True}


def observe(db, payload, now=None):
    now = time.time() if now is None else now
    lock(db)
    item_id = payload["message_id"]
    item = get_memory(db, NS, item_id)
    if not item:
        raise GrowthError("UNKNOWN_CONTROLLED_TEST")
    kind = payload["event"]
    if kind not in {"sent", "received", "read", "moved_from_spam", "failed", "warning", "not_found", "uncertain"}:
        raise GrowthError("UNKNOWN_CONTROLLED_TEST_EVENT")
    url = payload.get("url", "")
    event_key = "warmup-observation:" + digest([item_id, kind, url, payload.get("observation")])
    prior = db.scalar(select(Evidence).where(Evidence.key == event_key))
    if prior:
        return {"evidence_id": prior.id, "message_id": item_id, "state": item["state"], "counts_toward_acquisition": False}
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "mail.google.com" or not payload.get("observation"):
        raise GrowthError("ACTUAL_GMAIL_OBSERVATION_REQUIRED")
    observed_account = payload.get("account")
    if observed_account not in {item["sender"], item["recipient"]}:
        raise GrowthError("WRONG_CONTROLLED_ACCOUNT")
    if kind in {"received", "read", "moved_from_spam"} and observed_account != item["recipient"]:
        raise GrowthError("RECEIVING_ACCOUNT_REQUIRED")
    if kind in {"received", "read", "moved_from_spam", "sent"} and '/' not in parsed.fragment:
        raise GrowthError("ACTUAL_THREAD_RECEIPT_REQUIRED")
    state = get_memory(db,"working","controlled_email_tests")
    if kind == "sent":
        if not item.get("authorized_at") or observed_account != item["sender"]:
            raise GrowthError("NO_CONTROLLED_SEND_INTENT")
        if not item.get("sent_at"):
            item.update(state="sent", sent_at=now, sent_url=url, next_check_at=now+300)
            state.update(start_at=state.get("start_at") or now, next_at=now+4*3600)
        item.setdefault("sent_url", url)
    elif kind == "received":
        if payload.get("folder") not in {"inbox", "spam", "other"} or not item.get("authorized_at"):
            raise GrowthError("RETAIN_ORIGINAL_FOLDER_AND_SEND_INTENT")
        first = not item.get("received_at")
        if not item.get("sent_at"):
            item["sent_at"] = item["authorized_at"]
            state["start_at"] = state.get("start_at") or item["sent_at"]
        item.update(state="received", received_at=item.get("received_at") or now, received_url=url,
            original_folder=item.get("original_folder") or payload["folder"])
        authentication = dict(item.get("authentication", {}))
        for key in ["spf", "dkim", "dmarc", "from", "return_path", "reply_to"]:
            value = str(payload.get("authentication", {}).get(key, "UNKNOWN"))[:500]
            if key in {"spf", "dkim", "dmarc"}:
                value = value.lower() if value.lower() in {"pass", "fail"} else "UNKNOWN"
            if value != "UNKNOWN" or key not in authentication:
                authentication[key] = value
        item["authentication"] = authentication
        if item["original_folder"] == "spam" or any(item["authentication"].get(k) == "fail" for k in ["spf","dkim","dmarc"]):
            state["hold"] = "SPAM_PLACEMENT_OR_AUTHENTICATION_FAILURE"
            from .email_ramp import signal
            signal(db, item["sender"], "controlled_delivery_problem", item_id)
        if first and not item.get("parent_id") and not state.get("hold"):
            delay = 2700 + int(item_id[:6],16) % 4500
            _new(db, item["recipient"], item["sender"], now+delay, parent=item)
    elif kind in {"read", "moved_from_spam"}:
        if not item.get("received_at") or (kind == "moved_from_spam" and item.get("original_folder") != "spam"):
            raise GrowthError("ORIGINAL_DELIVERY_OBSERVATION_REQUIRED")
        item[kind+"_at"] = item.get(kind+"_at") or now
    elif kind in {"failed", "warning"}:
        item.update(state="failed", failure=payload["observation"][:500])
        state["hold"] = "CONTROLLED_DELIVERY_FAILURE" if kind == "failed" else "PROVIDER_WARNING"
        if kind == "warning":
            health = get_memory(db, "working", "outreach_email_health")
            remember(db, "working", "outreach_email_health", {**health, "paused": True,
                "reason": "PROVIDER_WARNING", "source": url, "evidence_message_id": item_id})
    elif kind == "uncertain":
        if not item.get("sent_at"):
            item.update(state="uncertain", next_check_at=now+3600)
    elif kind == "not_found":
        item["checks"] += 1
        item["next_check_at"] = now + (3600 if item["checks"] == 1 else 86400)
        if item["checks"] >= 3:
            state["hold"] = "CONTROLLED_DELIVERY_UNRESOLVED"
            item.update(state="unresolved")
    _save(db, item)
    remember(db,"working","controlled_email_tests",state)
    event = record(db, event_key,
        "WARMUP_"+kind.upper(), item_id, {**payload, "counts_toward_acquisition":False})
    return {"evidence_id":event.id,"message_id":item_id,"state":item["state"],"counts_toward_acquisition":False}


def ingest_controlled(db, sender, recipients, subject, text, provider_id):
    """Receiving bridge excludes controlled identities before merchant ingestion."""
    sender = parseaddr(sender)[1].lower()
    recipients = {parseaddr(r)[1].lower() for r in recipients}
    owned = set(config(db).get("accounts", {}))
    if sender not in owned or not recipients.intersection(owned):
        return False
    found = re.search(MARKER, text+"\n"+subject)
    item = get_memory(db, NS, found[1]) if found else {}
    # Even an unthreaded message from a controlled inbox is never a merchant lead.
    record(db,"warmup-inbound:"+provider_id,"WARMUP_INBOUND",sender,
        {"message_id":item.get("id"),"provider_id":provider_id,"recipients":sorted(recipients),
         "subject":subject[:200],"body":text[:4000],"classification":"CONTROLLED_TEST"})
    return True


def operator_action(db, action, payload):
    if action == "warmup-status": return status(db)
    if action == "warmup-prepare": return prepare(db,payload["message_id"])
    if action == "warmup-authorize": return authorize(db,payload["message_id"],payload["sender"])
    if action == "warmup-record": return observe(db,payload)
    raise GrowthError("UNKNOWN_WARMUP_ACTION")
