from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_plan_feature
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import TransferRecommendationsResponse
from app.services.shop_skus import load_location_stocks_for_shop
from app.services.transfers import recommend_transfers


router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=TransferRecommendationsResponse)
def read_transfer_recommendations(
    user: Annotated[User, Depends(require_plan_feature("transfers"))],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> TransferRecommendationsResponse:
    snapshots = load_location_stocks_for_shop(db, user.shop_id)
    return TransferRecommendationsResponse(transfers=recommend_transfers(snapshots))
