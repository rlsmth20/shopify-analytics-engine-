from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import User
from app.db.session import get_db_session
from app.schemas_v2 import BundleHealthResponse


router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.get("", response_model=BundleHealthResponse)
def read_bundle_health(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> BundleHealthResponse:
    _ = (user, db)
    return BundleHealthResponse(bundles=[])
