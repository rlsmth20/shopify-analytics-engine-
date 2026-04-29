from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import ForecastFeedResponse, ForecastResult
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.shop_skus import (
    load_daily_history_for_shop_sku,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)


router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("", response_model=ForecastFeedResponse)
def list_forecasts(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    horizon_days: int = 30,
) -> ForecastFeedResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return ForecastFeedResponse(forecasts=[])
    start_weekday = start_weekday_for_shop_history(db, user.shop_id, days=90)
    forecasts: list[ForecastResult] = []
    for sku in skus:
        history = load_daily_history_for_shop_sku(db, user.shop_id, sku.sku_id, 90)
        forecasts.append(
            forecast_sku(
                ForecastInputs(
                    sku_id=sku.sku_id,
                    daily_history=history,
                    on_hand=sku.inventory,
                    start_weekday=start_weekday,
                ),
                horizon_days=horizon_days,
            )
        )
    forecasts.sort(key=lambda f: f.stockout_probability_30d, reverse=True)
    return ForecastFeedResponse(forecasts=forecasts)


@router.get("/{sku_id}", response_model=ForecastResult)
def get_forecast(
    sku_id: str,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    horizon_days: int = 30,
) -> ForecastResult:
    skus = load_skus_for_shop(db, user.shop_id)
    sku = next((s for s in skus if s.sku_id == sku_id), None)
    if sku is None:
        raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' not found.")
    history = load_daily_history_for_shop_sku(db, user.shop_id, sku_id, 90)
    return forecast_sku(
        ForecastInputs(
            sku_id=sku_id,
            daily_history=history,
            on_hand=sku.inventory,
            start_weekday=start_weekday_for_shop_history(db, user.shop_id, 90),
        ),
        horizon_days=horizon_days,
    )
