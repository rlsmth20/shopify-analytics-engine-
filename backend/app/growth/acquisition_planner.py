"""Queue exhaustion is a planning event, not mission completion.

Deterministic admission/ranking surrounds bounded hypothesis synthesis on the
existing Codex subscription. No new service, scheduler, model API, or send path.
"""
import json
import re
import time
from urllib.parse import parse_qs, unquote, urlparse

from sqlalchemy import func, or_, select
from .models import Evidence, Experiment, Memory
from .policy import GrowthError
from .store import digest, get_memory, record, remember

CONTEXT_LIMIT = 12000
HYPOTHESES = "acquisition_hypothesis"
SEARCHES = "acquisition_search"


def mission(db):
    identity = get_memory(db, "strategic", "identity")
    started = identity.get("started_at")
    if started is None:
        return {"target": 10, "qualified": None, "complete": False, "missing_identity": True}
    first = select(Evidence.subject).where(Evidence.kind.in_(
        ["SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED"]),
        Evidence.data["verified"].as_boolean().is_(True)).group_by(Evidence.subject).having(
        func.min(Evidence.occurred_at) >= started).subquery()
    count = db.scalar(select(func.count()).select_from(first)) or 0
    return {"target": 10, "qualified": count, "complete": count >= 10,
            "started_at": started, "objective": identity.get("mission")}


def canonical(value):
    value = unquote(value).lower()
    value = re.sub(r"(?:after|before|order|sort|t):\S+|\b\d{4}-\d{2}-\d{2}\b", " ", value)
    for pattern, replacement in [(r"overstock|over.order(?:ed|ing)?|excess.inventory", " excessstock "),
                                  (r"dead.stock|slow.moving", " slowstock "),
                                  (r"stock.outs?|out.of.stock", " stockout "),
                                  (r"reordering|replenishment|reorder.point", " reorder "),
                                  (r"forecasting", " forecast ")]:
        value = re.sub(pattern, replacement, value)
    return set(re.findall(r"[a-z]{3,}", value)) - {"https", "www", "com", "the", "and", "for", "our", "with", "latest", "new"}


def similar(a, b):
    a, b = canonical(a), canonical(b)
    return bool(a and b) and len(a & b) / len(a | b) >= .72


def queries(sources):
    result = []
    for source in sources:
        for url in re.findall(r"https://[^\s]+", source):
            parsed = urlparse(url)
            for q in parse_qs(parsed.query).get("q", []):
                result.append({"source": parsed.hostname, "query": q})
    return result


def retain_result(db, task, result, event, now=None):
    """Idempotent evidence-backed metrics, inherited through qualification/send."""
    now = time.time() if now is None else now
    if task.get("stage") not in {"discover", "qualify", "prepare", "send", "outreach"}:
        return
    if get_memory(db, SEARCHES, task["id"]):
        return
    reported = result.get("search_result") or {}
    qualified = sum(s.get("stage") == "prepare" for s in result.get("successors", []))
    value = {"hypothesis_id": task.get("hypothesis_id"), "task_id": task["id"],
        "stage": task.get("stage"), "hypothesis": task.get("decision"),
        "source": task.get("source"), "queries": queries(result.get("sources", [])),
        "result_count": reported.get("result_count"), "qualified_count": qualified,
        "reported_qualified_count": reported.get("qualified_count"),
        "rejection_reasons": reported.get("rejection_reasons") or [],
        "qualification_policy": get_memory(db, "strategic", "qualification_policy").get("version", "legacy"),
        "cost": {"estimated_usd": None, "tokens": None, "basis": "existing Codex subscription; allocation unknown"},
        "date": now, "evidence_id": event.id, "outcome": result.get("outcome"),
        "value": "qualified_successor" if qualified else "candidate_successor" if result.get("successors") else "no_successor",
        "observation": result.get("observation", "")[:900]}
    remember(db, SEARCHES, task["id"], value)
    record(db, "search-outcome:" + task["id"], "ACQUISITION_SEARCH_OUTCOME", task["id"], value)
    hid = task.get("hypothesis_id")
    if hid:
        h = get_memory(db, HYPOTHESES, hid)
        if h:
            h = {**h, "qualified_count": h.get("qualified_count", 0) + qualified,
                 "observations": h.get("observations", 0) + 1,
                 "evidence_ids": (h.get("evidence_ids", []) + [event.id])[-20:]}
            if task.get("stage") == "discover":
                h["status"] = "explored" if result.get("successors") else "retired"
            if result.get("outcome") == "excluded":
                h["rejections"] = h.get("rejections", 0) + 1
            remember(db, HYPOTHESES, hid, h)
            remember(db, "beliefs", "acquisition:" + hid, {"epistemic": "BELIEF",
                "statement": h["hypothesis"], "sample_size": h["observations"],
                "confidence": min(.7, .15 + .05 * h["observations"]),
                "supporting_evidence": h["evidence_ids"] if h["qualified_count"] else [],
                "contradictory_evidence": h["evidence_ids"] if not h["qualified_count"] else [],
                "qualified_successors": h["qualified_count"],
                "interpretation": "Qualification evidence only; no inferred customer conversion.", "last_updated": now})


