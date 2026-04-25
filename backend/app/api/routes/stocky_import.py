"""Stocky CSV importer route."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.stocky_import import (
    StockyImportError,
    StockyImportResult,
    import_stocky_products_csv,
)


router = APIRouter(prefix="/integrations/stocky", tags=["stocky"])


@router.post("/import")
async def import_stocky_csv(
    shopify_domain: str = Form(...),
    csv_file: UploadFile = File(...),
) -> dict:
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await csv_file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV is larger than 25 MB.")

    try:
        result: StockyImportResult = import_stocky_products_csv(
            shopify_domain=shopify_domain,
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
