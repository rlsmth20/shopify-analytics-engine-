"""ShipStation CSV importer route."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.shipstation_import import (
    ShipStationImportError,
    ShipStationImportResult,
    import_shipstation_csv,
)


router = APIRouter(prefix="/integrations/shipstation", tags=["shipstation"])


@router.post("/import")
async def import_shipstation(
    shopify_domain: str = Form(...),
    csv_file: UploadFile = File(...),
) -> dict:
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await csv_file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV is larger than 50 MB.")

    try:
        result: ShipStationImportResult = import_shipstation_csv(
            shopify_domain=shopify_domain,
            csv_bytes=raw,
        )
    except ShipStationImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "shop_id": result.shop_id,
        "shopify_domain": result.shopify_domain,
        "rows_processed": result.rows_processed,
        "line_items_inserted": result.line_items_inserted,
        "rows_skipped": result.rows_skipped,
        "skip_reasons": result.skip_reasons,
        "distinct_skus": result.distinct_skus,
        "earliest_ship_date": result.earliest_ship_date,
        "latest_ship_date": result.latest_ship_date,
        "top_skus_by_velocity": [
            {
                "sku": v.sku,
                "units_30d": v.units_30d,
                "units_90d": v.units_90d,
                "units_180d": v.units_180d,
                "daily_average_180d": v.daily_average_180d,
            }
            for v in result.top_skus_by_velocity
        ],
    }
