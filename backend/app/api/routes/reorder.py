from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import PurchaseOrderDraftsResponse, ReorderFeedResponse
from app.services.purchase_orders import build_purchase_order_drafts
from app.services.reorder_optimizer import build_reorder_suggestions, build_vendor_totals
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import (
    load_daily_history_for_shop_skus,
    load_skus_for_shop,
)


router = APIRouter(prefix="/reorder", tags=["reorder"])


@router.get("", response_model=ReorderFeedResponse)
def list_reorder_suggestions(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    service_level: float = Query(0.95, ge=0.80, le=0.999),
) -> ReorderFeedResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return ReorderFeedResponse(
            service_level=service_level,
            suggestions=[],
            total_extended_cost=0.0,
            vendor_totals={},
        )
    settings = load_effective_shop_settings_map(db).get(user.shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    histories = load_daily_history_for_shop_skus(
        db,
        user.shop_id,
        [sku.sku_id for sku in skus],
        90,
    )

    def daily_history(sku_id: str, days: int = 90) -> list[int]:
        history = histories.get(sku_id, [])
        return history[-days:] if days < len(history) else history

    suggestions = build_reorder_suggestions(
        skus,
        daily_history,
        lead_time_config=settings.to_lead_time_config(),
        service_level=service_level,
    )
    totals = build_vendor_totals(suggestions)
    return ReorderFeedResponse(
        service_level=service_level,
        suggestions=suggestions,
        total_extended_cost=round(sum(s.extended_cost for s in suggestions), 2),
        vendor_totals=totals,
    )


@router.get("/purchase-orders", response_model=PurchaseOrderDraftsResponse)
def list_po_drafts(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    service_level: float = Query(0.95, ge=0.80, le=0.999),
) -> PurchaseOrderDraftsResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return PurchaseOrderDraftsResponse(drafts=[], total_capital_required=0.0)
    settings = load_effective_shop_settings_map(db).get(user.shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    histories = load_daily_history_for_shop_skus(
        db,
        user.shop_id,
        [sku.sku_id for sku in skus],
        90,
    )

    def daily_history(sku_id: str, days: int = 90) -> list[int]:
        history = histories.get(sku_id, [])
        return history[-days:] if days < len(history) else history

    suggestions = build_reorder_suggestions(
        skus,
        daily_history,
        lead_time_config=settings.to_lead_time_config(),
        service_level=service_level,
    )
    drafts = build_purchase_order_drafts(suggestions)
    return PurchaseOrderDraftsResponse(
        drafts=drafts,
        total_capital_required=round(sum(d.total_cost for d in drafts), 2),
    )
