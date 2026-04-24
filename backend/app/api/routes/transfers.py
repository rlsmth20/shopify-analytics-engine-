from fastapi import APIRouter

from app.schemas_v2 import TransferRecommendationsResponse
from app.services.transfers import DEMO_LOCATION_STOCKS, recommend_transfers


router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=TransferRecommendationsResponse)
def read_transfer_recommendations() -> TransferRecommendationsResponse:
    transfers = recommend_transfers(DEMO_LOCATION_STOCKS)
    return TransferRecommendationsResponse(transfers=transfers)
