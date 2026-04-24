from fastapi import APIRouter

from app.mock_data import MOCK_SKUS
from app.schemas_v2 import LiquidationResponse
from app.services.dead_stock import build_liquidation_plan


router = APIRouter(prefix="/liquidation", tags=["liquidation"])


@router.get("", response_model=LiquidationResponse)
def read_liquidation_plan() -> LiquidationResponse:
    suggestions = build_liquidation_plan(MOCK_SKUS)
    total = sum(s.projected_recovered_capital for s in suggestions)
    return LiquidationResponse(
        total_capital_recoverable=round(total, 2),
        suggestions=suggestions,
    )
