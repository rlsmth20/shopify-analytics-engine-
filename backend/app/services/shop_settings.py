from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select

from app.config.lead_time import (
    DEFAULT_SHOP_LEAD_TIME_CONFIG,
    LeadTimeConfig,
)
from app.db.models import CategoryLeadTime, Product, Shop, ShopSettings, VendorLeadTime
from app.db.session import session_scope
from app.services.shop_skus import AmbiguousSkuError, build_sku_alias_index


class ShopSettingsInputError(ValueError):
    """Raised when shop settings input is invalid."""


class ShopSettingsIdentityError(ShopSettingsInputError):
    """An alias does not identify a safe SKU override to change."""


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
        # Always use the resolved maps, including empty maps for a new shop.
        # Rebuilding from fixture defaults here would introduce unsaved rules.
        return LeadTimeConfig(
            global_default_lead_time_days=self.global_default_lead_time_days,
            global_safety_buffer_days=self.global_safety_buffer_days,
            allow_mock_fallback=self.allow_mock_fallback,
            vendor_lead_times=dict(self.vendor_lead_times),
            category_lead_times=dict(self.category_lead_times),
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
        vendor_lead_times = _load_vendor_lead_times_by_shop(session, shop_id=shop.id).get(shop.id, {})
        category_lead_times = _load_category_lead_times_by_shop(session, shop_id=shop.id).get(
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
            _load_vendor_lead_times_by_shop(session, shop_id=shop.id).get(shop.id, {}),
            _load_category_lead_times_by_shop(session, shop_id=shop.id).get(shop.id, {}),
        )


def load_effective_shop_settings_map(session, *, shop_id: int | None = None) -> dict[int, ResolvedShopSettings]:
    """Load one request's shop settings, or all shops for batch processing."""
    vendor_lead_times_by_shop = _load_vendor_lead_times_by_shop(session, shop_id=shop_id)
    category_lead_times_by_shop = _load_category_lead_times_by_shop(session, shop_id=shop_id)
    query = select(Shop, ShopSettings).outerjoin(ShopSettings, ShopSettings.shop_id == Shop.id)
    if shop_id is not None:
        query = query.where(Shop.id == shop_id)
    rows = session.execute(query).all()
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
        global_default_lead_time_days=DEFAULT_SHOP_LEAD_TIME_CONFIG.global_default_lead_time_days,
        global_safety_buffer_days=DEFAULT_SHOP_LEAD_TIME_CONFIG.global_safety_buffer_days,
        allow_mock_fallback=DEFAULT_SHOP_LEAD_TIME_CONFIG.allow_mock_fallback,
        is_persisted=False,
        vendor_lead_times=dict(DEFAULT_SHOP_LEAD_TIME_CONFIG.vendor_lead_times),
        category_lead_times=dict(DEFAULT_SHOP_LEAD_TIME_CONFIG.category_lead_times),
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


def get_sku_lead_times(
    shopify_domain: str,
) -> tuple[int | None, str, list[LeadTimeOverrideValue], list[str]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)

    with session_scope() as session:
        shop = session.scalar(
            select(Shop).where(Shop.shopify_domain == normalized_domain)
        )
        if shop is None:
            return None, normalized_domain, [], []

        products = session.scalars(
            select(Product)
            .where(Product.shop_id == shop.id)
            .order_by(Product.sku.asc(), Product.name.asc())
        ).all()
        items, warnings = _sku_override_view(products, build_sku_alias_index(session, shop.id))
        return shop.id, shop.shopify_domain, items, warnings


def upsert_sku_lead_times(
    *,
    shopify_domain: str,
    items: list[LeadTimeOverrideValue],
) -> tuple[int, str, list[LeadTimeOverrideValue], list[str]]:
    normalized_domain = normalize_shopify_domain(shopify_domain)
    normalized_items = _normalize_lead_time_items(items, kind="SKU")

    with session_scope() as session:
        shop = _get_or_create_shop(session, normalized_domain)
        products = session.scalars(
            select(Product).where(Product.shop_id == shop.id)
        ).all()
        index = build_sku_alias_index(session, shop.id)
        products_by_id = {product.id: product for product in products}
        requested = {}
        # Validate the complete request before clearing any prior override.
        for sku_id, lead_time_days in normalized_items.items():
            try:
                product = index.resolve(sku_id)
            except AmbiguousSkuError as exc:
                candidates = [products_by_id[product_id] for product_id in exc.product_ids]
                if candidates and all(product.sku_lead_time_days == lead_time_days for product in candidates):
                    continue  # Unchanged unresolved rows may accompany an unrelated safe edit.
                raise ShopSettingsIdentityError(
                    f"SKU '{sku_id}' matches multiple products. Review its identity before changing this override; no overrides were changed."
                ) from None
            if product is None:
                raise ShopSettingsInputError(
                    f"SKU lead time entry '{sku_id}' does not match a synced SKU."
                )
            requested[product.id] = lead_time_days

        mutable_ids = set(requested)
        for sku_id in {_sku_id_for_product(product) for product in products}:
            try:
                product = index.resolve(sku_id)
            except AmbiguousSkuError:
                continue
            if product is not None:
                mutable_ids.add(product.id)
        # Snapshot replacement applies only to uniquely resolved products.
        # Retired stubs and unresolved aliases retain their data, with warnings.
        for product_id in mutable_ids:
            products_by_id[product_id].sku_lead_time_days = requested.get(product_id)

        session.flush()
        saved_items, warnings = _sku_override_view(products, index)
        return shop.id, shop.shopify_domain, saved_items, warnings


def _sku_override_view(products, index):
    products_by_id = {product.id: product for product in products}
    selected_ids, items, warnings = set(), [], []
    for alias in sorted({_sku_id_for_product(product) for product in products}):
        try:
            product = index.resolve(alias)
        except AmbiguousSkuError as exc:
            candidates = [products_by_id[product_id] for product_id in exc.product_ids]
            selected_ids.update(exc.product_ids)
            values = {product.sku_lead_time_days for product in candidates}
            if any(value is not None for value in values):
                warnings.append(f"SKU '{alias}' has unresolved product identities. Its existing overrides were retained; review them before making changes.")
            if len(values) == 1 and None not in values:
                items.append(LeadTimeOverrideValue(name=alias, lead_time_days=values.pop()))
            continue
        if product is not None:
            selected_ids.add(product.id)
            if product.sku_lead_time_days is not None:
                items.append(LeadTimeOverrideValue(name=alias, lead_time_days=product.sku_lead_time_days))
    retained = [product for product in products if product.id not in selected_ids and product.sku_lead_time_days is not None]
    if retained:
        warnings.append(f"{len(retained)} override(s) on retired or superseded product records were retained. They were not reassigned to current products.")
    return items, warnings


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


def _load_vendor_lead_times_by_shop(session, *, shop_id: int | None = None) -> dict[int, dict[str, int]]:
    query = select(VendorLeadTime.shop_id, VendorLeadTime.vendor, VendorLeadTime.lead_time_days)
    if shop_id is not None:
        query = query.where(VendorLeadTime.shop_id == shop_id)
    rows = session.execute(query).all()
    lead_times_by_shop: dict[int, dict[str, int]] = {}
    for shop_id, vendor, lead_time_days in rows:
        lead_times_by_shop.setdefault(shop_id, {})[vendor] = int(lead_time_days)
    return lead_times_by_shop


def _load_category_lead_times_by_shop(session, *, shop_id: int | None = None) -> dict[int, dict[str, int]]:
    query = select(CategoryLeadTime.shop_id, CategoryLeadTime.category, CategoryLeadTime.lead_time_days)
    if shop_id is not None:
        query = query.where(CategoryLeadTime.shop_id == shop_id)
    rows = session.execute(query).all()
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


def _sku_id_for_product(product: Product) -> str:
    if product.sku:
        return product.sku[:128]

    bits = []
    for part in (product.name, product.variant_name, str(product.id)):
        if part is None:
            continue
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(part))
        slug = "-".join(filter(None, slug.split("-")))
        if slug:
            bits.append(slug)
    return ("-".join(bits) or "sku-unknown")[:128]
