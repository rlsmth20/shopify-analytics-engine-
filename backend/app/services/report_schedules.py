from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import ReportScheduleRecord


def list_report_schedules(db: DbSession, shop_id: int) -> list[ReportScheduleRecord]:
    return db.scalars(
        select(ReportScheduleRecord)
        .where(ReportScheduleRecord.shop_id == shop_id)
        .order_by(ReportScheduleRecord.report_type.asc())
    ).all()


def upsert_report_schedule(
    db: DbSession,
    *,
    shop_id: int,
    report_type: str,
    cadence: str,
    channel: str,
    recipient_email: str,
    enabled: bool,
) -> ReportScheduleRecord:
    record = db.scalar(
        select(ReportScheduleRecord)
        .where(ReportScheduleRecord.shop_id == shop_id)
        .where(ReportScheduleRecord.report_type == report_type)
    )
    if record is None:
        record = ReportScheduleRecord(shop_id=shop_id, report_type=report_type)
        db.add(record)
        db.flush()

    record.cadence = cadence
    record.channel = channel
    record.recipient_email = recipient_email
    record.enabled = enabled
    db.commit()
    db.refresh(record)
    return record
