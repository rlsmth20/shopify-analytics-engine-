"""Small durable primitives. Unique keys, CAS leases and append-only evidence."""
import hashlib
import json
import time

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from .models import Evidence, Memory, Work, uid


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def insert_once(db, entity_class, *, key, **values):
    existing = db.scalar(select(entity_class).where(entity_class.key == key))
    if existing:
        return existing, False
    try:
        with db.begin_nested():
            row = entity_class(key=key, **values)
            db.add(row)
            db.flush()
        return row, True
    except IntegrityError:
        return db.scalar(select(entity_class).where(entity_class.key == key)), False


def record(db, key, kind, subject, data, source="growth_operator", epistemic="OBSERVATION", occurred_at=None):
    return insert_once(db, Evidence, key=key, kind=kind, subject=subject, data=data,
                       source=source, epistemic=epistemic, occurred_at=occurred_at or time.time())[0]


def get_memory(db, namespace, key, default=None):
    row = db.scalar(select(Memory).where(Memory.namespace == namespace, Memory.key == key))
    return row.value if row else (default if default is not None else {})


def remember(db, namespace, key, value, *, source="growth_operator"):
    row = db.scalar(select(Memory).where(Memory.namespace == namespace, Memory.key == key))
    if row and row.value == value:
        return row
    if not row:
        row = Memory(namespace=namespace, key=key, value=value)
        db.add(row)
        db.flush()
    else:
        row.value = value
        row.version += 1
        row.updated_at = time.time()
    record(db, f"memory:{namespace}:{key}:{row.version}", "MEMORY_REVISION", f"{namespace}:{key}",
           {"version": row.version, "value": value}, source=source, epistemic="INFERENCE")
    return row


def enqueue(db, key, kind, payload=None, priority=0, due_at=None):
    return insert_once(db, Work, key=key, kind=kind, payload=payload or {}, priority=priority,
                       due_at=due_at or time.time())[0]


def claim(factory, lease_seconds=120):
    from .execution import priority_order
    now = time.time()
    with factory() as db:
        # A crashed task exhausts the same retry allowance as an explicit failure.
        db.execute(update(Work).where(Work.status == "running", Work.lease_until < now,
                                      Work.attempts >= Work.max_attempts)
                   .values(status="failed", error="lease_expired: retry allowance exhausted", updated_at=now))
        eligible = or_(Work.status == "ready", (Work.status == "running") & (Work.lease_until < now))
        candidates = list(db.scalars(select(Work.id).where(eligible, Work.due_at <= now,
                                   Work.attempts < Work.max_attempts)
                                   .order_by(priority_order(), Work.priority.desc(), Work.due_at, Work.id).limit(8)))
        for work_id in candidates:
            token = uid()
            changed = db.execute(update(Work).where(Work.id == work_id, eligible,
                                 Work.attempts < Work.max_attempts)
                                 .values(status="running", lease_token=token, lease_until=now + lease_seconds,
                                         attempts=Work.attempts + 1, updated_at=now)).rowcount
            if changed:
                db.commit()
                return db.get(Work, work_id)
        db.commit()
    return None


def heartbeat(factory, work_id, token, lease_seconds=120):
    with factory() as db:
        changed = db.execute(update(Work).where(Work.id == work_id, Work.lease_token == token,
                            Work.status == "running", Work.lease_until > time.time())
                            .values(lease_until=time.time() + lease_seconds, updated_at=time.time())).rowcount
        db.commit()
        return bool(changed)


def require_lease(db, work):
    # A write fence holds the row until the local decision/send intent commits.
    changed = db.execute(update(Work).where(Work.id == work.id, Work.lease_token == work.lease_token,
                        Work.status == "running", Work.lease_until > time.time())
                        .values(updated_at=time.time())).rowcount
    if not changed:
        raise RuntimeError("lease_lost")


def finish(factory, work, *, result=None, error=None, failure_class=None):
    with factory() as db:
        require_lease(db, work)
        now = time.time()
        status = "done"
        due = now
        if not error and result and result.get("defer_until", 0) > now:
            status, due = "ready", result["defer_until"]
        if error:
            if failure_class == "transient" and work.attempts < work.max_attempts:
                status, due = "ready", now + min(3600, 60 * 2 ** work.attempts)
            else:
                status = "blocked" if failure_class in {"configuration", "policy", "ambiguous"} else "failed"
        db.execute(update(Work).where(Work.id == work.id).values(
            status=status, due_at=due, lease_until=0, result=result or {},
            attempts=max(0, work.attempts - 1) if result and result.get("defer_until") else work.attempts,
            error=f"{failure_class}: {error}"[:500] if error else None, updated_at=now))
        record(db, f"work:{work.id}:{work.attempts}", "ACTION_RESULT", work.id,
               {"kind": work.kind, "status": status, "result": result or {}, "failure_class": failure_class})
        from .execution import ACQUISITION
        if work.kind in ACQUISITION and status == "done" and result and not result.get("cached") and result.get("decision") not in {"research_cap_reached", "discovery_cap_reached"}:
            record(db, f"acquisition:{work.id}:{work.attempts}", "ACQUISITION_PROGRESS", work.id,
                   {"executor": "server", "stage": work.kind, "result": result})
        db.commit()


def context(db, subject=None, limit=12):
    query = select(Evidence).where(Evidence.kind != "MEMORY_REVISION")
    if subject:
        query = query.where(Evidence.subject == subject)
    rows = db.scalars(query.order_by(Evidence.id.desc()).limit(min(limit, 30)))
    return [{"id": r.id, "kind": r.kind, "epistemic": r.epistemic, "source": r.source,
             "data": json.dumps(r.data, ensure_ascii=False)[:900]} for r in rows]
