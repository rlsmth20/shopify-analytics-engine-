"""Contact / bug-report form endpoint.

Public, no auth required. Forwards submissions to Rainer via Resend so
logged-in customers and prospective users can both reach support.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field

from app.services.transactional_email import send_contact_notification

router = APIRouter(prefix="/contact", tags=["contact"])

ContactType = Literal["bug", "feedback", "billing", "general"]


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    type: ContactType = "general"
    message: str = Field(min_length=10, max_length=4000)


class ContactResponse(BaseModel):
    ok: bool


@router.post("/submit", response_model=ContactResponse)
def submit(
    request: ContactRequest,
    background_tasks: BackgroundTasks,
) -> ContactResponse:
    background_tasks.add_task(
        send_contact_notification,
        name=request.name,
        email=request.email,
        contact_type=request.type,
        message=request.message,
    )
    return ContactResponse(ok=True)
