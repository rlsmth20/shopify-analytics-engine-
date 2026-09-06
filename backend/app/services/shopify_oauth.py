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
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import urllib.error
import urllib.request

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DbSession

from app.db.models import Shop, ShopifyConnection, User

logger = logging.getLogger(__name__)
_connection_locks = [threading.RLock() for _ in range(64)]


class ShopifyTokenExchangeError(RuntimeError):
    """Shopify could not establish an API connection; safe to show to merchants."""


class ShopifyTokenExchangeRejected(ShopifyTokenExchangeError):
    """The current ID token was rejected; the browser should get a fresh one."""


@contextmanager
def shopify_connection_lock(db: DbSession, shop_domain: str):
    """Serialize grants/refreshes, including across PostgreSQL app workers.

    Callers commit or roll back before leaving this context. The transaction
    advisory lock protects first installation, where no Shop row exists yet.
    """
    key = int.from_bytes(hashlib.sha256(shop_domain.encode()).digest()[:8], "big", signed=True)
    with _connection_locks[key % len(_connection_locks)]:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        try:
            yield
        except Exception:
            db.rollback()
            raise


SCOPES = "read_products,read_inventory,read_orders,read_locations"

FRONTEND_URL = os.getenv("FRONTEND_ORIGIN", "https://skubase.io").split(",")[0].strip().rstrip("/")


