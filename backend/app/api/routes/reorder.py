from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_plan_feature
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import (
    CashPlanResponse,
    CashPlanVendor,
    PurchaseOrderDraftsResponse,
    PurchaseOrderStatusResponse,
    ReceivePurchaseOrderRequest,
    ReorderFeedResponse,
    SavePurchaseOrderRequest,
)
from app.services.purchase_orders import build_purchase_order_drafts
from app.services.purchase_order_records import (
    list_saved_purchase_orders,
    receive_purchase_order,
    save_purchase_order,
    update_purchase_order_status,
)
from app.services.audit_log import record_audit_event
from app.services.reorder_optimizer import build_reorder_suggestions, build_vendor_totals
from app.services.shop_settings import build_default_shop_settings, load_effective_shop_settings_map
from app.services.shop_skus import (
    load_daily_history_for_shop_skus,
    load_skus_for_shop,
)


router = APIRouter(prefix="/reorder", tags=["reorder"])


@router.get("", response_model=ReorderFeedResponse)
def list_reorder_suggestions(
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
    service_level: float = Query(0.95, ge=0.80, le=0.999),
    shipping_cost: float = Query(35.0, ge=0.0, le=10000.0),
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
        order_cost=shipping_cost,
    )
    totals = build_vendor_totals(suggestions)
    return ReorderFeedResponse(
        service_level=service_level,
        suggestions=suggestions,
        total_extended_cost=round(sum(s.landed_extended_cost for s in suggestions), 2),
        vendor_totals=totals,
    )


@router.get("/cash-plan", response_model=CashPlanResponse)
def read_cash_plan(
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
    service_level: float = Query(0.95, ge=0.80, le=0.999),
    shipping_cost: float = Query(35.0, ge=0.0, le=10000.0),
) -> CashPlanResponse:
    """Open-to-buy view: cash the reorder queue needs now vs. what can wait.

    "Order now" = inventory is at or below the reorder point, so waiting risks
    a stockout within the lead time. Everything else is a deferrable top-up.
    """
    empty = CashPlanResponse(
        order_now_cost=0.0,
        deferrable_cost=0.0,
        total_cost=0.0,
        order_now_items=0,
        deferrable_items=0,
        vendors=[],
        explanation="No reorders recommended right now.",
    )
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return empty
    settings = load_effective_shop_settings_map(db).get(user.shop_id)
    if settings is None:
        settings = build_default_shop_settings()
    histories = load_daily_history_for_shop_skus(
        db,
        user.shop_id,
        [sku.sku_id for sku in skus],
        90,
    )
    suggestions = build_reorder_suggestions(
        skus,
        lambda sku_id: histories.get(sku_id, []),
        lead_time_config=settings.to_lead_time_config(),
        service_level=service_level,
        order_cost=shipping_cost,
    )
    if not suggestions:
        return empty

    vendors: dict[str, dict[str, float | int]] = {}
    order_now_cost = deferrable_cost = 0.0
    order_now_items = deferrable_items = 0
    for s in suggestions:
        urgent = s.current_on_hand <= s.reorder_point
        bucket = vendors.setdefault(
            s.vendor or "Unassigned",
            {"now": 0.0, "later": 0.0, "items": 0, "lead": 0},
        )
        bucket["items"] = int(bucket["items"]) + 1
        bucket["lead"] = max(int(bucket["lead"]), s.lead_time_days)
        if urgent:
            order_now_cost += s.landed_extended_cost
            order_now_items += 1
            bucket["now"] = float(bucket["now"]) + s.landed_extended_cost
        else:
            deferrable_cost += s.landed_extended_cost
            deferrable_items += 1
            bucket["later"] = float(bucket["later"]) + s.landed_extended_cost

    vendor_rows = sorted(
        (
            CashPlanVendor(
                vendor=name,
                order_now_cost=round(float(data["now"]), 2),
                deferrable_cost=round(float(data["later"]), 2),
                item_count=int(data["items"]),
                max_lead_time_days=int(data["lead"]),
            )
            for name, data in vendors.items()
        ),
        key=lambda row: row.order_now_cost + row.deferrable_cost,
        reverse=True,
    )
    return CashPlanResponse(
        order_now_cost=round(order_now_cost, 2),
        deferrable_cost=round(deferrable_cost, 2),
        total_cost=round(order_now_cost + deferrable_cost, 2),
        order_now_items=order_now_items,
        deferrable_items=deferrable_items,
        vendors=vendor_rows,
        explanation=(
            f"{order_now_items} SKU(s) are at or below their reorder point and need "
            f"${order_now_cost:,.0f} this week to avoid stockouts. "
            f"${deferrable_cost:,.0f} more is recommended but deferrable if cash is tight."
        ),
    )


