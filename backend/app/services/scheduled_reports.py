"""Scheduled report email delivery.

Turns the Reports page schedule preferences (ReportScheduleRecord rows for
actions / stockout / dead-stock / reorder) into real emails. Weekly schedules
go out on Mondays (UTC), monthly on the 1st; DigestSendLog dedups so
scheduler restarts never double-send.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import DigestSendLog, ReportScheduleRecord
from app.db.session import SessionLocal
from app.services.dead_stock import build_liquidation_plan
from app.services.inventory_engine import build_inventory_actions
from app.services.reorder_optimizer import build_reorder_suggestions
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import load_daily_history_for_shop_skus, load_skus_for_shop
from app.services.transactional_email import send_scheduled_report_email

logger = logging.getLogger(__name__)

MAX_ROWS = 12

REPORT_TITLES: dict[str, str] = {
    "actions": "Inventory Action Report",
    "stockout": "Stockout Risk Report",
    "dead-stock": "Dead Stock Report",
    "reorder": "Reorder Plan",
}


def build_report_email(db: DbSession, *, shop_id: int, report_type: str):
    """Return (title, intro, headers, rows, cta_path) or None when empty."""
    skus = load_skus_for_shop(db, shop_id)
    if not skus:
        return None
    settings = load_effective_shop_settings_map(db).get(shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    lead_config = settings.to_lead_time_config()

    if report_type == "actions":
        actions = build_inventory_actions(skus, lead_time_config=lead_config)[:MAX_ROWS]
        if not actions:
            return None
        rows = []
        for action in actions:
            impact = (
                getattr(action, "estimated_profit_impact", None)
                if action.status == "urgent"
                else getattr(action, "cash_tied_up", None)
            )
            rows.append([
                action.name,
                action.status.upper(),
                str(action.current_on_hand),
                f"{action.days_of_inventory:.0f}d",
                f"${impact:,.0f}" if impact is not None else "-",
                action.recommended_action,
            ])
        return (
            REPORT_TITLES[report_type],
            f"Your top {len(rows)} ranked inventory actions, most urgent first.",
            ["Product", "Status", "On hand", "Cover", "Impact", "Recommended action"],
            rows,
            "/actions",
        )

    histories = load_daily_history_for_shop_skus(db, shop_id, [sku.sku_id for sku in skus], 90)
    suggestions = build_reorder_suggestions(
        skus,
        lambda sku_id: histories.get(sku_id, []),
        lead_time_config=lead_config,
    )

    if report_type == "stockout":
        risky = sorted(
            (s for s in suggestions if s.expected_stockout_prob >= 0.2),
            key=lambda s: s.expected_stockout_prob,
            reverse=True,
        )[:MAX_ROWS]
        if not risky:
            return None
        rows = [
            [
                s.name,
                s.vendor or "-",
                str(s.current_on_hand),
                f"{s.expected_stockout_prob:.0%}",
                f"{s.lead_time_days}d",
                str(s.recommended_order_qty),
            ]
            for s in risky
        ]
        return (
            REPORT_TITLES[report_type],
            f"{len(rows)} SKUs at meaningful stockout risk inside their lead time.",
            ["Product", "Vendor", "On hand", "Stockout risk", "Lead time", "Reorder qty"],
            rows,
            "/forecast",
        )

    if report_type == "dead-stock":
        plan = build_liquidation_plan(skus)[:MAX_ROWS]
        if not plan:
            return None
        rows = [
            [
                item.name,
                str(item.on_hand),
                "No sales" if item.days_since_last_sale >= 999 else f"{item.days_since_last_sale}d",
                item.tactic.replace("_", " "),
                f"${item.capital_tied_up:,.0f}",
                f"${item.projected_recovered_capital:,.0f}",
            ]
            for item in plan
        ]
        return (
            REPORT_TITLES[report_type],
            f"{len(rows)} dead-stock SKUs with the most capital to recover.",
            ["Product", "On hand", "Stale", "Tactic", "Capital stuck", "Projected recovery"],
            rows,
            "/liquidation",
        )

    if report_type == "reorder":
        top = sorted(
            suggestions,
            key=lambda s: (s.expected_stockout_prob, s.landed_extended_cost),
            reverse=True,
        )[:MAX_ROWS]
        if not top:
            return None
        total = sum(s.landed_extended_cost for s in top)
        rows = [
            [
                s.name,
                s.vendor or "-",
                str(s.recommended_order_qty),
                f"${s.landed_extended_cost:,.0f}",
                f"{s.expected_stockout_prob:.0%}",
                f"{s.lead_time_days}d",
            ]
            for s in top
        ]
        return (
            REPORT_TITLES[report_type],
            f"Top {len(rows)} reorders - ${total:,.0f} total cash required.",
            ["Product", "Vendor", "Order qty", "Cost", "Risk", "Lead time"],
            rows,
            "/purchase-orders",
        )

    return None


def _already_sent(db: DbSession, *, shop_id: int, digest_type: str, within_days: int) -> bool:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=within_days)
    record = db.scalar(
        select(DigestSendLog)
        .where(DigestSendLog.shop_id == shop_id)
        .where(DigestSendLog.digest_type == digest_type)
        .order_by(DigestSendLog.sent_at.desc())
        .limit(1)
    )
    if record is None or record.sent_at is None:
        return False
    sent_at = record.sent_at
    if sent_at.tzinfo is not None:
        sent_at = sent_at.astimezone(timezone.utc).replace(tzinfo=None)
    return sent_at > cutoff


def run_scheduled_reports_once(*, force: bool = False) -> int:
    """Send due scheduled report emails. Returns the number sent."""
    now = datetime.now(timezone.utc)
    sent = 0
    with SessionLocal() as db:
        schedules = db.scalars(
            select(ReportScheduleRecord)
            .where(ReportScheduleRecord.enabled.is_(True))
            .where(ReportScheduleRecord.channel == "email")
            .where(ReportScheduleRecord.report_type.in_(list(REPORT_TITLES)))
        ).all()
        for schedule in schedules:
            recipient = (schedule.recipient_email or "").strip()
            if not recipient or "@" not in recipient:
                continue
            cadence = (schedule.cadence or "weekly").lower()
            if not force:
                if cadence == "monthly" and now.day != 1:
                    continue
                if cadence != "monthly" and now.weekday() != 0:  # Monday
                    continue
            digest_type = f"report_{schedule.report_type}"
            dedup_days = 27 if cadence == "monthly" else 6
            try:
                if _already_sent(
                    db, shop_id=schedule.shop_id, digest_type=digest_type, within_days=dedup_days
                ):
                    continue
                built = build_report_email(
                    db, shop_id=schedule.shop_id, report_type=schedule.report_type
                )
                if built is None:
                    continue
                title, intro, headers, rows, cta_path = built
                delivered = send_scheduled_report_email(
                    email=recipient,
                    title=title,
                    intro=intro,
                    headers=headers,
                    rows=rows,
                    cta_path=cta_path,
                    cadence=cadence,
                )
                if delivered:
                    db.add(
                        DigestSendLog(
                            shop_id=schedule.shop_id,
                            digest_type=digest_type,
                            recipient_email=recipient,
                        )
                    )
                    db.commit()
                    sent += 1
            except Exception:
                logger.exception(
                    "Scheduled report failed shop_id=%s type=%s",
                    schedule.shop_id,
                    schedule.report_type,
                )
                db.rollback()
    return sent
