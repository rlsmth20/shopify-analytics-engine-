"""Inventory risk snapshot lead capture for outbound campaigns."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import InventoryRiskSnapshotLead
from app.db.session import get_db_session
from app.services import rate_limit
from app.services.admin_access import require_admin_token
from app.services.spreadsheet_exports import leads_workbook, MIME

router = APIRouter(prefix="/inventory-risk-snapshot", tags=["inventory-risk-snapshot"])

InventoryIssue = Literal[
    "Stockouts",
    "Overstock / dead stock",
    "Reorder planning",
    "Supplier lead times",
    "Bundles / kits",
    "Not sure",
]

LeadStatus = Literal["New", "Reviewing", "Snapshot sent", "Demo booked", "Not qualified"]


def _check_admin_token(request: Request, token: Optional[str]) -> None:
    require_admin_token(
        request, token,
        disabled_detail="Admin export is disabled (ADMIN_BOOTSTRAP_TOKEN not set).",
    )


def _normalize_store_url(value: str) -> str:
    trimmed = value.strip().lower()
    if not trimmed:
        raise ValueError("Shopify store URL is required.")
    if " " in trimmed or "." not in trimmed:
        raise ValueError("Enter a valid Shopify store URL.")

    parsed = urlparse(trimmed if "://" in trimmed else f"https://{trimmed}")
    host = parsed.netloc or parsed.path
    if not host or "." not in host:
        raise ValueError("Enter a valid Shopify store URL.")
    if host in {"example.com", "test.com", "localhost"} or host.endswith(".test"):
        raise ValueError("Enter your real Shopify store URL.")
    return f"https://{host}{parsed.path if parsed.netloc else ''}".rstrip("/")


class SnapshotLeadRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company_name: str = Field(min_length=1, max_length=255)
    store_url: str = Field(min_length=4, max_length=500)
    approximate_sku_count: str = Field(min_length=1, max_length=64)
    biggest_inventory_issue: InventoryIssue
    source: str = Field(default="inventory_risk_snapshot", max_length=96)
    utm_source: Optional[str] = Field(default=None, max_length=255)
    utm_medium: Optional[str] = Field(default=None, max_length=255)
    utm_campaign: Optional[str] = Field(default=None, max_length=255)
    utm_content: Optional[str] = Field(default=None, max_length=255)
    utm_term: Optional[str] = Field(default=None, max_length=255)

    @field_validator("first_name", "company_name", "approximate_sku_count", "source")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required.")
        return stripped

    @field_validator("store_url")
    @classmethod
    def _valid_store_url(cls, value: str) -> str:
        return _normalize_store_url(value)

    @field_validator("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        stripped = (value or "").strip()
        return stripped or None


class SnapshotLeadResponse(BaseModel):
    id: int
    created_at: datetime
    first_name: str
    email: str
    company_name: str
    store_url: str
    approximate_sku_count: str
    biggest_inventory_issue: str
    source: str
    status: str


def _to_response(lead: InventoryRiskSnapshotLead) -> SnapshotLeadResponse:
    return SnapshotLeadResponse(
        id=lead.id,
        created_at=lead.created_at,
        first_name=lead.first_name,
        email=lead.email,
        company_name=lead.company_name,
        store_url=lead.store_url,
        approximate_sku_count=lead.approximate_sku_count,
        biggest_inventory_issue=lead.biggest_inventory_issue,
        source=lead.source,
        status=lead.status,
    )


@router.post("/leads", response_model=SnapshotLeadResponse)
def create_snapshot_lead(
    payload: SnapshotLeadRequest,
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
) -> SnapshotLeadResponse:
    rate_limit.enforce(request, ("lead_ip", None))
    lead = InventoryRiskSnapshotLead(
        first_name=payload.first_name,
        email=str(payload.email).lower().strip(),
        company_name=payload.company_name,
        store_url=payload.store_url,
        approximate_sku_count=payload.approximate_sku_count,
        biggest_inventory_issue=payload.biggest_inventory_issue,
        source=payload.source,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        status="New",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return _to_response(lead)


@router.get("/leads", response_model=list[SnapshotLeadResponse])
def list_snapshot_leads(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
    status_filter: Optional[LeadStatus] = None,
    limit: int = 200,
) -> list[SnapshotLeadResponse]:
    _check_admin_token(request, x_admin_token)
    query = select(InventoryRiskSnapshotLead).order_by(InventoryRiskSnapshotLead.created_at.desc())
    if status_filter:
        query = query.where(InventoryRiskSnapshotLead.status == status_filter)
    leads = db.scalars(query.limit(min(max(limit, 1), 1000))).all()
    return [_to_response(lead) for lead in leads]


@router.get("/leads/export.csv")
def export_snapshot_leads_csv(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> Response:
    """Legacy CSV export — kept as a fallback. Prefer /leads/export.xlsx for
    the formatted workbook with a Summary tab."""
    _check_admin_token(request, x_admin_token)
    leads = db.scalars(
        select(InventoryRiskSnapshotLead).order_by(InventoryRiskSnapshotLead.created_at.desc())
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "created_at", "first_name", "email", "company_name", "store_url",
        "approximate_sku_count", "biggest_inventory_issue", "source",
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "status",
    ])
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.created_at.isoformat() if lead.created_at else "",
            lead.first_name, lead.email, lead.company_name, lead.store_url,
            lead.approximate_sku_count, lead.biggest_inventory_issue, lead.source,
            lead.utm_source or "", lead.utm_medium or "", lead.utm_campaign or "",
            lead.utm_content or "", lead.utm_term or "", lead.status,
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory-risk-snapshot-leads.csv"},
    )


@router.get("/leads/export.xlsx")
def export_snapshot_leads_xlsx(
    request: Request,
    db: Annotated[DbSession, Depends(get_db_session)],
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> Response:
    """Formatted xlsx export — Summary tab (native Excel charts) plus a
    filterable Leads tab. Same auth model as the CSV endpoint."""
    _check_admin_token(request, x_admin_token)
    leads = db.scalars(
        select(InventoryRiskSnapshotLead).order_by(InventoryRiskSnapshotLead.created_at.desc())
    ).all()

    return Response(
        content=leads_workbook(leads), media_type=MIME,
        headers={"Content-Disposition": "attachment; filename=inventory-risk-snapshot-leads.xlsx"},
    )
