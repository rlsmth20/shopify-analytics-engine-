"""Duplicate merchant SKU aliases never choose another product's history or buys."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes import actions, analytics, bundles, forecast, liquidation, reorder, skus, transfers
from app.db.base import Base
from app.db.models import Inventory, OrderLineItem, Product, Shop
from app.db.session import get_db_session
from app.schemas_v2 import AlertRule, BundleComponent
from app.services import action_feed, alerts, auth, dashboard, shop_skus
from app.services.abc_analysis import build_scorecards
from app.services.bundle_analyzer import BundleDefinition, analyze_bundles
from app.services.inventory_engine import build_inventory_actions


class SkuIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="skubase-sku-identity-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "fixture.db"),
                                   connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.clock = patch.object(shop_skus, "_now_naive_utc", return_value=self.now)
        self.clock.start()
        with self.factory() as db:
            self.user = auth.get_or_create_user_for_email(db, email="identity-fixture@example.invalid")
            token = auth.create_session(db, user_id=self.user.id)
        self.shop_id = self.user.shop_id
        self.sequence = 0
        def sessions():
            with self.factory() as db:
                yield db
        app = FastAPI()
        for module in (actions, analytics, bundles, forecast, liquidation, reorder, skus, transfers):
            app.include_router(module.router)
        app.dependency_overrides[get_db_session] = sessions
        self.client = TestClient(app)
        self.client.cookies.set(auth.SESSION_COOKIE_NAME, token)

    def tearDown(self):
        self.client.close()
        self.clock.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def product(self, sku="REUSED", *, name=None, stock=10, daily=2, shop_id=None, locations=1):
        self.sequence += 1
        shop_id = shop_id or self.shop_id
        with self.factory() as db:
            product = Product(shop_id=shop_id, shopify_product_id=str(self.sequence),
                shopify_variant_id=str(self.sequence), sku=sku, name=name or f"Variant {self.sequence}",
                vendor=f"Vendor {self.sequence}", category="fixture", price=20, cost=10, sku_lead_time_days=21)
            db.add(product)
            db.flush()
            if stock is not None:
                for location in range(locations):
                    db.add(Inventory(shop_id=shop_id, product_id=product.id,
                        shopify_location_id=str(location), quantity=stock))
            for days in range(1, 46):
                if daily:
                    db.add(OrderLineItem(shop_id=shop_id, product_id=product.id, sku=sku,
                        quantity=daily, price=20, shopify_order_id=f"order-{days}",
                        created_at=self.now - timedelta(days=days)))
            db.commit()
            return product.id

    def read(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_retired_csv_alias_uses_unique_active_product_in_single_batch_and_http(self):
        retired = self.product(stock=None, daily=1)
        native = self.product(stock=10, daily=2)
        with self.factory() as db:
            index = shop_skus.build_sku_alias_index(db, self.shop_id)
            self.assertEqual(index.resolve("REUSED").id, native)
            self.assertFalse(index.is_ambiguous("REUSED"))
            single = shop_skus.load_daily_history_for_shop_sku(db, self.shop_id, "REUSED")
            batch = shop_skus.load_daily_history_for_shop_skus(db, self.shop_id, ["REUSED"])
            self.assertEqual(single, batch["REUSED"])
            self.assertEqual(sum(single), 90)
            self.assertEqual(db.scalar(select(func.sum(OrderLineItem.quantity)).where(OrderLineItem.product_id == retired)), 45)
        rows = self.read("/skus")
        self.assertEqual([row["product_id"] for row in rows], [native])
        listing = self.read("/forecast")["forecasts"][0]
        detail = self.read("/forecast/REUSED")
        self.assertEqual((listing["product_id"], detail["product_id"]), (native, native))
        self.assertEqual(listing["projected_30_day_demand"], detail["projected_30_day_demand"])
        self.assertEqual(detail["projected_30_day_demand"], 60)
        self.assertGreater(self.read("/reorder")["suggestions"][0]["recommended_order_qty"], 0)
        # The retired row must not become a bundle paired with its current owner.
        self.assertEqual(self.read("/bundles")["opportunities"], [])

    def test_active_zero_stock_does_not_resolve_duplicate_and_rows_remain_visible(self):
        first = self.product(stock=0, daily=2)
        second = self.product(stock=80, daily=1)
        with self.factory() as db:
            index = shop_skus.build_sku_alias_index(db, self.shop_id)
            self.assertTrue(index.is_ambiguous("REUSED"))
            with self.assertRaises(shop_skus.AmbiguousSkuError) as raised:
                index.resolve("REUSED")
            self.assertEqual(raised.exception.product_ids, [first, second])
            with self.assertRaises(shop_skus.AmbiguousSkuError):
                shop_skus.load_daily_history_for_shop_sku(db, self.shop_id, "REUSED")
            self.assertEqual(shop_skus.load_daily_history_for_shop_skus(db, self.shop_id, ["REUSED"]), {})
        rows = self.read("/skus")
        self.assertEqual({row["product_id"] for row in rows}, {first, second})
        self.assertEqual(sum(row["inventory"] for row in rows), 80)
        self.assertEqual(sum(row["last_30_day_sales"] for row in rows), 90)
        self.assertTrue(all(row["sku_id"] == "REUSED" and row["identity_ambiguous"] for row in rows))
        for path in ("/skus/REUSED", "/forecast/REUSED"):
            self.assertEqual(self.client.get(path).status_code, 409)
        feed = self.read("/forecast")
        self.assertEqual(len(feed["identity_issues"]), 2)
        for value in feed["forecasts"]:
            self.assertFalse(value["forecast_available"])
            self.assertEqual(value["demand_signal"], "ambiguous_identity")
            self.assertEqual(value["points"], [])
            self.assertIsNone(value["backtest_mae_14d"])
            self.assertIn("share this SKU", value["explain"])
        action_rows = self.read("/actions")["actions"]
        self.assertEqual(len(action_rows), 2)
        for row in action_rows:
            self.assertEqual(row["status"], "optimize")
            self.assertIn("Review duplicate", row["recommended_action"])
            self.assertFalse(row["planning_values_known"])
            self.assertTrue(all(value is None for value in row["planning_values"].values()))
            self.assertIsNone(row["financial_values"]["cash_tied_up"])

    def test_held_products_cannot_generate_buys_clearance_bundles_or_transfers(self):
        self.product(stock=10, daily=2, locations=2)
        self.product(stock=100, daily=1, locations=2)
        for path, collection in (("/reorder", "suggestions"), ("/reorder/purchase-orders", "drafts"),
                ("/reorder/buying-calendar", "events"), ("/liquidation", "suggestions"),
                ("/bundles", "opportunities"), ("/bundles/dead-stock-pairings", "pairings"),
                ("/transfers", "transfers")):
            with self.subTest(path=path):
                response = self.read(path)
                self.assertEqual(response[collection], [])
                self.assertEqual(len(response["identity_issues"]), 2)
                if "financial_values_known" in response:
                    self.assertFalse(response["financial_values_known"])
        cash = self.read("/reorder/cash-plan")
        self.assertFalse(cash["financial_values_known"])
        self.assertIsNone(cash["financial_values"]["total_cost"])
        self.assertIn("duplicate SKU", cash["explanation"])

    def test_unique_rows_keep_raw_supplier_sku_and_work_alongside_a_hold(self):
        self.product(stock=10)
        self.product(stock=80)
        unique = self.product("SUPPLIER-code_42", stock=3)
        response = self.read("/reorder")
        self.assertEqual([row["sku_id"] for row in response["suggestions"]], ["SUPPLIER-code_42"])
        self.assertEqual(response["suggestions"][0]["product_id"], unique)
        self.assertFalse(response["financial_values_known"])
        self.assertEqual(self.read("/skus/SUPPLIER-code_42")["product_id"], unique)
        po = self.read("/reorder/purchase-orders")["drafts"][0]
        self.assertEqual(po["lines"][0]["sku_id"], "SUPPLIER-code_42")

    def test_history_only_fallback_and_tenant_isolation_are_preserved(self):
        historical = self.product(stock=None)
        with self.factory() as db:
            other = Shop(shopify_domain="other-identity-fixture.myshopify.com")
            db.add(other)
            db.commit()
            other_id = other.id
        self.product(stock=10, shop_id=other_id)
        self.product(stock=20, shop_id=other_id)
        with self.factory() as db:
            self.assertEqual(shop_skus.build_sku_alias_index(db, self.shop_id).resolve("REUSED").id, historical)
            self.assertEqual(sum(shop_skus.load_daily_history_for_shop_sku(db, self.shop_id, "REUSED")), 90)
            self.assertIsNone(shop_skus.build_sku_alias_index(db, self.shop_id).resolve("ABSENT"))
        self.product(stock=None)
        with self.factory() as db:
            with self.assertRaises(shop_skus.AmbiguousSkuError):
                shop_skus.build_sku_alias_index(db, self.shop_id).resolve("REUSED")

    def test_unique_history_only_products_still_support_bundle_evidence(self):
        first = self.product("HISTORICAL-1", stock=None)
        second = self.product("HISTORICAL-2", stock=None)
        response = self.read("/bundles")
        self.assertEqual(response["orders_analyzed"], 45)
        self.assertEqual(len(response["opportunities"]), 1)
        self.assertEqual({response["opportunities"][0]["product_a_id"],
                          response["opportunities"][0]["product_b_id"]}, {first, second})

    def test_truncated_generated_alias_collision_is_also_held(self):
        self.product(None, name="a" * 140, stock=0)
        self.product(None, name="a" * 140, stock=10)
        rows = self.read("/skus")
        self.assertEqual(rows[0]["sku_id"], rows[1]["sku_id"])
        self.assertTrue(all(row["identity_ambiguous"] for row in rows))
        self.assertEqual(self.read("/reorder")["suggestions"], [])
        self.assertEqual(self.read("/bundles")["opportunities"], [])

    def test_batch_resolution_remains_bounded_with_missing_and_ambiguous_aliases(self):
        self.product(stock=0)
        self.product(stock=10)
        for number in range(10):
            self.product(f"UNIQUE-{number}", daily=0)
        statements = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with self.factory() as db:
                result = shop_skus.load_daily_history_for_shop_skus(db, self.shop_id,
                    ["REUSED", "ABSENT", *[f"UNIQUE-{number}" for number in range(10)]])
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertNotIn("REUSED", result)
        self.assertEqual(result["ABSENT"], [0] * 90)
        self.assertEqual(len(result), 11)
        self.assertLessEqual(len(statements), 4)

    def test_actual_aggregates_and_dashboard_preserve_rows_without_querying_ambiguous_history(self):
        self.product(stock=10, daily=2)
        self.product(stock=80, daily=1)
        with self.factory() as db:
            rows = shop_skus.load_skus_for_shop(db, self.shop_id)
            def must_not_resolve(*args):
                raise AssertionError("Ambiguous SKU callback must not be invoked")
            cards = build_scorecards(rows, must_not_resolve)
            self.assertEqual(sum(card.avg_daily_revenue for card in cards), 60)
            self.assertEqual(sum(card.contribution_pct for card in cards), 100)
            with patch.object(dashboard, "list_recent_events", return_value=[]):
                result = dashboard.build_dashboard(rows, shop_id=self.shop_id, daily_history_fn=must_not_resolve,
                    recent_revenue_fn=lambda days: [], start_weekday=0)
            kpis = {row.label: row for row in result.kpis}
            self.assertEqual(kpis["Revenue (30d)"].known_value, 1800)
            self.assertEqual(kpis["Inventory value"].known_value, 900)
            self.assertFalse(kpis["Profit at risk"].value_known)
            self.assertEqual(len(result.identity_issues), 2)
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 2)
            self.assertEqual(db.scalar(select(func.sum(OrderLineItem.quantity))), 135)
        health = self.read("/analytics/inventory-health")
        self.assertEqual(health["forecast_coverage"]["unavailable_skus"], 2)
        self.assertEqual(len(health["identity_issues"]), 2)

    def test_core_bundle_and_alert_builders_refuse_ambiguous_inputs(self):
        self.product(stock=10)
        self.product(stock=80)
        with self.factory() as db:
            rows = shop_skus.load_skus_for_shop(db, self.shop_id)
        definition = BundleDefinition(bundle_sku_id="KIT", bundle_name="Fixture kit",
            components=[BundleComponent(component_sku_id="REUSED", qty_per_bundle=1)])
        # Core builder also protects callers whose legacy inputs lack new metadata.
        for values in (rows, [row.model_copy(update={"identity_ambiguous": False}) for row in rows]):
            result = analyze_bundles([definition], values)[0]
            self.assertTrue(result.identity_ambiguous)
            self.assertFalse(result.planning_values_known)
            self.assertFalse(result.financial_values_known)
        missing = analyze_bundles([definition], [])[0]
        self.assertFalse(missing.planning_values_known)
        context = alerts.EvaluationContext(actions=build_inventory_actions(rows), forecasts=[], supplier_scores=[])
        for trigger, builder in (("stockout_risk", alerts._stockout_events), ("dead_stock", alerts._dead_stock_events),
                                 ("overstock", alerts._overstock_events)):
            rule = AlertRule(id="fixture", name="Any match", trigger=trigger, threshold=0,
                severity="warning", channels=["email"], created_at=datetime.now(timezone.utc))
            self.assertEqual(builder(rule, context, datetime.now(timezone.utc), False, {}, {"email"}), [])

    def test_legacy_action_feed_uses_same_hold_without_erasing_evidence(self):
        self.product(stock=None)
        self.product(stock=10)
        self.product(stock=80)
        @contextmanager
        def scope():
            with self.factory() as db:
                yield db
        with patch.object(action_feed, "session_scope", scope):
            snapshot = action_feed.load_persisted_sku_snapshot()
            self.assertEqual(len(snapshot.records), 2)
            result = action_feed._build_db_backed_actions(snapshot)
            self.assertEqual(len(result), 2)
            self.assertTrue(all(row.identity_ambiguous and row.data_quality_confidence == "low" for row in result))
            self.assertTrue(all("share this SKU" in row.explanation for row in result))


if __name__ == "__main__":
    unittest.main()
