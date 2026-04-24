from fastapi import APIRouter

from app.mock_data import MOCK_SKUS
from app.schemas_v2 import BundleHealthResponse
from app.services.bundle_analyzer import DEMO_BUNDLES, analyze_bundles


router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("", response_model=BundleHealthResponse)
def read_bundle_health() -> BundleHealthResponse:
    bundles = analyze_bundles(DEMO_BUNDLES, MOCK_SKUS)
    return BundleHealthResponse(bundles=bundles)
