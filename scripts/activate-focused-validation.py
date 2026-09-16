"""Idempotent owner-policy activation. Uses configured DATABASE_URL; never sends."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import select
from app.db.session import SessionLocal
from app.growth.models import Experiment, FirstContact, Memory
from app.growth.outbound import lock
from app.growth.store import get_memory, record, remember
from app.growth.validation import KEY, LABELS, VERSION


def activate(db):
    lock(db)
    current = get_memory(db, "strategic", "focused_validation")
    if current.get("version") == VERSION:
        return {"already_configured": True, "experiment_id": current["experiment_id"]}
    now = time.time()
    experiment = db.scalar(select(Experiment).where(Experiment.key == KEY))
    if not experiment:
        experiment = Experiment(key=KEY, specification={
            "policy": VERSION, "channel": "multichannel", "primary_channels": ["email", "shopify_community"],
            "hypothesis": "Shopify merchants with physical inventory complexity will respond to reorder recommendations plus exportable purchase orders.",
            "target_customer": LABELS["icp"], "offer": LABELS["offer"], "message_positioning": LABELS["offer"],
            "cohort_labels": LABELS, "max_contacts": 50,
            "primary_metric": "substantive_responses", "north_star": "PAYING_CUSTOMERS_AND_MRR",
            "success_condition": {"substantive_responses": 3, "positive_responses": 2, "strong_activation_events": 1},
            "stop_condition": "Review at 50 confirmed contacts or earlier strong positive/negative evidence; no automatic volume expansion.",
            "response_window_days": 7, "supporting_evidence_ids": [35118], "confidence": "low",
        }, started_at=now, stop_at=now + 45 * 86400)
        db.add(experiment); db.flush()
    proof = record(db, "owner-focused-validation:2026-09-16", "ACQUISITION_POLICY_UPDATED", experiment.id,
        {"version": VERSION, "experiment_id": experiment.id, "specification": experiment.specification,
         "supersedes": "volume-first channel allocation and fragmented new cohorts", "historical_receipts_unchanged": True},
        source="owner", epistemic="FACT")
    policy = {"version": VERSION, "active": True, "experiment_id": experiment.id, "campaign": KEY,
              "primary_channels": ["email", "shopify_community"], "cohort_labels": LABELS,
              "checkpoint_contacts": 50, "targets": {"substantive_replies": 3, "positive_replies": 2, "strong_activation": 1},
              "evidence_id": proof.id, "qualification": "Cheap basic fit. Unknown optional fields are neutral.",
              "priority": "Existing interest, email, useful Shopify Community. Preserve forms for later; no form spillover."}
    remember(db, "strategic", "focused_validation", policy, source="owner")
    strategy = get_memory(db, "strategic", "strategy")
    remember(db, "strategic", "strategy", {**strategy, "icp": LABELS["icp"], "positioning": LABELS["offer"],
        "next_experiment": KEY, "next_action": "focused_validation", "evidence_ids": [proof.id, 35118]}, source="owner")
    objective = get_memory(db, "strategic", "acquisition_objective")
    remember(db, "strategic", "acquisition_objective", {**objective, "requested_date": "2026-09-16",
        "requested_first_contacts": 50, "north_star": "PAYING_CUSTOMERS_AND_MRR", "volume_is_input": True,
        "experiment_id": experiment.id, "evidence_id": proof.id}, source="owner")
    deferred = []
    for row in db.scalars(select(Memory).where(Memory.namespace == "operator_task",
            Memory.value["status"].as_string() == "pending")):
        task = row.value
        if task.get("stage") not in {"send", "outreach", "prepare", "qualify", "discover"} or task.get("lease_until", 0) > now:
            continue
        if task.get("contact_id") and db.scalar(select(FirstContact.id).where(FirstContact.contact_id == task["contact_id"])):
            continue
        if "contact_form" in json.dumps(task).lower() or "contact form" in str(task.get("decision", "")).lower():
            record(db, "focused-defer:" + row.key, "ACQUISITION_TASK_DEFERRED", row.key,
                   {"reason": "form_channel_deprioritized_for_validation", "prior_task": task, "policy_evidence_id": proof.id})
            remember(db, "operator_task", row.key, {**task, "status": "strategy_deferred", "policy_evidence_id": proof.id}, source="owner")
            deferred.append(row.key)
    # Force one inexpensive review of the newly selected experiment, not a model wake.
    review = get_memory(db, "working", "acquisition_outcome_review")
    remember(db, "working", "acquisition_outcome_review", {**review, "checked_at": 0})
    return {"experiment_id": experiment.id, "policy_evidence_id": proof.id, "deferred_unattempted_form_tasks": deferred}


if __name__ == "__main__":
    with SessionLocal() as db:
        result = activate(db)
        db.commit()
        print(json.dumps(result))
