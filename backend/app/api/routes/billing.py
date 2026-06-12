"""Billing API — Checkout sessions, Customer Portal, subscription summary."""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.services.billing import (
    create_portal_session,
    current_entitlements_summary,
    current_subscription_summary,
    handle_webhook_event,
    is_configured,
    verify_webhook_signature,
)
from app.services.shopify_billing import (
    ShopifyBillingAuthError,
    create_shopify_subscription,
    has_active_shopify_connection,
)


router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str = Field(description="Internal plan key, e.g. 'growth_monthly'.")


class CheckoutResponse(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutResponse)
def start_checkout(
    payload: CheckoutRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> CheckoutResponse:
    # Stripe checkout is retired: skubase is distributed through the Shopify
    # App Store, and Shopify requires app charges to go through its Billing
    # API. Existing Stripe subscriptions keep working via the webhook/portal.
    if has_active_shopify_connection(db, shop_id=user.shop_id):
        return start_shopify_subscription(payload, user, db)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "skubase subscriptions are billed through Shopify. Connect your "
            "Shopify store on the Store Sync page, then choose a plan."
        ),
    )


class PortalResponse(BaseModel):
    url: str


@router.post("/portal", response_model=PortalResponse)
def open_portal(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> PortalResponse:
    if has_active_shopify_connection(db, shop_id=user.shop_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Billing for this store is managed through Shopify.",
        )
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not yet enabled.",
        )
    try:
        url = create_portal_session(db, user=user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PortalResponse(url=url)


@router.get("/me")
def my_subscription(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> dict:
    # The billing page is where merchants look right after changing plans —
    # always show live Shopify status here, never a cached snapshot.
    return current_subscription_summary(db, user=user, fresh_shopify=True)


@router.get("/entitlements")
def my_entitlements(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
    fresh: bool = False,
) -> dict:
    # `fresh=1` bypasses the short-TTL Shopify billing cache — the billing
    # page uses it so a just-approved plan change shows immediately.
    return current_entitlements_summary(db, user=user, fresh_shopify=fresh)


@router.post("/shopify/subscribe", response_model=CheckoutResponse)
def start_shopify_subscription(
    payload: CheckoutRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> CheckoutResponse:
    """Create a Shopify app subscription and return its confirmation URL.

    The frontend redirects the merchant (top-level, out of the iframe) to the
    confirmation URL where Shopify hosts charge approval; Shopify then sends
    them back into the embedded app's billing page.
    """
    if not has_active_shopify_connection(db, shop_id=user.shop_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Connect your Shopify store on the Store Sync page before "
                "choosing a plan."
            ),
        )
    try:
        url = create_shopify_subscription(db, user=user, plan=payload.plan)
    except ShopifyBillingAuthError as exc:
        # Stored Admin API token went stale (e.g. app reinstalled). The
        # frontend reacts to 409 by sending the merchant back through OAuth.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Shopify no longer accepts this store's access token. "
                "Re-authorize skubase to continue."
            ),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CheckoutResponse(url=url)


# Stripe webhook — separate prefix so signature verification is clean.
webhook_router = APIRouter(prefix="/stripe", tags=["stripe"])


@webhook_router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict:
    payload = await request.body()
    event = verify_webhook_signature(
        payload=payload,
        signature_header=stripe_signature or "",
    )
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    try:
        handle_webhook_event(db, event=event)
    except Exception as exc:
        # Log, but return 200 so Stripe doesn't retry indefinitely on bugs.
        import logging
        logging.getLogger(__name__).exception("Webhook handler failed: %s", exc)
    return {"received": True}
