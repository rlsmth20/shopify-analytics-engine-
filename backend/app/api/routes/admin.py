"""Admin routes — beta invitation, user management.

Gated by an ADMIN_BOOTSTRAP_TOKEN env var until we have admin users in the DB.
Once at least one admin user exists, prefer the require_admin dependency
which checks user.is_admin via cookie session.
"""
from __future__ import annotations

import os
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Shop, User
from app.db.session import get_db_session
from app.services.auth import (
    get_or_create_user_for_email,
    issue_magic_link_token,
    normalize_email,
)
from app.services.transactional_email import send_magic_link_email

router = APIRouter(prefix="/admin", tags=["admin"])

FRONTEND_URL = os.getenv("FRONTEND_ORIGIN", "https://skubase.io").split(",")[0].strip().rstrip("/")


def _check_admin_bootstrap(token: Optional[str]) -> None:
    """Gate admin endpoints by a shared secret while no admin User exists yet.

    Set ADMIN_BOOTSTRAP_TOKEN on Railway. Pass it as the X-Admin-Token header
    on requests. Once the first admin user is created, swap routes over to
    the require_admin cookie-based dependency.
    """
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin bootstrap is disabled (ADMIN_BOOTSTRAP_TOKEN not set).",
        )
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token.",
        )


class InviteRequest(BaseModel):
    email: EmailStr
    shopify_domain: Optional[str] = Field(default=None, max_length=255)
    is_admin: bool = False
    note: Optional[str] = Field(default=None, max_length=1000)


class InviteResponse(BaseModel):
    user_id: int
    email: str
    shop_id: int
    invited: bool
    is_admin: bool


@router.post("/invite", response_model=InviteResponse)
def invite_user(
    payload: InviteRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db_session)],
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> InviteResponse:
    """Create a User (and Shop if needed) and email them a sign-in link.

    Idempotent: if the email already exists, we reuse the User and just
    re-send the magic link. Useful for re-inviting beta users who lost
    their first email.
    """
    _check_admin_bootstrap(x_admin_token)

    user = get_or_create_user_for_email(
        db,
        email=str(payload.email),
        shopify_domain=payload.shopify_domain,
    )
    if payload.is_admin and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    raw_token = issue_magic_link_token(db, email=user.email)
    callback_url = f"{FRONTEND_URL}/auth/callback?token={raw_token}"
    background_tasks.add_task(
        send_magic_link_email,
        email=user.email,
        link=callback_url,
    )

    return InviteResponse(
        user_id=user.id,
        email=user.email,
        shop_id=user.shop_id,
        invited=True,
        is_admin=user.is_admin,
    )


class UserSummary(BaseModel):
    id: int
    email: str
    shop_id: int
    is_admin: bool


@router.get("/users", response_model=list[UserSummary])
def list_users(
    db: Annotated[DbSession, Depends(get_db_session)],
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> list[UserSummary]:
    _check_admin_bootstrap(x_admin_token)
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [
        UserSummary(id=u.id, email=u.email, shop_id=u.shop_id, is_admin=u.is_admin)
        for u in users
    ]
