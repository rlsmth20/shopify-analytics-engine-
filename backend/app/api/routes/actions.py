from fastapi import APIRouter, HTTPException

from app.schemas import ActionDataHealthSummaryResponse, ActionFeedResponse
from app.services.action_feed import (
    ActionFeedUnavailableError,
    build_action_data_health_summary,
    build_inventory_action_feed,
)


router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=ActionFeedResponse)
def read_actions() -> ActionFeedResponse:
    try:
        feed = build_inventory_action_feed()
    except ActionFeedUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ActionFeedResponse(
        data_source=feed.source,
        actions=feed.actions,
    )


@router.get("/debug-summary", response_model=ActionDataHealthSummaryResponse)
def read_action_data_health() -> ActionDataHealthSummaryResponse:
    summary = build_action_data_health_summary()
    return ActionDataHealthSummaryResponse(
        shops=summary.shops,
        products=summary.products,
        inventory_rows=summary.inventory_rows,
        order_line_items=summary.order_line_items,
        distinct_skus_with_usable_action_data=summary.distinct_skus_with_usable_action_data,
    )
