"""Output and bounded-work regressions for merchant dashboard requests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.models import Base, CategoryLeadTime, Shop, ShopSettings, VendorLeadTime
from app.schemas import SkuDetail
from app.services import dashboard, shop_settings


def sku(number, *, vendor=None):
    return SkuDetail(sku_id=f"SKU-{number}", name=f"Product {number}",
                     vendor=vendor or f"Vendor {number % 20}", category="Fixture", price=20, cost=10,
                     inventory=1000, last_30_day_sales=30, last_7_day_sales=7,
                     days_since_last_sale=1, sales_history_complete=True, sales_history_warnings=[])


def build(skus):
    return dashboard.build_dashboard(skus, shop_id=1,
        daily_history_fn=lambda sku_id, days: [1] * days,
        recent_revenue_fn=lambda days: [(day, 1000.0) for day in range(days)], start_weekday=0)


class CountingCatalog(list):
    visited = 0

    def __iter__(self):
        for item in super().__iter__():
            self.visited += 1
            yield item


class DashboardPerformanceTests(unittest.TestCase):
    def test_vendor_cash_totals_preserve_first_duplicate_match_and_unknown_vendor(self):
        skus = [sku(1, vendor="First"), sku(1, vendor="Second"), sku(2, vendor="Other")]
        actions = [SimpleNamespace(sku_id=sku_id, status="optimize", cash_tied_up=amount,
                                   excess_units=1, financial_values_known=True)
                   for sku_id, amount in [("SKU-1", 10), ("SKU-1", 5), ("SKU-2", 20), ("missing", 7)]]
        with patch.object(dashboard, "build_inventory_actions", return_value=actions):
            result = build(skus)
        self.assertEqual([(item.label, item.value) for item in result.cash_at_risk_by_vendor],
                         [("Other", 20), ("First", 15), ("Unknown", 7)])

    def test_large_catalog_work_does_not_grow_quadratically_per_inventory_action(self):
        skus = CountingCatalog(sku(number) for number in range(1000))
        result = build(skus)
        self.assertEqual(result.kpis[1].value, 10_000_000)
        self.assertEqual(len(result.cash_at_risk_by_vendor), 6)
        # Bounded catalog traversal detects the former two linear SKU scans
        # per action without a flaky wall-clock threshold.
        self.assertLess(skus.visited, 20 * len(skus))


class ShopSettingsPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.shop_ids = []
        for number in range(5):
            shop = Shop(shopify_domain=f"fixture-{number}.myshopify.com")
            self.db.add(shop)
            self.db.flush()
            self.shop_ids.append(shop.id)
            self.db.add_all([
                ShopSettings(shop_id=shop.id, global_default_lead_time_days=10 + number,
                             global_safety_buffer_days=3, allow_mock_fallback=False),
                VendorLeadTime(shop_id=shop.id, vendor="Shared supplier", lead_time_days=20 + number),
                CategoryLeadTime(shop_id=shop.id, category="Shared category", lead_time_days=30 + number),
            ])
        self.db.commit()
        self.db.expunge_all()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_targeted_settings_and_both_override_queries_stay_scoped_to_one_shop(self):
        statements = []
        @event.listens_for(self.engine, "before_cursor_execute")
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        target = self.shop_ids[2]
        result = shop_settings.load_effective_shop_settings_map(self.db, shop_id=target)
        self.assertEqual(list(result), [target])
        settings = result[target]
        self.assertEqual(settings.global_default_lead_time_days, 12)
        self.assertEqual(settings.vendor_lead_times, {"Shared supplier": 22})
        self.assertEqual(settings.category_lead_times, {"Shared category": 32})
        self.assertEqual(len(statements), 3)
        self.assertTrue(all("WHERE" in statement for statement in statements))

    def test_batch_call_preserves_all_shops_and_missing_target_returns_empty(self):
        result = shop_settings.load_effective_shop_settings_map(self.db)
        self.assertEqual(sorted(result), self.shop_ids)
        self.assertEqual(result[self.shop_ids[4]].vendor_lead_times, {"Shared supplier": 24})
        self.assertEqual(shop_settings.load_effective_shop_settings_map(self.db, shop_id=99999), {})


if __name__ == "__main__":
    unittest.main()