def history(db):
    # Legacy import stops when the market-discovery policy is activated. Existing
    # retained evidence remains available; no retrospective prospect processing.
    for row in ([] if get_memory(db, "strategic", "qualification_policy") else db.scalars(select(Memory).where(Memory.namespace == "operator_task",
            Memory.value["status"].as_string().in_(["done", "excluded"]))
            .order_by(Memory.id.desc()).limit(200))):
        task = row.value
        if task.get("stage") not in {"discover", "qualify"} or get_memory(db, SEARCHES, row.key):
            continue
        event = db.get(Evidence, task.get("result_evidence_id"))
        if event:
            retain_result(db, task, event.data, event, event.occurred_at)
    return [r.value for r in db.scalars(select(Memory).where(Memory.namespace == SEARCHES))]


def context(db, search_history):
    from .funnel import funnel_counts, bottleneck
    memories = {}
    for namespace in ("strategic", "beliefs", "customer", "channel", "learning"):
        memories[namespace] = [{"key": r.key, "value": json.dumps(r.value, default=str)[:1400]}
            for r in db.scalars(select(Memory).where(Memory.namespace == namespace)
                .order_by(Memory.updated_at.desc()).limit(5))]
    experiments = [{"id": e.id, "status": e.status, "specification": e.specification,
                   "result": e.result} for e in db.scalars(select(Experiment)
                   .order_by(Experiment.started_at.desc()).limit(5))]
    packet = {"mission": mission(db), "memory": memories,
        "funnel": funnel_counts(db), "bottleneck": bottleneck(db),
        "experiments": experiments,
        "search_history": [{k: h.get(k) for k in ("task_id", "hypothesis", "queries", "source", "result_count",
            "qualified_count", "rejection_reasons", "date", "evidence_id", "value")}
            for h in sorted(search_history, key=lambda h: h["date"], reverse=True)[:24]]}
    # Preserve valid JSON, trimming oldest history and long optional context.
    while len(json.dumps(packet, default=str)) > CONTEXT_LIMIT and packet["search_history"]:
        packet["search_history"].pop()
    while len(json.dumps(packet, default=str)) > CONTEXT_LIMIT and packet["experiments"]:
        packet["experiments"].pop()
    while len(json.dumps(packet, default=str)) > CONTEXT_LIMIT:
        largest = max(memories, key=lambda n: len(json.dumps(memories[n])))
        if not memories[largest]:
            break
        memories[largest].pop()
    return packet


