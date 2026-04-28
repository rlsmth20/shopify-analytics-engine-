"""Stocky CSV importer route — scoped to the authenticated user's shop."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import Shop, User
from app.db.session import get_db_session
from app.services.stocky_import import (
    StockyImportError,
    StockyImportResult,
    import_stocky_products_csv,
)


router = APIRouter(prefix="/integrations/stocky", tags=["stocky"])


@router.post("/import")
async def import_stocky_csv(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
    csv_file: UploadFile = File(...),
) -> dict:
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await csv_file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV is larger than 25 MB.")

    shop = db.get(Shop, user.shop_id)
    if shop is None:
        raise HTTPException(status_code=400, detail="Workspace shop not found.")

    try:
        result: StockyImportResult = import_stocky_products_csv(
            shopify_domain=shop.shopify_domain,
            csv_bytes=raw,
        )
    except StockyImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "shop_id": result.shop_id,
        "shopify_domain": result.shopify_domain,
        "products_processed": result.products_processed,
        "products_inserted": result.products_inserted,
        "products_updated": result.products_updated,
        "inventory_rows_inserted": result.inventory_rows_inserted,
        "rows_skipped": result.rows_skipped,
        "skip_reasons": result.skip_reasons,
    }
