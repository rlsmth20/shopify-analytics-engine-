"""Shopify Billing API support for Shopify-installed merchants."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import ShopifyConnection, Subscription, User

logger = logging.getLogger(__name__)

GRAPHQL_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-04")
FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("FRONTEND_ORIGIN", "https://skubase.io").split(",")[0]).strip().rstrip("/")
SHOPIFY_BILLING_TEST = os.getenv("SHOPIFY_BILLING_TEST", "false").lower() in {"1", "true", "yes"}

SHOPIFY_PLAN_AMOUNTS: dict[str, Decimal] = {
    "starter_monthly": Decimal("49.00"),
    "growth_monthly": Decimal("99.00"),
    "scale_monthly": Decimal("199.00"),
}

SHOPIFY_PLAN_NAMES: dict[str, str] = {
    "starter_monthly": "Skubase Starter",
    "growth_monthly": "Skubase Growth",
    "scale_monthly": "Skubase Scale",
}

SHOPIFY_PLAN_BY_NAME = {
    normalized: key
    for key, name in SHOPIFY_PLAN_NAMES.items()
    for normalized in {name.lower(), key.replace("_monthly", "").lower()}
}


def has_active_shopify_connection(db: DbSession, *, shop_id: int) -> bool:
    return _connection_for_shop(db, shop_id=shop_id) is not None


def current_shopify_subscription_summary(db: DbSession, *, user: User) -> dict:
    conn = _connection_for_shop(db, shop_id=user.shop_id)
    if conn is None:
        return {
            "billing_provider": "stripe",
            "shopify_installed": False,
        }

    active = _fetch_active_subscription(conn)
    local = _mirror_shopify_subscription(db, user=user, active_subscription=active)
    return {
        "billing_provider": "shopify",
        "shopify_installed": True,
        "plan": local.plan if local else "none",
        "status": local.status if local else "inactive",
        "current_period_end": local.current_period_end.isoformat() if local and local.current_period_end else None,
        "cancel_at_period_end": False,
        "has_payment_method": bool(local and local.status in {"active", "trialing"}),
        "stripe_configured": False,
        "shopify_billing_test": SHOPIFY_BILLING_TEST,
    }


def create_shopify_subscription(db: DbSession, *, user: User, plan: str) -> str:
    conn = _connection_for_shop(db, shop_id=user.shop_id)
    if conn is None:
        raise RuntimeError("No active Shopify connection for this workspace.")
    plan = plan.replace("_annual", "_monthly")
    if plan not in SHOPIFY_PLAN_AMOUNTS:
        raise RuntimeError(f"Unknown Shopify billing plan '{plan}'.")

    return_url = _return_url(conn.shopify_domain)
    variables = {
        "name": SHOPIFY_PLAN_NAMES[plan],
        "returnUrl": return_url,
        "trialDays": 14,
        "test": SHOPIFY_BILLING_TEST,
        "lineItems": [
            {
                "plan": {
                    "appRecurringPricingDetails": {
                        "price": {
                            "amount": str(SHOPIFY_PLAN_AMOUNTS[plan]),
                            "currencyCode": "USD",
                        },
                        "interval": "EVERY_30_DAYS",
                    }
                }
            }
        ],
    }
    payload = _gql(conn, APP_SUBSCRIPTION_CREATE, variables)
    result = ((payload.get("data") or {}).get("appSubscriptionCreate") or {})
    errors = result.get("userErrors") or []
    if errors:
        message = "; ".join(str(error.get("message", "")) for error in errors)
        raise RuntimeError(message or "Shopify could not create the app subscription.")
    confirmation_url = result.get("confirmationUrl")
    if not confirmation_url:
        raise RuntimeError("Shopify did not return a billing confirmation URL.")
    return str(confirmation_url)


def _connection_for_shop(db: DbSession, *, shop_id: int) -> ShopifyConnection | None:
    return db.scalar(
        select(ShopifyConnection).where(
            ShopifyConnection.shop_id == shop_id,
            ShopifyConnection.uninstalled_at.is_(None),
        )
    )


def _fetch_active_subscription(conn: ShopifyConnection) -> dict[str, Any] | None:
    payload = _gql(conn, CURRENT_APP_INSTALLATION_QUERY, {})
    subscriptions = (
        ((payload.get("data") or {}).get("currentAppInstallation") or {}).get("activeSubscriptions")
        or []
    )
    if not subscriptions:
        return None
    return subscriptions[0]


def _mirror_shopify_subscription(
    db: DbSession,
    *,
    user: User,
    active_subscription: dict[str, Any] | None,
) -> Subscription | None:
    sub = db.scalar(select(Subscription).where(Subscription.shop_id == user.shop_id))
    if active_subscription is None:
        if sub is None:
            return None
        if sub.stripe_subscription_id and str(sub.stripe_subscription_id).startswith("shopify:"):
            sub.status = "inactive"
            sub.plan = "none"
            db.commit()
        return sub

    if sub is None:
        sub = Subscription(shop_id=user.shop_id)
        db.add(sub)

    sub.stripe_subscription_id = f"shopify:{active_subscription.get('id', '')}"
    sub.status = _normalize_shopify_status(str(active_subscription.get("status") or "inactive"))
    sub.plan = _plan_from_shopify_subscription(active_subscription)
    sub.cancel_at_period_end = False
    current_period_end = active_subscription.get("currentPeriodEnd")
    if current_period_end:
        try:
            sub.current_period_end = datetime.fromisoformat(str(current_period_end).replace("Z", "+00:00"))
        except ValueError:
            sub.current_period_end = None
    db.commit()
    db.refresh(sub)
    return sub


def _plan_from_shopify_subscription(subscription: dict[str, Any]) -> str:
    name = str(subscription.get("name") or "").lower()
    if name in SHOPIFY_PLAN_BY_NAME:
        return SHOPIFY_PLAN_BY_NAME[name]
    for line_item in subscription.get("lineItems", []) or []:
        plan = ((line_item.get("plan") or {}).get("pricingDetails") or {})
        price = ((plan.get("price") or {}).get("amount"))
        if price is None:
            continue
        try:
            amount = Decimal(str(price)).quantize(Decimal("0.01"))
        except Exception:
            continue
        for key, expected in SHOPIFY_PLAN_AMOUNTS.items():
            if amount == expected:
                return key
    return "none"


def _normalize_shopify_status(status: str) -> str:
    lowered = status.lower()
    if lowered == "active":
        return "active"
    if lowered in {"pending", "accepted"}:
        return "trialing"
    if lowered == "cancelled":
        return "canceled"
    return lowered or "inactive"


def _return_url(shopify_domain: str) -> str:
    params = urlencode({"shop": shopify_domain, "billing": "approved"})
    return f"{FRONTEND_URL}/billing?{params}"


def _gql(conn: ShopifyConnection, query: str, variables: dict[str, Any]) -> dict:
    url = f"https://{conn.shopify_domain}/admin/api/{GRAPHQL_VERSION}/graphql.json"
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": conn.access_token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body_preview = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body_preview = "<unavailable>"
        logger.error("Shopify billing HTTP error code=%s body=%s", exc.code, body_preview)
        raise RuntimeError(f"Shopify billing request failed: {exc.code} {exc.reason}") from exc
    if payload.get("errors"):
        raise RuntimeError(f"Shopify billing GraphQL error: {payload['errors']}")
    return payload


CURRENT_APP_INSTALLATION_QUERY = """
query CurrentAppInstallation {
  currentAppInstallation {
    activeSubscriptions {
      id
      name
      status
      currentPeriodEnd
      trialDays
      lineItems {
        id
        plan {
          pricingDetails {
            ... on AppRecurringPricing {
              interval
              price { amount currencyCode }
            }
          }
        }
      }
    }
  }
}
"""


APP_SUBSCRIPTION_CREATE = """
mutation AppSubscriptionCreate(
  $name: String!
  $lineItems: [AppSubscriptionLineItemInput!]!
  $returnUrl: URL!
  $trialDays: Int
  $test: Boolean
) {
  appSubscriptionCreate(
    name: $name
    returnUrl: $returnUrl
    lineItems: $lineItems
    trialDays: $trialDays
    test: $test
    replacementBehavior: APPLY_IMMEDIATELY
  ) {
    userErrors { field message }
    appSubscription { id status }
    confirmationUrl
  }
}
"""
