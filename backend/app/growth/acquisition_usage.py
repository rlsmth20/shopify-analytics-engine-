"""Subscription usage is measurable in tokens; dollar allocation stays unknown."""
import json

from sqlalchemy import func, select
from .eligibility import POLICY
from .models import Evidence, FirstContact, Message, Usage
from .store import get_memory, insert_once


def route(stage):
    # Explicit overrides prevent the interactive owner's Astra setting leaking
    # into routine work. No automatic premium escalation or fallback.
    # Live validation showed Luna mishandling shell/browser state. Keep it for
    # isolated basic classification; use intermediate tool execution, never Astra.
    return ("gpt-5.6-luna" if stage == "qualify" else "gpt-5.6-terra", "low")


def begin(factory, task, model):
    with factory() as db:
        insert_once(db, Usage, key="acquisition-cli:" + task["lease_token"], category="model",
            model=model, task="acquisition_" + task["stage"], outcome="running", estimated_usd=None,
            result={"policy": POLICY, "task_id": task["id"], "hypothesis_id": task.get("hypothesis_id"),
                    "reasoning_effort": "low", "premium": False, "billing": "Codex subscription; allocation unknown"})
        db.commit()


def retain(factory, task, model, path, elapsed, outcome):
    usage = []
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
                if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
                    usage.append(event["usage"])
            except (ValueError, AttributeError):
                continue
    with factory() as db:
        row, _ = insert_once(db, Usage, key="acquisition-cli:" + task["lease_token"], category="model",
            model=model, task="acquisition_" + task["stage"],
            input_tokens=sum(u.get("input_tokens", 0) for u in usage) if usage else None,
            output_tokens=sum(u.get("output_tokens", 0) for u in usage) if usage else None,
            estimated_usd=None, latency_ms=int(elapsed * 1000), outcome=outcome,
            result={"policy": POLICY, "task_id": task["id"], "hypothesis_id": task.get("hypothesis_id"),
                    "reasoning_effort": "low", "billing": "Codex subscription; dollar allocation unknown",
                    "cached_input_tokens": sum(u.get("cached_input_tokens", 0) for u in usage),
                    "token_accounting": "reported completed turns; interrupted turn may be unreported",
                    "premium": False})
        row.input_tokens = sum(u.get("input_tokens", 0) for u in usage) if usage else None
        row.output_tokens = sum(u.get("output_tokens", 0) for u in usage) if usage else None
        row.latency_ms, row.outcome = int(elapsed * 1000), outcome
        row.result = {**row.result, "cached_input_tokens": sum(u.get("cached_input_tokens", 0) for u in usage),
                      "token_accounting": "reported completed turns; interrupted turn may be unreported"}
        db.commit()


def efficiency(db):
    since = get_memory(db, "strategic", "qualification_policy").get("started_at")
    if since is None:
        return {"policy": POLICY, "status": "not_started"}
    costs = list(db.scalars(select(Usage).where(Usage.key.like("acquisition-cli:%"), Usage.created_at >= since, Usage.task != "acquisition_deliverability")))
    unknown = any(c.estimated_usd is None for c in costs)
    dollars = None if unknown or not costs else sum(c.estimated_usd for c in costs)
    tokens = sum((c.input_tokens or 0) + (c.output_tokens or 0) for c in costs)
    cached = sum(c.result.get("cached_input_tokens", 0) for c in costs)
    # Every screened identity is retained, including compact rejection records.
    base = (Evidence.kind == "PROSPECT_ELIGIBILITY", Evidence.occurred_at >= since,
            Evidence.data["policy"].as_string() == POLICY)
    discovered = db.scalar(select(func.count(func.distinct(Evidence.subject))).where(*base)) or 0
    corrected = select(Evidence.data["corrects_evidence"].as_integer()).where(Evidence.kind == "PROSPECT_EXCLUDED",
        Evidence.data["corrects_evidence"].as_integer().is_not(None))
    eligible = db.scalar(select(func.count(func.distinct(Evidence.subject))).where(*base, Evidence.id.not_in(corrected),
        Evidence.data["eligible"].as_boolean().is_(True))) or 0
    sends = list(db.scalars(select(FirstContact).where(FirstContact.sent_at >= since)))
    responses = db.scalar(select(func.count(func.distinct(Message.contact_id))).where(Message.direction == "in",
        Message.created_at >= since, Message.classification.in_(
            ["SUBSTANTIVE_POSITIVE", "SUBSTANTIVE_NEUTRAL", "SUBSTANTIVE_NEGATIVE", "QUESTION"]))) or 0
    qualified = db.scalar(select(func.count(func.distinct(Evidence.subject))).where(Evidence.occurred_at >= since,
        Evidence.kind.in_(["SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED"]),
        Evidence.data["verified"].as_boolean().is_(True))) or 0
    counts = {"discovered_prospect": discovered, "eligible_prospect": eligible,
              "email_sent": sum(s.channel == "email" for s in sends), "first_contact_sent": len(sends),
              "substantive_reply": responses, "qualified_user": qualified}
    return {"policy": POLICY, "since": since, "model_spend_usd": dollars, "reported_tokens": tokens,
            "cached_input_tokens": cached, "uncached_input_tokens": sum(c.input_tokens or 0 for c in costs) - cached,
            "unknown_cost_runs": sum(c.estimated_usd is None for c in costs),
            "runs_by_model": {m: sum(c.model == m for c in costs) for m in sorted({c.model for c in costs})},
            "metrics": {k: {"count": n, "model_cost_usd": dollars / n if dollars is not None and n else None,
                            "reported_tokens": tokens / n if n else None} for k, n in counts.items()},
            "scope": "Policy-period operating ratios, not causal attribution; discovered means retained screened identity. Dollar allocation UNKNOWN."}
