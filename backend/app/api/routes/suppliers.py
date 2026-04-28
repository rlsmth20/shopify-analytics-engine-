from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import SupplierScoreboardResponse
from app.services.shop_skus import load_skus_for_shop
from app.services.supplier_scoring import build_supplier_scorecards


router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=SupplierScoreboardResponse)
def read_supplier_scoreboard(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> SupplierScoreboardResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return SupplierScoreboardResponse(vendors=[])
    # Until real PO/receipt data exists, supplier observations are empty;
    # build_supplier_scorecards handles an empty observation list gracefully.
    scorecards = build_supplier_scorecards([], skus)
    return SupplierScoreboardResponse(vendors=scorecards)
