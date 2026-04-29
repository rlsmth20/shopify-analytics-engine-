from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import (
    Inventory,
    OrderLineItem,
    Product,
    Shop,
    User,
)
from app.db.session import get_db_session
from app.schemas import ActionDataHealthSummaryResponse, ActionFeedResponse
from app.services.inventory_engine import build_inventory_actions
from app.services.shop_skus import load_skus_for_shop


router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=ActionFeedResponse)
def read_actions(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ActionFeedResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return ActionFeedResponse(data_source="db", actions=[])
    actions = build_inventory_actions(skus)
    return ActionFeedResponse(data_source="db", actions=actions)


@router.get("/debug-summary", response_model=ActionDataHealthSummaryResponse)
def read_action_data_health(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ActionDataHealthSummaryResponse:
    shop_count = 1  # The current user's shop only.
    products = db.scalar(
        select(func.count()).select_from(Product).where(Product.shop_id == user.shop_id)
    ) or 0
    inv_rows = db.scalar(
        select(func.count()).select_from(Inventory).where(Inventory.shop_id == user.shop_id)
    ) or 0
    olis = db.scalar(
        select(func.count()).select_from(OrderLineItem).where(OrderLineItem.shop_id == user.shop_id)
    ) or 0
    skus = load_skus_for_shop(db, user.shop_id)
    return ActionDataHealthSummaryResponse(
        shops=shop_count,
        products=int(products),
        inventory_rows=int(inv_rows),
        order_line_items=int(olis),
        distinct_skus_with_usable_action_data=len(skus),
    )
