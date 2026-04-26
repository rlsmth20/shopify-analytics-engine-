"""Waitlist signup route — captures email + shop domain pre-launch."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import WaitlistSignup
from app.db.session import session_scope


router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistSignupRequest(BaseModel):
    email: EmailStr
    shopify_domain: Optional[str] = Field(default=None, max_length=255)
    source: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=1000)


class WaitlistSignupResponse(BaseModel):
    id: int
    email: str
    shopify_domain: Optional[str]
    source: Optional[str]
    created_at: datetime
    already_signed_up: bool = False


@router.post("/signup", response_model=WaitlistSignupResponse)
def signup(request: WaitlistSignupRequest) -> WaitlistSignupResponse:
    email = request.email.lower().strip()
    domain = (request.shopify_domain or "").strip().lower() or None

    with session_scope() as session:
        # If they're already on the list, return their existing record
        existing = session.scalar(
            select(WaitlistSignup).where(WaitlistSignup.email == email)
        )
        if existing is not None:
            # Update domain/source/note if the latest submission has them
            if domain and not existing.shopify_domain:
                existing.shopify_domain = domain
            if request.source and not existing.source:
                existing.source = request.source
            if request.note and not existing.note:
                existing.note = request.note
            session.commit()
            session.refresh(existing)
            return WaitlistSignupResponse(
                id=existing.id,
                email=existing.email,
                shopify_domain=existing.shopify_domain,
                source=existing.source,
                created_at=existing.created_at,
                already_signed_up=True,
            )

        record = WaitlistSignup(
            email=email,
            shopify_domain=domain,
            source=request.source,
            note=request.note,
        )
        session.add(record)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Email already on the waitlist.") from exc
        session.refresh(record)

        return WaitlistSignupResponse(
            id=record.id,
            email=record.email,
            shopify_domain=record.shopify_domain,
            source=record.source,
            created_at=record.created_at,
            already_signed_up=False,
        )


@router.get("/count")
def count() -> dict[str, int]:
    """Public count for "join 247 merchants on the waitlist" social-proof copy."""
    with session_scope() as session:
        from sqlalchemy import func as sql_func
        n = session.scalar(select(sql_func.count()).select_from(WaitlistSignup))
        return {"count": int(n or 0)}
