"""Evidence-linked experiments; small samples change allocation cautiously."""
import math
import random
import time

from sqlalchemy import select

from .models import Contact, Evidence, Experiment, Memory, Message
from .store import digest, enqueue, get_memory, insert_once, record, remember

POSITIVE = {"SUBSTANTIVE_POSITIVE", "QUESTION", "SUBSTANTIVE_NEUTRAL"}


def ensure_experiment(db):
    active = db.scalar(select(Experiment).where(Experiment.status == "active", Experiment.key.like("health-check-%")).order_by(Experiment.started_at).limit(1))
    if active and active.specification.get("channel") != "requested_health_check":
        active.status = "inconclusive"
        active.result = {**active.result, "interpretation": "Stopped: Resend cannot carry unsolicited outreach. Preserve this cohort; requested-service fulfillment is a separate experiment."}
        record(db, "retired-channel:" + active.id, "EXPERIMENT_STOPPED", active.id, active.result)
        db.flush()
    elif active:
        evaluate(db, active.id)
        if active.status == "active":
            return active
    cycle = db.scalar(select(Experiment).where(Experiment.key.like("health-check-%")).order_by(Experiment.started_at.desc()).limit(1))
    index = int(cycle.specification.get("cycle", 0)) + 1 if cycle else 1
    allocation = get_memory(db, "strategic", "strategy").get("cash_allocation", .5)
    spec = {"cycle": index, "hypothesis": "Cash-exposure versus reorder-priority framing of a free Shopify Inventory Health Check changes qualified engagement.",
            "channel": "requested_health_check", "target_customer": "Shopify operators who explicitly requested an inventory check; ICP remains provisional",
            "message_positioning": {"cash": "cash tied up in slow-moving stock", "reorder": "what to reorder before stock runs out"},
            "action": "Fulfill each requested check with one concise setup message; never cold outreach through Resend",
            "primary_metric": "distinct qualified stores connected", "secondary_metrics": ["substantive responses", "signup", "activation", "payment"],
            "cost": {"advertising_usd": 0, "model_api_usd": "ledger", "human_minutes": None},
            "stop_condition": "14 days or 20 first contacts; stop early for complaints or downstream friction",
            "success_condition": "At least 2 connected stores; comparative winner needs >=10 mature contacts per arm and posterior superiority >=0.95",
            "observation_window_days": 7, "max_contacts": 20, "variables_changed": ["problem framing"],
            "allocation": "Initially 50/50; update only the next experiment using qualified outcome evidence", "cash_allocation": allocation}
    experiment, _ = insert_once(db, Experiment, key="health-check-" + str(index), specification=spec, stop_at=time.time() + 14 * 86400)
    record(db, f"experiment-start:{experiment.id}", "EXPERIMENT_STARTED", experiment.id, spec, epistemic="HYPOTHESIS")
    return experiment


def choose_variant(db, contact, experiment=None):
    # Allocation is fixed within each experiment. New experiments inherit learned weights.
    experiment = experiment or ensure_experiment(db)
    cash_weight = experiment.specification.get("cash_allocation", .5)
    bucket = int(digest(contact.identity)[:8], 16) / 0xFFFFFFFF
    return "cash" if bucket < cash_weight else "reorder"


