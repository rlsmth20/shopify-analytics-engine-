from fastapi import APIRouter, Query

from app.mock_data import MOCK_SKUS
from app.mock_data_v2 import daily_history_for_sku
from app.schemas_v2 import PurchaseOrderDraftsResponse, ReorderFeedResponse
from app.services.purchase_orders import build_purchase_order_drafts
from app.services.reorder_optimizer import build_reorder_suggestions, build_vendor_totals


router = APIRouter(prefix="/reorder", tags=["reorder"])


@router.get("", response_model=ReorderFeedResponse)
def list_reorder_suggestions(
    service_level: float = Query(0.95, ge=0.80, le=0.999),
) -> ReorderFeedResponse:
    suggestions = build_reorder_suggestions(
        MOCK_SKUS,
        daily_history_for_sku,
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
    service_level: float = Query(0.95, ge=0.80, le=0.999),
) -> PurchaseOrderDraftsResponse:
    suggestions = build_reorder_suggestions(
        MOCK_SKUS,
        daily_history_for_sku,
        service_level=service_level,
    )
    drafts = build_purchase_order_drafts(suggestions)
    return PurchaseOrderDraftsResponse(
        drafts=drafts,
        total_capital_required=round(sum(d.total_cost for d in drafts), 2),
    )
