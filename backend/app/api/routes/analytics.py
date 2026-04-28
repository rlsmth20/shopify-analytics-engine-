from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import ScorecardResponse
from app.services.abc_analysis import build_scorecards
from app.services.shop_skus import (
    load_daily_history_for_shop_sku,
    load_skus_for_shop,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/scorecards", response_model=ScorecardResponse)
def read_scorecards(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> ScorecardResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return ScorecardResponse(scorecards=[], a_count=0, b_count=0, c_count=0)
    cards = build_scorecards(
        skus,
        lambda sku_id: load_daily_history_for_shop_sku(db, user.shop_id, sku_id, 90),
    )
    return ScorecardResponse(
        scorecards=cards,
        a_count=sum(1 for c in cards if c.abc_class == "A"),
        b_count=sum(1 for c in cards if c.abc_class == "B"),
        c_count=sum(1 for c in cards if c.abc_class == "C"),
    )
