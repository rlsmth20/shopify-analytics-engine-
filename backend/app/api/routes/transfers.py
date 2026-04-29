from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_active_access
from app.db.models import User
from app.schemas_v2 import TransferRecommendationsResponse


router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=TransferRecommendationsResponse)
def read_transfer_recommendations(
    user: Annotated[User, Depends(require_active_access)],
) -> TransferRecommendationsResponse:
    # Multi-location transfer recommendations require per-location inventory
    # data which CSV importers don't yet split. Return empty until
    # Shopify-OAuth-driven multi-location ingestion lands in Phase 3.
    return TransferRecommendationsResponse(transfers=[])
