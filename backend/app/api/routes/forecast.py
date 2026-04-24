from fastapi import APIRouter

from app.mock_data import MOCK_SKUS
from app.mock_data_v2 import daily_history_for_sku, start_weekday_for_history
from app.schemas_v2 import ForecastFeedResponse, ForecastResult
from app.services.forecasting import ForecastInputs, forecast_sku


router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("", response_model=ForecastFeedResponse)
def list_forecasts(horizon_days: int = 30) -> ForecastFeedResponse:
    forecasts: list[ForecastResult] = []
    start_weekday = start_weekday_for_history()
    for sku in MOCK_SKUS:
        history = daily_history_for_sku(sku.sku_id, days=90)
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
def get_forecast(sku_id: str, horizon_days: int = 30) -> ForecastResult:
    sku = next((s for s in MOCK_SKUS if s.sku_id == sku_id), None)
    history = daily_history_for_sku(sku_id, days=90)
    on_hand = sku.inventory if sku else 0
    return forecast_sku(
        ForecastInputs(
            sku_id=sku_id,
            daily_history=history,
            on_hand=on_hand,
            start_weekday=start_weekday_for_history(),
        ),
        horizon_days=horizon_days,
    )
