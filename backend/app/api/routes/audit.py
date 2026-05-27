from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import AuditLogEvent, AuditLogResponse
from app.services.audit_log import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditLogResponse)
def get_audit_events(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogResponse:
    events = list_audit_events(db, shop_id=user.shop_id, limit=limit)
    return AuditLogResponse(
        events=[
            AuditLogEvent(
                id=event.id,
                event_type=event.event_type,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                summary=event.summary,
                metadata=event.event_metadata or {},
                created_at=event.created_at,
            )
            for event in events
        ]
    )