def score(proposal, search_history):
    relevant = [h for h in search_history if proposal["channel"].lower() in
                str(h.get("source", "")).lower() or any(proposal["channel"].lower() in
                str(q.get("source", "")).lower() for q in h.get("queries", []))]
    qualified = sum(h.get("qualified_count", 0) for h in relevant)
    misses = sum(h.get("value") == "no_successor" for h in relevant)
    vendors = sum("vendor" in str(h.get("rejection_reasons", [])).lower() for h in relevant)
    return round((proposal["expected_value"] * proposal["confidence"] + 1 / (1 + len(relevant)))
                 * (1 + qualified) / (1 + .3 * misses + .4 * vendors), 4)


def admit_hypotheses(db, task, result, event):
    """Model proposes; code rejects duplicate searches and bounds branches."""
    search_history = history(db)
    proposals = result.get("hypotheses") or []
    if len(proposals) > 2 or result.get("successors"):
        raise GrowthError("Planning must propose at most two hypotheses, not enqueue arbitrary successors")
    known = [r.value for r in db.scalars(select(Memory).where(Memory.namespace == HYPOTHESES))]
    admitted, rejected = [], []
    for p in proposals:
        required = ("hypothesis", "channel", "problem", "segment", "query", "decision", "rationale")
        if any(not isinstance(p.get(k), str) or not p[k].strip() or len(p[k]) > 1400 for k in required):
            raise GrowthError("Hypothesis text exceeds 1400 characters or lacks a required field; decision must fit 900 characters")
        if p.get("source") and (urlparse(p["source"]).scheme != "https" or not urlparse(p["source"]).hostname):
            raise GrowthError("Hypothesis source must be HTTPS or null")
        if not 0 <= p.get("expected_value", -1) <= 10 or not 0 <= p.get("confidence", -1) <= 1:
            raise GrowthError("Invalid hypothesis estimate")
        signature = p["channel"] + " " + p["query"]
        prior = [h["channel"] + " " + h["query"] for h in known]
        prior += [q["source"] + " " + q["query"] for h in search_history for q in h.get("queries", [])]
        if any(similar(signature, s) for s in prior):
            rejected.append({"query": p["query"], "reason": "semantically_duplicate_search"})
            continue
        hid = digest(sorted(canonical(signature)))
        value = {**p, "id": hid, "status": "candidate", "score": score(p, search_history),
                 "created_at": time.time(), "evidence_ids": [event.id], "observations": 0, "qualified_count": 0}
        remember(db, HYPOTHESES, hid, value)
        known.append(value)
        admitted.append(hid)
    if not admitted:
        idle = result.get("idle") or {}
        evidence = idle.get("attempted_evidence_ids", [])
        valid_idle = (not proposals and result.get("stop_reason") == "TRUE_IDLE" and
            isinstance(idle.get("external_condition"), str) and len(idle["external_condition"]) >= 20 and
            len(set(evidence)) >= 3 and all(db.get(Evidence, i) for i in evidence))
        remember(db, "working", "acquisition_planner", {"status": "TRUE_IDLE" if valid_idle else "planning_retry",
            "explanation": result.get("observation"), "external_condition": idle.get("external_condition"),
            "attempted_evidence_ids": evidence, "last_plan_evidence": event.id,
            "retry_at": time.time() + (21600 if valid_idle else 900)})
    else:
        remember(db, "working", "acquisition_planner", {"status": "hypotheses_ready", "last_plan_evidence": event.id})
    record(db, "hypothesis-admission:" + task["lease_token"], "ACQUISITION_HYPOTHESES", task["id"],
           {"admitted": admitted, "rejected": rejected, "source_evidence": event.id})
    return admitted


