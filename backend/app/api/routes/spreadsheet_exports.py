"""Stateless formatter for explicitly submitted report results; no database access."""
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from app.schemas_exports import HistoryExport, WorkbookExport
from app.services.spreadsheet_exports import MIME, health_workbook, history_workbook

router = APIRouter(prefix="/exports", tags=["exports"])
MAX_BYTES = 1_000_000
_slots = BoundedSemaphore(2)
_payload = TypeAdapter(WorkbookExport)


@router.post("/workbook.xlsx")
async def export_workbook(request: Request) -> Response:
    # Public health-check and sample users can format their own submitted data.
    # This endpoint cannot retrieve shop records, accept formulas, or fetch URLs.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "This export is too large. Download CSV instead.")
    try:
        payload = _payload.validate_json(data)
    except ValidationError:
        # Do not echo inventory values in validation errors or logs.
        raise HTTPException(422, "Invalid report data. Refresh the results and try again.") from None
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "Excel exports are busy. Please try again shortly.", headers={"Retry-After": "5"})
    try:
        builder = history_workbook if isinstance(payload, HistoryExport) else health_workbook
        content = await run_in_threadpool(builder, payload)
    finally:
        _slots.release()
    name = "inventory-history" if isinstance(payload, HistoryExport) else "inventory-health-check"
    suffix = "-sample" if payload.sample else ""
    return Response(content, media_type=MIME, headers={
        "Content-Disposition": f'attachment; filename="skubase-{name}{suffix}.xlsx"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })
