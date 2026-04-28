"""Billing API — Checkout sessions, Customer Portal, subscription summary."""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.services.billing import (
    PRICE_IDS,
    create_checkout_session,
    create_portal_session,
    current_subscription_summary,
    handle_webhook_event,
    is_configured,
    verify_webhook_signature,
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
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not yet enabled. Please contact support.",
        )
    price_id = PRICE_IDS.get(payload.plan, "")
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan '{payload.plan}'.",
        )
    try:
        url = create_checkout_session(db, user=user, price_id=price_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CheckoutResponse(url=url)


class PortalResponse(BaseModel):
    url: str


@router.post("/portal", response_model=PortalResponse)
def open_portal(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db_session)],
) -> PortalResponse:
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
    return current_subscription_summary(db, user=user)


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
