"""One bounded executive packet/day, shared by API models and subscribed Codex."""
import json
import time

from sqlalchemy import select

from . import funnel
from .models import Evidence, Experiment, Memory, Usage, Work
from .review_calendar import completed_review, review_day
from .store import digest, enqueue, get_memory, insert_once, record, remember

REVIEW_FIELDS = {"what_happened", "learned", "changed", "failed", "strongest_signal", "biggest_uncertainty",
                 "stop", "more", "icp", "positioning", "next_action", "reason", "evidence_ids", "funnel_bottleneck", "next_experiment"}
SIGNALS = {"OPPORTUNITY", "PROSPECT_RESEARCHED", "REPLY_RECEIVED", "ACCESS_REQUESTED", "SHOPIFY_CONNECTION",
           "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED", "CANCELLATION", "EXPERIMENT_EVALUATED",
           "PRODUCT_FEEDBACK", "CONTACT_FORM_RECEIVED", "HISTORICAL_PURCHASE_INTENT", "IMPLEMENTATION_FIX"}


def export_packet(db):
    now = time.time()
    window = review_day(now)
    day = window.day
    completed = completed_review(db, window)
    if completed:
        return {"day": day, "already_reviewed": True, "evidence_id": completed.id,
                "timezone": "America/Los_Angeles", "next_due": window.next_due}
    if now < window.due:
        return {"day": day, "not_due": True, "timezone": "America/Los_Angeles", "next_due": window.due}
    previous = get_memory(db, "strategic", "executive-packet:" + window.key)
    if previous.get("schema_version") == 3:
        return previous
    outcomes = list(db.scalars(select(Evidence).where(Evidence.kind.in_(SIGNALS - {"OPPORTUNITY", "IMPLEMENTATION_FIX", "HISTORICAL_PURCHASE_INTENT"})).order_by(Evidence.id.desc()).limit(6)))
    for kind in ("IMPLEMENTATION_FIX", "HISTORICAL_PURCHASE_INTENT"):
        landmark = db.scalar(select(Evidence).where(Evidence.kind == kind).order_by(Evidence.id.desc()).limit(1))
        if landmark:
            outcomes.append(landmark)
    candidates = list(db.scalars(select(Evidence).where(Evidence.kind == "OPPORTUNITY").order_by(Evidence.id.desc()).limit(8)))
    events = outcomes + candidates
    result = {"schema_version": 3, "day": day, "timezone": "America/Los_Angeles", "mission": get_memory(db, "strategic", "identity"),
              "strategy": get_memory(db, "strategic", "strategy"), "funnel": funnel.funnel_counts(db),
              "bottleneck": funnel.bottleneck(db),
              "evidence": [{"id": e.id, "kind": e.kind, "source": e.source, "epistemic": e.epistemic, "occurred_at": e.occurred_at,
                            "data": json.dumps(e.data, ensure_ascii=False)[:900]} for e in events],
              "beliefs": [m.value for m in db.scalars(select(Memory).where(Memory.namespace == "beliefs").order_by(Memory.updated_at.desc()).limit(4))],
              "required_fields": sorted(REVIEW_FIELDS),
              "allowed_actions": ["discover", "evaluate", "product_feedback", "research_contact", "service_obligations"],
              "allowed_discovery_focus": ["merchant_pain", "stocky_migration", "cash_exposure"],
              "acquisition_hold": get_memory(db, "working", "acquisition_hold"),
              "limits": {"advertising_usd": 0, "paid_api_usd": 0, "external_research_sources": 2,
                         "postal_address_requested": False, "cold_email_through_resend": False}}
    remember(db, "strategic", "executive-packet:" + window.key, result)
    db.commit()
    return result


