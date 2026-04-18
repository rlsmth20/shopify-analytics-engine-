from app.db.base import Base
from app.db.models import (
    CategoryLeadTime,
    Inventory,
    OrderLineItem,
    Product,
    Shop,
    ShopifySyncRun,
    ShopSettings,
    VendorLeadTime,
)
from app.db.session import engine


def init_db() -> None:
    # Importing model symbols ensures SQLAlchemy has registered all tables.
    _ = (
        CategoryLeadTime,
        Inventory,
        OrderLineItem,
        Product,
        Shop,
        ShopifySyncRun,
        ShopSettings,
        VendorLeadTime,
    )
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables initialized.")
