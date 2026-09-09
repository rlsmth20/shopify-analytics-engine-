"""Deterministic email ramp; all mutations share the existing dispatch lock.

Ceilings are not quotas. A tier needs elapsed Pacific days AND at least three
confirmed first contacts across two days, one delivery/reply, and a fresh inbox
check. Idle time cannot promote a sender. New senders never inherit history.
"""
import time
from datetime import date

from sqlalchemy import func, select

from .models import Evidence, FirstContact, Memory, Message
from .outbound import lock
from .review_calendar import review_day
from .store import digest, get_memory, insert_once, remember

NAMESPACE = "email_ramp"
CEILINGS = (5, 8, 12, 15, 20)
STAGE_DAYS = (3, 3, 4, 4)
MIN_CONFIRMED = 3
MIN_ACTIVE_DAYS = 2
HEALTH_FRESH_SECONDS = 86400
SIGNAL_WINDOW_SECONDS = 7 * 86400


def authentication(db, sender):
    item = get_memory(db, "strategic", "email_authentication").get("identities", {}).get(sender.lower(), {})
    verified = all(item.get(k) is True for k in ("spf", "dkim", "dmarc")) and bool(item.get("source") and item.get("verified_at"))
    return {"verified": verified, "evidence": item}


def pilot_completed(pilot):
    # An owner-reviewed real pilot is distinct from a safe test or paid account.
    return pilot.get("completed") is True and pilot.get("successful") is True and bool(pilot.get("source") and pilot.get("completed_at"))


def _initial(sender):
    return {"version": 1, "sender": sender, "start_at": None, "stage": 0,
            "stage_started_at": None, "last_increase_at": None, "daily_ceiling": 5,
            "signals": {}, "pause_reason": None}


def signal(db, sender, kind, event_id, now=None):
    """A replay-safe negative observation freezes increases, not ordinary replies."""
    now = time.time() if now is None else now
    sender = sender.lower()
    lock(db)
    _, fresh = insert_once(db, Evidence, key="email-ramp-signal:" + digest([sender, kind, event_id]),
        kind="EMAIL_RAMP_SIGNAL", subject=sender, source="outreach_delivery_observation",
        data={"signal": kind, "event_id": event_id}, occurred_at=now)
    if not fresh:
        return
    state = get_memory(db, NAMESPACE, digest(sender)) or _initial(sender)
    signals = {**state.get("signals", {}), kind: now}
    remember(db, NAMESPACE, digest(sender), {**state, "signals": signals, "pause_reason": kind})


def status(db, sender, now=None, *, persist=False, confirmed_at=None, advance=True):
    now = time.time() if now is None else now
    sender = sender.strip().lower()
    if persist:
        lock(db)
    key = digest(sender)
    original = get_memory(db, NAMESPACE, key)
    state = {**(original or _initial(sender))}
    if confirmed_at is not None and state["start_at"] is None:
        state.update(start_at=confirmed_at, stage_started_at=confirmed_at)
    day = review_day(now)
    # The actual first-contact ledger is authoritative. Unknown legacy sender
    # attribution is counted conservatively but never credited as ramp evidence.
    used = db.scalar(select(func.count()).select_from(FirstContact).where(
        FirstContact.channel == "email", FirstContact.status == "sent",
        FirstContact.sent_at >= day.start, FirstContact.sent_at < day.end)) or 0
    tier_start = state.get("stage_started_at") or now
    rows = list(db.execute(select(Message, Memory).join(Memory,
        (Memory.namespace == "outreach_email") & (Memory.key == Message.id)).where(
        Message.direction == "out", Message.sent_at >= max(tier_start, now - 30 * 86400),
        Message.sent_at <= now, Memory.value["safe_test"].as_boolean().is_(False),
        Memory.value["kind"].as_string() == "first_contact",
        Memory.value["sender"].as_string() == sender)).all())
    active_days = {review_day(row.sent_at).day for row, _ in rows}
    healthy_receipts = sum(row.status in {"delivered", "replied"} for row, _ in rows)
    health = get_memory(db, "working", "outreach_email_health")
    fresh_monitor = get_memory(db, "working", "outreach_inbox_cursor").get("checked_at", 0) >= now - HEALTH_FRESH_SECONDS
    recent_signals = {kind: at for kind, at in state.get("signals", {}).items() if at > now - SIGNAL_WINDOW_SECONDS}
    auth = authentication(db, sender)
    reason = (health.get("reason", "DELIVERABILITY_HOLD") if health.get("paused") else
              "RECENT_" + max(recent_signals, key=recent_signals.get).upper() if recent_signals else
              "AUTHENTICATION_NOT_VERIFIED" if not auth["verified"] else
              "DELIVERY_MONITOR_STALE" if not fresh_monitor else None)
    stage = state["stage"]
    elapsed_days = (date.fromisoformat(day.day) - date.fromisoformat(review_day(tier_start).day)).days
    evidence_ready = len(rows) >= MIN_CONFIRMED and len(active_days) >= MIN_ACTIVE_DAYS and healthy_receipts >= 1
    if persist and advance and stage < len(CEILINGS) - 1 and state["start_at"] is not None and not reason and evidence_ready and elapsed_days >= STAGE_DAYS[stage]:
        stage += 1
        state.update(stage=stage, stage_started_at=now, last_increase_at=now)
    state.update(daily_ceiling=CEILINGS[stage], pause_reason=reason,
                 day=day.day, actual_first_contacts_today=used,
                 recent_indicators=recent_signals)
    if persist:
        remember(db, NAMESPACE, key, state)
    return {**state, "normal_daily_ceiling": 20, "complete": stage == len(CEILINGS) - 1,
            "remaining": max(0, CEILINGS[stage] - used), "resets_at": day.end,
            "day_timezone": "America/Los_Angeles", "is_target": False,
            "late_confirmation_overage": max(0, used - CEILINGS[stage]),
            "authentication": auth, "increase_paused": bool(reason),
            "stage_evidence": {"confirmed": len(rows), "active_days": len(active_days),
                               "delivered_or_replied": healthy_receipts,
                               "minimum_confirmed": MIN_CONFIRMED, "minimum_active_days": MIN_ACTIVE_DAYS,
                               "ready": evidence_ready}}