def replenish(db, capacity, now=None):
    """Called under existing outbound lock by the persistent supervisor only."""
    from .operator import offer
    now = time.time() if now is None else now
    mission_state = mission(db)
    if mission_state["complete"] or mission_state.get("missing_identity") or capacity["remaining"] == 0:
        return None
    if get_memory(db, "working", "control").get("paused") or get_memory(db, "working", "acquisition_hold") or get_memory(db, "working", "browser_safety_check").get("requires_attention"):
        return None
    # Receipt reviews protect their contact, not unrelated acquisition capacity.
    active = db.scalar(select(Memory.id).where(Memory.namespace == "operator_task",
        Memory.value["status"].as_string().in_(["pending", "running"]),
        or_(func.coalesce(Memory.value["defer_reason"].as_string(), "") != "EMAIL_DAILY_CAP_REACHED",
            func.coalesce(Memory.value["retry_at"].as_float(), 0) <= now),
        Memory.value["stage"].as_string().not_in(["monitor", "reconcile"])).limit(1))
    if active:
        return None
    blocked = db.scalar(select(Memory.id).where(Memory.namespace == "operator_task",
        Memory.value["status"].as_string() == "blocked",
        Memory.value["stage"].as_string().not_in(["send", "outreach", "reconcile"]),
        Memory.value["result_evidence_id"].as_integer().is_(None),
        func.coalesce(Memory.value["error"].as_string(), "") != "RESEARCH_BUDGET_EXHAUSTED",
        Memory.value["attempts"].as_integer() >= 3).limit(1))
    if blocked:
        return None
    state = get_memory(db, "working", "acquisition_planner")
    if state.get("status") == "exploration_budget_wait":
        # Owner removed aggregate research-run quotas. Migrate an existing wait
        # without discarding history, resetting task retries, or bypassing holds.
        record(db, "research-wait-retired:" + digest(state), "ACQUISITION_RESEARCH_WAIT_RETIRED",
               "acquisition", {"prior_state": state, "reason": "Owner removed daily research-run ceiling"})
        state = {"status": "ready", "retry_at": 0}
        remember(db, "working", "acquisition_planner", state)
    if state.get("retry_at", 0) > now:
        return None
    search_history = history(db)
    candidates = [r.value for r in db.scalars(select(Memory).where(Memory.namespace == HYPOTHESES,
                   Memory.value["status"].as_string() == "candidate"))]
    trigger = record(db, "planner-empty:" + str(db.scalar(select(func.max(Evidence.id))) or 0),
        "ACQUISITION_QUEUE_EMPTY", "acquisition", {"depth": 0, "remaining_capacity": capacity["remaining"], "mission": mission_state}, occurred_at=now)
    if candidates:
        chosen = max(candidates, key=lambda p: score(p, search_history))
        event = record(db, "hypothesis-selected:" + chosen["id"], "ACQUISITION_HYPOTHESIS_SELECTED", chosen["id"],
            {"hypothesis": chosen, "score": score(chosen, search_history), "trigger_evidence": trigger.id})
        task = offer(db, key="hypothesis:" + chosen["id"], source=chosen.get("source"),
                     decision=("Test hypothesis: " + chosen["hypothesis"] + ". Query: " + chosen["query"] + ". " + chosen["decision"])[:1500],
                     evidence_id=event.id, stage="discover", priority=60)
        task = {**task, "hypothesis_id": chosen["id"]}
        remember(db, "operator_task", task["id"], task)
        remember(db, HYPOTHESES, chosen["id"], {**chosen, "status": "running", "task_id": task["id"]})
        remember(db, "working", "acquisition_planner", {"status": "executing_hypothesis", "task_id": task["id"], "selected_evidence": event.id})
        return task
    event = record(db, "planner-request:" + str(trigger.id), "ACQUISITION_PLANNER_QUEUED", "acquisition",
        {"trigger_evidence": trigger.id, "mission": mission_state, "context": context(db, search_history),
         "cost": {"estimated_usd": None, "model": "existing Codex subscription", "paid_api": False}})
    task = offer(db, key="autonomous-plan:" + str(event.id), source=None,
        decision="Select the highest-value unexamined acquisition hypothesis using retained outcomes. Propose at most two distinct bounded discovery decisions. No web research during planning. No sends. Explain expected acquisition/information value, evidence and rejected alternatives. Empty queue is not completion.",
        evidence_id=event.id, stage="plan", priority=55)
    remember(db, "working", "acquisition_planner", {"status": "planning", "task_id": task["id"], "trigger_evidence": trigger.id})
    return task
