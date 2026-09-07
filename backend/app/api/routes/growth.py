"""Thin owner APIs, constrained first-party events and signed Resend event ingestion."""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_admin
from app.db.models import User
from app.db.session import get_db_session
from app.growth.dashboard import dashboard
from app.growth.discovery import ingest_opportunity
from app.growth.funnel import CLIENT_EVENTS, product_event
from app.growth.models import Contact, Evidence, Message, SkillRevision, Usage, Work
from app.growth.policy import qualify
from app.growth.skills import activate_revision
from app.growth.store import digest, enqueue, get_memory, record, remember

router = APIRouter(prefix="/growth", tags=["growth"])
DB = Annotated[Session, Depends(get_db_session)]
Admin = Annotated[User, Depends(require_admin)]


@router.get("/dashboard")
def read_dashboard(db: DB, owner: Admin):
    return dashboard(db)


@router.get("/evidence")
def read_evidence(db: DB, owner: Admin, after: int = 0, subject: str | None = None):
    query = select(Evidence).where(Evidence.id > after)
    if subject:
        query = query.where(Evidence.subject == subject)
    return [{"id": e.id, "kind": e.kind, "subject": e.subject, "source": e.source, "epistemic": e.epistemic,
             "data": e.data, "occurred_at": e.occurred_at} for e in db.scalars(query.order_by(Evidence.id).limit(100))]


class Control(BaseModel):
    paused: bool


@router.post("/control")
def control(payload: Control, db: DB, owner: Admin):
    remember(db, "working", "control", payload.model_dump(), source="owner")
    db.commit()
    return payload


class ProductReview(BaseModel):
    evidence_id: int
    resolution: str = Field(min_length=15, max_length=1000)


@router.post("/product-review")
def resolve_product_hold(payload: ProductReview, db: DB, owner: Admin):
    if not db.get(Evidence, payload.evidence_id):
        raise HTTPException(400, "Retained verification evidence is required")
    record(db, f"product-resolution:{time.time_ns()}", "PRODUCT_REVIEWED", "product", payload.model_dump(), source="owner")
    remember(db, "working", "acquisition_hold", {}, source="owner")
    db.commit()
    return {"hold_released": True}


class ModelAssessment(BaseModel):
    baseline_usage_id: str
    evidence_ids: list[int] = Field(min_length=1, max_length=10)
    improved: bool
    outcome: str = Field(min_length=15, max_length=1000)


@router.post("/usage/{usage_id}/assessment")
def assess_model(usage_id: str, payload: ModelAssessment, db: DB, owner: Admin):
    candidate, baseline = db.get(Usage, usage_id), db.get(Usage, payload.baseline_usage_id)
    from app.growth.model_router import RATES
    if (not candidate or not baseline or candidate.task != baseline.task or
        candidate.model not in RATES or baseline.model not in RATES or
        RATES[candidate.model][1] <= RATES[baseline.model][1]):
        raise HTTPException(400, "Compare the same task against a cheaper recorded model call")
    evidence = list(db.scalars(select(Evidence).where(Evidence.id.in_(payload.evidence_ids))))
    if len(evidence) != len(set(payload.evidence_ids)):
        raise HTTPException(400, "Assessment needs retained outcome evidence")
    candidate.escalated_from, candidate.escalation_improved = baseline.model, payload.improved
    record(db, f"model-assessment:{usage_id}:{time.time_ns()}", "MODEL_ASSESSED", usage_id,
           payload.model_dump(), source="owner", epistemic="INFERENCE")
    db.commit()
    return {"recorded": True}


@router.post("/work/{work_id}/retry")
def retry_work(work_id: str, db: DB, owner: Admin):
    row = db.get(Work, work_id)
    if not row or row.status not in ("blocked", "failed"):
        raise HTTPException(409, "Only blocked or failed work can be resumed")
    if row.kind == "send":
        message = db.get(Message, row.payload.get("message_id"))
        if not message or message.status != "draft":
            raise HTTPException(409, "An uncertain send must be reconciled, not retried")
    row.status, row.attempts, row.due_at = "ready", 0, time.time()
    record(db, f"owner-retry:{row.id}:{time.time_ns()}", "OWNER_RETRY", row.id, {"kind": row.kind}, source="owner")
    db.commit()
    return {"queued": True}


class PublicEvidence(BaseModel):
    url: str = Field(max_length=1000)
    text: str = Field(min_length=10, max_length=5000)
    published_at: float | None = None
    author: str | None = Field(default=None, max_length=120)
    channel: str = Field(default="shopify_community", max_length=40)


@router.post("/opportunities")
def add_opportunity(payload: PublicEvidence, db: DB, owner: Admin):
    event = ingest_opportunity(db, **payload.model_dump())
    db.commit()
    return {"evidence_id": event.id, "contact_id": event.subject}


class VerifiedFact(BaseModel):
    text: str = Field(min_length=5, max_length=180)
    source: str = Field(min_length=5, max_length=1000)


class ContactApproval(BaseModel):
    email: EmailStr
    organization: str = Field(min_length=1, max_length=255)
    basis: Literal["public_business_contact", "requested_health_check", "requested_reply"]
    facts: list[VerifiedFact] = Field(min_length=1, max_length=3)
    inventory_problem: str = Field(min_length=10, max_length=1000)
    characteristics: dict[str, str] = Field(default_factory=dict, max_length=10)


