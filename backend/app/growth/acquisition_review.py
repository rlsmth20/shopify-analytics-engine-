"""Bounded outcome checkpoints. Activity supplies a sample; it never proves demand.

Called under the executor's existing transaction/lock. No network, model call,
queue insertion, send, limit change, or whole-agent pause occurs here.
"""
import time

from .store import digest, get_memory, record, remember

CACHE_SECONDS = 300
KEY = "acquisition_outcome_review"
RESULT_FIELDS = ("substantive_responses", "positive_responses", "paid", "shopify_connected")


def _count(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _band(n):
    return (int(n) // 100) * 100 if n >= 100 else 50 if n >= 50 else 25 if n >= 25 else 0


def assess(context, previous=None):
    """Pure decision step; stable cohorts and missing observations stay distinct."""
    previous = previous or {}
    prior = previous.get("cohort_state", {})
    state, changes, decisions = {}, [], []
    for cohort in context.get("cohorts", []):
        identity = str(cohort["id"])
        contacts = _count(cohort.get("confirmed_contacts")) or 0
        mature = _count(cohort.get("mature_contacts")) or 0
        results = {k: _count(cohort.get(k)) for k in RESULT_FIELDS}
        # Low observed response is evidence against this approach, never proof
        # of absent demand. Unknown response coverage is not observed zero.
        sparse = results["substantive_responses"]
        downstream = any((results[k] or 0) > 0 for k in ("paid", "shopify_connected", "positive_responses"))
        response_observed = cohort.get("response_observation_available") is True
        negative = mature >= 75 and response_observed and sparse is not None and sparse <= 1 and not downstream
        bounced = _count(cohort.get("bounced")) or 0
        optouts = _count(cohort.get("unsubscribed")) or 0
        # Diagnostic trigger, not a claim of statistical significance or an
        # inferred provider prohibition. Other healthy channels keep working.
        delivery_signal = contacts > 0 and (bounced >= 3 and bounced / contacts >= .2
                                           or optouts >= 3 and optouts / contacts >= .2)
        old = prior.get(identity, {})
        current = {"band": _band(contacts), "results": results,
                   "negative_signal": negative, "delivery_signal": delivery_signal}
        state[identity] = current
        meaningful = any(value is not None and value != old.get("results", {}).get(k)
                         and (value > 0 or old.get("results", {}).get(k) is not None)
                         for k, value in results.items())
        crossed = current["band"] > old.get("band", 0)
        new_negative = negative and not old.get("negative_signal", False)
        new_delivery_signal = delivery_signal and not old.get("delivery_signal", False)
        if meaningful or crossed or new_negative or new_delivery_signal:
            changes.append({"cohort_id": identity, "checkpoint": current["band"],
                            "new_outcome": meaningful, "new_negative_signal": new_negative,
                            "new_delivery_signal": new_delivery_signal})
        if delivery_signal:
            action = "INVESTIGATE_AFFECTED_COHORT_DELIVERY"
            next_action = "Investigate observed bounces or opt-outs in this cohort before expanding it; continue useful work on unaffected channels and existing customer conversations."
            claim = "Repeated observed bounces or opt-outs warrant an early cohort-specific deliverability/relevance review."
            confidence = "low"
        elif negative:
            action = "CHANGE_CURRENT_APPROACH"
            next_action = ("Check delivery and reply capture, then test a materially different offer, message, "
                           "target or legitimate channel in a new attributable cohort before extending this "
                           "approach by hundreds more contacts. Preserve existing conversations and outcomes.")
            claim = "This mature cohort has almost no recorded substantive response; the current acquisition approach needs revision."
            confidence = "moderate"
        elif (results["paid"] or 0) > 0:
            action = "EXPLORE_CUSTOMER_PATTERN"
            next_action = "Prioritize the paying merchant, verify retention/value, and test the same customer/problem pattern in a bounded new cohort."
            claim = "This cohort contains observed payment evidence; investigate repeatability rather than declaring a scalable channel."
            confidence = "low" if results["paid"] < 3 else "moderate"
        elif any((results[k] or 0) > 0 for k in RESULT_FIELDS):
            action = "ADVANCE_CONVERSATIONS"
            next_action = "Prioritize responding merchants and movement toward useful inventory analysis, Shopify connection and payment; preserve this cohort."
            claim = "This cohort has downstream merchant signals worth advancing; contacts alone do not validate demand."
            confidence = "low"
        else:
            action = "CONTINUE_CONTROLLED_LEARNING"
            next_action = "Keep meaningful variants stable while collecting responses; verify reply capture and delivery before interpreting silence."
            claim = "This cohort has insufficient downstream evidence to establish demand or reject it."
            confidence = "low"
        decisions.append({"cohort_id": identity, "experiment_id": cohort.get("experiment_id"),
                          "sample_size": contacts, "mature_sample_size": mature,
                          "results": results, "bounced": bounced, "unsubscribed": optouts,
                          "action": action, "next_action": next_action,
                          "claim": claim, "confidence": confidence,
                          "evidence_ids": cohort.get("evidence_ids", []),
                          "contradictory_evidence": cohort.get("contradictory_evidence", []),
                          "checkpoint": current["band"]})
    metrics = context.get("metrics", {})
    count = _count(metrics.get("confirmed_contacts")) or 0
    checkpoint = int(count) // 100 * 100
    checkpoint_due = checkpoint > previous.get("confirmed_checkpoint", 0)
    return {"metrics": metrics,
            "report": {k: context.get(k) for k in ("funnel", "accounting", "rates", "costs")},
            "cohort_state": state,
            "confirmed_checkpoint": checkpoint, "checkpoint_due": checkpoint_due,
            "changes": changes, "cohort_decisions": decisions,
            "review_due": checkpoint_due or bool(changes),
            "bottleneck": context.get("bottleneck", "UNKNOWN"),
            "next_decision_point": context.get("next_decision_point") or {
                "confirmed_contacts": checkpoint + 100,
                "earlier": "A meaningful customer result or strong negative delivery/response evidence"},
            "best_signal": context.get("best_signal", "UNKNOWN")}


def refresh(db, now=None):
    """Refresh cheaply at most once/5m; persist evidence only on real changes.

    Returns compact planner guidance. Caller owns commit. A runtime wake after
    restart picks up the durable timestamp/checkpoints without repeating review.
    """
    now = time.time() if now is None else now
    previous = get_memory(db, "working", KEY)
    if now < previous.get("checked_at", 0) + CACHE_SECONDS:
        return previous.get("guidance", {})
    from .outcomes import review_context
    context = review_context(db, now=now)
    result = assess(context, previous)
    ranked = sorted(result["cohort_decisions"], key=lambda d: (
        d["results"]["paid"] or 0, d["results"]["shopify_connected"] or 0,
        d["results"]["positive_responses"] or 0, d["results"]["substantive_responses"] or 0,
        d["action"] == "INVESTIGATE_AFFECTED_COHORT_DELIVERY",
        d["action"] == "CHANGE_CURRENT_APPROACH"), reverse=True)
    guidance = {"north_star": "PAYING_CUSTOMERS_AND_MRR",
                "metrics": result["metrics"], "bottleneck": result["bottleneck"],
                "next_decision_point": result["next_decision_point"],
                "best_signal": result["best_signal"],
                "decisions": [{k: d[k] for k in ("cohort_id", "experiment_id", "action", "next_action")}
                              for d in ranked
                              if d["action"] != "CONTINUE_CONTROLLED_LEARNING"][:20],
                "interpretation": "Contacts are inputs. UNKNOWN is unavailable evidence, not zero; no inferred funnel stages."}
    if result["review_due"]:
        event_data = {k: v for k, v in result.items() if k not in {"cohort_state", "review_due"}}
        event = record(db, "acquisition-outcome-review:" + digest(event_data),
                       "ACQUISITION_OUTCOME_REVIEW", "acquisition", event_data,
                       source="acquisition_review", epistemic="INFERENCE", occurred_at=now)
        changed = {c["cohort_id"] for c in result["changes"]}
        for decision in result["cohort_decisions"]:
            if decision["cohort_id"] not in changed:
                continue
            remember(db, "experiment_beliefs", "acquisition:" + decision["cohort_id"], {
                "type": "BELIEF", "claim": decision["claim"],
                "supporting_evidence": decision["evidence_ids"],
                "contradictory_evidence": decision["contradictory_evidence"],
                "evaluation_evidence_id": event.id, "sample_size": decision["sample_size"],
                "mature_sample_size": decision["mature_sample_size"],
                "source_experiments": [decision["experiment_id"]] if decision["experiment_id"] else [],
                "confidence": decision["confidence"],
                "confidence_meaning": "Cautious qualitative interpretation, not statistical certainty or a causal claim",
                "observed_results": decision["results"], "last_updated": now}, source="acquisition_review")
        guidance["review_evidence_id"] = event.id
        guidance["reviewed_at"] = now
    else:
        for key in ("review_evidence_id", "reviewed_at"):
            if key in previous.get("guidance", {}):
                guidance[key] = previous["guidance"][key]
    remember(db, "strategic", "acquisition_learning", guidance, source="acquisition_review")
    remember(db, "working", KEY, {"checked_at": now, "guidance": guidance,
        "cohort_state": result["cohort_state"], "confirmed_checkpoint": result["confirmed_checkpoint"]},
        source="acquisition_review")
    return guidance
