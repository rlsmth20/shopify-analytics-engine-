"""ShipStation CSV importer route — scoped to the authenticated user's shop."""
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DbSession

from app.api.deps import require_active_access
from app.db.models import Shop, User
from app.db.session import get_db_session
from app.services.shipstation_import import (
    ShipStationImportError,
    ShipStationImportResult,
    import_shipstation_csv,
)


router = APIRouter(prefix="/integrations/shipstation", tags=["shipstation"])


@router.post("/import")
async def import_shipstation(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
    csv_file: UploadFile = File(...),
    source_scope: Annotated[Literal["unknown", "non_shopify"], Form()] = "unknown",
) -> dict:
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await csv_file.read(50 * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV is larger than 50 MB.")

    shop = db.get(Shop, user.shop_id)
    if shop is None:
        raise HTTPException(status_code=400, detail="Workspace shop not found.")

    try:
        result: ShipStationImportResult = import_shipstation_csv(
            shopify_domain=shop.shopify_domain,
            csv_bytes=raw,
            source_scope=source_scope,
            shop_id=user.shop_id,
        )
    except ShipStationImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return asdict(result)
