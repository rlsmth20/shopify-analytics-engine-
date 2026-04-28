"""Shopify ingestion route — auth-gated. Manual sync trigger placeholder."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.db.models import User
from app.schemas import ShopifyIngestionRequest, ShopifyIngestionResponse


router = APIRouter(prefix="/integrations/shopify", tags=["shopify"])


@router.post("/ingest", response_model=ShopifyIngestionResponse)
def ingest_from_shopify(
    payload: ShopifyIngestionRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> ShopifyIngestionResponse:
    # OAuth-driven ingestion ships in Phase 3. The endpoint stays so the
    # frontend can reach it and surface the "not yet wired" state cleanly.
    raise HTTPException(
        status_code=501,
        detail="Shopify OAuth ingestion is not yet available. Use the CSV importers for now.",
    )
