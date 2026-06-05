"""Verify Shopify App Bridge session tokens for embedded app requests."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Shop, ShopifyConnection, User


class ShopifySessionTokenError(ValueError):
    """Raised when a Shopify session token cannot be trusted."""


@dataclass(frozen=True)
class ShopifySessionClaims:
    shop_domain: str
    user_sub: str
    payload: dict[str, Any]


def verify_shopify_session_token(token: str) -> ShopifySessionClaims:
    """Verify a Shopify App Bridge HS256 JWT and return trusted claims.

    Shopify session tokens are short-lived JWTs signed with
    SHOPIFY_CLIENT_SECRET. We validate signature, exp, nbf, aud, iss/dest, and
    then extract the originating shop domain.
    """
    secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    client_id = os.getenv("SHOPIFY_CLIENT_ID", "")
    if not secret or not client_id:
        raise ShopifySessionTokenError("Shopify session token verification is not configured.")

    parts = token.split(".")
    if len(parts) != 3:
        raise ShopifySessionTokenError("Malformed Shopify session token.")
    header_b64, payload_b64, signature_b64 = parts
    header = _decode_json(header_b64)
    payload = _decode_json(payload_b64)

    if header.get("alg") != "HS256":
        raise ShopifySessionTokenError("Unsupported Shopify session token algorithm.")

    signed = f"{header_b64}.{payload_b64}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
    expected_signature = _base64url_encode(digest)
    if not hmac.compare_digest(expected_signature, signature_b64):
        raise ShopifySessionTokenError("Invalid Shopify session token signature.")

    now = datetime.now(timezone.utc).timestamp()
    exp = _numeric_claim(payload, "exp")
    nbf = _numeric_claim(payload, "nbf", required=False)
    if exp <= now:
        raise ShopifySessionTokenError("Expired Shopify session token.")
    if nbf is not None and nbf > now + 5:
        raise ShopifySessionTokenError("Shopify session token is not valid yet.")

    aud = payload.get("aud")
    if aud != client_id:
        raise ShopifySessionTokenError("Shopify session token audience mismatch.")

    iss_domain = _shop_from_url(str(payload.get("iss") or ""))
    dest_domain = _shop_from_url(str(payload.get("dest") or ""))
    if not iss_domain or not dest_domain or iss_domain != dest_domain:
        raise ShopifySessionTokenError("Shopify session token shop mismatch.")

    sub = str(payload.get("sub") or "")
    if not sub:
        raise ShopifySessionTokenError("Shopify session token missing user subject.")

    return ShopifySessionClaims(shop_domain=dest_domain, user_sub=sub, payload=payload)


def resolve_user_from_shopify_session_token(
    db: DbSession,
    token: str,
) -> User | None:
    """Resolve a verified embedded Shopify session token to a Skubase user."""
    claims = verify_shopify_session_token(token)
    conn = db.scalar(
        select(ShopifyConnection).where(
            ShopifyConnection.shopify_domain == claims.shop_domain,
            ShopifyConnection.uninstalled_at.is_(None),
        )
    )
    if conn is None or not conn.access_token:
        return None

    shop = db.get(Shop, conn.shop_id)
    if shop is None:
        return None

    user_email = f"shopify-admin+{claims.user_sub}@{claims.shop_domain}"
    user = db.scalar(select(User).where(User.email == user_email))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user is None:
        user = User(
            email=user_email,
            shop_id=shop.id,
            is_admin=False,
            trial_ends_at=now + timedelta(days=14),
            last_login_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login_at = now
        if user.trial_ends_at is None:
            user.trial_ends_at = now + timedelta(days=14)
        db.commit()
        db.refresh(user)
    return user


def _decode_json(value: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(_pad_base64(value)).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:
        raise ShopifySessionTokenError("Could not decode Shopify session token.") from exc
    if not isinstance(payload, dict):
        raise ShopifySessionTokenError("Invalid Shopify session token payload.")
    return payload


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _pad_base64(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def _numeric_claim(payload: dict[str, Any], key: str, *, required: bool = True) -> float | None:
    value = payload.get(key)
    if value is None:
        if required:
            raise ShopifySessionTokenError(f"Shopify session token missing {key}.")
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ShopifySessionTokenError(f"Shopify session token {key} is invalid.") from exc


def _shop_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    host = host.strip().lower()
    if host.endswith("/admin"):
        host = host[: -len("/admin")]
    if host.endswith(".myshopify.com"):
        return host
    return None
