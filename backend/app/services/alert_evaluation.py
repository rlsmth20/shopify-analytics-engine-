"""Shared alert evaluation helpers for API routes and background jobs."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Subscription, User
from app.schemas_v2 import AlertEvent, NotificationChannel
from app.services.alerts import EvaluationContext, evaluate, seed_default_rules_and_channels
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_engine import build_inventory_actions
from app.services.plan_entitlements import ALERT_CHANNEL_MIN_TIER, plan_allows_alert_channel
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import (
    load_daily_history_for_shop_skus,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)
from app.services.supplier_scoring import build_supplier_scorecards


def current_plan(db: DbSession, user: User) -> str | None:
    from app.services.shopify_billing import (
        current_shopify_subscription_summary,
        has_active_shopify_connection,
    )

    if has_active_shopify_connection(db, shop_id=user.shop_id):
        shopify_sub = current_shopify_subscription_summary(db, user=user)
        if shopify_sub.get("status") in ("active", "trialing"):
            return str(shopify_sub.get("plan") or "none")
        return None

    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is None or sub.status not in ("active", "trialing"):
        return None
    return sub.plan


def user_has_active_access(db: DbSession, user: User) -> bool:
    if user.is_admin:
        return True

    trial_ends = user.trial_ends_at
    if trial_ends is not None:
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        if trial_ends > datetime.now(timezone.utc):
            return True

    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    return sub is not None and sub.status in ("active", "trialing")


def allowed_alert_channels(db: DbSession, user: User) -> set[NotificationChannel]:
    if user.is_admin:
        return set(ALERT_CHANNEL_MIN_TIER.keys())

    trial_ends = user.trial_ends_at
    if trial_ends is not None:
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        if trial_ends > datetime.now(timezone.utc):
            return set(ALERT_CHANNEL_MIN_TIER.keys())

    plan = current_plan(db, user)
    return {
        channel
        for channel in ALERT_CHANNEL_MIN_TIER
        if plan_allows_alert_channel(plan, channel)
    }


def build_evaluation_context(db: DbSession, shop_id: int) -> EvaluationContext | None:
    skus = load_skus_for_shop(db, shop_id)
    if not skus:
        return None

    settings = load_effective_shop_settings_map(db).get(shop_id)
    if settings is None:
        settings = build_default_shop_settings()

    actions = build_inventory_actions(skus, lead_time_config=settings.to_lead_time_config())
    start_weekday = start_weekday_for_shop_history(db, shop_id, 90)
    histories = load_daily_history_for_shop_skus(
        db,
        shop_id,
        [sku.sku_id for sku in skus],
        90,
    )
    forecasts = [
        forecast_sku(
            ForecastInputs(
                sku_id=sku.sku_id,
                daily_history=histories.get(sku.sku_id, []),
                on_hand=sku.inventory,
                start_weekday=start_weekday,
            )
        )
        for sku in skus
    ]
    suppliers = build_supplier_scorecards([], skus)
    return EvaluationContext(
        actions=actions,
        forecasts=forecasts,
        supplier_scores=suppliers,
    )


def evaluate_shop_alerts(
    db: DbSession,
    user: User,
    *,
    dry_run: bool,
    cooldown_seconds: int = 0,
) -> list[AlertEvent]:
    seed_default_rules_and_channels(user.shop_id)
    context = build_evaluation_context(db, user.shop_id)
    if context is None:
        return []

    return evaluate(
        user.shop_id,
        context,
        deliver_channels=not dry_run,
        allowed_channels=allowed_alert_channels(db, user),
        cooldown_seconds=cooldown_seconds if not dry_run else 0,
    )