def evaluate(db, experiment_id):
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        return {}
    if experiment.specification.get("channel") == "organic_search":
        return evaluate_organic(db, experiment)
    if experiment.specification.get("channel") != "requested_health_check":
        # External-channel cohorts use retained public/form receipts. Do not
        # overwrite them with an empty requested-service email evaluation.
        return experiment.result
    assigned = list(db.scalars(select(Message).where(Message.experiment_id == experiment_id, Message.direction == "out",
                            Message.reply_to_id.is_(None), Message.variant.in_(["cash", "reorder"]))))
    outgoing = [m for m in assigned if m.sent_at is not None]
    incoming = list(db.scalars(select(Message).where(Message.experiment_id == experiment_id, Message.direction == "in")))
    by_contact = {}
    for msg in incoming:
        by_contact.setdefault(msg.contact_id, []).append(msg)
    stats = {v: {"sent": 0, "mature": 0, "mature_engaged": 0, "engaged": 0, "connected": 0, "negative": 0, "censored": 0, "evidence_ids": [], "contradictions": []} for v in ("cash", "reorder")}
    connected_shops = {v: set() for v in stats}
    now = time.time()
    for message in outgoing:
        if message.variant not in stats:
            continue  # Support answers are obligations, not experimental assignments.
        s = stats[message.variant]
        s["sent"] += 1
        replies = by_contact.get(message.contact_id, [])
        engaged = any(r.classification in POSITIVE for r in replies)
        negative = any(r.classification in {"SUBSTANTIVE_NEGATIVE", "UNSUBSCRIBE"} for r in replies)
        mature = now - message.sent_at >= 7 * 86400
        s["engaged"] += int(engaged)
        s["negative"] += int(negative)
        s["mature"] += int(mature)
        s["mature_engaged"] += int(mature and engaged)
        s["censored"] += int(not mature)
        contact = db.get(Contact, message.contact_id)
        if contact and contact.shop_id:
            connected = db.scalar(select(Evidence.id).where(Evidence.subject == f"shop:{contact.shop_id}",
                                  Evidence.kind == "SHOPIFY_CONNECTION", Evidence.occurred_at >= message.sent_at))
            if connected is not None:
                connected_shops[message.variant].add(contact.shop_id)
        for event in db.scalars(select(Evidence).where(Evidence.subject == message.contact_id, Evidence.kind == "REPLY_RECEIVED")):
            if event.data.get("experiment_id") != experiment_id:
                continue
            if event.data.get("classification") in POSITIVE:
                s["evidence_ids"].append(event.id)
            elif event.data.get("classification") in {"SUBSTANTIVE_NEGATIVE", "UNSUBSCRIBE"}:
                s["contradictions"].append(event.id)
    rng = random.Random(42)
    distributions = {}
    for v, s in stats.items():
        s["connected"] = len(connected_shops[v])
        # Beta(1,1) smoothing. Report interval, denominator and contradictory replies.
        a, b = 1 + s["mature_engaged"], 1 + max(0, s["mature"] - s["mature_engaged"])
        draws = sorted(rng.betavariate(a, b) for _ in range(2000))
        distributions[v] = draws
        s["response_probability_estimate"] = round(a / (a + b), 3)
        s["credible_interval_95"] = [round(draws[50], 3), round(draws[1949], 3)]
    rng.shuffle(distributions["cash"])
    p_cash = sum(a > b for a, b in zip(distributions["cash"], distributions["reorder"])) / 2000
    qualified = len(set().union(*connected_shops.values()))
    enrollment_closed = (now >= experiment.stop_at or len(assigned) >= experiment.specification["max_contacts"]
                         or experiment.status == "observing")
    unresolved_sends = sum(m.sent_at is None and m.status in {"draft", "sending", "unknown"} for m in assigned)
    observation_pending = any(s["censored"] for s in stats.values()) or unresolved_sends > 0
    mature_enough = min(s["mature"] for s in stats.values()) >= 10
    outcome = "inconclusive"
    if qualified >= 2:
        outcome = "winning"
    elif enrollment_closed and not observation_pending and sum(s["mature"] for s in stats.values()) >= 10:
        outcome = "losing"
    winner = ("cash" if p_cash >= .95 else "reorder" if p_cash <= .05 else None) if mature_enough else None
    result = {"arms": stats, "outcome": outcome, "sample_size": len(outgoing), "qualified_stores": qualified,
              "enrollment_closed": enrollment_closed, "observation_pending": observation_pending,
              "unresolved_sends": unresolved_sends,
              "p_cash_higher_response": p_cash, "response_winner": winner,
              "interpretation": "Responses are leading signals; connected stores are the primary outcome. Silence remains censored for seven days.",
              "confidence": "low" if not mature_enough else "moderate",
              "next_action": ("Continue observing this cohort; preserve its messages and assignments" if enrollment_closed and observation_pending
                              else "Keep learning with a small qualified sample" if not winner else f"Test {winner} framing on a new cohort")}
    if experiment.result != result:
        experiment.result = result
        event = record(db, f"experiment-result:{experiment.id}:{digest(result)}", "EXPERIMENT_EVALUATED", experiment.id, result, epistemic="INFERENCE")
        for variant, s in stats.items():
            remember(db, "experiment_beliefs", experiment.id + ":" + variant, {"type": "BELIEF", "claim": f"{variant.title()} framing may attract qualified inventory conversations.",
                     "supporting_evidence": s["evidence_ids"], "contradictory_evidence": s["contradictions"],
                     "confidence": s["response_probability_estimate"], "confidence_meaning": "posterior response rate, not certainty in causal superiority",
                     "credible_interval_95": s["credible_interval_95"], "sample_size": s["mature"],
                     "source_experiments": [experiment.id], "last_updated": now, "evaluation_evidence_id": event.id})
            cohorts = [m.value for m in db.scalars(select(Memory).where(Memory.namespace == "experiment_beliefs", Memory.key.like("%:" + variant)))]
            support = sorted({i for c in cohorts for i in c["supporting_evidence"]})
            against = sorted({i for c in cohorts for i in c["contradictory_evidence"]})
            remember(db, "beliefs", "response:" + variant, {"type": "BELIEF",
                "claim": f"{variant.title()} framing may help requested inventory checks progress; separate cohorts remain available.",
                "supporting_evidence": support, "contradictory_evidence": against,
                "confidence": s["response_probability_estimate"], "credible_interval_95": s["credible_interval_95"],
                "confidence_meaning": "Latest cohort posterior response rate; not pooled causal certainty",
                "sample_size": sum(c["sample_size"] for c in cohorts), "latest_cohort_sample_size": s["mature"],
                "source_experiments": sorted({i for c in cohorts for i in c["source_experiments"]}),
                "last_updated": now, "evaluation_evidence_id": event.id})
        # A leading signal can cautiously influence *future* behavior without claiming victory.
        strategy = get_memory(db, "strategic", "strategy")
        if winner:
            favored = winner
            strategy = {**strategy, "next_experiment_framing": favored, "learning_evidence_id": event.id,
                        "cash_allocation": .6 if favored == "cash" else .4,
                        "positioning_confidence": "mature cohort evidence; responses alone do not establish paid conversion"}
            remember(db, "strategic", "strategy", strategy)
        # Preserve empirical characteristics, with explicit unknown conversions.
        remember(db, "skill_performance", "requested_service:" + experiment.id,
                 {"experiment_id": experiment.id, "skill": "requested_service", "sent": len(outgoing),
                  "engaged": sum(s["engaged"] for s in stats.values()), "connected": qualified,
                  "failures": sum(s["negative"] for s in stats.values()), "evaluation_evidence_id": event.id,
                  "interpretation": "Observed cohort outcomes; do not infer that the skill caused conversion."})
        for message in outgoing:
            contact = db.get(Contact, message.contact_id)
            if contact:
                observed = {e.kind for e in db.scalars(select(Evidence).where(Evidence.subject == f"shop:{contact.shop_id}"))} if contact.shop_id else set()
                remember(db, "customer", contact.id, {"characteristics": contact.characteristics,
                    "response": any(r.classification in POSITIVE for r in by_contact.get(contact.id, [])),
                    "shop_id": contact.shop_id, "signup": "SIGNUP" in observed, "connection": "SHOPIFY_CONNECTION" in observed,
                    "activation": "INVENTORY_ANALYSIS_VIEWED" in observed,
                    "payment": True if "SUBSCRIPTION_PURCHASED" in observed else None,
                    "retention": False if "CANCELLATION" in observed else None, "experiment_id": experiment.id})
    if enrollment_closed:
        # Ending enrollment is not evidence that the final send has had time to
        # produce a response. Keep it in periodic evaluation across restarts.
        experiment.status = "observing" if observation_pending else outcome
    return result