def import_review(db, result, *, model="codex", input_tokens=None, output_tokens=None, latency_ms=None):
    now = time.time()
    window = review_day(now)
    day = window.day
    if now < window.due:
        raise ValueError("Executive review is not due until 9 a.m. America/Los_Angeles")
    packet = get_memory(db, "strategic", "executive-packet:" + window.key)
    if not packet or result.get("day") != day or not REVIEW_FIELDS.issubset(result):
        raise ValueError("Review requires today's exported packet and all executive fields")
    prior = completed_review(db, window)
    if prior:
        return {"already_recorded": True, "evidence_id": prior.id}
    valid_ids = {e["id"] for e in packet["evidence"]}
    cited = result["evidence_ids"]
    if (not isinstance(cited, list) or not cited or not all(isinstance(x, int) and x in valid_ids for x in cited)
        or result["next_action"] not in packet["allowed_actions"] or len(json.dumps(result)) > 14000
        or not all(isinstance(result[k], str) and result[k].strip() for k in REVIEW_FIELDS - {"evidence_ids"})):
        raise ValueError("Review must cite supplied evidence and choose an available bounded action")
    if any(v is not None and (not isinstance(v, int) or v < 0) for v in (input_tokens, output_tokens, latency_ms)):
        raise ValueError("Usage measurements must be nonnegative or unknown")
    if result.get("discovery_focus", "merchant_pain") not in packet["allowed_discovery_focus"]:
        raise ValueError("Discovery must select a bounded existing channel strategy")
    event = record(db, "executive-review:" + window.key, "EXECUTIVE_REVIEW", "mission", result,
                   source="codex_executive", epistemic="INFERENCE", occurred_at=now)
    strategy = get_memory(db, "strategic", "strategy")
    remember(db, "strategic", "review", {**result, "reviewer_model": model, "evidence_id": event.id})
    remember(db, "strategic", "strategy", {**strategy, **{k: result[k] for k in ("icp", "positioning", "next_action", "biggest_uncertainty", "next_experiment")},
             "discovery_focus": result.get("discovery_focus", "merchant_pain"),
             "evidence_ids": cited, "executive_evidence_id": event.id}, source="codex_executive")
    insert_once(db, Usage, key="executive:" + window.key, category="codex_subscription", task="daily_review", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms, outcome="completed",
                estimated_usd=None, reserved_usd=0,
                result={"evidence_id": event.id, "incremental_api_spend_usd": 0, "subscription_cost_allocation": "UNKNOWN"})
    action = result["next_action"]
    if action == "evaluate":
        for experiment in db.scalars(select(Experiment).where(Experiment.status.in_(["active", "observing"])).limit(5)):
            enqueue(db, "executive-evaluate:" + day + ":" + experiment.id, "evaluate", {"experiment_id": experiment.id}, priority=70)
    if action == "product_feedback" and packet["bottleneck"]["stage"] != "insufficient_evidence":
        enqueue(db, "executive-feedback:" + day, "product_feedback", {"feedback": packet["bottleneck"]}, priority=90)
    else:
        enqueue(db, "executive-observe:" + day, "observe", priority=85)
    # Research is constrained to already observed subjects; review prose cannot supply a fetch URL.
    for evidence_id in cited[:2] if action == "research_contact" else []:
        source = db.get(Evidence, evidence_id)
        if source.kind == "OPPORTUNITY":
            enqueue(db, "executive-research:" + str(source.id), "research_contact",
                    {"evidence_id": source.id, "contact_id": source.subject}, priority=65)
    for work in db.scalars(select(Work).where(Work.kind == "daily_review", Work.status.in_(["ready", "blocked"]))):
        if work.key == "review:" + window.key:
            work.status, work.result = "done", {"evidence_id": event.id, "reviewer": "codex"}
    remember(db, "working", "executive", {"last_review": now, "next_due": window.next_due,
             "day": day, "timezone": "America/Los_Angeles", "mode": "codex", "model": model})
    remember(db, "working", "operator_daily_review", {"pacific_date": day,
             "evidence_id": event.id, "timezone": "America/Los_Angeles"})
    db.commit()
    return {"evidence_id": event.id, "next_action": action}
