"""Scheduled report email delivery.

Turns the Reports page schedule preferences (ReportScheduleRecord rows for
actions / stockout / dead-stock / reorder) into real emails. Weekly schedules
are eligible on Mondays (UTC), monthly on the 1st. The shared durable ledger
freezes each period's email, bounds retries, and holds uncertain outcomes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import ReportScheduleRecord
from app.db.session import SessionLocal
from app.services.dead_stock import build_liquidation_plan
from app.services.inventory_engine import build_inventory_actions
from app.services.reorder_optimizer import build_reorder_suggestions
from app.services.scheduled_delivery import deliver_scheduled_email
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import load_daily_history_for_shop_skus, load_skus_for_shop
from app.services.transactional_email import build_scheduled_report_email_params

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
    settings = load_effective_shop_settings_map(db, shop_id=shop_id).get(shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    lead_config = settings.to_lead_time_config()

    if report_type == "actions":
        actions = build_inventory_actions(skus, lead_time_config=lead_config)[:MAX_ROWS]
        if not actions:
            return None
        rows = []
        for action in actions:
            needs_review = action.identity_ambiguous or not action.planning_values_known
            impact = (
                getattr(action, "estimated_profit_impact", None)
                if action.status == "urgent"
                else getattr(action, "cash_tied_up", None)
            )
            rows.append([
                action.name,
                "REVIEW" if needs_review else action.status.upper(),
                str(action.current_on_hand),
                "Unknown" if needs_review else f"{action.days_of_inventory:.0f}d",
                f"${impact:,.0f}" if impact is not None and action.financial_values_known and not needs_review else "Unknown",
                (action.identity_warning or "Review SKU identity and planning inputs before ordering or clearing stock.")
                    if needs_review else action.recommended_action,
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
                item.tactic.replace("_", " ") if item.financial_values_known else "Add unit costs",
                f"${item.capital_tied_up:,.0f}" if item.financial_values_known else "Unknown",
                f"${item.projected_recovered_capital:,.0f}" if item.financial_values_known else "Unknown",
            ]
            for item in plan
        ]
        return (
            REPORT_TITLES[report_type],
            f"{len(rows)} stale SKUs to review; financial recommendations require recorded unit costs.",
            ["Product", "On hand", "Stale", "Tactic", "Capital stuck", "Projected recovery"],
            rows,
            "/liquidation",
        )

    if report_type == "reorder":
        top = sorted(
            suggestions,
            key=lambda s: (s.expected_stockout_prob, s.landed_extended_cost if s.financial_values_known else 0),
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
                f"${s.landed_extended_cost:,.0f}" if s.financial_values_known else "Unknown",
                f"{s.expected_stockout_prob:.0%}",
                f"{s.lead_time_days}d",
            ]
            for s in top
        ]
        return (
            REPORT_TITLES[report_type],
            (f"Top {len(rows)} reorders - ${total:,.0f} total cash required." if all(s.financial_values_known for s in top)
             else f"Top {len(rows)} reorders. Add missing unit costs to measure total cash required."),
            ["Product", "Vendor", "Order qty", "Cost", "Risk", "Lead time"],
            rows,
            "/purchase-orders",
        )

    return None


def run_scheduled_reports_once(*, force: bool = False) -> int:
    """Send due reports; return the number of newly recorded provider acceptances."""
    now = datetime.now(timezone.utc)
    sent = 0
    with SessionLocal() as db:
        schedule_ids = db.scalars(
            select(ReportScheduleRecord.id)
            .where(ReportScheduleRecord.enabled.is_(True))
            .where(ReportScheduleRecord.channel == "email")
            .where(ReportScheduleRecord.cadence.in_(["weekly", "monthly"]))
            .where(ReportScheduleRecord.report_type.in_(list(REPORT_TITLES)))
        ).all()
    if not force and now.weekday() != 0 and now.day != 1:
        return 0
    for schedule_id in schedule_ids:
        try:
            sent += int(deliver_scheduled_email(schedule_id, _prepared_report, force=force))
        except Exception:
            logger.exception("Scheduled report failed schedule_id=%s", schedule_id)
    return sent


def _prepared_report(db: DbSession, schedule: ReportScheduleRecord) -> dict | None:
    built = build_report_email(db, shop_id=schedule.shop_id, report_type=schedule.report_type)
    if built is None:
        return None
    title, intro, headers, rows, cta_path = built
    return build_scheduled_report_email_params(email=schedule.recipient_email.strip(), title=title,
        intro=intro, headers=headers, rows=rows, cta_path=cta_path, cadence=schedule.cadence)
