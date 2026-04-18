from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select

from app.config.lead_time import (
    MOCK_LEAD_TIME_CONFIG,
    LeadTimeConfig,
    build_lead_time_config,
)
from app.db.models import CategoryLeadTime, Shop, ShopSettings, VendorLeadTime
from app.db.session import session_scope


class ShopSettingsInputError(ValueError):
    """Raised when shop settings input is invalid."""


@dataclass(frozen=True)
class LeadTimeOverrideValue:
    name: str
    lead_time_days: int


@dataclass(frozen=True)
class ResolvedShopSettings:
    shop_id: int | None
    shopify_domain: str
    global_default_lead_time_days: int
    global_safety_buffer_days: int
    allow_mock_fallback: bool
    is_persisted: bool
    vendor_lead_times: dict[str, int]
    category_lead_times: dict[str, int]
    uses_file_defaults: bool

    def to_lead_time_config(self) -> LeadTimeConfig:
        if self.uses_file_defaults:
            return build_lead_time_config(
                global_default_lead_time_days=self.global_default_lead_time_days,
                global_safety_buffer_days=self.global_safety_buffer_days,
                allow_mock_fallback=self.allow_mock_fallback,
            )

        return LeadTimeConfig(
            global_default_lead_time_days=self.global_default_lead_time_days,
            global_safety_buffer_days=self.global_safety_buffer_days,
            allow_mock_fallback=self.allow_mock_fallback,
            vendor_lead_times=self.vendor_lead_times,
            category_lead_times=self.category_lead_times,
        )


def get_shop_settings(shopify_domain: str) -> ResolvedShopSettings:
    normalized_domain = normalize_shopify_domain(shopify_domain)

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            return build_default_shop_settings(normalized_domain)

        settings = session.scalar(
            select(ShopSettings).where(ShopSettings.shop_id == shop.id)
        )
        vendor_lead_times = _load_vendor_lead_times_by_shop(session).get(shop.id, {})
        category_lead_times = _load_category_lead_times_by_shop(session).get(
            shop.id, {}
        )
        return _build_resolved_shop_settings(
            shop,
            settings,
            vendor_lead_times,
            category_lead_times,
        )


def upsert_shop_settings(
    *,
    shopify_domain: str,
    global_default_lead_time_days: int,
    global_safety_buffer_days: int,
    allow_mock_fallback: bool,
) -> ResolvedShopSettings:
    normalized_domain = normalize_shopify_domain(shopify_domain)
    if global_default_lead_time_days < 1:
        raise ShopSettingsInputError(
            "global_default_lead_time_days must be at least 1."
        )
    if global_safety_buffer_days < 0:
        raise ShopSettingsInputError(
            "global_safety_buffer_days must be at least 0."
        )

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            shop = Shop(shopify_domain=normalized_domain)
            session.add(shop)
            session.flush()

        settings = session.scalar(
            select(ShopSettings).where(ShopSettings.shop_id == shop.id)
        )
        if settings is None:
            settings = ShopSettings(
                shop_id=shop.id,
                global_default_lead_time_days=global_default_lead_time_days,
                global_safety_buffer_days=global_safety_buffer_days,
                allow_mock_fallback=allow_mock_fallback,
            )
            session.add(settings)
        else:
            settings.global_default_lead_time_days = global_default_lead_time_days
            settings.global_safety_buffer_days = global_safety_buffer_days
            settings.allow_mock_fallback = allow_mock_fallback

        session.flush()
        return _build_resolved_shop_settings(
            shop,
            settings,
            _load_vendor_lead_times_by_shop(session).get(shop.id, {}),
            _load_category_lead_times_by_shop(session).get(shop.id, {}),
        )


def load_effective_shop_settings_map(session) -> dict[int, ResolvedShopSettings]:
    vendor_lead_times_by_shop = _load_vendor_lead_times_by_shop(session)
    category_lead_times_by_shop = _load_category_lead_times_by_shop(session)
    rows = session.execute(
        select(Shop, ShopSettings).outerjoin(ShopSettings, ShopSettings.shop_id == Shop.id)
    ).all()
    return {
        shop.id: _build_resolved_shop_settings(
            shop,
            settings,
            vendor_lead_times_by_shop.get(shop.id, {}),
            category_lead_times_by_shop.get(shop.id, {}),
        )
        for shop, settings in rows
    }


