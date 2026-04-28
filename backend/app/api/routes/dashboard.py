"""Dashboard route — auth-gated, scoped to the current user's shop."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import DashboardResponse
from app.services.dashboard import build_dashboard
from app.services.shop_skus import (
    load_daily_history_for_shop_sku,
    load_recent_daily_revenue_for_shop,
    load_skus_for_shop,
    start_weekday_for_shop_history,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def read_dashboard(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> DashboardResponse:
    skus = load_skus_for_shop(db, user.shop_id)

    def daily_history(sku_id: str, days: int) -> list[int]:
        return load_daily_history_for_shop_sku(db, user.shop_id, sku_id, days)

    def recent_revenue(days: int) -> list[tuple[int, float]]:
        return load_recent_daily_revenue_for_shop(db, user.shop_id, days)

    return build_dashboard(
        skus,
        daily_history_fn=daily_history,
        recent_revenue_fn=recent_revenue,
        start_weekday=start_weekday_for_shop_history(db, user.shop_id),
    )
