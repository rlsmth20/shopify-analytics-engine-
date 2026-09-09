"""Receipt recovery remains executable when reservations occupy the send ceiling.

No timeout or missing receipt proves that a message was not sent. A leased
executor reviews retained action evidence before releasing an unused admission.
"""
import time

from sqlalchemy import func, select
from .models import Contact, Evidence, FirstContact, Memory
from .policy import GrowthError
from .store import get_memory, record, remember


def offer_review(db, row, *, receipt_completion=False):
    from . import operator
    previous = get_memory(db, "outreach_reconciliation", row.id)
    existing = get_memory(db, operator.NAMESPACE, previous.get("task_id", ""))
    if existing.get("status") in {"pending", "running"} and existing.get("attempts", 0) < operator.MAX_ATTEMPTS:
        if receipt_completion and not existing.get("receipt_completion"):
            remember(db, operator.NAMESPACE, existing["id"], {**existing, "receipt_completion": True})
        return
    intent = db.scalar(select(Evidence).where(Evidence.key == "first-contact-intent:" + row.id))
    contact = db.get(Contact, row.contact_id)
    if not intent or not contact:
        return
    generation = previous.get("generation", 0) + 1
    task = operator.offer(db, key=f"reconcile:{row.id}:{generation}", source=contact.source,
        contact_id=contact.id, stage="reconcile", priority=100, evidence_id=intent.id,
        decision="Review the retained execution trace for this reservation. Never submit or replay it. Return submission outcome not_sent only with affirmative evidence that no submission occurred; sent requires an actual receipt; otherwise uncertain. The supervisor applies the result and selects the next action.")
    remember(db, operator.NAMESPACE, task["id"], {**task, "reservation_id": row.id, "receipt_completion": receipt_completion})
    remember(db, "outreach_reconciliation", row.id, {"generation": generation, "task_id": task["id"], "retry_at": 0})


def enqueue_recovery(db):
    from . import operator
    now = time.time()
    runnable = db.scalar(select(Memory.id).where(Memory.namespace == operator.NAMESPACE,
        Memory.value["stage"].as_string() == "reconcile",
        Memory.value["receipt_completion"].as_boolean().is_(True),
        Memory.value["status"].as_string().in_(["pending", "running"]),
        Memory.value["attempts"].as_integer() < operator.MAX_ATTEMPTS,
        func.coalesce(Memory.value["retry_at"].as_float(), 0) <= now).limit(1))
    if runnable:
        return
    for row in db.scalars(select(FirstContact).where(
            FirstContact.status.in_(["reserved", "uncertain"]))):
        active = db.scalar(select(Memory.id).where(Memory.namespace == operator.NAMESPACE,
            Memory.value["contact_id"].as_string() == row.contact_id,
            Memory.value["status"].as_string() == "running",
            Memory.value["lease_until"].as_float() > now))
        if active:
            continue
        send_tasks = select(Memory.key).where(Memory.namespace == operator.NAMESPACE,
            Memory.value["contact_id"].as_string() == row.contact_id,
            Memory.value["stage"].as_string().in_(["send", "outreach"]))
        failed_send = db.scalar(select(Evidence.id).where(Evidence.subject.in_(send_tasks),
            Evidence.kind == "EXECUTION_FAULT", Evidence.occurred_at >= row.reserved_at).limit(1))
        if row.reserved_at >= now - 600 and not failed_send:
            continue
        previous = get_memory(db, "outreach_reconciliation", row.id)
        # A reviewed uncertain send remains held. Reinspect on new evidence,
        # not every poll; this must not become another monitoring busy loop.
        if previous.get("retry_at", 0) > now:
            continue
        existing = get_memory(db, operator.NAMESPACE, previous.get("task_id", ""))
        if existing.get("status") in {"pending", "running"} and existing.get("attempts", 0) < operator.MAX_ATTEMPTS:
            continue
        if existing.get("attempts", 0) >= operator.MAX_ATTEMPTS and not previous.get("retry_at"):
            remember(db, "outreach_reconciliation", row.id, {**previous, "retry_at": now + 3600})
            continue
        offer_review(db, row, receipt_completion=bool(failed_send))
        # One owned review at a time; do not hold the shared send lock while
        # materializing the entire historical backlog over a remote connection.
        return


