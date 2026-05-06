from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user, require_active_access
from app.db.models import Product, User
from app.db.session import get_db_session
from app.schemas import SkuDetail
from app.services.shop_skus import load_skus_for_shop


router = APIRouter(prefix="/skus", tags=["skus"])


@router.get("", response_model=list[SkuDetail])
def read_skus(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> list[SkuDetail]:
    return load_skus_for_shop(db, user.shop_id)


@router.get("/summary")
def read_sku_summary(
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> dict[str, int]:
    product_count = db.scalar(
        select(func.count()).select_from(Product).where(Product.shop_id == user.shop_id)
    ) or 0
    return {"product_count": int(product_count)}


@router.get("/{sku_id}", response_model=SkuDetail)
def read_sku(
    sku_id: str,
    user: Annotated[User, Depends(require_active_access)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> SkuDetail:
    skus = load_skus_for_shop(db, user.shop_id)
    sku = next((s for s in skus if s.sku_id == sku_id), None)
    if sku is None:
        raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' was not found.")
    return sku
