import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    AuditLogRecord,
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
    ReportScheduleRecord,
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
                    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS "
                    "approved_at TIMESTAMP WITH TIME ZONE"
                ))
                conn.execute(text(
                    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS "
                    "subtotal_cost NUMERIC(12, 2) DEFAULT 0"
                ))
                conn.execute(text(
                    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS "
                    "shipping_cost NUMERIC(12, 2) DEFAULT 0"
                ))
                conn.execute(text(
                    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS "
                    "approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_purchase_orders_approved_by_user_id "
                    "ON purchase_orders (approved_by_user_id)"
                ))
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                    "trial_ends_at TIMESTAMP WITH TIME ZONE"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "scope VARCHAR(32) DEFAULT 'storewide'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "match_mode VARCHAR(16) DEFAULT 'all'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "target_skus JSON DEFAULT '[]'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "product_title_contains VARCHAR(255) DEFAULT ''"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "categories JSON DEFAULT '[]'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "suppliers JSON DEFAULT '[]'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "tags JSON DEFAULT '[]'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "collections JSON DEFAULT '[]'"
                ))
                conn.execute(text(
                    "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS "
                    "locations JSON DEFAULT '[]'"
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
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS audit_log_records ("
                    "id SERIAL PRIMARY KEY, "
                    "shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE, "
                    "user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, "
                    "event_type VARCHAR(64) NOT NULL, "
                    "entity_type VARCHAR(64) NOT NULL, "
                    "entity_id VARCHAR(128) NOT NULL, "
                    "summary VARCHAR(1000) NOT NULL, "
                    "event_metadata JSON DEFAULT '{}' NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL"
                    ")"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_audit_log_records_shop_id "
                    "ON audit_log_records (shop_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_audit_log_records_created_at "
                    "ON audit_log_records (created_at)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS report_schedule_records ("
                    "id SERIAL PRIMARY KEY, "
                    "shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE, "
                    "report_type VARCHAR(64) NOT NULL, "
                    "cadence VARCHAR(32) DEFAULT 'weekly' NOT NULL, "
                    "channel VARCHAR(32) DEFAULT 'email' NOT NULL, "
                    "recipient_email VARCHAR(320) DEFAULT '' NOT NULL, "
                    "enabled BOOLEAN DEFAULT TRUE NOT NULL, "
                    "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL, "
                    "updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL, "
                    "CONSTRAINT uq_report_schedules_shop_report UNIQUE (shop_id, report_type)"
                    ")"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_report_schedule_records_shop_id "
                    "ON report_schedule_records (shop_id)"
                ))
                conn.execute(text(
                    "ALTER TABLE shopify_connections ADD COLUMN IF NOT EXISTS "
                    "access_token_expires_at TIMESTAMP WITH TIME ZONE"
                ))
                conn.execute(text(
                    "ALTER TABLE shopify_connections ADD COLUMN IF NOT EXISTS "
                    "refresh_token VARCHAR(500)"
                ))
                conn.execute(text(
                    "ALTER TABLE shopify_connections ADD COLUMN IF NOT EXISTS "
                    "refresh_token_expires_at TIMESTAMP WITH TIME ZONE"
                ))
            else:
                # SQLite: check column existence via PRAGMA before adding.
                result = conn.execute(text("PRAGMA table_info(purchase_orders)"))
                purchase_order_columns = {row[1] for row in result}
                if "approved_at" not in purchase_order_columns:
                    conn.execute(text(
                        "ALTER TABLE purchase_orders ADD COLUMN approved_at TIMESTAMP"
                    ))
                if "subtotal_cost" not in purchase_order_columns:
                    conn.execute(text(
                        "ALTER TABLE purchase_orders ADD COLUMN subtotal_cost NUMERIC(12, 2) DEFAULT 0"
                    ))
                if "shipping_cost" not in purchase_order_columns:
                    conn.execute(text(
                        "ALTER TABLE purchase_orders ADD COLUMN shipping_cost NUMERIC(12, 2) DEFAULT 0"
                    ))
                if "approved_by_user_id" not in purchase_order_columns:
                    conn.execute(text(
                        "ALTER TABLE purchase_orders ADD COLUMN approved_by_user_id INTEGER "
                        "REFERENCES users(id) ON DELETE SET NULL"
                    ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_purchase_orders_approved_by_user_id "
                    "ON purchase_orders (approved_by_user_id)"
                ))
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
                sqlite_alert_columns = {
                    "scope": "VARCHAR(32) DEFAULT 'storewide'",
                    "match_mode": "VARCHAR(16) DEFAULT 'all'",
                    "target_skus": "JSON DEFAULT '[]'",
                    "product_title_contains": "VARCHAR(255) DEFAULT ''",
                    "categories": "JSON DEFAULT '[]'",
                    "suppliers": "JSON DEFAULT '[]'",
                    "tags": "JSON DEFAULT '[]'",
                    "collections": "JSON DEFAULT '[]'",
                    "locations": "JSON DEFAULT '[]'",
                }
                for column_name, column_type in sqlite_alert_columns.items():
                    if column_name not in alert_columns:
                        conn.execute(text(
                            f"ALTER TABLE alert_rules ADD COLUMN {column_name} {column_type}"
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
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS audit_log_records ("
                    "id INTEGER PRIMARY KEY, "
                    "shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE, "
                    "user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, "
                    "event_type VARCHAR(64) NOT NULL, "
                    "entity_type VARCHAR(64) NOT NULL, "
                    "entity_id VARCHAR(128) NOT NULL, "
                    "summary VARCHAR(1000) NOT NULL, "
                    "event_metadata JSON DEFAULT '{}' NOT NULL, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL"
                    ")"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_audit_log_records_shop_id "
                    "ON audit_log_records (shop_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_audit_log_records_created_at "
                    "ON audit_log_records (created_at)"
                ))
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS report_schedule_records ("
                    "id INTEGER PRIMARY KEY, "
                    "shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE, "
                    "report_type VARCHAR(64) NOT NULL, "
                    "cadence VARCHAR(32) DEFAULT 'weekly' NOT NULL, "
                    "channel VARCHAR(32) DEFAULT 'email' NOT NULL, "
                    "recipient_email VARCHAR(320) DEFAULT '' NOT NULL, "
                    "enabled BOOLEAN DEFAULT 1 NOT NULL, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                    "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                    "CONSTRAINT uq_report_schedules_shop_report UNIQUE (shop_id, report_type)"
                    ")"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_report_schedule_records_shop_id "
                    "ON report_schedule_records (shop_id)"
                ))
                result = conn.execute(text("PRAGMA table_info(shopify_connections)"))
                connection_columns = {row[1] for row in result}
                sqlite_connection_columns = {
                    "access_token_expires_at": "TIMESTAMP",
                    "refresh_token": "VARCHAR(500)",
                    "refresh_token_expires_at": "TIMESTAMP",
                }
                for column_name, column_type in sqlite_connection_columns.items():
                    if column_name not in connection_columns:
                        conn.execute(text(
                            f"ALTER TABLE shopify_connections ADD COLUMN {column_name} {column_type}"
                        ))
            conn.commit()
        except Exception:
            logger.exception("Safe migration failed (non-fatal if column already exists)")


def init_db() -> None:
    # Importing model symbols ensures SQLAlchemy has registered all tables.
    _ = (
        AlertRuleRecord,
        AuditLogRecord,
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
        ReportScheduleRecord,
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
