import time

from sqlalchemy import func, select

from .funnel import bottleneck, funnel_counts
from .models import Contact, Evidence, Experiment, Memory, Message, Usage, Work
from .policy import Policy
from .store import get_memory


def dashboard(db):
    now = time.time()
    day = int(now // 86400) * 86400
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    today_events = dict(db.execute(select(Evidence.kind, func.count()).where(Evidence.occurred_at >= day).group_by(Evidence.kind)).all())
    stats = funnel_counts(db)
    contacts = list(db.scalars(select(Contact).order_by(Contact.created_at.desc()).limit(50)))
    experiments = list(db.scalars(select(Experiment).order_by(Experiment.started_at.desc()).limit(20)))
    beliefs = list(db.scalars(select(Memory).where(Memory.namespace == "beliefs").order_by(Memory.updated_at.desc()).limit(12)))
    known_cost = db.scalar(select(func.coalesce(func.sum(Usage.estimated_usd), 0)))
    reserved_unknown = db.scalar(select(func.coalesce(func.sum(Usage.reserved_usd), 0)).where(Usage.estimated_usd.is_(None)))
    acquisition_cost = known_cost + reserved_unknown
    mission = get_memory(db, "strategic", "identity")
    cohort = funnel_counts(db, since=mission.get("started_at", now))
    contracts = [m.value for m in db.scalars(select(Memory).where(Memory.namespace == "economics")) if m.value.get("active")]
    mrr = sum(c["monthly_recurring_usd"] for c in contracts) if contracts and all(c.get("monthly_recurring_usd") is not None for c in contracts) else None
    qualified = db.scalar(select(func.count(func.distinct(Evidence.subject))).where(Evidence.kind.in_(
        ["SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED"]),
        Evidence.occurred_at >= mission.get("started_at", 0))) or 0
    activity = get_memory(db, "working", "activity")
    if now - activity.get("last_wake", 0) > 900:
        activity = {**activity, "health": "stale_or_stopped"}
    errors = list(db.scalars(select(Work).where(Work.status.in_(["failed", "blocked"]))
                            .order_by(Work.updated_at.desc()).limit(12)))
    next_work = db.scalar(select(Work).where(Work.status == "ready").order_by(Work.due_at, Work.priority.desc()).limit(1))
    return {
        "mission": {**mission, "qualified_users": qualified, "target": 10},
        "today": {"actions": today_events.get("ACTION_RESULT", 0), "conversations_found": today_events.get("OPPORTUNITY", 0),
                  "emails_sent": today_events.get("EMAIL_SENT", 0), "replies": today_events.get("REPLY_RECEIVED", 0),
                  "signups": today_events.get("SIGNUP", 0), "connections": today_events.get("SHOPIFY_CONNECTION", 0),
                  "activations": today_events.get("INVENTORY_ANALYSIS_VIEWED", 0), "purchases": today_events.get("SUBSCRIPTION_PURCHASED", 0)},
        "funnel": stats,
        "pipeline": {"prospects": count(Contact), "qualified_prospects": count(Contact, Contact.status == "qualified"),
                     "active_conversations": count(Contact, Contact.status == "active_conversation"),
                     "high_intent_prospects": count(Contact, Contact.status.in_(["high_intent", "active_conversation"])),
                     "contacts": [{"id": c.id, "organization": c.organization, "status": c.status, "source": c.source,
                                   "qualification": c.qualification, "contact_basis": c.contact_basis} for c in contacts]},
        "experiments": {"counts": dict(db.execute(select(Experiment.status, func.count()).group_by(Experiment.status)).all()),
                        "items": [{"id": e.id, "status": e.status, "specification": e.specification, "result": e.result, "started_at": e.started_at} for e in experiments]},
        "learning": {"beliefs": [{"key": b.key, "updated_at": b.updated_at, **b.value} for b in beliefs],
                     "recent_changes": [b.key for b in beliefs if b.updated_at >= day],
                     "contradictions": [b.value for b in beliefs if b.value.get("contradictory_evidence")]},
        "strategy": {**get_memory(db, "strategic", "strategy"), "bottleneck": bottleneck(db),
                     "review": get_memory(db, "strategic", "review"), "acquisition_hold": get_memory(db, "working", "acquisition_hold")},
        "economics": {"mrr": mrr, "customers": len(contracts) if contracts else None, "model_api_spend": known_cost,
                      "unresolved_cost_reservations": reserved_unknown, "advertising_spend": 0, "acquisition_spend": acquisition_cost,
                      "cac": None,
                      "cost_per_signup": acquisition_cost / cohort["SIGNUP"] if cohort["SIGNUP"] else None,
                      "cost_per_connection": acquisition_cost / cohort["SHOPIFY_CONNECTION"] if cohort["SHOPIFY_CONNECTION"] else None,
                      "cost_per_activation": acquisition_cost / cohort["INVENTORY_ANALYSIS_VIEWED"] if cohort["INVENTORY_ANALYSIS_VIEWED"] else None,
                      "arpu": None, "churn": None, "ltv": None, "ltv_cac": None, "payback_months": None,
                      "trial_to_paid": None,
                      "limitations": "Attribution and collected payments must be verified before interpreting CAC. MRR/LTV remain unknown until billing amounts and retention are observed."},
        "agent": {**activity, "next_action": next_work.kind if next_work else "await_scheduled_wake",
                  "next_due": next_work.due_at if next_work else None, "queue_ready": count(Work, Work.status == "ready"),
                  "errors": [{"id": w.id, "kind": w.kind, "error": w.error, "at": w.updated_at} for w in errors],
                  "paused": get_memory(db, "working", "control").get("paused", False),
                  "daily_budget_usd": Policy.from_env().daily_usd, "paid_ads_allowed": False},
        "recent_actions": [{"id": e.id, "kind": e.kind, "at": e.occurred_at, "source": e.source, "data": e.data} for e in db.scalars(
            select(Evidence).where(Evidence.kind != "MEMORY_REVISION").order_by(Evidence.id.desc()).limit(20))],
    }
