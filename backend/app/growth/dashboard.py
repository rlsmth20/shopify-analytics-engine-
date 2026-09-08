import time
import os
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import load_only

from .funnel import STAGES, bottleneck
from .inbox_health import projection as inbox_transport
from .models import Contact, Evidence, Experiment, FirstContact, Memory, Message, Usage, Work
from .policy import Policy
from .store import digest, get_memory
from .acquisition_usage import efficiency

SUBSTANTIVE = {"SUBSTANTIVE_POSITIVE", "SUBSTANTIVE_NEUTRAL", "SUBSTANTIVE_NEGATIVE", "QUESTION"}
CONVERSIONS = ("SIGNUP", "SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED")


def measured_funnel(db, since=0):
    """Client visits are observations; customer stages need backend verification."""
    counts = dict(db.execute(select(Evidence.kind, func.count(func.distinct(Evidence.subject))).where(
        Evidence.kind.in_(STAGES), Evidence.occurred_at >= since,
        or_(Evidence.kind == "VISITOR", Evidence.data["verified"].as_boolean().is_(True)))
        .group_by(Evidence.kind)).all())
    return {stage: counts.get(stage, 0) for stage in STAGES}


def outreach_projection(db, now):
    """Read-only, bounded cohort evidence; an accepted form is not delivered mail.

    Outcomes are observations after first contact, not causal attribution. Keep
    absent identity linkage explicit rather than counting it as failed conversion.
    """
    limit = 500
    rows = list(db.scalars(select(FirstContact).order_by(FirstContact.reserved_at.desc(), FirstContact.id).limit(limit + 1)))
    truncated = len(rows) > limit
    rows = rows[:limit]
    contact_ids = [r.contact_id for r in rows]
    contacts = {c.id: c for c in db.scalars(select(Contact).where(Contact.id.in_(contact_ids)))} if contact_ids else {}
    messages = defaultdict(list)
    for message in db.scalars(select(Message).where(Message.contact_id.in_(contact_ids)).options(load_only(
        Message.id, Message.contact_id, Message.experiment_id, Message.direction, Message.status,
        Message.provider_id, Message.reply_to_id, Message.classification, Message.created_at, Message.sent_at))):
        messages[message.contact_id].append(message)
    provider_ids = {m.provider_id for items in messages.values() for m in items if m.provider_id}
    provider_events = defaultdict(set)
    if provider_ids:
        for event in db.scalars(select(Evidence).where(Evidence.kind == "PROVIDER_EVENT",
            Evidence.source == "resend_signed_webhook", Evidence.data["data"]["email_id"].as_string().in_(provider_ids))):
            provider_events[event.data["data"]["email_id"]].add(event.data.get("type"))
    subjects = contact_ids + [f"shop:{c.shop_id}" for c in contacts.values() if c.shop_id is not None]
    evidence = defaultdict(list)
    if subjects:
        for event in db.scalars(select(Evidence).where(Evidence.subject.in_(subjects),
            Evidence.kind.in_((*CONVERSIONS, "REPLY_RECEIVED", "ACCESS_REQUESTED")))):
            evidence[event.subject].append(event)
    groups = {}
    for row in rows:
        snapshot = row.cohort or {}
        cohort_key = digest([row.experiment_id, row.channel, snapshot.get("icp"), snapshot.get("offer"), snapshot.get("message_version"), snapshot.get("qualification_policy")])
        group = groups.setdefault(cohort_key, {"id": cohort_key, "experiment_id": row.experiment_id,
            "channel": row.channel, "icp": snapshot.get("icp") if isinstance(snapshot.get("icp"), str) else None,
            "offer": snapshot.get("offer"), "message_version": snapshot.get("message_version"),
            "qualification_policy": snapshot.get("qualification_policy", "legacy"),
            "sent": 0, "pending": 0, "mature": 0, "email_delivered": 0 if row.channel == "email" else None,
            "email_bounced": 0 if row.channel == "email" else None, "delivery_unknown": 0,
            "substantive_replies": 0, "positive_interest": 0, "linked_contacts": 0,
            "first_sent_at": None, "latest_sent_at": None, "outcomes": {stage: set() for stage in CONVERSIONS}})
        if row.status != "sent" or row.sent_at is None:
            group["pending"] += 1
            continue
        group["sent"] += 1
        group["mature"] += int(now - row.sent_at >= 7 * 86400)
        group["first_sent_at"] = min(group["first_sent_at"] or row.sent_at, row.sent_at)
        group["latest_sent_at"] = max(group["latest_sent_at"] or row.sent_at, row.sent_at)
        related = [m for m in messages[row.contact_id] if m.experiment_id in (None, row.experiment_id)]
        incoming = [m for m in related if m.direction == "in" and row.sent_at <= m.created_at <= now]
        events = [e for e in evidence[row.contact_id] if row.sent_at <= e.occurred_at <= now
                  and e.data.get("experiment_id") in (None, row.experiment_id)]
        # The message carries the latest classification; raw evidence can retain
        # an earlier UNKNOWN classification. Manual public replies have no message.
        message_ids = {m.id for m in incoming}
        classes = {m.classification for m in incoming} | {e.data.get("classification") for e in events
            if e.kind == "REPLY_RECEIVED" and e.data.get("message_id") not in message_ids}
        group["substantive_replies"] += int(bool(classes & SUBSTANTIVE))
        group["positive_interest"] += int("SUBSTANTIVE_POSITIVE" in classes or any(e.kind == "ACCESS_REQUESTED" for e in events))
        if row.channel == "email":
            first_mail = [m for m in related if m.direction == "out" and m.reply_to_id is None and m.sent_at is not None]
            # An engaged reply does not manufacture a provider delivery receipt.
            delivered = any(m.status == "delivered" or "email.delivered" in provider_events[m.provider_id] for m in first_mail)
            bounced = any(m.status == "bounced" or "email.bounced" in provider_events[m.provider_id] for m in first_mail)
            group["email_delivered"] += int(delivered)
            group["email_bounced"] += int(bounced)
            group["delivery_unknown"] += int(not delivered and not bounced)
        contact = contacts.get(row.contact_id)
        if contact and contact.shop_id is not None:
            group["linked_contacts"] += 1
            for event in evidence[f"shop:{contact.shop_id}"]:
                if event.kind in CONVERSIONS and row.sent_at <= event.occurred_at <= now and event.data.get("verified") is True:
                    group["outcomes"][event.kind].add(event.subject)
    cohorts = []
    for group in groups.values():
        group["outcomes"] = {stage: len(shops) for stage, shops in group["outcomes"].items()}
        group["outcome_linkage_complete"] = group["sent"] > 0 and group["linked_contacts"] == group["sent"]
        group["substantive_reply_rate"] = group["substantive_replies"] / group["sent"] if group["sent"] else None
        group["positive_interest_rate"] = group["positive_interest"] / group["sent"] if group["sent"] else None
        cohorts.append(group)
    # Daily chart is independent of the bounded cohort sample. Count merchants,
    # not individual reply messages, and exclude automated/system mail.
    day = int(now // 86400) * 86400
    buckets = {day - i * 86400: {"first_contacts": set(), "substantive_replies": set()} for i in range(6, -1, -1)}
    since = min(buckets)
    for contact_id, at in db.execute(select(FirstContact.contact_id, FirstContact.sent_at).where(
        FirstContact.status == "sent", FirstContact.sent_at >= since, FirstContact.sent_at <= now)):
        buckets[int(at // 86400) * 86400]["first_contacts"].add(contact_id)
    reply_messages = list(db.scalars(select(Message).where(Message.direction == "in", Message.created_at >= since,
        Message.created_at <= now)))
    for message in reply_messages:
        if message.classification in SUBSTANTIVE:
            buckets[int(message.created_at // 86400) * 86400]["substantive_replies"].add(message.contact_id)
    reply_ids = {m.id for m in reply_messages}
    for event in db.scalars(select(Evidence).where(Evidence.kind == "REPLY_RECEIVED", Evidence.occurred_at >= since,
        Evidence.occurred_at <= now)):
        if event.data.get("message_id") not in reply_ids and event.data.get("classification") in SUBSTANTIVE:
            buckets[int(event.occurred_at // 86400) * 86400]["substantive_replies"].add(event.subject)
    return {"cohorts": cohorts, "cohort_contact_limit": limit, "cohorts_truncated": truncated,
        "contact_count": len(rows), "sent": sum(c["sent"] for c in cohorts),
        "pending": sum(c["pending"] for c in cohorts),
        "activity": [{"day": datetime.fromtimestamp(at, timezone.utc).date().isoformat(),
            **{key: len(values) for key, values in counts.items()}} for at, counts in buckets.items()],
        "limitations": "Public replies are published and forms are accepted; neither verifies email delivery. Outcomes are distinct verified stores observed after contact, not proof of causation. Missing account links remain unknown. Cohorts retain their original channel, experiment, ICP, offer and message version."}


def dashboard(db):
    from .execution import state as execution_state
    from .outbound import status as outbound_status
    now = time.time()
    day = int(now // 86400) * 86400
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    today_events = dict(db.execute(select(Evidence.kind, func.count()).where(Evidence.occurred_at >= day).group_by(Evidence.kind)).all())
    today_funnel = measured_funnel(db, since=day)
    stats = measured_funnel(db)
    contacts = list(db.scalars(select(Contact).order_by(Contact.created_at.desc()).limit(50)))
    experiments = list(db.scalars(select(Experiment).order_by(Experiment.started_at.desc()).limit(20)))
    beliefs = list(db.scalars(select(Memory).where(Memory.namespace == "beliefs").order_by(Memory.updated_at.desc()).limit(12)))
    known_cost = db.scalar(select(func.coalesce(func.sum(Usage.estimated_usd), 0)))
    reserved_unknown = db.scalar(select(func.coalesce(func.sum(Usage.reserved_usd), 0)).where(Usage.estimated_usd.is_(None)))
    acquisition_cost = known_cost + reserved_unknown
    mission = get_memory(db, "strategic", "identity")
    cohort = measured_funnel(db, since=mission.get("started_at", now))
    outreach = outreach_projection(db, now)
    contracts = [m.value for m in db.scalars(select(Memory).where(Memory.namespace == "economics")) if m.value.get("active")]
    mrr = sum(c["monthly_recurring_usd"] for c in contracts) if contracts and all(c.get("monthly_recurring_usd") is not None for c in contracts) else None
    first_qualified = select(Evidence.subject).where(Evidence.kind.in_(
        ["SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED"]),
        Evidence.data["verified"].as_boolean().is_(True)).group_by(Evidence.subject).having(
        func.min(Evidence.occurred_at) >= mission.get("started_at", now)).subquery()
    qualified = db.scalar(select(func.count()).select_from(first_qualified)) or 0
    activity = get_memory(db, "working", "activity")
    if now - activity.get("last_wake", 0) > 900:
        activity = {**activity, "health": "stale_or_stopped"}
    errors = list(db.scalars(select(Work).where(Work.status.in_(["failed", "blocked"]))
                            .order_by(Work.updated_at.desc()).limit(12)))
    next_work = db.scalar(select(Work).where(Work.status == "ready").order_by(Work.due_at, Work.priority.desc()).limit(1))
    return {
        "generated_at": now,
        "execution": execution_state(db, now),
        "measurement": {"day_timezone": "UTC", "mission_started_at": mission.get("started_at"),
                        "mission_funnel": cohort, "funnel_scope": "All recorded product activity; includes accounts predating the growth mission."},
        "mission": {**mission, "qualified_users": qualified, "target": 10},
        "today": {"actions": today_events.get("ACTION_RESULT", 0), "conversations_found": today_events.get("OPPORTUNITY", 0),
                  "emails_sent": today_events.get("EMAIL_SENT", 0), "replies": outreach["activity"][-1]["substantive_replies"],
                  "first_contacts": outreach["activity"][-1]["first_contacts"],
                  "signups": today_funnel["SIGNUP"], "connections": today_funnel["SHOPIFY_CONNECTION"],
                  "activations": today_funnel["INVENTORY_ANALYSIS_VIEWED"], "purchases": today_funnel["SUBSCRIPTION_PURCHASED"]},
        "funnel": stats,
        "outreach": outreach,
        "pipeline": {"prospects": count(Contact), "qualified_prospects": count(Contact,
                     Contact.qualification["qualified"].as_boolean().is_(True), Contact.suppressed.is_(False),
                     ~Contact.status.in_(["declined", "unsubscribed", "delivery_failure", "bounced", "ineligible"])),
                     "active_conversations": count(Contact, Contact.status == "active_conversation", Contact.suppressed.is_(False)),
                     "high_intent_prospects": count(Contact, Contact.status.in_(["high_intent", "active_conversation"]), Contact.suppressed.is_(False)),
                     "contacts": [{"id": c.id, "organization": c.organization, "status": c.status, "source": c.source,
                                   "qualification": c.qualification, "contact_basis": c.contact_basis, "suppressed": c.suppressed} for c in contacts]},
        "experiments": {"counts": dict(db.execute(select(Experiment.status, func.count()).group_by(Experiment.status)).all()),
                        "items": [{"id": e.id, "status": e.status, "specification": e.specification, "result": e.result, "started_at": e.started_at} for e in experiments]},
        "learning": {"beliefs": [{"key": b.key, "updated_at": b.updated_at, **b.value} for b in beliefs],
                     "recent_changes": [b.key for b in beliefs if b.updated_at >= day],
                     "contradictions": [b.value for b in beliefs if b.value.get("contradictory_evidence")]},
        "strategy": {**get_memory(db, "strategic", "strategy"), "bottleneck": bottleneck(db),
                     "review": get_memory(db, "strategic", "review"), "acquisition_hold": get_memory(db, "working", "acquisition_hold")},
        "economics": {"mrr": mrr, "customers": len(contracts) if contracts else None, "model_api_spend": known_cost,
                      "acquisition_efficiency": efficiency(db),
                      "unknown_cost_records": count(Usage, Usage.estimated_usd.is_(None)),
                      "unresolved_cost_reservations": reserved_unknown, "advertising_spend": 0, "acquisition_spend": acquisition_cost,
                      "cac": None,
                      "cost_per_signup": acquisition_cost / cohort["SIGNUP"] if cohort["SIGNUP"] else None,
                      "cost_per_connection": acquisition_cost / cohort["SHOPIFY_CONNECTION"] if cohort["SHOPIFY_CONNECTION"] else None,
                      "cost_per_activation": acquisition_cost / cohort["INVENTORY_ANALYSIS_VIEWED"] if cohort["INVENTORY_ANALYSIS_VIEWED"] else None,
                      "arpu": None, "churn": None, "ltv": None, "ltv_cac": None, "payback_months": None,
                      "trial_to_paid": None,
                      "limitations": "Attribution and collected payments must be verified before interpreting CAC. MRR/LTV remain unknown until billing amounts and retention are observed."},
        "agent": {**activity, "next_action": next_work.kind if next_work else "await_scheduled_wake",
                  "inbox_transport": inbox_transport(db, now=now),
                  "first_contact_capacity": outbound_status(db),
                  "executive": get_memory(db, "working", "executive"),
                  "capabilities": {"requested_service_email": Policy.from_env().email_enabled,
                     "promotional_email": False, "public_research": True, "community_posting": False,
                     "payment_receipts": bool(os.getenv("SHOPIFY_PARTNER_API_TOKEN")),
                     "executive_review": os.getenv("GROWTH_REVIEW_MODE", "api")},
                  "next_due": next_work.due_at if next_work else None, "queue_ready": count(Work, Work.status == "ready"),
                  "errors": [{"id": w.id, "kind": w.kind, "error": w.error, "at": w.updated_at} for w in errors],
                  "paused": get_memory(db, "working", "control").get("paused", False),
                  "daily_budget_usd": Policy.from_env().daily_usd, "paid_ads_allowed": False},
        "review_queue": [{"id": e.id, "kind": e.kind, "at": e.occurred_at, "source": e.source, "data": e.data}
                         for e in db.scalars(select(Evidence).where(Evidence.kind.in_(["OWNER_ATTENTION", "COMMUNITY_RESPONSE_DRAFTED", "PRODUCT_FEEDBACK"]))
                         .order_by(Evidence.id.desc()).limit(12)) if e.kind != "PRODUCT_FEEDBACK" or get_memory(db, "working", "acquisition_hold")],
        "recent_actions": [{"id": e.id, "kind": e.kind, "at": e.occurred_at, "source": e.source, "data": e.data} for e in db.scalars(
            select(Evidence).where(Evidence.kind != "MEMORY_REVISION").order_by(Evidence.id.desc()).limit(20))],
    }
