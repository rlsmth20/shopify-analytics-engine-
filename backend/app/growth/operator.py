"""Bounded, leased handoff from server discovery to the browser operator.

Queue state never grants permission to send. FirstContact remains the sole
shared admission gate, and external receipts remain the proof of outreach.
"""
import time
from urllib.parse import urlparse

from sqlalchemy import select, func

from .models import Evidence, FirstContact, Memory, uid
from .outbound import lock, status
from .policy import GrowthError
from .store import digest, get_memory, record, remember

NAMESPACE = "operator_task"
LEASE_SECONDS = 1800
MAX_ATTEMPTS = 3


def offer(db, *, key, source, decision, evidence_id, contact_id=None, priority=50):
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise GrowthError("Operator task requires a stable bounded key")
    if source and (urlparse(source).scheme != "https" or not urlparse(source).hostname or len(source) > 1000):
        raise GrowthError("Operator source must be an HTTPS reference")
    evidence = db.get(Evidence, evidence_id)
    if not evidence or not isinstance(decision, str) or not decision.strip() or len(decision) > 1500:
        raise GrowthError("Operator handoff needs retained evidence and a concrete decision")
    lock(db)
    task_id = digest(key)
    prior = get_memory(db, NAMESPACE, task_id)
    if prior:
        return prior  # Restarts cannot reset terminal outcomes or active leases.
    item = {"id": task_id, "key": key, "source": source, "decision": decision,
            "evidence_id": evidence_id, "contact_id": contact_id,
            "priority": max(0, min(100, float(priority))), "status": "pending",
            "attempts": 0, "created_at": time.time(), "send_authorized": False}
    remember(db, NAMESPACE, task_id, item)
    record(db, "operator-offer:" + task_id, "OPERATOR_TASK_QUEUED", task_id, item)
    return item


def claim(db, task_id, *, now=None):
    now = time.time() if now is None else now
    lock(db)
    item = dict(get_memory(db, NAMESPACE, task_id))
    if not item or item["status"] not in {"pending", "running"}:
        raise GrowthError("Task is missing or already resolved")
    if item["status"] == "running" and item.get("lease_until", 0) > now:
        raise GrowthError("Another operator holds this task", "capacity")
    if item["attempts"] >= MAX_ATTEMPTS:
        raise GrowthError("Operator task exhausted recovery attempts; inspect its evidence")
    item.update(status="running", attempts=item["attempts"] + 1,
                lease_token=uid(), lease_until=now + LEASE_SECONDS)
    remember(db, NAMESPACE, task_id, item)
    record(db, "operator-claim:" + item["lease_token"], "OPERATOR_TASK_CLAIMED", task_id,
           {"attempt": item["attempts"], "lease_until": item["lease_until"]})
    return item


def complete(db, *, task_id, lease_token, evidence_id, outcome, next_step, now=None):
    now = time.time() if now is None else now
    if outcome not in {"done", "excluded", "blocked"} or not isinstance(next_step, str) or not next_step.strip() or len(next_step) > 1500:
        raise GrowthError("Record a bounded result and the concrete next step")
    lock(db)
    item = dict(get_memory(db, NAMESPACE, task_id))
    if not item or item.get("lease_token") != lease_token:
        raise GrowthError("Operator lease no longer belongs to this invocation", "ambiguous")
    if item["status"] in {"done", "excluded", "blocked"}:
        if item.get("result_evidence_id") == evidence_id and item["status"] == outcome:
            return item
        raise GrowthError("Task already has a different audited outcome")
    if item.get("lease_until", 0) <= now:
        raise GrowthError("Operator lease expired; do not act on an old claim", "ambiguous")
    evidence = db.get(Evidence, evidence_id)
    if not evidence or evidence.recorded_at < item["created_at"]:
        raise GrowthError("Completion requires new retained outcome evidence")
    item.update(status=outcome, result_evidence_id=evidence_id, next_step=next_step,
                completed_at=now, send_authorized=False)
    remember(db, NAMESPACE, task_id, item)
    record(db, "operator-result:" + task_id, "OPERATOR_TASK_COMPLETED", task_id,
           {"status": outcome, "result_evidence_id": evidence_id, "next_step": next_step})
    return item


def export_packet(db):
    # Import the old manually maintained backlog once; retain the original memory.
    legacy = get_memory(db, "working", "operator_pipeline")
    for item in legacy.get("items", [])[:12]:
        if item.get("status") != "pending":
            continue
        evidence_id = item.get("last_checked_evidence") or legacy.get("policy_evidence_id")
        if evidence_id and db.get(Evidence, evidence_id):
            offer(db, key="legacy:" + item["id"], source=item.get("source"),
                  decision=item["decision"] + " " + item.get("next_step", ""), evidence_id=evidence_id)
    now = time.time()
    active = (Memory.namespace == NAMESPACE, Memory.value["status"].as_string().in_(["pending", "running"]))
    lease = func.coalesce(Memory.value["lease_until"].as_float(), 0)
    attempts = func.coalesce(Memory.value["attempts"].as_integer(), 0)
    # Filter before bounding retrieval: old pending tasks must never disappear
    # behind newer terminal history or high-priority tasks with live leases.
    available = [r.value for r in db.scalars(select(Memory).where(*active, lease <= now, attempts < MAX_ATTEMPTS)
        .order_by(Memory.value["priority"].as_float().desc(), Memory.id).limit(6))]
    exhausted = [r.key for r in db.scalars(select(Memory).where(*active, lease <= now, attempts >= MAX_ATTEMPTS)
        .order_by(Memory.id).limit(6))]
    claimed = db.scalar(select(func.count()).select_from(Memory).where(*active, lease > now))
    recent = list(db.scalars(select(FirstContact).where(FirstContact.sent_at > now - 86400).order_by(FirstContact.sent_at.desc()).limit(20)))
    return {"tasks": available, "claimed_tasks": claimed,
            "exhausted_tasks": exhausted[:6], "capacity": status(db),
            "recent_sends": [{"id": r.id, "channel": r.channel, "receipt": r.receipt} for r in recent],
            "next_action": "claim_next_task" if available else "resolve_exhausted_tasks" if exhausted else "wait_for_current_operator" if claimed else "replenish_pipeline",
            "support_monitor": get_memory(db, "channel", "support_mailbox"),
            "instruction": "Handle real replies/review mail first, then advance this queue. Empty inbox is not completion. No queue item authorizes a send."}


def operator_action(db, action, payload):
    if action == "operator-export":
        return export_packet(db)
    if action == "operator-enqueue":
        return offer(db, **payload)
    if action == "operator-claim":
        return claim(db, payload["task_id"])
    if action == "operator-complete":
        return complete(db, **payload)
    raise GrowthError("Unknown operator operation")
