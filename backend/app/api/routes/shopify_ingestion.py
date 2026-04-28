"""Shopify integration — OAuth install/callback + manual sync trigger."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.services.shopify_oauth import (
    build_install_url,
    consume_oauth_state,
    exchange_code_for_token,
    is_configured,
    issue_oauth_state,
    normalize_shop_domain,
    persist_connection,
    verify_callback_hmac,
)


router = APIRouter(prefix="/integrations/shopify", tags=["shopify"])


@router.get("/install")
def install(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
    shop: str = Query(..., description="The merchant's myshopify domain (e.g. yourshop.myshopify.com)."),
) -> dict:
    """Return the Shopify authorize URL the user should be redirected to."""
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify integration is not yet enabled.",
        )
    shop_domain = normalize_shop_domain(shop)
    if shop_domain is None:
        raise HTTPException(status_code=400, detail="Invalid Shopify domain.")
    state = issue_oauth_state(db, user=user, shop_domain=shop_domain)
    try:
        url = build_install_url(shop_domain=shop_domain, state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"authorize_url": url}


@router.get("/callback")
def callback(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> RedirectResponse:
    """Final leg of OAuth — Shopify redirects the merchant here."""
    qs = dict(request.query_params)
    if not verify_callback_hmac(qs):
        raise HTTPException(status_code=400, detail="Invalid Shopify HMAC signature.")

    state = qs.get("state", "")
    code = qs.get("code", "")
    shop = qs.get("shop", "")
    shop_domain = normalize_shop_domain(shop)
    if not state or not code or shop_domain is None:
        raise HTTPException(status_code=400, detail="Missing OAuth parameters.")

    resolved = consume_oauth_state(db, raw_state=state)
    if resolved is None:
        raise HTTPException(status_code=400, detail="OAuth state expired or invalid.")
    user_id, expected_shop_domain = resolved
    if expected_shop_domain != shop_domain:
        raise HTTPException(status_code=400, detail="Shop domain mismatch.")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    payload = exchange_code_for_token(shop_domain=shop_domain, code=code)
    if payload is None or "access_token" not in payload:
        raise HTTPException(status_code=400, detail="Could not exchange code for token.")

    persist_connection(
        db,
        shop_id=user.shop_id,
        shop_domain=shop_domain,
        access_token=payload["access_token"],
        scope=payload.get("scope", ""),
    )

    # Send the merchant back into the app shell.
    import os
    frontend = os.getenv("FRONTEND_ORIGIN", "https://skubase.io").rstrip("/")
    return RedirectResponse(url=f"{frontend}/store-sync?connected=1", status_code=302)


@router.get("/connection")
def my_connection(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> dict:
    """Return whether the current user's shop has an active Shopify connection."""
    from sqlalchemy import select
    from app.db.models import ShopifyConnection

    conn = db.scalar(
        select(ShopifyConnection).where(ShopifyConnection.shop_id == user.shop_id)
    )
    if conn is None or conn.uninstalled_at is not None:
        return {
            "connected": False,
            "shopify_domain": None,
            "last_sync_at": None,
            "scope": None,
        }
    return {
        "connected": True,
        "shopify_domain": conn.shopify_domain,
        "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        "scope": conn.scope,
    }


@router.post("/sync")
def trigger_sync(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> dict:
    """Run a one-shot ingestion against this shop's Shopify connection."""
    from app.services.shopify_sync import sync_shop_now

    try:
        result = sync_shop_now(db, shop_id=user.shop_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
