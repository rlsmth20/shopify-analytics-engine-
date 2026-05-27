from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import AuditLogRecord


def record_audit_event(
    db: DbSession,
    *,
    shop_id: int,
    user_id: int | None,
    event_type: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    metadata: dict | None = None,
    commit: bool = True,
) -> AuditLogRecord:
    event = AuditLogRecord(
        shop_id=shop_id,
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        event_metadata=metadata or {},
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def list_audit_events(
    db: DbSession,
    *,
    shop_id: int,
    limit: int = 50,
) -> list[AuditLogRecord]:
    return db.scalars(
        select(AuditLogRecord)
        .where(AuditLogRecord.shop_id == shop_id)
        .order_by(AuditLogRecord.created_at.desc())
        .limit(limit)
    ).all()
