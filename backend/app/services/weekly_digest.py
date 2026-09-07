"""Weekly Buy List digest — the Monday (UTC) reorder email.

Driven by ReportScheduleRecord rows with report_type="weekly_buy_list": the
merchant opts in on the Purchase Orders page. The background scheduler prepares
the top reorder recommendations and known cash requirements. The shared durable
ledger freezes each week's email, bounds retries, and holds uncertain outcomes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import ReportScheduleRecord
from app.db.session import SessionLocal
from app.schemas_v2 import ReorderSuggestion
from app.services.reorder_optimizer import build_known_vendor_totals, build_reorder_suggestions, build_vendor_totals
from app.services.scheduled_delivery import deliver_scheduled_email
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import load_daily_history_for_shop_skus, load_skus_for_shop
from app.services.transactional_email import build_buy_list_email_params

logger = logging.getLogger(__name__)

DIGEST_TYPE = "weekly_buy_list"
SEND_WEEKDAY_UTC = 0  # Monday
MAX_ITEMS = 12


def build_buy_list(db: DbSession, *, shop_id: int) -> tuple[list[ReorderSuggestion], float, dict[str, float]]:
    """Top reorder recommendations for a shop, most urgent first."""
    skus = load_skus_for_shop(db, shop_id)
    if not skus:
        return [], 0.0, {}
    settings = load_effective_shop_settings_map(db, shop_id=shop_id).get(shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    histories = load_daily_history_for_shop_skus(db, shop_id, [sku.sku_id for sku in skus], 90)

    suggestions = build_reorder_suggestions(
        skus,
        lambda sku_id: histories.get(sku_id, []),
        lead_time_config=settings.to_lead_time_config(),
    )
    suggestions.sort(
        key=lambda s: (s.expected_stockout_prob, s.landed_extended_cost if s.financial_values_known else 0),
        reverse=True,
    )
    top = suggestions[:MAX_ITEMS]
    total = round(sum(s.landed_extended_cost for s in top), 2)
    return top, total, build_vendor_totals(top)


def run_weekly_digests_once(*, force: bool = False) -> int:
    """Send due buy lists; return newly recorded provider acceptances.

    Sends only on Mondays (UTC) unless force=True; safe to call every
    scheduler tick because the durable ledger claims each schedule/calendar week.
    """
    if not force and datetime.now(timezone.utc).weekday() != SEND_WEEKDAY_UTC:
        return 0

    sent = 0
    with SessionLocal() as db:
        schedule_ids = db.scalars(
            select(ReportScheduleRecord.id)
            .where(ReportScheduleRecord.report_type == DIGEST_TYPE)
            .where(ReportScheduleRecord.enabled.is_(True))
            .where(ReportScheduleRecord.channel == "email")
            .where(ReportScheduleRecord.cadence == "weekly")
        ).all()
    for schedule_id in schedule_ids:
        try:
            sent += int(deliver_scheduled_email(schedule_id, _prepared_buy_list, force=force))
        except Exception:
            logger.exception("Weekly buy list failed schedule_id=%s", schedule_id)
    return sent


def _prepared_buy_list(db: DbSession, schedule: ReportScheduleRecord) -> dict | None:
    items, total, vendor_totals = build_buy_list(db, shop_id=schedule.shop_id)
    if not items:
        return None
    return build_buy_list_email_params(email=schedule.recipient_email.strip(),
        items=[{"name": item.name, "vendor": item.vendor, "qty": item.recommended_order_qty,
                "cost": item.landed_extended_cost if item.financial_values_known else None,
                "stockout_prob": item.expected_stockout_prob, "lead_time_days": item.lead_time_days} for item in items],
        total_cost=total if all(item.financial_values_known for item in items) else None,
        vendor_totals=build_known_vendor_totals(items, vendor_totals))
