from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import ValidationError

from app.integrations.shopify_client import ShopifyClientError
from app.schemas import (
    LatestShopifySyncStatusResponse,
    ProcessedCountsResponse,
    ShopifyIngestionRequest,
    ShopifyIngestionResponse,
    ShopifySyncRunResponse,
)
from app.services.shopify_ingestion import (
    LatestShopifySyncStatus,
    ProcessedCounts,
    ShopifyIngestionInputError,
    get_latest_shopify_sync_status,
    run_manual_shopify_ingestion,
)


router = APIRouter(prefix="/integrations/shopify", tags=["shopify"])


def _parse_request(
    payload: dict[str, Any] = Body(...),
) -> ShopifyIngestionRequest:
    try:
        return ShopifyIngestionRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=_format_validation_error(exc),
        ) from exc


def _format_validation_error(exc: ValidationError) -> str:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append(f"{location}: {error['msg']}")

    return "Invalid input. " + "; ".join(details)


@router.post("/ingest", response_model=ShopifyIngestionResponse)
def ingest_shopify(
    payload: ShopifyIngestionRequest = Depends(_parse_request),
) -> ShopifyIngestionResponse:
    try:
        summary = run_manual_shopify_ingestion(
            shopify_domain=payload.shopify_domain,
            access_token=payload.access_token,
        )
    except ShopifyIngestionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ShopifyClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ShopifyIngestionResponse(
        shops=_to_response_counts(summary.shops),
        products=_to_response_counts(summary.products),
        inventory_rows=_to_response_counts(summary.inventory_rows),
        order_line_items=_to_response_counts(summary.order_line_items),
    )


@router.get("/sync-status", response_model=LatestShopifySyncStatusResponse)
def read_latest_shopify_sync_status(
    shopify_domain: str = Query(min_length=1),
) -> LatestShopifySyncStatusResponse:
    try:
        status = get_latest_shopify_sync_status(shopify_domain)
    except ShopifyIngestionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LatestShopifySyncStatusResponse(
        shop_id=status.shop_id,
        shopify_domain=status.shopify_domain,
        latest_run=_to_sync_run_response(status),
    )


def _to_response_counts(counts: ProcessedCounts) -> ProcessedCountsResponse:
    return ProcessedCountsResponse(
        processed=counts.processed,
        inserted=counts.inserted,
        updated=counts.updated,
        skipped=counts.skipped,
    )


def _to_sync_run_response(
    status: LatestShopifySyncStatus,
) -> ShopifySyncRunResponse | None:
    if status.latest_run is None:
        return None

    return ShopifySyncRunResponse(
        id=status.latest_run.id,
        shop_id=status.latest_run.shop_id,
        started_at=status.latest_run.started_at,
        finished_at=status.latest_run.finished_at,
        status=status.latest_run.status,
        error_message=status.latest_run.error_message,
        products_count=status.latest_run.products_count,
        inventory_rows_count=status.latest_run.inventory_rows_count,
        order_line_items_count=status.latest_run.order_line_items_count,
    )
