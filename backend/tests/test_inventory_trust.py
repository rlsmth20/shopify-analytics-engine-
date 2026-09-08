import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.db.models import Base, Inventory, InventoryValueSnapshot, OrderLineItem, Product, Shop, ShopifySyncRun
from app.schemas import SkuDetail
from app.schemas_v2 import AlertRule
from app.services import alerts, inventory_value, shop_skus
from app.services.dead_stock import build_liquidation_plan
from app.services.bundle_opportunities import recommend_dead_stock_pairings
from app.services.inventory_engine import build_inventory_actions
from app.services.inventory_health import build_inventory_health


class InventoryTrustTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.now = datetime(2026, 9, 6, 12)
        self.shop = Shop(shopify_domain="inventory-fixture.myshopify.com")
        self.db.add(self.shop)
        self.db.flush()
        self.product = Product(shop_id=self.shop.id, shopify_product_id="1", shopify_variant_id="1",
                               name="Fixture", price=20, cost=10)
        self.db.add(self.product)
        self.db.flush()
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_inventory(self, quantity=10):
        self.db.add(Inventory(shop_id=self.shop.id, product_id=self.product.id,
                              shopify_location_id="aggregate", quantity=quantity))
        self.db.commit()

    def add_sale(self, days_ago, quantity=1):
        self.db.add(OrderLineItem(shop_id=self.shop.id, product_id=self.product.id,
                                  shopify_order_id=f"fixture:{days_ago}:{quantity}", quantity=quantity, price=20,
                                  created_at=self.now - timedelta(days=days_ago)))
        self.db.commit()

    def add_sync(self, status="succeeded", age_days=0):
        self.db.add(ShopifySyncRun(shop_id=self.shop.id, status=status,
                                   finished_at=None if status == "running" else self.now - timedelta(days=age_days)))
        self.db.commit()

    def load_sku(self):
        with patch.object(shop_skus, "_now_naive_utc", return_value=self.now):
            return shop_skus.load_skus_for_shop(self.db, self.shop.id)[0]

    def test_missing_sales_get_monitoring_without_liquidation_or_dead_stock_capital(self):
        self.add_inventory()
        self.add_sync()
        sku = self.load_sku()
        self.assertFalse(sku.sales_history_complete)
        action = build_inventory_actions([sku])[0]
        self.assertEqual((action.status, action.data_quality_confidence, action.excess_units, action.cash_tied_up),
                         ("optimize", "low", 0, 0))
        self.assertIn("Monitor sales", action.recommended_action)
        self.assertTrue(action.data_quality_warnings)
        self.assertFalse(action.sales_history_complete)
        self.assertFalse(action.planning_values_known)
        self.assertTrue(all(value is None for value in action.planning_values.values()))
        self.assertEqual(build_liquidation_plan([sku]), [])
        health = build_inventory_health(skus=[sku], forecasts=[])
        buckets = {bucket.label: bucket.value for bucket in health.health_buckets}
        self.assertEqual((buckets["Dead stock"], buckets["Overstock"], buckets["No signal"]), (0, 0, 1))
        self.assertEqual(next(kpi.value for kpi in health.kpis if kpi.label == "Dead-stock capital"), 0)
        self.assertEqual(health.top_cash_trapped, [])

    def test_limited_observed_history_does_not_claim_measured_excess(self):
        self.add_inventory(500)
        self.add_sale(5, quantity=2)
        self.add_sync()
        sku = self.load_sku()
        self.assertFalse(sku.sales_history_complete)
        action = build_inventory_actions([sku])[0]
        self.assertEqual((action.status, action.excess_units, action.cash_tied_up), ("optimize", 0, 0))
        self.assertIn("Monitor sales", action.recommended_action)

    def test_bundle_clearance_does_not_treat_missing_sales_as_dead_stock(self):
        self.add_inventory(10)
        with patch.object(shop_skus, "_now_naive_utc", return_value=self.now):
            result = recommend_dead_stock_pairings(self.db, self.shop.id)
        self.assertEqual((result.dead_stock_sku_count, result.dead_stock_capital, result.pairings), (0, 0, []))
        self.add_sale(100)
        with patch.object(shop_skus, "_now_naive_utc", return_value=self.now):
            result = recommend_dead_stock_pairings(self.db, self.shop.id)
        self.assertEqual((result.dead_stock_sku_count, result.dead_stock_capital), (1, 100))

    def test_limited_history_preserves_reorder_warning_from_observed_demand(self):
        self.add_inventory(0)
        self.add_sale(2, quantity=30)
        self.add_sync()
        action = build_inventory_actions([self.load_sku()])[0]
        self.assertEqual((action.status, action.data_quality_confidence), ("urgent", "low"))
        self.assertIn("Reorder", action.recommended_action)
        self.assertGreater(action.target_inventory_units, 0)

    def test_established_imported_history_without_sync_metadata_still_supports_stale_stock(self):
        self.add_inventory()
        self.add_sale(100)
        sku = self.load_sku()
        self.assertTrue(sku.sales_history_complete)
        self.assertEqual(build_inventory_actions([sku])[0].status, "dead")
        self.assertEqual(len(build_liquidation_plan([sku])), 1)
        health = build_inventory_health(skus=[sku], forecasts=[])
        self.assertEqual(next(bucket.value for bucket in health.health_buckets if bucket.label == "Dead stock"), 1)

    def test_partial_failed_or_stale_sync_prevents_liquidation_of_old_recorded_sales(self):
        self.add_inventory()
        self.add_sale(100)
        for status, age in [("partial", 0), ("failed", 0), ("succeeded", 3)]:
            with self.subTest(status=status, age=age):
                self.add_sync(status, age)
                sku = self.load_sku()
                self.assertFalse(sku.sales_history_complete)
                self.assertEqual(build_liquidation_plan([sku]), [])
                self.assertEqual(build_inventory_actions([sku])[0].status, "optimize")
        self.add_sync("succeeded", 0)
        self.add_sync("running", 0)
        self.assertTrue(self.load_sku().sales_history_complete)

    def test_zero_quantity_and_future_rows_do_not_establish_observed_sales_history(self):
        self.add_inventory()
        self.add_sale(100, quantity=0)
        self.add_sale(-1, quantity=10)
        sku = self.load_sku()
        self.assertFalse(sku.sales_history_complete)
        self.assertEqual((sku.last_30_day_sales, sku.last_7_day_sales), (0, 0))
        self.assertEqual(build_liquidation_plan([sku]), [])

    def test_legacy_sku_contract_keeps_normal_reorder_calculation(self):
        sku = SkuDetail(sku_id="normal", name="Normal SKU", vendor="Unassigned", category="uncategorized",
                        price=20, cost=10, inventory=0, last_30_day_sales=60, last_7_day_sales=14,
                        days_since_last_sale=1)
        action = build_inventory_actions([sku])[0]
        self.assertTrue(sku.sales_history_complete)
        self.assertEqual((action.status, action.data_quality_confidence, action.target_inventory_units,
                          action.reorder_point_units), ("urgent", "high", 45, 31))

    def test_monitoring_never_fires_overstock_alert_but_established_excess_still_does(self):
        self.add_inventory(500)
        monitoring = build_inventory_actions([self.load_sku()])[0]
        rule = AlertRule(id="fixture-overstock", name="Excess stock", trigger="overstock", severity="warning",
                         channels=[], threshold=0, created_at=self.now)
        context = alerts.EvaluationContext(actions=[monitoring], forecasts=[], supplier_scores=[])
        with patch.object(alerts, "_fire") as fire:
            self.assertEqual(alerts._evaluate_rule(rule, context, self.now, False, {}, None), [])
            fire.assert_not_called()

        self.add_sale(50)
        self.add_sale(1, quantity=30)
        established = build_inventory_actions([self.load_sku()])[0]
        self.assertTrue(established.sales_history_complete)
        self.assertGreater(established.excess_units, 0)
        context = alerts.EvaluationContext(actions=[established], forecasts=[], supplier_scores=[])
        with patch.object(alerts, "_fire", return_value="fixture-event") as fire:
            self.assertEqual(alerts._evaluate_rule(rule, context, self.now, False, {}, None), ["fixture-event"])
            fire.assert_called_once()

    def test_empty_catalog_overwrites_same_day_value_with_zero(self):
        self.db.add(Inventory(shop_id=self.shop.id, product_id=self.product.id,
                              shopify_location_id="aggregate", quantity=10))
        self.db.commit()
        before = inventory_value.capture_inventory_value_snapshot(self.db, shop_id=self.shop.id)
        snapshot_id = before.id
        self.assertEqual(before.total_cost_value, 100)

        self.db.execute(delete(Inventory).where(Inventory.shop_id == self.shop.id))
        self.db.commit()
        after = inventory_value.capture_inventory_value_snapshot(self.db, shop_id=self.shop.id)
        self.assertEqual(after.id, snapshot_id)
        self.assertEqual((after.total_units, after.sku_count, after.total_cost_value, after.total_retail_value),
                         (0, 0, 0, 0))

    def test_empty_new_shop_does_not_borrow_another_shops_history(self):
        other = Shop(shopify_domain="other-history.myshopify.com")
        self.db.add(other)
        self.db.flush()
        self.db.add(InventoryValueSnapshot(shop_id=other.id, snapshot_date="2026-01-01",
                                           total_units=10, sku_count=1, total_cost_value=100, total_retail_value=200))
        self.db.commit()
        self.assertIsNone(inventory_value.capture_inventory_value_snapshot(self.db, shop_id=self.shop.id))

    def test_scheduled_capture_includes_empty_shop_with_prior_history(self):
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        self.db.add(InventoryValueSnapshot(shop_id=self.shop.id, snapshot_date=yesterday,
                                           total_units=10, sku_count=1, total_cost_value=100, total_retail_value=200))
        self.db.commit()
        with patch.object(inventory_value, "SessionLocal", side_effect=lambda: Session(self.engine)):
            self.assertEqual(inventory_value.capture_all_inventory_snapshots(), 1)
        rows = self.db.scalars(select(InventoryValueSnapshot).order_by(InventoryValueSnapshot.snapshot_date)).all()
        self.assertEqual([(row.total_units, row.total_cost_value) for row in rows], [(10, 100), (0, 0)])


if __name__ == "__main__":
    unittest.main()
