"""Alert rules + notification channels — auth-gated."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import Subscription, User
from app.db.session import get_db_session
from app.schemas_v2 import (
    AlertEventsResponse,
    AlertListResponse,
    AlertRule,
    CreateAlertRuleRequest,
    NotificationChannelConfig,
    NotificationChannelsResponse,
    TestAlertRequest,
    UpdateNotificationChannelRequest,
)
from app.services.alerts import (
    EvaluationContext,
    create_rule,
    delete_rule,
    evaluate,
    list_channel_configs,
    list_recent_events,
    list_rules,
    seed_default_rules_and_channels,
    toggle_rule,
    update_channel_config,
)
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_engine import build_inventory_actions
from app.services.notifications import deliver
from app.services.plan_entitlements import ALERT_CHANNEL_MIN_TIER, plan_allows_alert_channel
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import (
    load_daily_history_for_shop_skus,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)
from app.services.supplier_scoring import build_supplier_scorecards


router = APIRouter(prefix="/alerts", tags=["alerts"])


def _current_plan(db: DbSession, user: User) -> str | None:
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is None or sub.status not in ("active", "trialing"):
        return None
    return sub.plan


def _allowed_alert_channels(db: DbSession, user: User) -> set[NotificationChannel]:
    if user.is_admin:
        return set(ALERT_CHANNEL_MIN_TIER.keys())

    from datetime import datetime, timezone

    trial_ends = user.trial_ends_at
    if trial_ends is not None:
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        if trial_ends > datetime.now(timezone.utc):
            return set(ALERT_CHANNEL_MIN_TIER.keys())

    plan = _current_plan(db, user)
    return {
        channel
        for channel in ALERT_CHANNEL_MIN_TIER
        if plan_allows_alert_channel(plan, channel)
    }


def _require_alert_channels(
    db: DbSession,
    user: User,
    channels: list[NotificationChannel],
) -> None:
    allowed = _allowed_alert_channels(db, user)
    blocked = [channel for channel in channels if channel not in allowed]
    if blocked:
        raise HTTPException(
            status_code=403,
            detail=(
                "Your current plan does not include these alert channels: "
                + ", ".join(blocked)
                + ". Upgrade to continue."
            ),
        )


@router.get("/rules", response_model=AlertListResponse)
def read_rules(
    user: Annotated[User, Depends(require_active_access)],
) -> AlertListResponse:
    seed_default_rules_and_channels(user.shop_id)
    return AlertListResponse(rules=list_rules(user.shop_id))


@router.post("/rules", response_model=AlertRule)
def create_alert_rule(
    request: CreateAlertRuleRequest,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> AlertRule:
    seed_default_rules_and_channels(user.shop_id)
    _require_alert_channels(db, user, request.channels)
    return create_rule(
        shop_id=user.shop_id,
        name=request.name,
        trigger=request.trigger,
        severity=request.severity,
        channels=request.channels,
        threshold=request.threshold,
        enabled=request.enabled,
    )


@router.delete("/rules/{rule_id}")
def remove_rule(
    rule_id: str,
    user: Annotated[User, Depends(require_active_access)],
) -> dict[str, bool]:
    ok = delete_rule(user.shop_id, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True}


@router.patch("/rules/{rule_id}/toggle", response_model=AlertRule)
def toggle_alert_rule(
    rule_id: str,
    enabled: bool,
    user: Annotated[User, Depends(require_active_access)],
) -> AlertRule:
    updated = toggle_rule(user.shop_id, rule_id, enabled)
    if updated is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated


@router.get("/channels", response_model=NotificationChannelsResponse)
def read_channels(
    user: Annotated[User, Depends(require_active_access)],
) -> NotificationChannelsResponse:
    seed_default_rules_and_channels(user.shop_id)
    return NotificationChannelsResponse(channels=list_channel_configs(user.shop_id))


@router.post("/channels", response_model=NotificationChannelConfig)
def update_channel(
    request: UpdateNotificationChannelRequest,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> NotificationChannelConfig:
    _require_alert_channels(db, user, [request.channel])
    return update_channel_config(
        shop_id=user.shop_id,
        channel=request.channel,
        enabled=request.enabled,
        target=request.target,
    )


@router.post("/test")
def send_test_alert(
    request: TestAlertRequest,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> dict[str, str | bool]:
    _require_alert_channels(db, user, [request.channel])
    record = deliver(
        channel=request.channel,
        target=request.target,
        subject="skubase — test alert",
        body=(
            "This is a test notification from skubase. "
            "If you received this, your channel is configured correctly."
        ),
    )
    return {
        "delivered": record.delivered,
        "error": record.error or "",
    }


@router.get("/events", response_model=AlertEventsResponse)
def read_events(
    user: Annotated[User, Depends(require_active_access)],
    limit: int = 50,
) -> AlertEventsResponse:
    seed_default_rules_and_channels(user.shop_id)
    return AlertEventsResponse(events=list_recent_events(user.shop_id, limit=limit))


@router.post("/evaluate", response_model=AlertEventsResponse)
def evaluate_now(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    dry_run: bool = True,
) -> AlertEventsResponse:
    """Force an immediate evaluation against the current user's shop data."""
    seed_default_rules_and_channels(user.shop_id)

    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return AlertEventsResponse(events=[])

    settings = load_effective_shop_settings_map(db).get(user.shop_id)
    if settings is None:
        settings = build_default_shop_settings()

    actions = build_inventory_actions(skus, lead_time_config=settings.to_lead_time_config())
    start_weekday = start_weekday_for_shop_history(db, user.shop_id, 90)
    histories = load_daily_history_for_shop_skus(
        db,
        user.shop_id,
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

    events = evaluate(
        user.shop_id,
        EvaluationContext(
            actions=actions,
            forecasts=forecasts,
            supplier_scores=suppliers,
        ),
        deliver_channels=not dry_run,
        allowed_channels=_allowed_alert_channels(db, user),
    )
    return AlertEventsResponse(events=events)