def build_default_shop_settings(shopify_domain: str = "defaults") -> ResolvedShopSettings:
    return ResolvedShopSettings(
        shop_id=None,
        shopify_domain=shopify_domain,
        global_default_lead_time_days=MOCK_LEAD_TIME_CONFIG.global_default_lead_time_days,
        global_safety_buffer_days=MOCK_LEAD_TIME_CONFIG.global_safety_buffer_days,
        allow_mock_fallback=MOCK_LEAD_TIME_CONFIG.allow_mock_fallback,
        is_persisted=False,
        vendor_lead_times=dict(MOCK_LEAD_TIME_CONFIG.vendor_lead_times),
        category_lead_times=dict(MOCK_LEAD_TIME_CONFIG.category_lead_times),
        uses_file_defaults=True,
    )


def get_vendor_lead_times(shopify_domain: str) -> tuple[int | None, str, list[LeadTimeOverrideValue]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            return None, normalized_domain, []

        items = session.scalars(
            select(VendorLeadTime)
            .where(VendorLeadTime.shop_id == shop.id)
            .order_by(VendorLeadTime.vendor.asc())
        ).all()
        return (
            shop.id,
            shop.shopify_domain,
            [
                LeadTimeOverrideValue(
                    name=item.vendor,
                    lead_time_days=item.lead_time_days,
                )
                for item in items
            ],
        )


def upsert_vendor_lead_times(
    *,
    shopify_domain: str,
    items: list[LeadTimeOverrideValue],
) -> tuple[int, str, list[LeadTimeOverrideValue]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)
    normalized_items = _normalize_lead_time_items(items, kind="vendor")

    with session_scope() as session:
        shop = _get_or_create_shop(session, normalized_domain)
        existing_rows = {
            row.vendor: row
            for row in session.scalars(
                select(VendorLeadTime).where(VendorLeadTime.shop_id == shop.id)
            )
        }

        for stale_name, row in list(existing_rows.items()):
            if stale_name not in normalized_items:
                session.delete(row)

        for name, lead_time_days in normalized_items.items():
            row = existing_rows.get(name)
            if row is None:
                session.add(
                    VendorLeadTime(
                        shop_id=shop.id,
                        vendor=name,
                        lead_time_days=lead_time_days,
                    )
                )
                continue

            row.lead_time_days = lead_time_days

        session.flush()
        return (
            shop.id,
            shop.shopify_domain,
            [
                LeadTimeOverrideValue(name=name, lead_time_days=lead_time_days)
                for name, lead_time_days in sorted(normalized_items.items())
            ],
        )


def get_category_lead_times(
    shopify_domain: str,
) -> tuple[int | None, str, list[LeadTimeOverrideValue]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            return None, normalized_domain, []

        items = session.scalars(
            select(CategoryLeadTime)
            .where(CategoryLeadTime.shop_id == shop.id)
            .order_by(CategoryLeadTime.category.asc())
        ).all()
        return (
            shop.id,
            shop.shopify_domain,
            [
                LeadTimeOverrideValue(
                    name=item.category,
                    lead_time_days=item.lead_time_days,
                )
                for item in items
            ],
        )


def upsert_category_lead_times(
    *,
    shopify_domain: str,
    items: list[LeadTimeOverrideValue],
) -> tuple[int, str, list[LeadTimeOverrideValue]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)
    normalized_items = _normalize_lead_time_items(items, kind="category")

    with session_scope() as session:
        shop = _get_or_create_shop(session, normalized_domain)
        existing_rows = {
            row.category: row
            for row in session.scalars(
                select(CategoryLeadTime).where(CategoryLeadTime.shop_id == shop.id)
            )
        }

        for stale_name, row in list(existing_rows.items()):
            if stale_name not in normalized_items:
                session.delete(row)

        for name, lead_time_days in normalized_items.items():
            row = existing_rows.get(name)
            if row is None:
                session.add(
                    CategoryLeadTime(
                        shop_id=shop.id,
                        category=name,
                        lead_time_days=lead_time_days,
                    )
                )
                continue

            row.lead_time_days = lead_time_days

        session.flush()
        return (
            shop.id,
            shop.shopify_domain,
            [
                LeadTimeOverrideValue(name=name, lead_time_days=lead_time_days)
                for name, lead_time_days in sorted(normalized_items.items())
            ],
        )


def normalize_shopify_domain(shopify_domain: str) -> str:
    candidate = shopify_domain.strip()
    if not candidate:
        raise ShopSettingsInputError("shopify_domain must not be empty.")

    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    domain = (parsed.netloc or parsed.path).strip().lower()

    if not domain:
        raise ShopSettingsInputError(
            "shopify_domain must be a hostname like store-name.myshopify.com."
        )
    if parsed.query or parsed.fragment:
        raise ShopSettingsInputError("shopify_domain must not include query params.")
    if parsed.netloc and parsed.path not in ("", "/"):
        raise ShopSettingsInputError("shopify_domain must not include a path.")
    if "/" in domain or " " in domain or "." not in domain:
        raise ShopSettingsInputError(
            "shopify_domain must be a hostname like store-name.myshopify.com."
        )
    if domain.startswith((".", "-")) or domain.endswith((".", "-")) or ".." in domain:
        raise ShopSettingsInputError(
            "shopify_domain must be a valid hostname like store-name.myshopify.com."
        )
    if not all(character.isalnum() or character in ".-" for character in domain):
        raise ShopSettingsInputError(
            "shopify_domain contains invalid characters."
        )

    return domain


def _build_resolved_shop_settings(
    shop: Shop,
    settings: ShopSettings | None,
    vendor_lead_times: dict[str, int],
    category_lead_times: dict[str, int],
) -> ResolvedShopSettings:
    if settings is None and not vendor_lead_times and not category_lead_times:
        default_settings = build_default_shop_settings(shop.shopify_domain)
        return ResolvedShopSettings(
            shop_id=shop.id,
            shopify_domain=shop.shopify_domain,
            global_default_lead_time_days=default_settings.global_default_lead_time_days,
            global_safety_buffer_days=default_settings.global_safety_buffer_days,
            allow_mock_fallback=default_settings.allow_mock_fallback,
            is_persisted=False,
            vendor_lead_times=dict(default_settings.vendor_lead_times),
            category_lead_times=dict(default_settings.category_lead_times),
            uses_file_defaults=True,
        )

    default_settings = build_default_shop_settings(shop.shopify_domain)
    return ResolvedShopSettings(
        shop_id=shop.id,
        shopify_domain=shop.shopify_domain,
        global_default_lead_time_days=(
            settings.global_default_lead_time_days
            if settings is not None
            else default_settings.global_default_lead_time_days
        ),
        global_safety_buffer_days=(
            settings.global_safety_buffer_days
            if settings is not None
            else default_settings.global_safety_buffer_days
        ),
        allow_mock_fallback=(
            settings.allow_mock_fallback
            if settings is not None
            else default_settings.allow_mock_fallback
        ),
        is_persisted=settings is not None,
        vendor_lead_times=dict(vendor_lead_times),
        category_lead_times=dict(category_lead_times),
        uses_file_defaults=False,
    )


def _load_vendor_lead_times_by_shop(session) -> dict[int, dict[str, int]]:
    rows = session.execute(
        select(VendorLeadTime.shop_id, VendorLeadTime.vendor, VendorLeadTime.lead_time_days)
    ).all()
    lead_times_by_shop: dict[int, dict[str, int]] = {}
    for shop_id, vendor, lead_time_days in rows:
        lead_times_by_shop.setdefault(shop_id, {})[vendor] = int(lead_time_days)
    return lead_times_by_shop


def _load_category_lead_times_by_shop(session) -> dict[int, dict[str, int]]:
    rows = session.execute(
        select(
            CategoryLeadTime.shop_id,
            CategoryLeadTime.category,
            CategoryLeadTime.lead_time_days,
        )
    ).all()
    lead_times_by_shop: dict[int, dict[str, int]] = {}
    for shop_id, category, lead_time_days in rows:
        lead_times_by_shop.setdefault(shop_id, {})[category] = int(lead_time_days)
    return lead_times_by_shop


def _get_or_create_shop(session, shopify_domain: str) -> Shop:
    shop = session.scalar(select(Shop).where(Shop.shopify_domain == shopify_domain))
    if shop is None:
        shop = Shop(shopify_domain=shopify_domain)
        session.add(shop)
        session.flush()

    return shop


def _normalize_lead_time_items(
    items: list[LeadTimeOverrideValue],
    *,
    kind: str,
) -> dict[str, int]:
    normalized_items: dict[str, int] = {}
    for item in items:
        name = item.name.strip()
        if not name:
            raise ShopSettingsInputError(f"{kind} must not be empty.")
        if item.lead_time_days < 1:
            raise ShopSettingsInputError("lead_time_days must be at least 1.")
        if name in normalized_items:
            raise ShopSettingsInputError(
                f"Duplicate {kind} lead time entry: {name}."
            )
        normalized_items[name] = item.lead_time_days

    return normalized_items
