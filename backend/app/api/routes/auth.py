"""Authentication routes: magic-link request/verify, logout, me."""
from __future__ import annotations

import os
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db_session
from app.services.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    cookie_kwargs,
    create_session,
    consume_magic_link_token,
    get_or_create_user_for_email,
    issue_magic_link_token,
    revoke_session,
)
from app.services.transactional_email import send_magic_link_email

router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_URL = os.getenv("FRONTEND_ORIGIN", "https://slelfly.com").rstrip("/")


class MagicLinkRequest(BaseModel):
    email: EmailStr
    shopify_domain: Optional[str] = Field(default=None, max_length=255)


class MagicLinkResponse(BaseModel):
    sent: bool
    # We always return 200 + sent=True even if the email is unknown — this
    # avoids leaking which addresses have accounts. The email itself is the
    # signal of success.


class MeResponse(BaseModel):
    id: int
    email: str
    shop_id: int
    is_admin: bool


@router.post("/magic-link/request", response_model=MagicLinkResponse)
def request_magic_link(
    payload: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> MagicLinkResponse:
    raw_token = issue_magic_link_token(db, email=payload.email)
    callback_url = f"{FRONTEND_URL}/auth/callback?token={raw_token}"
    background_tasks.add_task(
        send_magic_link_email,
        email=str(payload.email).lower().strip(),
        link=callback_url,
    )
    return MagicLinkResponse(sent=True)


class VerifyRequest(BaseModel):
    token: str
    shopify_domain: Optional[str] = Field(default=None, max_length=255)


@router.post("/magic-link/verify", response_model=MeResponse)
def verify_magic_link(
    payload: VerifyRequest,
    response: Response,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> MeResponse:
    email = consume_magic_link_token(db, raw_token=payload.token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This sign-in link is invalid or expired. Request a new one.",
        )
    user = get_or_create_user_for_email(
        db,
        email=email,
        shopify_domain=payload.shopify_domain,
    )
    raw_session = create_session(db, user_id=user.id)
    response.set_cookie(
        value=raw_session,
        **cookie_kwargs(max_age_seconds=int(SESSION_TTL.total_seconds())),
    )
    return MeResponse(
        id=user.id,
        email=user.email,
        shop_id=user.shop_id,
        is_admin=user.is_admin,
    )


@router.post("/logout")
def logout(
    response: Response,
    db: Annotated[DbSession, Depends(get_db_session)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, bool]:
    if session_token:
        revoke_session(db, raw_token=session_token)
    # Clear the cookie regardless. max_age=0 expires it on receipt.
    response.set_cookie(value="", **cookie_kwargs(max_age_seconds=0))
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        shop_id=user.shop_id,
        is_admin=user.is_admin,
    )
