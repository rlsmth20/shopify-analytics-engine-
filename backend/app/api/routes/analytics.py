from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import (
    InventoryHealthResponse,
    InventoryValueHistoryResponse,
    InventoryValuePoint,
    ScorecardResponse,
)
from app.services.abc_analysis import build_scorecards
from app.services.inventory_value import (
    capture_inventory_value_snapshot,
    inventory_value_history,
)
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_health import build_inventory_health
from app.services.shop_skus import (
    load_daily_history_for_shop_skus,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/scorecards", response_model=ScorecardResponse)
def read_scorecards(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ScorecardResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return ScorecardResponse(scorecards=[], a_count=0, b_count=0, c_count=0)
    histories = load_daily_history_for_shop_skus(
        db,
        user.shop_id,
        [sku.sku_id for sku in skus],
        90,
    )
    cards = build_scorecards(
        skus,
        lambda sku_id: histories.get(sku_id, []),
    )
    return ScorecardResponse(
        scorecards=cards,
        a_count=sum(1 for c in cards if c.abc_class == "A"),
        b_count=sum(1 for c in cards if c.abc_class == "B"),
        c_count=sum(1 for c in cards if c.abc_class == "C"),
    )


@router.get("/inventory-value", response_model=InventoryValueHistoryResponse)
def read_inventory_value_history(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    days: int = Query(90, ge=7, le=365),
) -> InventoryValueHistoryResponse:
    """Inventory value over time — Shopify has no native equivalent."""
    # Ensure today's point exists so a freshly-synced shop sees data at once.
    capture_inventory_value_snapshot(db, shop_id=user.shop_id)
    points = inventory_value_history(db, shop_id=user.shop_id, days=days)
    latest_cost = points[-1]["cost_value"] if points else 0.0
    latest_retail = points[-1]["retail_value"] if points else 0.0
    change_30d = None
    if len(points) > 1:
        baseline = points[max(0, len(points) - 31)]["cost_value"]
        if baseline > 0:
            change_30d = round((latest_cost - baseline) / baseline * 100, 1)
    return InventoryValueHistoryResponse(
        points=[InventoryValuePoint(**point) for point in points],
        latest_cost_value=latest_cost,
        latest_retail_value=latest_retail,
        change_30d_pct=change_30d,
    )


@router.get("/inventory-health", response_model=InventoryHealthResponse)
def read_inventory_health(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> InventoryHealthResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return build_inventory_health(skus=[], forecasts=[])

    start_weekday = start_weekday_for_shop_history(db, user.shop_id, days=90)
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
    return build_inventory_health(skus=skus, forecasts=forecasts)
