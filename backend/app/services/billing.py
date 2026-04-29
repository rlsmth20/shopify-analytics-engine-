"""Stripe billing — Checkout sessions, webhook handlers, Customer Portal.

Designed to fail closed: if STRIPE_SECRET_KEY isn't set, all billing routes
return 503 with a clear message. The webhook handler verifies signatures
when STRIPE_WEBHOOK_SECRET is configured.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Shop, Subscription, User

logger = logging.getLogger(__name__)


# Map our internal plan name to a Stripe Price ID set via env vars.
# The user creates the Products in the Stripe dashboard and pastes the
# price IDs into Railway. No Price ID == that tier is unavailable.
PRICE_IDS = {
    "starter_monthly": os.getenv("STRIPE_PRICE_STARTER_MONTHLY", ""),
    "growth_monthly": os.getenv("STRIPE_PRICE_GROWTH_MONTHLY", ""),
    "scale_monthly": os.getenv("STRIPE_PRICE_SCALE_MONTHLY", ""),
    "starter_annual": os.getenv("STRIPE_PRICE_STARTER_ANNUAL", ""),
    "growth_annual": os.getenv("STRIPE_PRICE_GROWTH_ANNUAL", ""),
    "scale_annual": os.getenv("STRIPE_PRICE_SCALE_ANNUAL", ""),
}

# Map of Stripe Price ID back to our internal plan name. Built once.
PLAN_BY_PRICE_ID: dict[str, str] = {
    pid: name for name, pid in PRICE_IDS.items() if pid
}

FRONTEND_URL = os.getenv("FRONTEND_ORIGIN", "https://skubase.io").split(",")[0].strip().rstrip("/")


def _stripe():
    """Return the configured stripe module, or None if not set up."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        return None
    try:
        import stripe  # type: ignore
    except ImportError:
        logger.error("stripe package not installed")
        return None
    stripe.api_key = key
    return stripe


def is_configured() -> bool:
    return _stripe() is not None


def get_or_create_customer(db: DbSession, *, user: User) -> str:
    """Return the Stripe customer ID for this shop, creating it if needed."""
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is not None and sub.stripe_customer_id:
        return sub.stripe_customer_id

    stripe = _stripe()
    if stripe is None:
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing).")

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"shop_id": str(user.shop_id), "user_id": str(user.id)},
    )

    if sub is None:
        sub = Subscription(
            shop_id=user.shop_id,
            stripe_customer_id=customer.id,
            plan="none",
            status="inactive",
        )
        db.add(sub)
    else:
        sub.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def create_checkout_session(
    db: DbSession,
    *,
    user: User,
    price_id: str,
    success_path: str = "/dashboard?checkout=success",
    cancel_path: str = "/pricing?checkout=cancelled",
) -> str:
    """Create a Stripe Checkout session and return its hosted URL."""
    stripe = _stripe()
    if stripe is None:
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing).")
    if not price_id:
        raise RuntimeError("Selected plan is not available (price ID is empty).")

    customer_id = get_or_create_customer(db, user=user)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        allow_promotion_codes=True,
        success_url=f"{FRONTEND_URL}{success_path}",
        cancel_url=f"{FRONTEND_URL}{cancel_path}",
        client_reference_id=str(user.shop_id),
        subscription_data={"metadata": {"shop_id": str(user.shop_id)}},
    )
    return session.url


def create_portal_session(db: DbSession, *, user: User) -> str:
    """Create a Customer Portal session and return its URL."""
    stripe = _stripe()
    if stripe is None:
        raise RuntimeError("Stripe is not configured.")

    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is None or not sub.stripe_customer_id:
        raise RuntimeError("No Stripe customer for this shop. Subscribe first.")

    portal = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{FRONTEND_URL}/billing",
    )
    return portal.url


def handle_webhook_event(db: DbSession, *, event: dict) -> None:
    """Apply a verified Stripe webhook event to the local Subscription row."""
    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        shop_id_raw = data_object.get("client_reference_id")
        subscription_id = data_object.get("subscription")
        customer_id = data_object.get("customer")
        if not shop_id_raw or not subscription_id:
            return
        try:
            shop_id = int(shop_id_raw)
        except (ValueError, TypeError):
            return
        sub = db.scalar(select(Subscription).where(Subscription.shop_id == shop_id))
        if sub is None:
            sub = Subscription(shop_id=shop_id)
            db.add(sub)
        sub.stripe_customer_id = customer_id
        sub.stripe_subscription_id = subscription_id
        sub.status = "active"
        db.commit()
        return

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        sub_obj = data_object
        stripe_sub_id = sub_obj.get("id")
        if not stripe_sub_id:
            return
        sub = db.scalar(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        if sub is None:
            # Fallback: try matching by customer id.
            customer_id = sub_obj.get("customer")
            if customer_id:
                sub = db.scalar(
                    select(Subscription).where(Subscription.stripe_customer_id == customer_id)
                )
            if sub is None:
                return

        sub.stripe_subscription_id = stripe_sub_id
        sub.status = sub_obj.get("status", "inactive")
        sub.cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))
        period_end = sub_obj.get("current_period_end")
        if isinstance(period_end, (int, float)):
            sub.current_period_end = datetime.fromtimestamp(int(period_end), tz=timezone.utc)
        # Resolve plan from the subscription's first price.
        items = sub_obj.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            if price_id in PLAN_BY_PRICE_ID:
                sub.plan = PLAN_BY_PRICE_ID[price_id]
        db.commit()
        return


def verify_webhook_signature(*, payload: bytes, signature_header: str) -> Optional[dict]:
    """Verify the Stripe-Signature header. Returns the event dict or None."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe = _stripe()
    if stripe is None or not secret:
        # In dev / when secret isn't set, accept the payload as-is for testing.
        # Production should always have STRIPE_WEBHOOK_SECRET set.
        try:
            import json
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return None
    try:
        return stripe.Webhook.construct_event(payload, signature_header, secret)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        return None


def current_subscription_summary(db: DbSession, *, user: User) -> dict:
    """Frontend-friendly view of the current user's subscription."""
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is None:
        return {
            "plan": "none",
            "status": "inactive",
            "current_period_end": None,
            "cancel_at_period_end": False,
            "has_payment_method": False,
            "stripe_configured": is_configured(),
        }
    return {
        "plan": sub.plan,
        "status": sub.status,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "has_payment_method": bool(sub.stripe_customer_id),
        "stripe_configured": is_configured(),
    }