@router.put("/contacts/{contact_id}/qualification")
def qualify_contact(contact_id: str, payload: ContactApproval, db: DB, owner: Admin):
    contact = db.get(Contact, contact_id)
    if not contact or contact.suppressed:
        raise HTTPException(409, "Missing or suppressed contact")
    contact.email, contact.organization, contact.contact_basis = str(payload.email).lower(), payload.organization, payload.basis
    contact.facts = [{**f.model_dump(), "verified": True, "verified_by": owner.id} for f in payload.facts]
    contact.characteristics = payload.characteristics
    contact.qualification = qualify(payload.inventory_problem, merchant_verified=True)
    contact.status = "qualified" if contact.qualification["qualified"] else "prospect"
    enqueue(db, f"approved-opportunity:{contact.id}", "opportunity", {"contact_id": contact.id}, priority=85)
    record(db, f"contact-approved:{contact.id}:{time.time_ns()}", "CONTACT_VERIFIED", contact.id,
           {"basis": payload.basis, "fact_sources": [f.source for f in payload.facts]}, source="owner")
    db.commit()
    return {"qualification": contact.qualification}


@router.get("/skills")
def list_skills(db: DB, owner: Admin):
    return [{"name": s.name, "version": s.version, "status": s.status, "specification": s.specification,
             "validation": s.validation, "evidence_ids": s.evidence_ids} for s in db.scalars(select(SkillRevision))]


@router.post("/skills/{name}/{version}/activate")
def activate_skill(name: str, version: int, db: DB, owner: Admin):
    try:
        activate_revision(db, name, version)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    db.commit()
    return {"active": version}


class ClientEvent(BaseModel):
    id: str = Field(pattern=r"^[a-f0-9-]{32,36}$")
    visitor_id: str = Field(pattern=r"^[a-f0-9-]{32,36}$")
    name: str = Field(max_length=64)
    landing_page: str = Field(default="/", max_length=250)
    attribution: dict[str, str] = Field(default_factory=dict, max_length=6)


@router.post("/events", status_code=202)
def client_event(payload: ClientEvent, request: Request, db: DB,
                 user: Annotated[User | None, Depends(get_optional_user)]):
    verified_views = {"INVENTORY_ANALYSIS_VIEWED", "KEY_ACTION_VIEWED"}
    if payload.name not in CLIENT_EVENTS | verified_views:
        raise HTTPException(400, "This event requires a verified server observation")
    if user and user.is_admin:
        return {"accepted": False, "reason": "admin"}
    origin = request.headers.get("origin", "")
    allowed = {"https://skubase.io", "https://www.skubase.io", *os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")}
    if origin not in allowed:
        raise HTTPException(403, "Untrusted event origin")
    if payload.name in verified_views:
        delivered = payload.name.replace("_VIEWED", "_DELIVERED")
        if not user or not db.scalar(select(Evidence.id).where(Evidence.subject == f"shop:{user.shop_id}",
                         Evidence.kind == delivered, Evidence.occurred_at > time.time() - 3600)):
            raise HTTPException(400, "Usable analysis must be served to this authenticated store first")
        product_event(db, payload.name, user.shop_id, f"view:{payload.name}:{user.shop_id}:{int(time.time() // 86400)}",
                      data={"view_confirmed_by": "authenticated_browser_after_render"})
        enqueue(db, f"view-wake:{int(time.time() // 300)}", "observe", priority=80)
    subject = "visitor:" + payload.visitor_id
    # Durable per-visitor caps limit accidental loops; edge rate limits should cover hostile rotating identities.
    recent = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.subject == subject, Evidence.recorded_at > time.time() - 3600)) or 0
    if recent >= 60:
        raise HTTPException(429, "Event rate exceeded")
    attribution = {k: v[:120] for k, v in payload.attribution.items() if k in {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "referrer"}}
    landing = urlparse(payload.landing_page).path[:200] or "/"
    if not landing.startswith("/"):
        landing = "/"
    if payload.name not in verified_views:
        record(db, "client:" + payload.id, payload.name, subject,
               {"landing_page": landing, "attribution": attribution, "verified": False}, source="first_party_browser")
    if user:
        # Server session determines identity; client never supplies a user/shop ID.
        record(db, f"visitor-link:{payload.visitor_id}:{user.shop_id}", "IDENTITY_LINK", subject,
               {"shop_id": user.shop_id}, source="authenticated_session", epistemic="FACT")
        if not get_memory(db, "attribution", f"shop:{user.shop_id}"):
            remember(db, "attribution", f"shop:{user.shop_id}", {"visitor_id": payload.visitor_id, "landing_page": landing, **attribution})
    db.commit()
    return {"accepted": True}


def verify_resend(body, headers):
    secret = os.getenv("GROWTH_RESEND_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503, "Inbound webhook not configured")
    try:
        timestamp = int(headers.get("svix-timestamp", "0"))
        if abs(time.time() - timestamp) > 300:
            raise ValueError()
        signed = headers["svix-id"].encode() + b"." + str(timestamp).encode() + b"." + body
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        signatures = [s.split(",", 1)[1] for s in headers.get("svix-signature", "").split() if s.startswith("v1,")]
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            raise ValueError()
    except (ValueError, KeyError):
        raise HTTPException(401, "Invalid webhook signature") from None


@router.post("/webhooks/resend")
async def resend_webhook(request: Request, db: DB):
    body = await request.body()
    if len(body) > 64000:
        raise HTTPException(413, "Webhook too large")
    verify_resend(body, request.headers)
    event = json.loads(body)
    event_id = request.headers["svix-id"]
    if event.get("type") == "email.received":
        record(db, "provider-event:" + event_id, "PROVIDER_EVENT", "mailbox", event, source="resend_signed_webhook")
        enqueue(db, "inbound-webhook:" + event_id, "inbox", priority=100)
    else:
        from app.growth.messaging import record_signed_provider_event
        record_signed_provider_event(db, event_id, event)
    db.commit()
    return {"accepted": True}
