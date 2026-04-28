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


if __name__ == "__main__":
    init_db()
    print("Database tables initialized.")
