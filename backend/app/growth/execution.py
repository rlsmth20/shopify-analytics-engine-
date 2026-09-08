"""Shared execution policy and read-only operational state, across both executors."""
import time
from sqlalchemy import case, func, select
from .models import Evidence, FirstContact, Memory, Work
from .outbound import status
from .store import get_memory, record, remember

ACQUISITION = {"send", "opportunity", "research_contact", "discover"}


def priority_order():
    # Kind outranks legacy numerical scores: maintenance cannot starve acquisition.
    return case((Work.kind.in_(["reply", "inbox"]), 0),
                (Work.kind.in_(list(ACQUISITION)), 1),
                (Work.kind == "product_feedback", 2),
                (Work.kind == "evaluate", 3),
                (Work.kind.in_(["observe", "payments"]), 4), else_=5)


def state(db, now=None):
    now = time.time() if now is None else now
    capacity = status(db, now)
    jobs = list(db.scalars(select(Work).where(Work.kind.in_(list(ACQUISITION)),
        Work.status.in_(["ready", "running", "blocked", "failed"]))))
    browser = [r.value for r in db.scalars(select(Memory).where(Memory.namespace == "operator_task"))
               if r.value.get("status") in {"pending", "running", "blocked"}
               and r.value.get("stage", "discover") != "monitor"]
    pending = [w for w in jobs if w.status == "ready"]
    pending_browser = [w for w in browser if w["status"] == "pending"]
    active_browser = [w for w in browser if w["status"] in {"pending", "running"}]
    ages = [w.created_at for w in pending] + [w["created_at"] for w in pending_browser]
    last = db.scalar(select(Evidence).where(Evidence.kind == "ACQUISITION_PROGRESS")
                     .order_by(Evidence.id.desc()).limit(1))
    sent = db.scalar(select(func.max(FirstContact.sent_at)))
    executor = get_memory(db, "working", "browser_executor")
    planner = get_memory(db, "working", "acquisition_planner")
    ready = db.scalar(select(Work).where(Work.status == "ready", Work.due_at <= now)
                      .order_by(priority_order(), Work.priority.desc(), Work.due_at).limit(1))
    permitted = (capacity["remaining"] > 0 and not get_memory(db, "working", "control").get("paused")
                 and not get_memory(db, "working", "acquisition_hold")
                 and not get_memory(db, "working", "browser_safety_check").get("requires_attention"))
    executable_ages = [w.created_at for w in pending if w.due_at <= now] + [w["created_at"] for w in pending_browser if w.get("retry_at", 0) <= now]
    fault = None
    if permitted and executable_ages and now - max(min(executable_ages), last.occurred_at if last else 0) > 600:
        fault = "ACQUISITION_STARVED"
    last_browser = db.scalar(select(func.max(Evidence.occurred_at)).where(
        Evidence.kind == "ACQUISITION_PROGRESS", Evidence.data["executor"].as_string() != "server")) or 0
    if permitted and any(now - max(w.get("created_at", now), last_browser) > 600
            and w.get("retry_at", 0) <= now for w in active_browser):
        fault = "ACQUISITION_STARVED"
    if permitted and active_browser and now - executor.get("heartbeat_at", 0) > 120:
        fault = "ACQUISITION_EXECUTOR_OFFLINE"
    if permitted and not active_browser and planner.get("status") in {"planning", "hypotheses_ready", "executing_hypothesis"} and now - executor.get("heartbeat_at", 0) > 120:
        fault = "ACQUISITION_EXECUTOR_OFFLINE"
    if any(w.get("attempts", 0) >= 3 and w.get("lease_until", 0) <= now for w in browser):
        fault = "ACQUISITION_RETRIES_EXHAUSTED"
    blocker = ("SAFETY_BLOCKED" if get_memory(db, "working", "control").get("paused") or
               get_memory(db, "working", "acquisition_hold") else
               "DAILY_CAP_REACHED" if not capacity["remaining"] else executor.get("blocker"))
    future = [w.due_at for w in pending if w.due_at > now]
    future += [w.get("retry_at", 0) for w in browser if w.get("retry_at", 0) > now]
    next_at = now if ready or any(w.get("retry_at", 0) <= now for w in pending_browser) else min(future, default=now + 30)
    return {"daily_new_contact_cap": 20, "window_hours": 24,
        "sent_today": capacity["used"] - capacity["unresolved"], "reserved_or_uncertain": capacity["unresolved"],
        "remaining_capacity": capacity["remaining"],
        "qualified_ready": sum(w.get("stage") in {"prepare", "send", "outreach"} and w["status"] == "pending" for w in browser),
        "discovery_pending": sum(w.kind in {"discover", "research_contact"} for w in pending) +
                             sum(w.get("stage", "discover") in {"discover", "qualify"} for w in pending_browser),
        "acquisition_tasks_running": sum(w.status == "running" and w.lease_until > now for w in jobs) +
                                     sum(w["status"] == "running" and w.get("lease_until", 0) > now for w in browser),
        "oldest_pending_acquisition_age": now - min(ages) if ages else None,
        "last_acquisition_action": {"at": last.occurred_at, **last.data} if last else None,
        "last_successful_send": sent, "current_blocker": blocker, "operational_fault": fault,
        "next_action": "execute_" + next((w.get("stage", "discover") for w in active_browser if w["status"] == "running"), "acquisition")
            if executor.get("task_id") else "claim_browser_acquisition" if pending_browser and not blocker else ready.kind if ready else "await_retry",
        "next_wake_retry": capacity["next_slot_at"] if blocker == "DAILY_CAP_REACHED" else next_at,
        "executor": executor, "planner": planner}


def watchdog(db):
    snapshot = state(db)
    previous = get_memory(db, "working", "execution_fault")
    fault = snapshot["operational_fault"]
    if fault != previous.get("fault"):
        remember(db, "working", "execution_fault", {"fault": fault, "at": time.time()})
        if fault:
            record(db, f"execution-fault:{fault}:{int(time.time() // 600)}", "EXECUTION_FAULT", "acquisition",
                   {"fault": fault, "recovery": "Pull executor reclaims expired leases; server selects P1 before maintenance"})
    return snapshot
