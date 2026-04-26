from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("shop_id", "shopify_variant_id", name="uq_products_shop_variant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    shopify_product_id: Mapped[str] = mapped_column(String(255), index=True)
    shopify_variant_id: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    variant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sku_lead_time_days: Mapped[int | None] = mapped_column(nullable=True)

    shop: Mapped["Shop"] = relationship(back_populates="products")
    inventory_rows: Mapped[list["Inventory"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    order_line_items: Mapped[list["OrderLineItem"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "product_id",
            "shopify_location_id",
            name="uq_inventory_shop_product_location",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    shopify_location_id: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
        onupdate=func.now(),
    )

    shop: Mapped["Shop"] = relationship(back_populates="inventory_rows")
    product: Mapped[Product] = relationship(back_populates="inventory_rows")


class OrderLineItem(Base):
    __tablename__ = "order_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), index=True)
    shopify_order_id: Mapped[str] = mapped_column(String(255), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    quantity: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    shop: Mapped["Shop"] = relationship(back_populates="order_line_items")
    product: Mapped[Product] = relationship(back_populates="order_line_items")


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopify_domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    settings: Mapped["ShopSettings | None"] = relationship(
        back_populates="shop",
        cascade="all, delete-orphan",
        uselist=False,
    )
    products: Mapped[list[Product]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    inventory_rows: Mapped[list[Inventory]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    order_line_items: Mapped[list[OrderLineItem]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    sync_runs: Mapped[list["ShopifySyncRun"]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    vendor_lead_times: Mapped[list["VendorLeadTime"]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    category_lead_times: Mapped[list["CategoryLeadTime"]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    global_default_lead_time_days: Mapped[int]
    global_safety_buffer_days: Mapped[int]
    allow_mock_fallback: Mapped[bool] = mapped_column(Boolean, default=True)

    shop: Mapped[Shop] = relationship(back_populates="settings")


class ShopifySyncRun(Base):
    __tablename__ = "shopify_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    products_count: Mapped[int] = mapped_column(default=0)
    inventory_rows_count: Mapped[int] = mapped_column(default=0)
    order_line_items_count: Mapped[int] = mapped_column(default=0)

    shop: Mapped[Shop] = relationship(back_populates="sync_runs")


class VendorLeadTime(Base):
    __tablename__ = "vendor_lead_times"
    __table_args__ = (
        UniqueConstraint("shop_id", "vendor", name="uq_vendor_lead_times_shop_vendor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        index=True,
    )
    vendor: Mapped[str] = mapped_column(String(255), index=True)
    lead_time_days: Mapped[int]

    shop: Mapped[Shop] = relationship(back_populates="vendor_lead_times")


class CategoryLeadTime(Base):
    __tablename__ = "category_lead_times"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "category",
            name="uq_category_lead_times_shop_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(255), index=True)
    lead_time_days: Mapped[int]

    shop: Mapped[Shop] = relationship(back_populates="category_lead_times")


class AlertRuleRecord(Base):
    """Persisted alert rule. Alerts were in-memory in v0.2; persisted in v0.3."""

    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    trigger: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    threshold: Mapped[float] = mapped_column(Float, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
    )
    last_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class NotificationChannelRecord(Base):
    """Persisted channel configuration (email, sms, slack, webhook)."""

    __tablename__ = "notification_channels"

    channel: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    target: Mapped[str] = mapped_column(String(500), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
        onupdate=func.now(),
    )


class WaitlistSignup(Base):
    """Captures merchant interest before real auth + Stripe billing ship.

    Replaces /dashboard as the entry point. Stores email + shop domain +
    where they signed up from so we can prioritize follow-up.
    """

    __tablename__ = "waitlist_signups"
    __table_args__ = (
        UniqueConstraint("email", name="uq_waitlist_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    shopify_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
