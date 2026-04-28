"""Shopify OAuth — install URL builder, code exchange, signature verification.

The OAuth flow is:
  1. Merchant clicks "Connect Shopify" in our app.
  2. We send them to https://{shop}.myshopify.com/admin/oauth/authorize?...
  3. They approve; Shopify redirects to our /integrations/shopify/callback
     with a `code`, `shop`, and `hmac` parameter.
  4. We verify the HMAC and exchange the code for an access token.
  5. We persist the token on a ShopifyConnection row tied to the user's shop.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_module
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import urllib.error
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Shop, ShopifyConnection, User

logger = logging.getLogger(__name__)


SCOPES = "read_products,read_inventory,read_orders,read_locations"

FRONTEND_URL = os.getenv("FRONTEND_ORIGIN", "https://slelfly.com").rstrip("/")
BACKEND_URL = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")


def is_configured() -> bool:
    return bool(os.getenv("SHOPIFY_API_KEY") and os.getenv("SHOPIFY_API_SECRET"))


def normalize_shop_domain(shop: str) -> Optional[str]:
    """Return a normalized myshopify.com domain or None if invalid."""
    if not shop:
        return None
    s = shop.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    if s.endswith(".myshopify.com"):
        # Validate the prefix is a slug.
        slug = s[: -len(".myshopify.com")]
        if slug and all(c.isalnum() or c == "-" for c in slug):
            return s
        return None
    if s and all(c.isalnum() or c == "-" for c in s):
        return f"{s}.myshopify.com"
    return None


def build_install_url(*, shop_domain: str, state: str) -> str:
    """Build the Shopify authorize URL the user is redirected to."""
    if not BACKEND_URL:
        raise RuntimeError("BACKEND_PUBLIC_URL is not set on the server.")
    api_key = os.getenv("SHOPIFY_API_KEY", "")
    if not api_key:
        raise RuntimeError("SHOPIFY_API_KEY is not set on the server.")

    redirect_uri = f"{BACKEND_URL}/integrations/shopify/callback"
    params = {
        "client_id": api_key,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "grant_options[]": "per-user",
    }
    return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"


def issue_oauth_state(db: DbSession, *, user: User, shop_domain: str) -> str:
    """Mint a one-time state token, stash it in the user's session pretext.

    Implementation note: we reuse the MagicLinkToken table for short-lived
    state — the token's email column stores the requested shop domain,
    so the callback can validate origin without adding a new table.
    """
    from app.db.models import MagicLinkToken
    from app.services.auth import _sha256

    raw = secrets.token_urlsafe(24)
    record = MagicLinkToken(
        email=f"shopify_oauth:{user.id}:{shop_domain}",
        token_hash=_sha256(raw),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10),
        used=False,
    )
    db.add(record)
    db.commit()
    return raw


def consume_oauth_state(db: DbSession, *, raw_state: str) -> Optional[tuple[int, str]]:
    """Returns (user_id, shop_domain) if the state is valid, else None."""
    from app.db.models import MagicLinkToken
    from app.services.auth import _sha256, _as_naive_utc, _now

    token_hash = _sha256(raw_state)
    record = db.scalar(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    if record is None or record.used:
        return None
    if _as_naive_utc(record.expires_at) < _now():
        return None
    if not record.email.startswith("shopify_oauth:"):
        return None
    parts = record.email.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        user_id = int(parts[1])
    except ValueError:
        return None
    shop_domain = parts[2]
    record.used = True
    db.commit()
    return user_id, shop_domain


def verify_callback_hmac(query_params: dict[str, str]) -> bool:
    """Verify the HMAC Shopify includes on every callback redirect."""
    secret = os.getenv("SHOPIFY_API_SECRET", "")
    if not secret:
        return False
    received_hmac = query_params.get("hmac")
    if not received_hmac:
        return False
    canonical = "&".join(
        f"{k}={v}" for k, v in sorted(query_params.items()) if k != "hmac"
    )
    expected = hmac_module.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac_module.compare_digest(expected, received_hmac)


def exchange_code_for_token(*, shop_domain: str, code: str) -> Optional[dict]:
    """Exchange the OAuth code for an access token via Shopify's OAuth API."""
    api_key = os.getenv("SHOPIFY_API_KEY", "")
    api_secret = os.getenv("SHOPIFY_API_SECRET", "")
    if not api_key or not api_secret:
        return None

    url = f"https://{shop_domain}/admin/oauth/access_token"
    body = urlencode({
        "client_id": api_key,
        "client_secret": api_secret,
        "code": code,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            import json as _json
            payload = _json.loads(resp.read().decode("utf-8"))
            return payload
    except urllib.error.HTTPError as exc:
        logger.error("Shopify token exchange HTTPError: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Shopify token exchange failed: %s", exc)
        return None


def persist_connection(
    db: DbSession,
    *,
    shop_id: int,
    shop_domain: str,
    access_token: str,
    scope: str,
) -> ShopifyConnection:
    """Insert or update the ShopifyConnection row for a workspace shop."""
    existing = db.scalar(
        select(ShopifyConnection).where(ShopifyConnection.shop_id == shop_id)
    )
    if existing is None:
        existing = ShopifyConnection(
            shop_id=shop_id,
            shopify_domain=shop_domain,
            access_token=access_token,
            scope=scope,
        )
        db.add(existing)
    else:
        existing.shopify_domain = shop_domain
        existing.access_token = access_token
        existing.scope = scope
        existing.uninstalled_at = None
    # Update the Shop's domain to match the merchant's actual domain so the
    # placeholder synthetic domain gets replaced once they connect.
    shop = db.get(Shop, shop_id)
    if shop is not None:
        shop.shopify_domain = shop_domain
    db.commit()
    db.refresh(existing)
    return existing