def evaluate_organic(db, experiment):
    events = list(db.scalars(select(Evidence).where(Evidence.occurred_at >= experiment.started_at,
        Evidence.kind.in_(["ACCESS_REQUESTED", "CALCULATOR_USED", "SHOPIFY_CONNECTION"]))))
    requests = {e.subject for e in events if e.kind == "ACCESS_REQUESTED" and e.data.get("utm_campaign") == experiment.key}
    visitors = {e.subject for e in events if e.kind == "CALCULATOR_USED" and
                (e.data.get("landing_page") == "/tools/reorder-point-calculator" or
                 e.data.get("attribution", {}).get("utm_campaign") == experiment.key)}
    shops = {m.key for m in db.scalars(select(Memory).where(Memory.namespace == "attribution"))
             if m.value.get("utm_campaign") == experiment.key}
    shops.update(f"shop:{c.shop_id}" for c in db.scalars(select(Contact).where(Contact.id.in_(requests))) if c.shop_id)
    connected = {e.subject for e in events if e.kind == "SHOPIFY_CONNECTION" and e.subject in shops}
    outcome = "winning" if connected else "inconclusive"
    result = {"qualified_stores": len(connected), "health_check_requests": len(requests), "calculator_users": len(visitors),
              "outcome": outcome, "confidence": "low", "sample_size": len(visitors),
              "interpretation": "Attributed connections are the outcome; tool uses are diagnostic only. Missing attribution is not inferred.",
              "next_action": "Review request-to-connection friction" if requests else "Observe qualified demand before expanding content"}
    if experiment.result != result:
        experiment.result = result
        record(db, f"organic-result:{experiment.id}:{digest(result)}", "EXPERIMENT_EVALUATED", experiment.id, result, epistemic="INFERENCE")
    if time.time() >= experiment.stop_at:
        experiment.status = outcome
    return result
