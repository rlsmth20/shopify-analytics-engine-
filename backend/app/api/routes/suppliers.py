from fastapi import APIRouter

from app.mock_data import MOCK_SKUS
from app.mock_data_v2 import supplier_observations
from app.schemas_v2 import SupplierScoreboardResponse
from app.services.supplier_scoring import build_supplier_scorecards


router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=SupplierScoreboardResponse)
def read_supplier_scoreboard() -> SupplierScoreboardResponse:
    scorecards = build_supplier_scorecards(supplier_observations(), MOCK_SKUS)
    return SupplierScoreboardResponse(vendors=scorecards)
