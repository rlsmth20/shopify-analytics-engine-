"""Alert rules + notification channels — auth-gated."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
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
from app.services.shop_skus import (
    load_daily_history_for_shop_sku,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)
from app.services.supplier_scoring import build_supplier_scorecards


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/rules", response_model=AlertListResponse)
def read_rules(
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertListResponse:
    seed_default_rules_and_channels()
    return AlertListResponse(rules=list_rules())


@router.post("/rules", response_model=AlertRule)
def create_alert_rule(
    request: CreateAlertRuleRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertRule:
    seed_default_rules_and_channels()
    return create_rule(
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
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    ok = delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True}


@router.patch("/rules/{rule_id}/toggle", response_model=AlertRule)
def toggle_alert_rule(
    rule_id: str,
    enabled: bool,
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertRule:
    updated = toggle_rule(rule_id, enabled)
    if updated is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated


@router.get("/channels", response_model=NotificationChannelsResponse)
def read_channels(
    _user: Annotated[User, Depends(get_current_user)],
) -> NotificationChannelsResponse:
    seed_default_rules_and_channels()
    return NotificationChannelsResponse(channels=list_channel_configs())


@router.post("/channels", response_model=NotificationChannelConfig)
def update_channel(
    request: UpdateNotificationChannelRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> NotificationChannelConfig:
    return update_channel_config(
        channel=request.channel,
        enabled=request.enabled,
        target=request.target,
    )


@router.post("/test")
def send_test_alert(
    request: TestAlertRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str | bool]:
    record = deliver(
        channel=request.channel,
        target=request.target,
        subject="slelfly — test alert",
        body=(
            "This is a test notification from slelfly. "
            "If you received this, your channel is configured correctly."
        ),
    )
    return {
        "delivered": record.delivered,
        "error": record.error or "",
    }


@router.get("/events", response_model=AlertEventsResponse)
def read_events(
    _user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
) -> AlertEventsResponse:
    seed_default_rules_and_channels()
    return AlertEventsResponse(events=list_recent_events(limit=limit))


@router.post("/evaluate", response_model=AlertEventsResponse)
def evaluate_now(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
    dry_run: bool = True,
) -> AlertEventsResponse:
    """Force an immediate evaluation against the current user's shop data."""
    seed_default_rules_and_channels()

    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return AlertEventsResponse(events=[])

    actions = build_inventory_actions(skus)
    start_weekday = start_weekday_for_shop_history(db, user.shop_id, 90)
    forecasts = [
        forecast_sku(
            ForecastInputs(
                sku_id=sku.sku_id,
                daily_history=load_daily_history_for_shop_sku(db, user.shop_id, sku.sku_id, 90),
                on_hand=sku.inventory,
                start_weekday=start_weekday,
            )
        )
        for sku in skus
    ]
    suppliers = build_supplier_scorecards([], skus)

    events = evaluate(
        EvaluationContext(
            actions=actions,
            forecasts=forecasts,
            supplier_scores=suppliers,
        ),
        deliver_channels=not dry_run,
    )
    return AlertEventsResponse(events=events)
