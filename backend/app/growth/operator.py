"""Bounded, leased handoff from server discovery to the browser operator.

Queue state never grants permission to send. FirstContact remains the sole
shared admission gate, and external receipts remain the proof of outreach.
"""
import time
from urllib.parse import urlparse

from sqlalchemy import select, func, or_

from .models import Evidence, FirstContact, Memory, uid
from .outbound import lock, status
from .policy import GrowthError
from .store import digest, get_memory, record, remember

NAMESPACE = "operator_task"
LEASE_SECONDS = 1800
MAX_ATTEMPTS = 3


def offer(db, *, key, source, decision, evidence_id, contact_id=None, priority=50, stage=None):
    stage = stage or ("outreach" if contact_id else "discover")
    if stage not in {"plan", "discover", "qualify", "prepare", "send", "outreach", "monitor", "reply", "reconcile", "deliverability"}:
        raise GrowthError("Unknown acquisition stage")
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
            "stage": stage, "attempts": 0, "created_at": time.time(), "send_authorized": False}
    remember(db, NAMESPACE, task_id, item)
    record(db, "operator-offer:" + task_id, "OPERATOR_TASK_QUEUED", task_id, item)
    return item


def claim(db, task_id, *, now=None, executor=None):
    now = time.time() if now is None else now
    lock(db)
    item = dict(get_memory(db, NAMESPACE, task_id))
    if not item or item["status"] not in {"pending", "running"}:
        raise GrowthError("Task is missing or already resolved")
    if item["status"] == "running" and item.get("lease_until", 0) > now:
        raise GrowthError("Another operator holds this task", "capacity")
    if item.get("retry_at", 0) > now:
        raise GrowthError("Task is waiting for its durable retry", "capacity")
    if item["attempts"] >= MAX_ATTEMPTS:
        raise GrowthError("Operator task exhausted recovery attempts; inspect its evidence")
    item.update(status="running", attempts=item["attempts"] + 1,
                lease_token=uid(), lease_until=now + LEASE_SECONDS,
                executor=executor or "codex_operator", last_progress_at=now)
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
    # Retire an invalid historical handoff without spending another browser wake.
    from .identity import owned_identity, INELIGIBLE
    from .models import Contact
    for row in db.scalars(select(Memory).where(Memory.namespace == NAMESPACE,
            or_(Memory.value["status"].as_string().in_(["pending", "running"]),
                (Memory.value["stage"].as_string() == "reply") & (Memory.value["status"].as_string() == "blocked")),
            func.coalesce(Memory.value["lease_until"].as_float(), 0) <= now)):
        candidate = db.get(Contact, row.value.get("contact_id")) if row.value.get("contact_id") else None
        if row.value.get("stage") == "reply" and candidate:
            source = db.get(Evidence, row.value.get("evidence_id"))
            admission = db.scalar(select(FirstContact).where(FirstContact.contact_id == candidate.id))
            if (source and source.data.get("stop_reason") == "OUTREACH_OUTCOMES_UNRESOLVED"
                    and admission and admission.status != "sent" and source.data.get("stage") != "reply"):
                # Legacy schemas lacked a reconcile successor. Receipt work is
                # not a substantive customer reply and must use the receipt contract.
                remember(db, NAMESPACE, row.key, {**row.value, "stage": "reconcile", "status": "pending",
                    "reservation_id": admission.id, "receipt_completion": True, "retry_at": 0,
                    "prior_reply_attempts": row.value.get("attempts", 0), "attempts": 0})
        if row.value.get("stage") == "reconcile" and "prior_reply_attempts" in row.value and candidate:
            source = db.get(Evidence, row.value.get("evidence_id"))
            admission = db.scalar(select(FirstContact).where(FirstContact.contact_id == candidate.id))
            if source and source.data.get("stage") == "reply" and admission and admission.status == "sent":
                # Earlier migration confused an uncertain conversation reply with
                # its already-confirmed first contact. Restore read-only thread
                # reconciliation without touching that original send ledger.
                restored = {k: v for k, v in row.value.items() if k not in {"reservation_id", "receipt_completion"}}
                restored.update(stage="reply", attempts=restored.pop("prior_reply_attempts"))
                remember(db, NAMESPACE, row.key, restored)
                record(db, "conversation-receipt-restored:" + row.key, "CONVERSATION_RECEIPT_RESTORED",
                    candidate.id, {"task_id": row.key, "source_evidence_id": source.id,
                                   "first_contact_unchanged": admission.id})
        if row.value.get("status") == "blocked":
            continue
        if row.value.get("stage") != "reconcile" and candidate and (owned_identity(candidate.identity) or candidate.suppressed or candidate.status in INELIGIBLE):
            lock(db)
            proof = record(db, "owned-account-exclusion:" + row.key, "PROSPECT_EXCLUDED", candidate.id,
                {"reason": "OBVIOUSLY_INAPPROPRIATE_TARGET" if owned_identity(candidate.identity) else
                    candidate.qualification.get("reason") or "SUPPRESSED", "identity": candidate.identity})
            remember(db, NAMESPACE, row.key, {**row.value, "status": "excluded",
                "result_evidence_id": proof.id, "completed_at": now,
                "next_step": "Select the next independently sourced merchant"})
    active = (Memory.namespace == NAMESPACE, Memory.value["status"].as_string().in_(["pending", "running"]))
    lease = func.coalesce(Memory.value["lease_until"].as_float(), 0)
    attempts = func.coalesce(Memory.value["attempts"].as_integer(), 0)
    # Filter before bounding retrieval: old pending tasks must never disappear
    # behind newer terminal history or high-priority tasks with live leases.
    from sqlalchemy import case
    stage = Memory.value["stage"].as_string()
    capacity = status(db, now)
    available = [r.value for r in db.scalars(select(Memory).where(*active, lease <= now, attempts < MAX_ATTEMPTS,
        func.coalesce(Memory.value["retry_at"].as_float(), 0) <= now)
        .order_by(case((stage == "reply", 0),
                      ((stage == "monitor") & Memory.value["key"].as_string().startswith("community-inbox:"), 1),
                      (stage == "monitor", 1 if get_memory(db, "working", "browser_safety_check").get("requires_attention") else 4),
                      ((stage == "reconcile") & Memory.value["receipt_completion"].as_boolean().is_(True), 2),
                      (stage == "deliverability", 2),
                      (stage == "reconcile", 2 if capacity["blocker"] in {"DAILY_CAP_REACHED", "OUTREACH_UNCERTAINTY_SAFETY_HOLD"} else 4), else_=3),
                  Memory.value["priority"].as_float().desc(), Memory.id).limit(6))]
    exhausted = [r.key for r in db.scalars(select(Memory).where(*active, lease <= now, attempts >= MAX_ATTEMPTS)
        .order_by(Memory.id).limit(6))]
    claimed = db.scalar(select(func.count()).select_from(Memory).where(*active, lease > now))
    recent = list(db.scalars(select(FirstContact).where(FirstContact.sent_at > now - 86400).order_by(FirstContact.sent_at.desc()).limit(20)))
    from .models import Experiment
    experiments = [{"id": e.id, "key": e.key, "channel": e.specification.get("channel"),
                    "offer": e.specification.get("message_positioning") or e.specification.get("message"),
                    "stop_at": e.stop_at} for e in db.scalars(select(Experiment).where(
                        Experiment.status == "active", Experiment.stop_at > now).order_by(Experiment.started_at.desc()).limit(8))]
    return {"tasks": available, "claimed_tasks": claimed,
            "active_experiments": experiments,
            "exhausted_tasks": exhausted[:6], "capacity": capacity,
            "recent_sends": [{"id": r.id, "channel": r.channel, "receipt": r.receipt} for r in recent],
            "next_action": "claim_next_task" if available else "resolve_exhausted_tasks" if exhausted else "wait_for_current_operator" if claimed else "replenish_pipeline",
            "support_monitor": get_memory(db, "channel", "support_mailbox"),
            "instruction": "Handle real replies/review mail first, then advance this queue. Empty inbox is not completion. No queue item authorizes a send."}


