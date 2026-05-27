from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import (
    ReportSchedule,
    ReportSchedulesResponse,
    UpsertReportScheduleRequest,
)
from app.services.audit_log import record_audit_event
from app.services.report_schedules import list_report_schedules, upsert_report_schedule

router = APIRouter(prefix="/reports/schedules", tags=["report-schedules"])


@router.get("", response_model=ReportSchedulesResponse)
def get_report_schedules(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ReportSchedulesResponse:
    return ReportSchedulesResponse(
        schedules=[_to_schema(record) for record in list_report_schedules(db, user.shop_id)]
    )


@router.post("", response_model=ReportSchedule)
def save_report_schedule(
    payload: UpsertReportScheduleRequest,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ReportSchedule:
    record = upsert_report_schedule(
        db,
        shop_id=user.shop_id,
        report_type=payload.report_type,
        cadence=payload.cadence,
        channel=payload.channel,
        recipient_email=payload.recipient_email,
        enabled=payload.enabled,
    )
    record_audit_event(
        db,
        shop_id=user.shop_id,
        user_id=user.id,
        event_type="report_schedule_saved",
        entity_type="report_schedule",
        entity_id=payload.report_type,
        summary=f"{payload.report_type} report schedule saved for {payload.recipient_email}.",
        metadata={
            "report_type": payload.report_type,
            "cadence": payload.cadence,
            "channel": payload.channel,
            "enabled": payload.enabled,
        },
    )
    return _to_schema(record)


def _to_schema(record) -> ReportSchedule:
    return ReportSchedule(
        id=record.id,
        report_type=record.report_type,
        cadence=record.cadence,
        channel=record.channel,
        recipient_email=record.recipient_email,
        enabled=record.enabled,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
