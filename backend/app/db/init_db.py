import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    AlertRuleRecord,
    CategoryLeadTime,
    InventoryRiskSnapshotLead,
    Inventory,
    MagicLinkToken,
    NotificationChannelRecord,
    OrderLineItem,
    Product,
    PurchaseOrderLineRecord,
    PurchaseOrderReceiptRecord,
    PurchaseOrderRecord,
    Session,
    Shop,
    ShopifyConnection,
    ShopifySyncRun,
    ShopSettings,
    Subscription,
    User,
    VendorLeadTime,
    WaitlistSignup,
)
from app.db.session import engine

logger = logging.getLogger(__name__)


def run_safe_migrations() -> None:
    """Add columns introduced after initial deployment.

    Uses ADD COLUMN IF NOT EXISTS (PostgreSQL) or a pragma check (SQLite)
    so re-running on an already-migrated DB is a no-op.
    """
    db_url = str(engine.url)
    is_postgres = "postgresql" in db_url or "postgres" in db_url

    with engine.connect() as conn:
        try:
            if is_postgres:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                    "trial_ends_at TIMESTAMP WITH TIME ZONE"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_alert_rules_shop_id "
                    "ON alert_rules (shop_id)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS inventory_risk_snapshot_leads ("
                    "id SERIAL PRIMARY KEY, "
                    "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), "
                    "first_name VARCHAR(120) NOT NULL, "
                    "email VARCHAR(320) NOT NULL, "
                    "company_name VARCHAR(255) NOT NULL, "
                    "store_url VARCHAR(500) NOT NULL, "
                    "approximate_sku_count VARCHAR(64) NOT NULL, "
                    "biggest_inventory_issue VARCHAR(64) NOT NULL, "
                    "source VARCHAR(96) DEFAULT 'inventory_risk_snapshot' NOT NULL, "
                    "utm_source VARCHAR(255), "
                    "utm_medium VARCHAR(255), "
                    "utm_campaign VARCHAR(255), "
                    "utm_content VARCHAR(255), "
                    "utm_term VARCHAR(255), "
                    "status VARCHAR(64) DEFAULT 'New' NOT NULL"
                    ")"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_inventory_risk_snapshot_leads_created_at "
                    "ON inventory_risk_snapshot_leads (created_at)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_inventory_risk_snapshot_leads_email "
                    "ON inventory_risk_snapshot_leads (email)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_inventory_risk_snapshot_leads_status "
                    "ON inventory_risk_snapshot_leads (status)"
                ))
            else:
                # SQLite: check column existence via PRAGMA before adding.
                result = conn.execute(text("PRAGMA table_info(users)"))
                existing = {row[1] for row in result}
                if "trial_ends_at" not in existing:
                    conn.execute(text(
                        "ALTER TABLE users ADD COLUMN trial_ends_at TIMESTAMP"
                    ))
                result = conn.execute(text("PRAGMA table_info(alert_rules)"))
                alert_columns = {row[1] for row in result}
                if "shop_id" not in alert_columns:
                    conn.execute(text(
                        "ALTER TABLE alert_rules ADD COLUMN shop_id INTEGER "
                        "REFERENCES shops(id) ON DELETE CASCADE"
                    ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_alert_rules_shop_id "
                    "ON alert_rules (shop_id)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS inventory_risk_snapshot_leads ("
                    "id INTEGER PRIMARY KEY, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                    "first_name VARCHAR(120) NOT NULL, "
                    "email VARCHAR(320) NOT NULL, "
                    "company_name VARCHAR(255) NOT NULL, "
                    "store_url VARCHAR(500) NOT NULL, "
                    "approximate_sku_count VARCHAR(64) NOT NULL, "
                    "biggest_inventory_issue VARCHAR(64) NOT NULL, "
                    "source VARCHAR(96) DEFAULT 'inventory_risk_snapshot' NOT NULL, "
                    "utm_source VARCHAR(255), "
                    "utm_medium VARCHAR(255), "
                    "utm_campaign VARCHAR(255), "
                    "utm_content VARCHAR(255), "
                    "utm_term VARCHAR(255), "
                    "status VARCHAR(64) DEFAULT 'New' NOT NULL"
                    ")"
                ))
            conn.commit()
        except Exception:
            logger.exception("Safe migration failed (non-fatal if column already exists)")


def init_db() -> None:
    # Importing model symbols ensures SQLAlchemy has registered all tables.
    _ = (
        AlertRuleRecord,
        CategoryLeadTime,
        InventoryRiskSnapshotLead,
        Inventory,
        MagicLinkToken,
        NotificationChannelRecord,
        OrderLineItem,
        Product,
        PurchaseOrderLineRecord,
        PurchaseOrderReceiptRecord,
        PurchaseOrderRecord,
        Session,
        Shop,
        ShopifyConnection,
        ShopifySyncRun,
        ShopSettings,
        Subscription,
        User,
        VendorLeadTime,
        WaitlistSignup,
    )
    Base.metadata.create_all(bind=engine)
    run_safe_migrations()


if __name__ == "__main__":
    init_db()
    print("Database tables initialized.")
