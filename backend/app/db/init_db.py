import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    AlertRuleRecord,
    CategoryLeadTime,
    Inventory,
    MagicLinkToken,
    NotificationChannelRecord,
    OrderLineItem,
    Product,
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
            else:
                # SQLite: check column existence via PRAGMA before adding.
                result = conn.execute(text("PRAGMA table_info(users)"))
                existing = {row[1] for row in result}
                if "trial_ends_at" not in existing:
                    conn.execute(text(
                        "ALTER TABLE users ADD COLUMN trial_ends_at TIMESTAMP"
                    ))
            conn.commit()
        except Exception:
            logger.exception("Safe migration failed (non-fatal if column already exists)")


def init_db() -> None:
    # Importing model symbols ensures SQLAlchemy has registered all tables.
    _ = (
        AlertRuleRecord,
        CategoryLeadTime,
        Inventory,
        MagicLinkToken,
        NotificationChannelRecord,
        OrderLineItem,
        Product,
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
