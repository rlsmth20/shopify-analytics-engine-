"""Real shop defaults must not inherit purchasing assumptions from demo fixtures."""
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes.actions import _build_action_feed
from app.config.lead_time import MOCK_LEAD_TIME_CONFIG, build_lead_time_config
from app.db.models import Base, CategoryLeadTime, Inventory, OrderLineItem, Product, Shop, ShopSettings, VendorLeadTime
from app.services import shop_settings
from app.services.inventory_engine import build_inventory_actions
from app.services.reorder_optimizer import build_reorder_suggestions
from app.services.shop_skus import load_skus_for_shop


class ShopDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.shop = Shop(shopify_domain="defaults-test.myshopify.com")
        self.db.add(self.shop)
        self.db.commit()

        @contextmanager
        def local_session():
            yield self.db
            self.db.commit()

        sessions = patch.object(shop_settings, "session_scope", local_session)
        sessions.start()
        self.addCleanup(sessions.stop)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_product(self, *, sku_lead_time_days=None):
        product = Product(shop_id=self.shop.id, shopify_product_id="1", shopify_variant_id="1",
                          sku="REAL-COAT", name="Merchant coat", vendor="Northstar Apparel",
                          category="outerwear", price=20, cost=10, sku_lead_time_days=sku_lead_time_days)
        self.db.add(product)
        self.db.flush()
        self.db.add(Inventory(shop_id=self.shop.id, product_id=product.id, shopify_location_id="1", quantity=45))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for number, (days_ago, quantity) in enumerate([(45, 1), (15, 46), (1, 14)]):
            self.db.add(OrderLineItem(shop_id=self.shop.id, product_id=product.id,
                                     shopify_order_id=str(number), sku=product.sku, quantity=quantity,
                                     price=20, created_at=now - timedelta(days=days_ago)))
        self.db.commit()
        return product

    def effective(self):
        return shop_settings.load_effective_shop_settings_map(self.db, shop_id=self.shop.id)[self.shop.id]

    def save_globals(self, settings):
        return shop_settings.upsert_shop_settings(shopify_domain=self.shop.shopify_domain,
            global_default_lead_time_days=settings.global_default_lead_time_days,
            global_safety_buffer_days=settings.global_safety_buffer_days,
            allow_mock_fallback=settings.allow_mock_fallback)

    def test_new_shop_has_no_unrecorded_overrides_even_when_product_names_match_demo(self):
        self.add_product()
        for settings in [shop_settings.get_shop_settings(self.shop.shopify_domain), self.effective(),
                         shop_settings.get_shop_settings("not-yet-created.myshopify.com")]:
            config = settings.to_lead_time_config()
            self.assertEqual((config.global_default_lead_time_days, config.global_safety_buffer_days), (14, 7))
            self.assertEqual(config.vendor_lead_times, {})
            self.assertEqual(config.category_lead_times, {})
            self.assertFalse(settings.is_persisted)
        for getter in [shop_settings.get_vendor_lead_times, shop_settings.get_category_lead_times,
                       shop_settings.get_sku_lead_times]:
            self.assertEqual(getter(self.shop.shopify_domain)[2], [])
        self.assertIsNone(load_skus_for_shop(self.db, self.shop.id)[0].sku_lead_time_days)

    def test_saving_identical_defaults_keeps_live_actions_and_reorders_identical(self):
        self.add_product()
        skus = load_skus_for_shop(self.db, self.shop.id)
        before = self.effective()
        actions_before = build_inventory_actions(skus, before.to_lead_time_config())
        reorders_before = build_reorder_suggestions(skus, lambda sku_id: [2] * 90,
                                                   lead_time_config=before.to_lead_time_config())
        self.assertEqual(actions_before, [])
        self.save_globals(before)
        self.db.expire_all()
        after = self.effective()
        self.assertTrue(after.is_persisted)
        self.assertEqual(before.to_lead_time_config(), after.to_lead_time_config())
        self.assertEqual(actions_before, build_inventory_actions(skus, after.to_lead_time_config()))
        self.assertEqual(reorders_before, build_reorder_suggestions(skus, lambda sku_id: [2] * 90,
                                                                   lead_time_config=after.to_lead_time_config()))

    def test_saved_customer_overrides_and_compatibility_flag_survive_global_save(self):
        product = self.add_product(sku_lead_time_days=9)
        self.db.add_all([
            ShopSettings(shop_id=self.shop.id, global_default_lead_time_days=23,
                         global_safety_buffer_days=4, allow_mock_fallback=False),
            VendorLeadTime(shop_id=self.shop.id, vendor="Northstar Apparel", lead_time_days=31),
            CategoryLeadTime(shop_id=self.shop.id, category="outerwear", lead_time_days=28),
        ])
        self.db.commit()
        before = self.effective()
        self.save_globals(before)
        self.db.expire_all()
        after = self.effective()
        self.assertEqual(before.to_lead_time_config(), after.to_lead_time_config())
        self.assertFalse(after.allow_mock_fallback)
        self.assertEqual(after.vendor_lead_times, {"Northstar Apparel": 31})
        self.assertEqual(after.category_lead_times, {"outerwear": 28})
        self.assertEqual(self.db.get(Product, product.id).sku_lead_time_days, 9)
        sku = load_skus_for_shop(self.db, self.shop.id)[0]
        sku = sku.model_copy(update={"inventory": 1})
        action = build_inventory_actions([sku], after.to_lead_time_config())[0]
        self.assertEqual((action.lead_time_days_used, action.lead_time_source), (9, "sku_override"))

    def test_saved_overrides_without_global_row_still_take_precedence(self):
        self.db.add(CategoryLeadTime(shop_id=self.shop.id, category="outerwear", lead_time_days=29))
        self.db.commit()
        before = self.effective()
        self.assertFalse(before.is_persisted)
        self.assertEqual(before.category_lead_times, {"outerwear": 29})
        self.assertEqual(before.vendor_lead_times, {})
        self.save_globals(before)
        self.assertEqual(before.to_lead_time_config(), self.effective().to_lead_time_config())

    def test_explicit_demo_fixture_retains_its_example_rules(self):
        self.add_product()
        demo = build_lead_time_config(base_config=MOCK_LEAD_TIME_CONFIG)
        self.assertEqual(demo.vendor_lead_times["Northstar Apparel"], 16)
        self.assertEqual(demo.category_lead_times["outerwear"], 18)
        actions = build_inventory_actions(load_skus_for_shop(self.db, self.shop.id), demo)
        self.assertEqual(len(actions), 1)
        self.assertEqual((actions[0].lead_time_days_used, actions[0].lead_time_source), (16, "vendor"))
        # Mutating a resolved copy must not change another merchant or the fixture.
        config = self.effective().to_lead_time_config()
        config.vendor_lead_times["Northstar Apparel"] = 99
        self.assertEqual(self.effective().vendor_lead_times, {})
        self.assertEqual(MOCK_LEAD_TIME_CONFIG.vendor_lead_times["Northstar Apparel"], 16)

    def test_empty_authenticated_feed_stays_empty_with_compatibility_flag_true(self):
        defaults = self.effective()
        self.assertTrue(defaults.allow_mock_fallback)
        result = _build_action_feed(self.db, SimpleNamespace(shop_id=self.shop.id))
        self.assertEqual(result.data_source, "db")
        self.assertEqual(result.actions, [])
        self.assertIsNone(self.db.scalar(select(ShopSettings)))


if __name__ == "__main__":
    unittest.main()
