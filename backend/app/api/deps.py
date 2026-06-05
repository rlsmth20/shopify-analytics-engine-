"""Reusable FastAPI dependencies for authentication and DB session."""
from __future__ import annotations

import logging
from typing import Annotated, Callable, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Subscription, User
from app.db.session import get_db_session
from app.services.auth import SESSION_COOKIE_NAME, resolve_session
from app.services.plan_entitlements import FeatureKey, plan_allows_feature
from app.services.shopify_session_tokens import (
    ShopifySessionTokenError,
    resolve_user_from_shopify_session_token,
)

logger = logging.getLogger(__name__)


def get_current_user(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    """Require a valid session cookie. 401 if missing or invalid.

    Use as a FastAPI dependency on any route that should be auth-gated:
        @router.get("/some-private")
        def handler(user: User = Depends(get_current_user)): ...
    """
    bearer = _bearer_token(request)
    if bearer:
        try:
            user = resolve_user_from_shopify_session_token(db, bearer)
        except ShopifySessionTokenError as exc:
            logger.info(
                "auth_me_failed reason=invalid_shopify_session_token origin=%s error=%s",
                request.headers.get("origin"),
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Shopify session token.",
            ) from exc
        if user is not None:
            return user
        logger.info(
            "auth_me_failed reason=shopify_session_not_installed origin=%s",
            request.headers.get("origin"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Shopify app is not installed for this shop.",
        )

    if not session_token:
        logger.info(
            "auth_me_failed reason=missing_cookie origin=%s",
            request.headers.get("origin"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    user = resolve_session(db, raw_token=session_token)
    if user is None:
        logger.info(
            "auth_me_failed reason=invalid_session origin=%s",
            request.headers.get("origin"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
        )
    return user


def get_optional_user(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> Optional[User]:
    """Same as get_current_user but returns None instead of 401."""
    bearer = _bearer_token(request)
    if bearer:
        try:
            return resolve_user_from_shopify_session_token(db, bearer)
        except ShopifySessionTokenError:
            return None
    if not session_token:
        return None
    return resolve_session(db, raw_token=session_token)


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an authenticated user with is_admin=True."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


def require_active_access(
    db: Annotated[DbSession, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an active trial or paid subscription.

    Returns the user if access is granted. Raises HTTP 402 if:
    - No trial (trial_ends_at is None or has passed), AND
    - No active Stripe subscription for the shop.

    Admin users always pass (useful for support access).
    """
    if user.is_admin:
        return user

    from datetime import datetime, timedelta, timezone

    # Check trial window. Backfill trial_ends_at for accounts created before
    # the column was added — they get a fresh 14-day window on first access.
    trial_ends = user.trial_ends_at
    if trial_ends is None:
        trial_ends = datetime.now(timezone.utc) + timedelta(days=14)
        user.trial_ends_at = trial_ends
        db.add(user)
        db.commit()

    if trial_ends.tzinfo is None:
        trial_ends = trial_ends.replace(tzinfo=timezone.utc)
    if trial_ends > datetime.now(timezone.utc):
        return user  # still in trial

    from app.services.shopify_billing import (
        current_shopify_subscription_summary,
        has_active_shopify_connection,
    )

    if has_active_shopify_connection(db, shop_id=user.shop_id):
        shopify_sub = current_shopify_subscription_summary(db, user=user)
        if shopify_sub.get("status") in ("active", "trialing"):
            return user

    # Check paid subscription. Accept both active and trialing Stripe states.
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if sub is not None and sub.status in ("active", "trialing"):
        return user

    from app.services.billing import reconcile_subscription_from_stripe

    reconciled = reconcile_subscription_from_stripe(db, user=user)
    if reconciled is not None and reconciled.status in ("active", "trialing"):
        return user

    raise HTTPException(
        status_code=402,
        detail="Your trial has ended. Subscribe to continue using skubase.",
    )


def require_plan_feature(feature: FeatureKey) -> Callable[..., User]:
    """Require active access plus a paid plan that includes a feature.

    Trial users get full product access so they can evaluate higher-tier
    workflows before choosing a plan.
    """

    def dependency(
        db: Annotated[DbSession, Depends(get_db_session)],
        user: Annotated[User, Depends(require_active_access)],
    ) -> User:
        if user.is_admin:
            return user

        from datetime import datetime, timezone
        from app.services.shopify_billing import (
            current_shopify_subscription_summary,
            has_active_shopify_connection,
        )

        is_shopify_installed = has_active_shopify_connection(db, shop_id=user.shop_id)
        if not is_shopify_installed:
            trial_ends = user.trial_ends_at
            if trial_ends is not None:
                if trial_ends.tzinfo is None:
                    trial_ends = trial_ends.replace(tzinfo=timezone.utc)
                if trial_ends > datetime.now(timezone.utc):
                    return user

        if is_shopify_installed:
            shopify_sub = current_shopify_subscription_summary(db, user=user)
            if shopify_sub.get("status") in ("active", "trialing"):
                if plan_allows_feature(str(shopify_sub.get("plan") or "none"), feature):
                    return user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your current Shopify plan does not include this feature. Upgrade to continue.",
            )

        sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
        if sub is not None and sub.status in ("active", "trialing"):
            if plan_allows_feature(sub.plan, feature):
                return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your current plan does not include this feature. Upgrade to continue.",
        )

    return dependency
