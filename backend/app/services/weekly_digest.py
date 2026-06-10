"""Weekly Buy List digest — the Monday morning reorder email.

Driven by ReportScheduleRecord rows with report_type="weekly_buy_list": the
merchant opts in on the Reports page, and the background scheduler sends one
email per shop per week with the top reorder recommendations and the cash
required. Dedup is handled by DigestSendLog so scheduler restarts on a Monday
do not double-send.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import DigestSendLog, ReportScheduleRecord
from app.db.session import SessionLocal
from app.schemas_v2 import ReorderSuggestion
from app.services.reorder_optimizer import build_reorder_suggestions, build_vendor_totals
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import load_daily_history_for_shop_skus, load_skus_for_shop
from app.services.transactional_email import send_buy_list_email

logger = logging.getLogger(__name__)

DIGEST_TYPE = "weekly_buy_list"
SEND_WEEKDAY_UTC = 0  # Monday
MAX_ITEMS = 12


def build_buy_list(db: DbSession, *, shop_id: int) -> tuple[list[ReorderSuggestion], float, dict[str, float]]:
    """Top reorder recommendations for a shop, most urgent first."""
    skus = load_skus_for_shop(db, shop_id)
    if not skus:
        return [], 0.0, {}
    settings = load_effective_shop_settings_map(db).get(shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    histories = load_daily_history_for_shop_skus(db, shop_id, [sku.sku_id for sku in skus], 90)

    suggestions = build_reorder_suggestions(
        skus,
        lambda sku_id: histories.get(sku_id, []),
        lead_time_config=settings.to_lead_time_config(),
    )
    suggestions.sort(
        key=lambda s: (s.expected_stockout_prob, s.landed_extended_cost),
        reverse=True,
    )
    top = suggestions[:MAX_ITEMS]
    total = round(sum(s.landed_extended_cost for s in top), 2)
    return top, total, build_vendor_totals(top)


def _already_sent_this_week(db: DbSession, *, shop_id: int) -> bool:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=6)
    record = db.scalar(
        select(DigestSendLog)
        .where(DigestSendLog.shop_id == shop_id)
        .where(DigestSendLog.digest_type == DIGEST_TYPE)
        .order_by(DigestSendLog.sent_at.desc())
        .limit(1)
    )
    if record is None:
        return False
    sent_at = record.sent_at
    if sent_at is not None and sent_at.tzinfo is not None:
        sent_at = sent_at.astimezone(timezone.utc).replace(tzinfo=None)
    return sent_at is not None and sent_at > cutoff


def run_weekly_digests_once(*, force: bool = False) -> int:
    """Send due weekly buy-list digests. Returns the number of emails sent.

    Sends only on Mondays (UTC) unless force=True; safe to call every
    scheduler tick because DigestSendLog dedups per shop per week.
    """
    if not force and datetime.now(timezone.utc).weekday() != SEND_WEEKDAY_UTC:
        return 0

    sent = 0
    with SessionLocal() as db:
        schedules = db.scalars(
            select(ReportScheduleRecord)
            .where(ReportScheduleRecord.report_type == DIGEST_TYPE)
            .where(ReportScheduleRecord.enabled.is_(True))
        ).all()
        for schedule in schedules:
            recipient = (schedule.recipient_email or "").strip()
            if not recipient or "@" not in recipient:
                continue
            try:
                if _already_sent_this_week(db, shop_id=schedule.shop_id):
                    continue
                items, total, vendor_totals = build_buy_list(db, shop_id=schedule.shop_id)
                if not items:
                    continue
                delivered = send_buy_list_email(
                    email=recipient,
                    items=[
                        {
                            "name": item.name,
                            "vendor": item.vendor,
                            "qty": item.recommended_order_qty,
                            "cost": item.landed_extended_cost,
                            "stockout_prob": item.expected_stockout_prob,
                            "lead_time_days": item.lead_time_days,
                        }
                        for item in items
                    ],
                    total_cost=total,
                    vendor_totals=vendor_totals,
                )
                if delivered:
                    db.add(
                        DigestSendLog(
                            shop_id=schedule.shop_id,
                            digest_type=DIGEST_TYPE,
                            recipient_email=recipient,
                        )
                    )
                    db.commit()
                    sent += 1
            except Exception:
                logger.exception("Weekly buy list failed for shop_id=%s", schedule.shop_id)
                db.rollback()
    return sent
