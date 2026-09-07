"""Use the same paid-plan capabilities for saved schedules and background sends."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import User
from app.services.billing import current_entitlements_summary
from app.services.plan_entitlements import CapabilityKey

logger = logging.getLogger(__name__)

REPORT_CAPABILITIES: dict[str, CapabilityKey] = {
    "actions": "action_queue_basic",
    "stockout": "forecast",
    "dead-stock": "dead_stock_basic",
    "reorder": "reorder_pos",
    "weekly_buy_list": "reorder_pos",
}


def report_schedule_access_error(
    db: DbSession, user: User, report_type: str | None = None,
) -> tuple[int, str] | None:
    """Return a route-friendly denial; background callers use the same decision."""
    if report_type is not None and report_type not in REPORT_CAPABILITIES:
        return 422, "Unsupported scheduled report type."
    try:
        entitlements = current_entitlements_summary(db, user=user)
    except Exception:
        logger.exception("Could not verify scheduled-report access for shop_id=%s", user.shop_id)
        return 503, "Plan access could not be verified. Please try again before enabling report emails."
    if not entitlements.get("billing_status_loaded") or entitlements.get("billing_status_error"):
        return 503, "Plan access could not be verified. Check Billing before enabling report emails."
    if entitlements.get("subscription_status") not in {"active", "trialing"}:
        return 402, "An active trial or subscription is required for report emails."

    # Match the active-access gate's three-day renewal grace for mirrored paid
    # periods. A stale 'active' label must not keep a background schedule alive.
    period_end = entitlements.get("current_period_end")
    if period_end and entitlements.get("plan_id") != "trial" and not user.is_admin:
        try:
            ends_at = datetime.fromisoformat(str(period_end).replace("Z", "+00:00"))
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return 503, "The subscription period could not be verified. Check Billing before enabling report emails."
        if ends_at + timedelta(days=3) <= datetime.now(timezone.utc):
            return 402, "The subscription period has ended. Check Billing before enabling report emails."

    capabilities = set(entitlements.get("capabilities") or [])
    if "scheduled_reports" not in capabilities:
        return 403, "Scheduled report emails are included on Scale. Upgrade from Billing to enable them."
    if report_type is not None and REPORT_CAPABILITIES[report_type] not in capabilities:
        return 403, "Your current plan does not include this report. Check Billing before enabling it."
    return None


def shop_may_send_scheduled_report(db: DbSession, *, shop_id: int, report_type: str) -> bool:
    # Prefer a merchant account over a support administrator when both exist.
    user = db.scalar(select(User).where(User.shop_id == shop_id).order_by(User.is_admin, User.id).limit(1))
    if user is None:
        logger.warning("Skipping scheduled report without a merchant account: shop_id=%s", shop_id)
        return False
    denied = report_schedule_access_error(db, user, report_type)
    if denied is not None:
        logger.info("Skipping scheduled report without verified access: shop_id=%s report=%s status=%s", shop_id, report_type, denied[0])
        return False
    return True
