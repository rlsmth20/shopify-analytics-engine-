from fastapi import APIRouter, HTTPException

from app.mock_data import get_sku, list_skus
from app.schemas import SkuDetail


router = APIRouter(prefix="/skus", tags=["skus"])


@router.get("", response_model=list[SkuDetail])
def read_skus() -> list[SkuDetail]:
    return list_skus()


@router.get("/{sku_id}", response_model=SkuDetail)
def read_sku(sku_id: str) -> SkuDetail:
    sku = get_sku(sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' was not found.")

    return sku
