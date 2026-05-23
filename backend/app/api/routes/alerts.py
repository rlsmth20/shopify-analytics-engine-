"""Alert rules + notification channels — auth-gated."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import (
    AlertEventsResponse,
    AlertListResponse,
    AlertRule,
    CreateAlertRuleRequest,
    NotificationChannel,
    NotificationChannelConfig,
    NotificationChannelsResponse,
    TestAlertRequest,
    UpdateNotificationChannelRequest,
)
from app.services.alert_evaluation import allowed_alert_channels, evaluate_shop_alerts
from app.services.alerts import (
    create_rule,
    delete_rule,
    list_channel_configs,
    list_recent_events,
    list_rules,
    seed_default_rules_and_channels,
    toggle_rule,
    update_channel_config,
)
from app.services.notifications import deliver


router = APIRouter(prefix="/alerts", tags=["alerts"])


def _require_alert_channels(
    db: DbSession,
    user: User,
    channels: list[NotificationChannel],
) -> None:
    allowed = allowed_alert_channels(db, user)
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
    events = evaluate_shop_alerts(
        db,
        user,
        dry_run=dry_run,
        cooldown_seconds=0,
    )
    return AlertEventsResponse(events=events)
