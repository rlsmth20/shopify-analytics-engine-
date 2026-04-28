"""Reusable FastAPI dependencies for authentication and DB session."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.db.models import User
from app.db.session import get_db_session
from app.services.auth import SESSION_COOKIE_NAME, resolve_session


def get_current_user(
    db: Annotated[DbSession, Depends(get_db_session)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    """Require a valid session cookie. 401 if missing or invalid.

    Use as a FastAPI dependency on any route that should be auth-gated:
        @router.get("/some-private")
        def handler(user: User = Depends(get_current_user)): ...
    """
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    user = resolve_session(db, raw_token=session_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
        )
    return user


def get_optional_user(
    db: Annotated[DbSession, Depends(get_db_session)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> Optional[User]:
    """Same as get_current_user but returns None instead of 401."""
    if not session_token:
        return None
    return resolve_session(db, raw_token=session_token)


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
