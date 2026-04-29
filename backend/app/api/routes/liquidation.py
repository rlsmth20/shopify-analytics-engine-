from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import LiquidationResponse
from app.services.dead_stock import build_liquidation_plan
from app.services.shop_skus import load_skus_for_shop


router = APIRouter(prefix="/liquidation", tags=["liquidation"])


@router.get("", response_model=LiquidationResponse)
def read_liquidation_plan(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> LiquidationResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return LiquidationResponse(total_capital_recoverable=0.0, suggestions=[])
    suggestions = build_liquidation_plan(skus)
    total = sum(s.projected_recovered_capital for s in suggestions)
    return LiquidationResponse(
        total_capital_recoverable=round(total, 2),
        suggestions=suggestions,
    )