@router.get("/purchase-orders", response_model=PurchaseOrderDraftsResponse)
def list_po_drafts(
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
    service_level: float = Query(0.95, ge=0.80, le=0.999),
    shipping_cost: float = Query(35.0, ge=0.0, le=10000.0),
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
        order_cost=shipping_cost,
    )
    drafts = build_purchase_order_drafts(suggestions, shipping_cost_per_po=shipping_cost)
    saved = list_saved_purchase_orders(db, user.shop_id)
    saved_open_vendors = {
        po.vendor
        for po in saved
        if po.status not in {"received", "cancelled"}
    }
    drafts = [draft for draft in drafts if draft.vendor not in saved_open_vendors]
    return PurchaseOrderDraftsResponse(
        drafts=[*saved, *drafts],
        total_capital_required=round(sum(d.total_cost for d in [*saved, *drafts]), 2),
    )


@router.post("/purchase-orders", response_model=PurchaseOrderStatusResponse)
def save_po_draft(
    payload: SavePurchaseOrderRequest,
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> PurchaseOrderStatusResponse:
    saved = save_purchase_order(db, shop_id=user.shop_id, draft=payload.draft)
    record_audit_event(
        db,
        shop_id=user.shop_id,
        user_id=user.id,
        event_type="purchase_order_saved",
        entity_type="purchase_order",
        entity_id=saved.po_id,
        summary=f"Purchase order {saved.po_id} saved for {saved.vendor}.",
        metadata={"vendor": saved.vendor, "total_cost": saved.total_cost, "status": saved.status},
    )
    return PurchaseOrderStatusResponse(
        po=saved
    )


@router.post("/purchase-orders/{po_id}/status", response_model=PurchaseOrderStatusResponse)
def update_po_status(
    po_id: str,
    status: str,
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> PurchaseOrderStatusResponse:
    if status not in {"draft", "ready", "approved", "sent", "partially_received", "received", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid purchase order status.")
    po = update_purchase_order_status(
        db,
        shop_id=user.shop_id,
        po_id=po_id,
        status=status,
        user_id=user.id,
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    record_audit_event(
        db,
        shop_id=user.shop_id,
        user_id=user.id,
        event_type=f"purchase_order_{status}",
        entity_type="purchase_order",
        entity_id=po.po_id,
        summary=f"Purchase order {po.po_id} marked {status}.",
        metadata={"vendor": po.vendor, "total_cost": po.total_cost, "status": po.status},
    )
    return PurchaseOrderStatusResponse(po=po)


@router.post("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderStatusResponse)
def receive_po(
    po_id: str,
    payload: ReceivePurchaseOrderRequest,
    user: Annotated[User, Depends(require_plan_feature("reorder_pos"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> PurchaseOrderStatusResponse:
    po = receive_purchase_order(
        db,
        shop_id=user.shop_id,
        po_id=po_id,
        received_lines={
            line.sku_id: (line.received_qty, line.received_unit_cost)
            for line in payload.lines
        },
        received_at=payload.received_at,
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    record_audit_event(
        db,
        shop_id=user.shop_id,
        user_id=user.id,
        event_type="purchase_order_received",
        entity_type="purchase_order",
        entity_id=po.po_id,
        summary=f"Receipt recorded for purchase order {po.po_id}.",
        metadata={
            "vendor": po.vendor,
            "received_lines": [line.model_dump() for line in payload.lines],
            "status": po.status,
        },
    )
    return PurchaseOrderStatusResponse(po=po)
