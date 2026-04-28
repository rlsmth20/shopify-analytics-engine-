"""Authentication service — magic-link tokens and server-side sessions.

Design rules:
- Random tokens are generated with secrets.token_urlsafe(32) (256 bits).
- Only the SHA-256 hash of the token is persisted; the raw value never
  hits the database. A DB compromise does not yield usable cookies.
- Magic-link tokens are single-use (used=True after redemption) and short-
  lived (15 minutes by default). Sessions live 30 days.
- Cookie is set HTTP-only, Secure, SameSite=None so the cross-origin
  Vercel-frontend / Railway-backend split works. Local dev tolerates
  SameSite=Lax via the IS_PRODUCTION flag.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import MagicLinkToken, Session as SessionModel, Shop, User

# Cookie name. Frontend reads/writes nothing here — the backend sets it,
# the browser presents it on every request, the backend reads it back.
SESSION_COOKIE_NAME = "slelfly_session"

MAGIC_LINK_TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(days=30)

IS_PRODUCTION = os.getenv("ENVIRONMENT", "production").lower() != "development"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------- Magic-link tokens ----------

def issue_magic_link_token(db: DbSession, *, email: str) -> str:
    """Create a magic-link token. Returns the raw token (only ever returned here).

    The caller must email the raw token to the user; we never log it.
    """
    email = normalize_email(email)
    raw_token = secrets.token_urlsafe(32)
    record = MagicLinkToken(
        email=email,
        token_hash=_sha256(raw_token),
        expires_at=_now() + MAGIC_LINK_TTL,
        used=False,
    )
    db.add(record)
    db.commit()
    return raw_token


def consume_magic_link_token(db: DbSession, *, raw_token: str) -> Optional[str]:
    """Validate a magic-link token. Returns the email if valid, None otherwise.

    Marks the token as used; subsequent calls with the same token return None.
    """
    token_hash = _sha256(raw_token)
    record = db.scalar(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    if record is None:
        return None
    if record.used:
        return None
    if record.expires_at < _now():
        return None
    record.used = True
    db.commit()
    return record.email


# ---------- Sessions ----------

def create_session(db: DbSession, *, user_id: int) -> str:
    """Create a session row, returning the raw cookie token."""
    raw_token = secrets.token_urlsafe(32)
    record = SessionModel(
        user_id=user_id,
        token_hash=_sha256(raw_token),
        expires_at=_now() + SESSION_TTL,
    )
    db.add(record)
    db.commit()
    return raw_token


def resolve_session(db: DbSession, *, raw_token: str) -> Optional[User]:
    """Map a cookie value to its User, or None if invalid/expired."""
    token_hash = _sha256(raw_token)
    record = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    if record is None:
        return None
    if record.expires_at < _now():
        return None
    record.last_seen_at = _now()
    db.commit()
    user = db.get(User, record.user_id)
    return user


def revoke_session(db: DbSession, *, raw_token: str) -> None:
    """Delete the session row for a given cookie value (logout)."""
    token_hash = _sha256(raw_token)
    record = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    if record is not None:
        db.delete(record)
        db.commit()


# ---------- User provisioning ----------

def get_or_create_user_for_email(
    db: DbSession,
    *,
    email: str,
    shopify_domain: Optional[str] = None,
) -> User:
    """Resolve or create the User row for a magic-link verification.

    First-time logins create a Shop and a User in one transaction. Subsequent
    logins return the existing User. shopify_domain is best-effort; we fall
    back to a synthetic domain derived from the email so the unique
    constraint on Shop.shopify_domain is satisfied.
    """
    email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.last_login_at = _now()
        db.commit()
        return user

    domain = (shopify_domain or "").strip().lower() or None
    if domain is None:
        # Synthesize a placeholder so the NOT NULL + UNIQUE constraints hold.
        # The real Shopify domain is set later when the merchant connects.
        local = email.split("@", 1)[0].replace(".", "-").replace("+", "-")
        domain = f"pending-{local}-{secrets.token_hex(4)}.slelfly.invalid"

    shop = db.scalar(select(Shop).where(Shop.shopify_domain == domain))
    if shop is None:
        shop = Shop(shopify_domain=domain)
        db.add(shop)
        db.flush()  # Assign shop.id

    user = User(
        email=email,
        shop_id=shop.id,
        is_admin=False,
        last_login_at=_now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------- Cookie helpers ----------

def cookie_kwargs(*, max_age_seconds: int) -> dict:
    """FastAPI/Starlette set_cookie kwargs that work cross-origin in prod."""
    return {
        "key": SESSION_COOKIE_NAME,
        "max_age": max_age_seconds,
        "httponly": True,
        "secure": IS_PRODUCTION,
        "samesite": "none" if IS_PRODUCTION else "lax",
        "path": "/",
    }