def operator_action(db, action, payload):
    if action == "operator-monitor-start":
        task = get_memory(db, NAMESPACE, payload.get("task_id", ""))
        if (task.get("status") != "running" or task.get("lease_token") != payload.get("lease_token")
                or task.get("lease_until", 0) <= time.time()):
            raise GrowthError("A current task lease is required to begin browser observations")
        event = record(db, "browser-check-start:" + uid(), "CHANNEL_CHECK_STARTED", task["id"],
            {"lease_token": task["lease_token"]}, source="authenticated_browser_executor")
        return {"check_id": event.id, "started_at": event.occurred_at, "expires_at": event.occurred_at + 300,
                "next_action": "Read live Gmail and Reddit now, then record operator-monitor with this check_id"}
    if action == "operator-monitor":
        from urllib.parse import urlparse
        now = time.time()
        task = get_memory(db, NAMESPACE, payload.get("task_id", ""))
        observed_at = payload.get("checked_at", 0)
        if payload.get("check_id"):
            started = db.get(Evidence, payload["check_id"])
            if (not started or started.kind != "CHANNEL_CHECK_STARTED" or started.subject != payload.get("task_id")
                    or started.data.get("lease_token") != payload.get("lease_token")):
                raise GrowthError("Browser check does not belong to the current task lease")
            # Conservative freshness begins BEFORE the observations, never at
            # receipt time. A model cannot accidentally supply a guessed epoch.
            observed_at = started.occurred_at
        observations = payload.get("observations", [])
        if (task.get("status") != "running" or task.get("lease_token") != payload.get("lease_token")
            or task.get("lease_until", 0) <= now or not isinstance(observed_at, (int, float))
            or not now - 300 <= observed_at <= now + 5):
            raise GrowthError("Fresh browser observations and a current task lease are required")
        if (payload.get("mailbox") != "info@skubase.io" or not isinstance(observations, list)
            or not 2 <= len(observations) <= 5 or
            any(not isinstance(o.get("observation"), str) or not 1 <= len(o["observation"]) <= 800
                or urlparse(o.get("source", "")).scheme != "https" for o in observations)):
            raise GrowthError("Bounded actual business-mailbox and Reddit observations required")
        hosts = {urlparse(o["source"]).hostname for o in observations}
        if "mail.google.com" not in hosts or not hosts.intersection({"www.reddit.com", "reddit.com"}):
            raise GrowthError("Both dedicated Gmail and Reddit must be checked")
        from .store import digest
        attention = payload.get("requires_attention")
        if not isinstance(attention, bool):
            raise GrowthError("Explicit reply/incident attention state required")
        event = record(db, "browser-monitor:" + digest([payload["task_id"], observed_at, observations]),
            "CHANNEL_MONITOR", payload["task_id"], {"observations": observations, "mailbox": payload["mailbox"],
                "requires_attention": attention, "lease_token": payload["lease_token"], "check_id": payload.get("check_id")},
            source="authenticated_browser_executor", occurred_at=observed_at)
        remember(db, "working", "browser_safety_check", {"checked_at": observed_at,
            "evidence_id": event.id, "requires_attention": attention})
        return {"evidence_id": event.id, "checked_at": observed_at, "requires_attention": attention}
    if action == "operator-assess":
        from .eligibility import assess
        return assess(db, payload)
    if action == "operator-state":
        from .execution import state
        return state(db)
    if action == "operator-export":
        return export_packet(db)
    if action == "operator-enqueue":
        return offer(db, **payload)
    if action == "operator-claim":
        return claim(db, payload["task_id"])
    if action == "operator-complete":
        return complete(db, **payload)
    raise GrowthError("Unknown operator operation")
