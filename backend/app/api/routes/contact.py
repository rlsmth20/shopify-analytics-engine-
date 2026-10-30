"""Contact / bug-report form endpoint.

Public, no auth required. Sends submissions to info@skubase.io via Resend so
logged-in customers and prospective users can both reach support.
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.services import rate_limit
from app.services.transactional_email import send_contact_notification

router = APIRouter(prefix="/contact", tags=["contact"])

ContactType = Literal["bug", "feedback", "billing", "general"]


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    type: ContactType = "general"
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("email")
    @classmethod
    def require_reply_address(cls, value: str) -> str:
        if re.fullmatch(
            r"shopify-(?:admin\+\d+|owner)@[^@\s]+\.myshopify\.com", value, re.IGNORECASE
        ):
            raise ValueError("Enter an email address where you can receive a reply.")
        return value


class ContactResponse(BaseModel):
    ok: bool


@router.post("/submit", response_model=ContactResponse)
def submit(payload: ContactRequest, request: Request) -> ContactResponse:
    # Every submission becomes an email to the operator inbox.
    rate_limit.enforce(request, ("contact_ip", None), ("contact_email", str(payload.email).lower()))
    # FastAPI runs synchronous endpoints in its thread pool. Wait for the
    # provider acknowledgement so a failed send is not reported as success.
    delivered = send_contact_notification(
        name=payload.name,
        email=payload.email,
        contact_type=payload.type,
        message=payload.message,
    )
    if not delivered:
        raise HTTPException(
            status_code=503,
            detail="We couldn't send your message. Please try again or email info@skubase.io directly.",
        )
    return ContactResponse(ok=True)
