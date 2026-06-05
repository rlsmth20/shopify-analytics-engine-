"""Authentication routes: magic-link request/verify, logout, me."""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
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
    cookie_settings_summary,
    cookie_kwargs,
    create_session,
    get_or_create_user_for_email,
    get_magic_link_token_status,
    issue_magic_link_token,
    mark_magic_link_token_used,
    revoke_session,
)
from app.services.transactional_email import send_magic_link_email

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Canonical frontend URL used for outbound links (magic-link emails, redirects).
# FRONTEND_ORIGIN may be comma-separated for CORS — use the first entry as the
# canonical link target.
FRONTEND_URL = (
    os.getenv("FRONTEND_URL")
    or os.getenv("FRONTEND_ORIGIN", "https://skubase.io").split(",")[0]
).strip().rstrip("/")


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:2]}***@{domain}"


def _auth_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": code, "message": message},
    )


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
    trial_ends_at: Optional[str]
    in_trial: bool


def _build_me_response(user: User) -> MeResponse:
    now = datetime.now(timezone.utc)
    trial_ends_at = user.trial_ends_at
    if trial_ends_at is not None and trial_ends_at.tzinfo is None:
        trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
    in_trial = trial_ends_at is not None and trial_ends_at > now
    return MeResponse(
        id=user.id,
        email=user.email,
        shop_id=user.shop_id,
        is_admin=user.is_admin,
        trial_ends_at=trial_ends_at.isoformat() if trial_ends_at else None,
        in_trial=in_trial,
    )


@router.post("/magic-link/request", response_model=MagicLinkResponse)
def request_magic_link(
    payload: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> MagicLinkResponse:
    raw_token = issue_magic_link_token(db, email=payload.email)
    callback_url = f"{FRONTEND_URL}/auth/callback?token={raw_token}"
    logger.info(
        "magic_link_requested email=%s domain=%s frontend_url=%s",
        _mask_email(str(payload.email).lower().strip()),
        str(payload.email).split("@")[-1],
        FRONTEND_URL,
    )
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
    request: Request,
    response: Response,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> MeResponse:
    logger.info("magic_link_verify_started origin=%s", request.headers.get("origin"))
    token_status, token_record = get_magic_link_token_status(db, raw_token=payload.token)
    if token_status != "valid" or token_record is None:
        logger.info("magic_link_verify_rejected status=%s", token_status)
        messages = {
            "invalid_token": "This sign-in link is invalid. Please request a fresh sign-in link.",
            "used_token": "This sign-in link has already been used. Please request a fresh sign-in link.",
            "expired_token": "This sign-in link is expired. Please request a fresh sign-in link.",
        }
        raise _auth_error(
            token_status,
            messages.get(token_status, "This sign-in link is invalid or expired. Request a new one."),
        )
    email = token_record.email
    user = get_or_create_user_for_email(
        db,
        email=email,
        shopify_domain=payload.shopify_domain,
    )
    raw_session = create_session(db, user_id=user.id)
    cookie_summary = cookie_settings_summary()
    response.set_cookie(
        value=raw_session,
        **cookie_kwargs(max_age_seconds=int(SESSION_TTL.total_seconds())),
    )
    mark_magic_link_token_used(db, token_record)
    logger.info(
        "magic_link_verify_success email=%s user_id=%s cookie=%s",
        _mask_email(email),
        user.id,
        cookie_summary,
    )
    return _build_me_response(user)


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
    legacy_auth_cookie = cookie_kwargs(max_age_seconds=0)
    legacy_auth_cookie["path"] = "/auth"
    response.set_cookie(value="", **legacy_auth_cookie)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session_token: Annotated[Optional[str], Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> MeResponse:
    if session_token:
        response.set_cookie(
            value=session_token,
            **cookie_kwargs(max_age_seconds=int(SESSION_TTL.total_seconds())),
        )
    logger.info(
        "auth_me_success user_id=%s origin=%s cookie_present=%s",
        user.id,
        request.headers.get("origin"),
        bool(session_token),
    )
    return _build_me_response(user)
