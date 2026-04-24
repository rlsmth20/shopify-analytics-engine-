from fastapi import APIRouter

from app.mock_data import MOCK_SKUS
from app.mock_data_v2 import daily_history_for_sku
from app.schemas_v2 import ScorecardResponse
from app.services.abc_analysis import build_scorecards


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/scorecards", response_model=ScorecardResponse)
def read_scorecards() -> ScorecardResponse:
    cards = build_scorecards(MOCK_SKUS, daily_history_for_sku)
    return ScorecardResponse(
        scorecards=cards,
        a_count=sum(1 for c in cards if c.abc_class == "A"),
        b_count=sum(1 for c in cards if c.abc_class == "B"),
        c_count=sum(1 for c in cards if c.abc_class == "C"),
    )
