"""Verify Shopify App Bridge session tokens for embedded app requests."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import math
import re
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
    if len(parts) != 3 or any(not re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts):
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
    nbf = _numeric_claim(payload, "nbf")
    if exp <= now:
        raise ShopifySessionTokenError("Expired Shopify session token.")
    if nbf is not None and nbf > now + 5:
        raise ShopifySessionTokenError("Shopify session token is not valid yet.")

    aud = payload.get("aud")
    if aud != client_id:
        raise ShopifySessionTokenError("Shopify session token audience mismatch.")

    iss_domain = _shop_from_url(str(payload.get("iss") or ""))
    dest_domain = _shop_from_url(str(payload.get("dest") or ""))
    if (not iss_domain or not dest_domain or iss_domain != dest_domain
            or urlparse(str(payload.get("iss"))).path != "/admin"
            or urlparse(str(payload.get("dest"))).path not in ("", "/")):
        raise ShopifySessionTokenError("Shopify session token shop mismatch.")

    sub = str(payload.get("sub") or "")
    if not re.fullmatch(r"[0-9]+", sub):
        raise ShopifySessionTokenError("Shopify session token missing user subject.")

    return ShopifySessionClaims(shop_domain=dest_domain, user_sub=sub, payload=payload)


def resolve_user_from_shopify_session_token(
    db: DbSession,
    token: str,
) -> User | None:
    """Resolve a verified embedded Shopify session token to a Skubase user."""
    claims = verify_shopify_session_token(token)
    from app.services.shopify_oauth import shopify_connection_lock

    with shopify_connection_lock(db, claims.shop_domain):
        return _resolve_installed_user(db, token, claims)


def _resolve_installed_user(db: DbSession, token: str, claims: ShopifySessionClaims) -> User:
    from app.services.shopify_oauth import (
        exchange_session_token, get_or_create_embedded_user_for_shop, persist_connection,
    )

    conn = db.scalar(
        select(ShopifyConnection).join(Shop, Shop.id == ShopifyConnection.shop_id).where(
            Shop.shopify_domain == claims.shop_domain,
            ShopifyConnection.shopify_domain == claims.shop_domain,
        ).execution_options(populate_existing=True)
    )
    now = datetime.now(timezone.utc)
    expiry = conn.access_token_expires_at if conn else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    needs_grant = (conn is None or not conn.access_token or conn.uninstalled_at is not None
                   or expiry is None or expiry <= now + timedelta(seconds=120))
    # Provision only after Shopify confirms the grant. A forged/expired ID token
    # can never create an account, and a failed exchange leaves no partial install.
    payload = exchange_session_token(shop_domain=claims.shop_domain, session_token=token) if needs_grant else None
    owner = get_or_create_embedded_user_for_shop(db, shop_domain=claims.shop_domain, commit=False)
    if payload is not None:
        conn = persist_connection(db, shop_id=owner.shop_id, shop_domain=claims.shop_domain,
                                  token_payload=payload, commit=False)

    user_email = f"shopify-admin+{claims.user_sub}@{claims.shop_domain}"
    user = db.scalar(select(User).where(User.email == user_email))
    now = now.replace(tzinfo=None)

    if user is None:
        user = User(
            email=user_email,
            shop_id=owner.shop_id,
            is_admin=False,
            trial_ends_at=owner.trial_ends_at,
            last_login_at=now,
        )
        db.add(user)
    else:
        user.last_login_at = now
        if user.trial_ends_at is None:
            user.trial_ends_at = owner.trial_ends_at
        if user.shop_id != owner.shop_id:
            raise ShopifySessionTokenError("Shopify user workspace mismatch.")
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
        numeric = float(value)
        if isinstance(value, bool) or not math.isfinite(numeric):
            raise ValueError("Non-finite token timestamp")
        return numeric
    except (TypeError, ValueError) as exc:
        raise ShopifySessionTokenError(f"Shopify session token {key} is invalid.") from exc


def _shop_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if (parsed.scheme == "https" and not parsed.query and not parsed.fragment
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com", host)):
        return host
    return None
