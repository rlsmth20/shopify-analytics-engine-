from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    CategoryLeadTimeEntry,
    CategoryLeadTimeSettingsResponse,
    ShopSettingsResponse,
    UpdateCategoryLeadTimesRequest,
    UpdateShopSettingsRequest,
    UpdateVendorLeadTimesRequest,
    VendorLeadTimeEntry,
    VendorLeadTimeSettingsResponse,
)
from app.services.shop_settings import (
    LeadTimeOverrideValue,
    ShopSettingsInputError,
    get_category_lead_times,
    get_shop_settings,
    get_vendor_lead_times,
    upsert_category_lead_times,
    upsert_shop_settings,
    upsert_vendor_lead_times,
)


router = APIRouter(prefix="/shop-settings", tags=["shop-settings"])


@router.get("", response_model=ShopSettingsResponse)
def read_shop_settings(
    shopify_domain: str = Query(min_length=1),
) -> ShopSettingsResponse:
    try:
        settings = get_shop_settings(shopify_domain)
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ShopSettingsResponse(
        shop_id=settings.shop_id,
        shopify_domain=settings.shopify_domain,
        global_default_lead_time_days=settings.global_default_lead_time_days,
        global_safety_buffer_days=settings.global_safety_buffer_days,
        allow_mock_fallback=settings.allow_mock_fallback,
        is_persisted=settings.is_persisted,
    )


@router.put("", response_model=ShopSettingsResponse)
def update_shop_settings(
    payload: UpdateShopSettingsRequest,
) -> ShopSettingsResponse:
    try:
        settings = upsert_shop_settings(
            shopify_domain=payload.shopify_domain,
            global_default_lead_time_days=payload.global_default_lead_time_days,
            global_safety_buffer_days=payload.global_safety_buffer_days,
            allow_mock_fallback=payload.allow_mock_fallback,
        )
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ShopSettingsResponse(
        shop_id=settings.shop_id,
        shopify_domain=settings.shopify_domain,
        global_default_lead_time_days=settings.global_default_lead_time_days,
        global_safety_buffer_days=settings.global_safety_buffer_days,
        allow_mock_fallback=settings.allow_mock_fallback,
        is_persisted=settings.is_persisted,
    )


@router.get("/vendor-lead-times", response_model=VendorLeadTimeSettingsResponse)
def read_vendor_lead_times(
    shopify_domain: str = Query(min_length=1),
) -> VendorLeadTimeSettingsResponse:
    try:
        shop_id, normalized_domain, items = get_vendor_lead_times(shopify_domain)
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return VendorLeadTimeSettingsResponse(
        shop_id=shop_id,
        shopify_domain=normalized_domain,
        items=[
            VendorLeadTimeEntry(vendor=item.name, lead_time_days=item.lead_time_days)
            for item in items
        ],
    )


@router.put("/vendor-lead-times", response_model=VendorLeadTimeSettingsResponse)
def update_vendor_lead_times(
    payload: UpdateVendorLeadTimesRequest,
) -> VendorLeadTimeSettingsResponse:
    try:
        shop_id, normalized_domain, items = upsert_vendor_lead_times(
            shopify_domain=payload.shopify_domain,
            items=[
                LeadTimeOverrideValue(
                    name=item.vendor,
                    lead_time_days=item.lead_time_days,
                )
                for item in payload.items
            ],
        )
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return VendorLeadTimeSettingsResponse(
        shop_id=shop_id,
        shopify_domain=normalized_domain,
        items=[
            VendorLeadTimeEntry(vendor=item.name, lead_time_days=item.lead_time_days)
            for item in items
        ],
    )


@router.get("/category-lead-times", response_model=CategoryLeadTimeSettingsResponse)
def read_category_lead_times(
    shopify_domain: str = Query(min_length=1),
) -> CategoryLeadTimeSettingsResponse:
    try:
        shop_id, normalized_domain, items = get_category_lead_times(shopify_domain)
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CategoryLeadTimeSettingsResponse(
        shop_id=shop_id,
        shopify_domain=normalized_domain,
        items=[
            CategoryLeadTimeEntry(
                category=item.name,
                lead_time_days=item.lead_time_days,
            )
            for item in items
        ],
    )


@router.put("/category-lead-times", response_model=CategoryLeadTimeSettingsResponse)
def update_category_lead_times(
    payload: UpdateCategoryLeadTimesRequest,
) -> CategoryLeadTimeSettingsResponse:
    try:
        shop_id, normalized_domain, items = upsert_category_lead_times(
            shopify_domain=payload.shopify_domain,
            items=[
                LeadTimeOverrideValue(
                    name=item.category,
                    lead_time_days=item.lead_time_days,
                )
                for item in payload.items
            ],
        )
    except ShopSettingsInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CategoryLeadTimeSettingsResponse(
        shop_id=shop_id,
        shopify_domain=normalized_domain,
        items=[
            CategoryLeadTimeEntry(
                category=item.name,
                lead_time_days=item.lead_time_days,
            )
            for item in items
        ],
    )
