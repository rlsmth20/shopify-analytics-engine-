from fastapi import APIRouter

from app.schemas_v2 import DashboardResponse
from app.services.dashboard import build_dashboard


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def read_dashboard() -> DashboardResponse:
    return build_dashboard()
