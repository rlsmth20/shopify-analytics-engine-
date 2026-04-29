from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import BundleHealthResponse
from app.services.bundle_analyzer import DEMO_BUNDLES, analyze_bundles
from app.services.shop_skus import load_skus_for_shop


router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("", response_model=BundleHealthResponse)
def read_bundle_health(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> BundleHealthResponse:
    skus = load_skus_for_shop(db, user.shop_id)
    if not skus:
        return BundleHealthResponse(bundles=[])
    bundles = analyze_bundles(DEMO_BUNDLES, skus)
    return BundleHealthResponse(bundles=bundles)