def _backend_url() -> str:
    """Public backend origin used for the OAuth redirect_uri.

    Prefers the explicit BACKEND_PUBLIC_URL, falling back to Railway's
    injected public domain (the custom domain when one is attached). The
    result must match a whitelisted redirect URL in the Partner Dashboard.
    """
    explicit = os.getenv("BACKEND_PUBLIC_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if railway_domain:
        return f"https://{railway_domain}"
    return ""


BACKEND_URL = _backend_url()


@dataclass(frozen=True)
class OAuthStateResolution:
    user_id: int | None
    shop_domain: str
    host: str | None = None


def is_configured() -> bool:
    return bool(os.getenv("SHOPIFY_CLIENT_ID") and os.getenv("SHOPIFY_CLIENT_SECRET"))


def normalize_shop_domain(shop: str) -> Optional[str]:
    """Return a normalized myshopify.com domain or None if invalid."""
    if not shop:
        return None
    s = shop.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    if s.endswith(".myshopify.com"):
        # Validate the prefix is a slug.
        slug = s[: -len(".myshopify.com")]
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", slug):
            return s
        return None
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", s):
        return f"{s}.myshopify.com"
    return None


def build_install_url(*, shop_domain: str, state: str) -> str:
    """Build the Shopify authorize URL the user is redirected to."""
    if not BACKEND_URL:
        raise RuntimeError("BACKEND_PUBLIC_URL is not set on the server.")
    api_key = os.getenv("SHOPIFY_CLIENT_ID", "")
    if not api_key:
        raise RuntimeError("SHOPIFY_CLIENT_ID is not set on the server.")

    redirect_uri = f"{BACKEND_URL}/integrations/shopify/callback"
    # No grant_options here: "per-user" would request an ONLINE token that
    # expires after ~24h, breaking background sync and billing with 401s.
    # The default (offline) token persists until the app is uninstalled.
    params = {
        "client_id": api_key,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    logger.info(
        "shopify_oauth_install shop=%s redirect_uri=%s (must be whitelisted in the Partner Dashboard)",
        shop_domain,
        redirect_uri,
    )
    return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"


def issue_oauth_state(
    db: DbSession,
    *,
    user: User | None,
    shop_domain: str,
    host: str | None = None,
) -> str:
    """Mint a one-time state token, stash it in the user's session pretext.

    Implementation note: we reuse the MagicLinkToken table for short-lived
    state — the token's email column stores the requested shop domain,
    so the callback can validate origin without adding a new table.
    """
    from app.db.models import MagicLinkToken
    from app.services.auth import _sha256

    raw = secrets.token_urlsafe(24)
    user_part = str(user.id) if user is not None else "embedded"
    state_parts = ["shopify_oauth", user_part, shop_domain]
    if host:
        state_parts.append(host)
    record = MagicLinkToken(
        email=":".join(state_parts),
        token_hash=_sha256(raw),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10),
        used=False,
    )
    db.add(record)
    db.commit()
    return raw


def consume_oauth_state(db: DbSession, *, raw_state: str) -> Optional[OAuthStateResolution]:
    """Returns OAuth state details if the state is valid, else None."""
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
    parts = record.email.split(":")
    if len(parts) < 3:
        return None
    if parts[1] == "embedded":
        user_id = None
    else:
        try:
            user_id = int(parts[1])
        except ValueError:
            return None
    shop_domain = parts[2]
    host = parts[3] if len(parts) > 3 and parts[3] else None
    record.used = True
    db.commit()
    return OAuthStateResolution(user_id=user_id, shop_domain=shop_domain, host=host)


def verify_callback_hmac(query_params: dict[str, str]) -> bool:
    """Verify the HMAC Shopify includes on every callback redirect."""
    secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
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
    api_key = os.getenv("SHOPIFY_CLIENT_ID", "")
    api_secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    if not api_key or not api_secret:
        return None

    url = f"https://{shop_domain}/admin/oauth/access_token"
    body = urlencode({
        "client_id": api_key,
        "client_secret": api_secret,
        "code": code,
        # Public apps should request renewable offline tokens. expiring=1
        # yields a ~1h access token plus a 90-day refresh
        # token (rotated on every refresh by ensure_fresh_access_token).
        "expiring": "1",
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


def _expiry_from_seconds(seconds: object) -> datetime | None:
    try:
        ttl = int(seconds)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if ttl <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=ttl)


def apply_token_payload(conn: ShopifyConnection, payload: dict) -> None:
    """Copy token fields from a Shopify token-grant response onto the row.

    Used for both the initial code exchange and refresh-token grants. Shopify
    rotates the refresh token on every refresh, so keep the old one only if
    the response omits it.
    """
    conn.access_token = payload["access_token"]
    conn.access_token_expires_at = _expiry_from_seconds(payload.get("expires_in"))
    new_refresh = payload.get("refresh_token")
    if new_refresh:
        conn.refresh_token = str(new_refresh)
        conn.refresh_token_expires_at = _expiry_from_seconds(
            payload.get("refresh_token_expires_in")
        )


def exchange_session_token(*, shop_domain: str, session_token: str) -> dict:
    """Exchange an already-verified App Bridge ID token for an offline grant."""
    if not is_configured():
        raise ShopifyTokenExchangeError("Shopify authentication is not configured. Please contact support.")
    if normalize_shop_domain(shop_domain) != shop_domain:
        raise ShopifyTokenExchangeRejected("Invalid Shopify shop.")
    body = urlencode({
        "client_id": os.environ["SHOPIFY_CLIENT_ID"],
        "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"],
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": session_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "requested_token_type": "urn:shopify:params:oauth:token-type:offline-access-token",
        "expiring": "1",
    }).encode()
    req = urllib.request.Request(
        f"https://{shop_domain}/admin/oauth/access_token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    try:
        import json
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Never log grant bodies: they contain app secrets and session tokens.
        logger.warning("shopify_session_exchange_failed shop=%s status=%s", shop_domain, exc.code)
        if exc.code in (400, 401):
            raise ShopifyTokenExchangeRejected("Shopify could not verify this session. Please try again.") from exc
        raise ShopifyTokenExchangeError("Shopify could not connect your store. Please try again shortly.") from exc
    except (OSError, ValueError) as exc:
        raise ShopifyTokenExchangeError("Could not reach Shopify to connect your store. Please try again.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str) or not payload["access_token"]:
        raise ShopifyTokenExchangeError("Shopify returned an incomplete connection. Please try again.")
    if _expiry_from_seconds(payload.get("expires_in")) is None or not payload.get("refresh_token"):
        raise ShopifyTokenExchangeError("Shopify did not return a renewable connection. Please try again.")
    return payload


def ensure_fresh_access_token(db: DbSession, conn: ShopifyConnection) -> str:
    with shopify_connection_lock(db, conn.shopify_domain):
        db.refresh(conn)
        token = _refresh_access_token(db, conn)
        db.commit()
        return token


def _refresh_access_token(db: DbSession, conn: ShopifyConnection) -> str:
    """Return a usable access token, refreshing via the refresh token if needed.

    Legacy connections (no expiry recorded) are returned as-is — Shopify will
    reject them with 403 and the caller's error message tells the merchant to
    reconnect, which mints an expiring token pair.
    """
    if conn.access_token_expires_at is None or not conn.refresh_token:
        return conn.access_token

    expires_at = conn.access_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at - datetime.now(timezone.utc) > timedelta(seconds=120):
        return conn.access_token

    api_key = os.getenv("SHOPIFY_CLIENT_ID", "")
    api_secret = os.getenv("SHOPIFY_CLIENT_SECRET", "")
    if not api_key or not api_secret:
        return conn.access_token

    url = f"https://{conn.shopify_domain}/admin/oauth/access_token"
    body = urlencode({
        "client_id": api_key,
        "client_secret": api_secret,
        "grant_type": "refresh_token",
        "refresh_token": conn.refresh_token,
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
    except urllib.error.HTTPError as exc:
        logger.error(
            "Shopify token refresh failed for %s: status=%s",
            conn.shopify_domain, exc.code,
        )
        return conn.access_token
    except Exception:
        logger.exception("Shopify token refresh failed for %s", conn.shopify_domain)
        return conn.access_token

    if not payload.get("access_token"):
        logger.error(
            "Shopify token refresh for %s returned no access_token", conn.shopify_domain
        )
        return conn.access_token

    apply_token_payload(conn, payload)
    db.commit()
    logger.info("Refreshed Shopify access token for %s", conn.shopify_domain)
    return conn.access_token


def persist_connection(
    db: DbSession,
    *,
    shop_id: int,
    shop_domain: str,
    token_payload: dict,
    commit: bool = True,
) -> ShopifyConnection:
    """Insert or update the ShopifyConnection row for a workspace shop."""
    # The verified Shopify shop owns the connection. A separate website-login
    # workspace must never be renamed over an existing installed store.
    canonical = db.scalar(select(Shop).where(Shop.shopify_domain == shop_domain))
    if canonical is not None:
        shop_id = canonical.id
    existing = db.scalar(
        select(ShopifyConnection).where(ShopifyConnection.shop_id == shop_id)
    )
    if existing is None:
        existing = ShopifyConnection(
            shop_id=shop_id,
            shopify_domain=shop_domain,
            access_token=token_payload["access_token"],
            scope=str(token_payload.get("scope") or ""),
        )
        db.add(existing)
    else:
        existing.shopify_domain = shop_domain
        existing.scope = str(token_payload.get("scope") or "")
        if existing.uninstalled_at is not None:
            existing.installed_at = datetime.now(timezone.utc)
        existing.uninstalled_at = None
    apply_token_payload(existing, token_payload)
    # Update the Shop's domain to match the merchant's actual domain so the
    # placeholder synthetic domain gets replaced once they connect.
    shop = db.get(Shop, shop_id)
    if shop is not None:
        shop.shopify_domain = shop_domain
    if commit:
        db.commit()
        db.refresh(existing)
    else:
        db.flush()

    # A fresh install/re-auth changes what Shopify will report — drop any
    # cached billing snapshot for this shop.
    from app.services.shopify_billing import invalidate_shopify_billing_cache

    invalidate_shopify_billing_cache(shop_id)
    return existing


def get_or_create_embedded_user_for_shop(db: DbSession, *, shop_domain: str, commit: bool = True) -> User:
    """Provision a Skubase user/workspace for Shopify-originated installs."""
    from app.services.auth import TRIAL_TTL, _now

    shop = db.scalar(select(Shop).where(Shop.shopify_domain == shop_domain))
    if shop is None:
        shop = Shop(shopify_domain=shop_domain)
        db.add(shop)
        db.flush()

    email = f"shopify-owner@{shop_domain}"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            shop_id=shop.id,
            is_admin=False,
            trial_ends_at=_now() + TRIAL_TTL,
            last_login_at=_now(),
        )
        db.add(user)
    else:
        user.last_login_at = _now()
        if user.trial_ends_at is None:
            user.trial_ends_at = _now() + TRIAL_TTL
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def embedded_admin_redirect_url(
    *,
    shop_domain: str,
    host: str | None = None,
    path: str = "",
) -> str:
    """Return a URL that lands the merchant inside the embedded app.

    `path` is an in-app route like "/billing"; it defaults to the app home.
    Used after OAuth installs and as the Shopify billing returnUrl.
    """
    app_handle = os.getenv("SHOPIFY_APP_HANDLE", "").strip()
    if app_handle:
        store_handle = shop_domain.removesuffix(".myshopify.com")
        return f"https://admin.shopify.com/store/{store_handle}/apps/{app_handle}{path}"

    # Without a handle, the legacy admin path with the API key still lands
    # inside the embedded app — never strand a fresh install on the bare
    # website outside Shopify admin.
    client_id = os.getenv("SHOPIFY_CLIENT_ID", "").strip()
    if client_id:
        return f"https://{shop_domain}/admin/apps/{client_id}{path}"

    params = {"shop": shop_domain, "embedded": "1", "connected": "1"}
    if host:
        params["host"] = host
    return f"{FRONTEND_URL}{path or '/dashboard'}?{urlencode(params)}"
