from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_plan_feature
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import BundleOpportunitiesResponse, DeadStockPairingsResponse
from app.services.bundle_opportunities import (
    recommend_bundle_opportunities,
    recommend_dead_stock_pairings,
)


router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("", response_model=BundleOpportunitiesResponse)
def read_bundle_health(
    user: Annotated[User, Depends(require_plan_feature("bundle_analysis"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> BundleOpportunitiesResponse:
    opportunities, orders_analyzed = recommend_bundle_opportunities(db, user.shop_id)
    return BundleOpportunitiesResponse(
        bundles=[],
        opportunities=opportunities,
        orders_analyzed=orders_analyzed,
    )


@router.get("/dead-stock-pairings", response_model=DeadStockPairingsResponse)
def read_dead_stock_pairings(
    user: Annotated[User, Depends(require_plan_feature("bundle_analysis"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> DeadStockPairingsResponse:
    """Bundle suggestions that pair fast movers with dead stock to clear it."""
    return recommend_dead_stock_pairings(db, user.shop_id)
