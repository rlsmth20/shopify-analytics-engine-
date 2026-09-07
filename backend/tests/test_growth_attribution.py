"""Attribution regressions run against isolated storage without external effects."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import InventoryRiskSnapshotLead, Shop, ShopifyConnection, User
from app.growth.funnel import reconcile
from app.growth.learning import evaluate_organic
from app.growth.models import Contact, Evidence, Experiment


class GrowthAttributionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.env = patch.dict("os.environ", {"GROWTH_EXCLUDED_SHOP_DOMAINS": "excluded.myshopify.com"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.engine.dispose()

    def account(self, db, email="merchant@example.test", domain="merchant.myshopify.com", admin=False):
        shop = Shop(shopify_domain=domain)
        db.add(shop)
        db.flush()
        db.add(User(email=email, shop_id=shop.id, is_admin=admin))
        db.add(ShopifyConnection(shop_id=shop.id, shopify_domain=domain, access_token="fixture-only"))
        db.commit()
        return shop.id

    def lead(self, db, email="merchant@example.test"):
        db.add(InventoryRiskSnapshotLead(first_name="Merchant", email=email, company_name="Fixture",
            store_url="https://unverified-store-claim.example.test", approximate_sku_count="50-250",
            biggest_inventory_issue="Stockouts", utm_campaign="fixture-organic"))
        db.commit()

    def test_same_batch_request_links_account_and_attributes_connection_once(self):
        with self.factory() as db:
            shop_id = self.account(db)
            self.lead(db)
            experiment = Experiment(key="fixture-organic", specification={"channel": "organic_search"},
                started_at=(datetime.now(timezone.utc) - timedelta(days=1)).timestamp(),
                stop_at=(datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
            db.add(experiment)
            db.commit()
            for _ in range(2):
                reconcile(db)
                db.commit()
            contact = db.scalar(select(Contact).where(Contact.email == "merchant@example.test"))
            self.assertEqual(contact.shop_id, shop_id)
            self.assertEqual(evaluate_organic(db, experiment)["qualified_stores"], 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(
                Evidence.kind == "IDENTITY_LINK", Evidence.subject == contact.id)), 1)

    def test_request_after_user_cursor_passes_still_links_account(self):
        with self.factory() as db:
            shop_id = self.account(db)
            reconcile(db)
            db.commit()
            self.lead(db)
            reconcile(db)
            db.commit()
            self.assertEqual(db.scalar(select(Contact).where(Contact.email == "merchant@example.test")).shop_id, shop_id)

    def test_late_research_contact_links_without_a_new_signup_or_form(self):
        with self.factory() as db:
            shop_id = self.account(db)
            reconcile(db)
            db.commit()
            contact = Contact(identity="email:merchant@example.test", email="merchant@example.test", source="fixture")
            db.add(contact)
            db.commit()
            reconcile(db)
            db.commit()
            self.assertEqual(contact.shop_id, shop_id)

    def test_unmatched_contacts_do_not_starve_bounded_identity_matching(self):
        with self.factory() as db:
            shop_id = self.account(db)
            for n in range(3):
                db.add(Contact(identity=f"email:unknown{n}@example.test", email=f"unknown{n}@example.test", source="fixture", created_at=0))
            contact = Contact(identity="email:merchant@example.test", email="merchant@example.test", source="fixture")
            db.add(contact)
            db.commit()
            reconcile(db, batch_size=1)
            db.commit()
            self.assertEqual(contact.shop_id, shop_id)

    def test_internal_accounts_and_claimed_store_urls_cannot_create_identity_links(self):
        with self.factory() as db:
            for email, domain, admin in [
                ("admin@example.test", "admin.myshopify.com", True),
                ("internal@skubase.io", "internal.myshopify.com", False),
                ("test@example.test", "excluded.myshopify.com", False),
            ]:
                self.account(db, email, domain, admin)
                self.lead(db, email)
            self.lead(db, "unknown@example.test")
            reconcile(db)
            db.commit()
            self.assertTrue(all(c.shop_id is None for c in db.scalars(select(Contact))))
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "IDENTITY_LINK")), 0)


if __name__ == "__main__":
    unittest.main()