def packet(db, task):
    row = db.get(FirstContact, task["reservation_id"])
    if not row:
        raise GrowthError("Reservation already reconciled")
    task_ids = [r.key for r in db.scalars(select(Memory).where(Memory.namespace == "operator_task",
        Memory.value["contact_id"].as_string() == row.contact_id,
        Memory.value["stage"].as_string().in_(["send", "outreach"])))]
    events = list(db.scalars(select(Evidence).where(Evidence.subject.in_(task_ids),
        Evidence.kind.in_(["ACQUISITION_STAGE_RESULT", "EXECUTION_FAULT"]),
        Evidence.occurred_at >= row.reserved_at).order_by(Evidence.id).limit(16)))
    return {"reservation_id": row.id, "status": row.status, "reserved_at": row.reserved_at,
        "channel": row.channel, "events": [{"id": e.id, "key": e.key, "data": e.data} for e in events],
        "execution_logs": [".growth-deploy/executor/" + e.key.split(":")[-1] + ".jsonl"
                           for e in events if e.key.startswith(("browser-stage:", "executor-failure:"))]}


def apply_result(db, task, result, stage_event):
    from .outbound import complete, reconcile_not_sent
    submission = result.get("submission")
    if not submission:
        if task.get("stage") == "reconcile":
            raise GrowthError("Reconciliation requires an explicit submission outcome")
        if task.get("stage") in {"send", "outreach"}:
            prior = db.scalar(select(FirstContact).where(FirstContact.contact_id == task.get("contact_id")))
            if (prior and prior.status != "sent") or (result.get("outcome") == "done" and not prior):
                raise GrowthError("Return submission with the reservation ID and verified outcome; prose is not a persisted receipt")
        return
    row = db.get(FirstContact, submission.get("reservation_id"))
    if (not row or row.contact_id != task.get("contact_id") or
            (task.get("stage") == "reconcile" and row.id != task.get("reservation_id"))):
        raise GrowthError("Submission outcome does not belong to this task")
    outcome = submission.get("outcome")
    reason = submission.get("reason")
    proofs = submission.get("evidence_ids", [])
    if not reason or outcome not in {"sent", "not_sent", "uncertain"}:
        raise GrowthError("Explicit submission observation required")
    if task.get("stage") == "reconcile" and outcome == "not_sent":
        allowed = {e["id"] for e in packet(db, task)["events"]}
        if not proofs or not set(proofs).issubset(allowed):
            raise GrowthError("No-send recovery requires IDs from reconciliation.events: " + str(sorted(allowed)))
    reservation_id = row.id
    if outcome == "not_sent":
        if row.status != "reserved":
            raise GrowthError("Uncertain or confirmed external submissions cannot be released by a no-click report")
        intent = db.scalar(select(Evidence).where(Evidence.key == "first-contact-intent:" + row.id))
        proof = record(db, "no-send:" + task["lease_token"], "OUTREACH_NOT_SENT_VERIFIED", row.id,
            {"no_external_effect": True, "reason": reason, "evidence_ids": proofs,
             "stage_evidence_id": stage_event.id, "task_id": task["id"], "lease_token": task["lease_token"]},
            source="authenticated_browser_executor")
        reconcile_not_sent(db, row.id, proof.id)
        from . import operator
        # Terminalize obsolete send attempts before creating one fresh successor.
        # It must obtain a new admission; the expired reservation stays invalid.
        for old in db.scalars(select(Memory).where(Memory.namespace == operator.NAMESPACE,
                Memory.value["contact_id"].as_string() == task["contact_id"],
                Memory.value["stage"].as_string().in_(["send", "outreach"]))):
            if old.key != task["id"]:
                remember(db, operator.NAMESPACE, old.key, {**old.value, "status": "excluded",
                    "result_evidence_id": proof.id, "completed_at": time.time(),
                    "next_step": "Verified unused admission released; successor prepares a new admission"})
        contact = db.get(Contact, task["contact_id"])
        # Recovered historical admissions get one fresh preparation. A newly
        # failed send releases its slot but must not regenerate itself forever.
        if intent and contact and task.get("stage") == "reconcile":
            operator.offer(db, key="after-release:" + reservation_id, source=contact.source,
                contact_id=contact.id, stage="prepare", priority=90, evidence_id=intent.id,
                decision="Prior action was VERIFIED NOT SENT and its unused reservation was released. Reuse the retained verified merchant facts and approved exact copy/cohort in source evidence. Prepare a fresh send task under standing owner authorization, with a fresh admission at send time. Never reuse the old reservation ID. Preserve current eligibility, suppression and channel checks.")
    else:
        complete(db, row.id, outcome=outcome, receipt=submission.get("receipt") if outcome == "sent" else {"observation": reason})
    previous = get_memory(db, "outreach_reconciliation", reservation_id)
    remember(db, "outreach_reconciliation", reservation_id, {**previous, "outcome": outcome,
        "evidence_id": stage_event.id, "checked_at": time.time(),
        "retry_at": time.time() + 86400 if outcome == "uncertain" else 0})
