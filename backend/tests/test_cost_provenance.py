"""Missing unit costs must not become confident financial decisions or saved prices."""
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import liquidation, reorder
from app.db.models import Base, Inventory, OrderLineItem, Product, PurchaseOrderRecord, Shop
from app.schemas import SkuDetail
from app.schemas_v2 import BundleComponent, SavePurchaseOrderRequest, DashboardKpi, DashboardSeriesPoint, InventoryHealthKpi, InventoryHealthSku
from app.services import alerts, bundle_opportunities, dashboard, scheduled_reports, shop_skus, stocky_import, transactional_email
from app.services.abc_analysis import build_scorecards
from app.services.bundle_analyzer import BundleDefinition, analyze_bundles
from app.services.cost_provenance import unit_cost_details
from app.services.dead_stock import build_liquidation_plan
from app.services.inventory_copilot import _format_actions_for_prompt
from app.services.inventory_engine import build_inventory_actions
from app.services.inventory_health import build_inventory_health
from app.services.purchase_order_records import save_purchase_order
from app.services.purchase_orders import build_purchase_order_drafts
from app.services.reorder_optimizer import build_reorder_suggestions


def sku(**changes):
    values = dict(sku_id="FIXTURE", name="Fixture", vendor="Supplier", category="Apparel", price=100,
                  cost=40, cost_source="estimated_from_price", inventory=500,
                  last_30_day_sales=30, last_7_day_sales=7, days_since_last_sale=1)
    values.update(changes)
    return SkuDetail(**values)


def suggestions(product):
    return build_reorder_suggestions([product], lambda _: [2] * 90, order_cost=35)


class CostProvenanceTests(unittest.TestCase):
    def test_legacy_metric_constructors_serialize_known_values_without_false_unknowns(self):
        examples = [DashboardKpi(label="Revenue", value=15, unit="currency", delta_pct=None, tone="positive"),
                    DashboardSeriesPoint(label="Healthy", value=0),
                    InventoryHealthKpi(label="High-confidence forecasts", value=1, unit="count", note="Fixture"),
                    InventoryHealthSku(sku_id="A", name="A", vendor="Supplier", value=0, note="Fixture", severity="info")]
        for item in examples:
            with self.subTest(model=type(item).__name__):
                payload = item.model_dump(mode="json")
                self.assertEqual(payload["known_value"], payload["value"])
                payload["value_known"] = False
                self.assertIsNone(type(item).model_validate(payload).model_dump(mode="json")["known_value"])

    def test_cost_resolution_preserves_real_zero_and_marks_compatibility_estimates(self):
        for cost, price, expected in [(0, 100, (0, "recorded")), (12, 100, (12, "recorded")),
                                     (None, 100, (40, "estimated_from_price")),
                                     (None, 0, (0, "missing")), (-1, 20, (8, "estimated_from_price"))]:
            with self.subTest(cost=cost, price=price):
                self.assertEqual(unit_cost_details(SimpleNamespace(cost=cost, price=price)), expected)

    def test_missing_cost_preserves_demand_and_legacy_values_but_nulls_canonical_capital(self):
        action = build_inventory_actions([sku()])[0]
        self.assertEqual((action.status, action.excess_units, action.cash_tied_up), ("optimize", 425, 17000))
        self.assertEqual(action.data_quality_confidence, "high")
        self.assertTrue(action.sales_history_complete)
        self.assertFalse(action.financial_values_known)
        self.assertIsNone(action.model_dump(mode="json")["financial_values"]["cash_tied_up"])
        self.assertTrue(any("Unit cost is missing" in warning for warning in action.data_quality_warnings))
        self.assertNotIn("$", action.explanation + action.recommended_action)
        zero = build_inventory_actions([sku(cost=0, cost_source="recorded")])[0]
        self.assertTrue(zero.financial_values_known)
        self.assertEqual(zero.financial_values["cash_tied_up"], 0)

    def test_unknown_cost_does_not_drive_profit_or_capital_ranking(self):
        for on_hand in [0, 500]:
            cheap = build_inventory_actions([sku(inventory=on_hand, price=20, cost=8)])[0]
            expensive = build_inventory_actions([sku(inventory=on_hand, price=10000, cost=4000)])[0]
            self.assertEqual(cheap.priority_score, expensive.priority_score)
        urgent = build_inventory_actions([sku(inventory=0)])[0]
        self.assertIsNone(urgent.financial_values["estimated_profit_impact"])
        context = _format_actions_for_prompt([urgent, build_inventory_actions([sku()])[0]])
        self.assertIn("UNKNOWN", context)
        self.assertNotIn("$", context)

    def test_scorecard_revenue_remains_valid_while_profit_is_unknown(self):
        scorecard = build_scorecards([sku()], lambda _: [1] * 90)[0]
        self.assertEqual(scorecard.avg_daily_revenue, 100)
        self.assertFalse(scorecard.financial_values_known)
        self.assertIsNone(scorecard.financial_values["profit_per_unit"])

    def test_dashboard_and_health_totals_do_not_present_incomplete_cost_as_a_total(self):
        catalog = [sku(), sku(sku_id="KNOWN", cost=10, cost_source="recorded", vendor="Known")]
        result = dashboard.build_dashboard(catalog, shop_id=987654,
                    daily_history_fn=lambda _sku, days: [1] * days,
                    recent_revenue_fn=lambda _days: [], start_weekday=0)
        kpis = {kpi.label: kpi for kpi in result.kpis}
        for label in ["Inventory value", "Cash tied up"]:
            self.assertFalse(kpis[label].value_known)
            self.assertIsNone(kpis[label].known_value)
        by_vendor = {point.label: point for point in result.cash_at_risk_by_vendor}
        self.assertFalse(by_vendor["Supplier"].value_known)
        self.assertEqual(by_vendor["Known"].known_value, 4250)
        health = build_inventory_health(skus=[sku(days_since_last_sale=120)], forecasts=[])
        for item in health.kpis:
            if item.label in {"Inventory cost on hand", "Dead-stock capital"}:
                self.assertFalse(item.value_known)
                self.assertIsNone(item.known_value)
        self.assertEqual(health.top_cash_trapped, [])
        self.assertEqual(next(bucket.value for bucket in health.health_buckets if bucket.label == "Dead stock"), 1)
        self.assertTrue(any(item.title == "Add unit costs" for item in health.insights))

    def test_reorder_keeps_demand_target_but_skips_eoq_from_guessed_cost(self):
        unknown = suggestions(sku(inventory=0))[0]
        recorded = suggestions(sku(inventory=0, cost_source="recorded"))[0]
        self.assertEqual(unknown.order_up_to, recorded.order_up_to)
        self.assertEqual(unknown.reorder_point, recorded.reorder_point)
        self.assertEqual(unknown.economic_order_qty, 0)
        self.assertGreater(recorded.economic_order_qty, 0)
        self.assertTrue(all(value is None for value in unknown.financial_values.values()))
        self.assertIn("unavailable", unknown.rationale)
        self.assertNotIn("$", unknown.rationale)
        draft = build_purchase_order_drafts([unknown])[0]
        self.assertFalse(draft.financial_values_known)
        self.assertIsNone(draft.financial_values["total_cost"])
        self.assertIsNone(draft.lines[0].financial_values["unit_cost"])
        zero_draft = build_purchase_order_drafts(suggestions(sku(inventory=0, cost=0, cost_source="recorded")))[0]
        self.assertEqual((zero_draft.financial_values["subtotal_cost"], zero_draft.financial_values["total_cost"]), (0, 35))

    def test_incomplete_history_zero_excess_sentinel_does_not_certify_zero_capital(self):
        product = sku(inventory=100, last_30_day_sales=0, last_7_day_sales=0,
                      days_since_last_sale=999, sales_history_complete=False)
        action = build_inventory_actions([product])[0]
        self.assertEqual(action.excess_units, 0)
        self.assertIsNone(action.financial_values["cash_tied_up"])
        result = dashboard.build_dashboard([product], shop_id=987654,
                    daily_history_fn=lambda _sku, days: [0] * days,
                    recent_revenue_fn=lambda _days: [], start_weekday=0)
        self.assertIsNone(next(kpi.known_value for kpi in result.kpis if kpi.label == "Cash tied up"))
        self.assertIsNone(result.cash_at_risk_by_vendor[0].known_value)
        for cost_source in ["estimated_from_price", "recorded"]:
            health = build_inventory_health(skus=[product.model_copy(update={"cost_source": cost_source})], forecasts=[])
            self.assertIsNone(next(kpi.known_value for kpi in health.kpis if kpi.label == "Dead-stock capital"))

    def test_liquidation_keeps_physical_review_without_guessed_margin_discount_or_recovery(self):
        unknown = sku(days_since_last_sale=160)
        plan = build_liquidation_plan([unknown])
        self.assertEqual(len(plan), 1)
        item = plan[0]
        self.assertEqual(item.on_hand, 500)
        self.assertFalse(item.financial_values_known)
        self.assertTrue(all(value is None for value in item.financial_values.values()))
        self.assertIn("No markdown", item.rationale)
        self.assertNotIn("$", item.rationale)
        with patch.object(liquidation, "load_skus_for_shop", return_value=[unknown]):
            result = liquidation.read_liquidation_plan(SimpleNamespace(shop_id=1), None)
        self.assertIsNone(result.financial_values["total_capital_recoverable"])

    def test_bundle_quantities_remain_valid_without_stranded_capital_claims(self):
        definition = BundleDefinition("KIT", "Kit", [BundleComponent(component_sku_id="A", qty_per_bundle=1),
                                                    BundleComponent(component_sku_id="B", qty_per_bundle=1)])
        result = analyze_bundles([definition], [sku(sku_id="A", inventory=500),
                                               sku(sku_id="B", inventory=1, cost_source="recorded")])[0]
        self.assertEqual(result.max_bundles_sellable, 1)
        self.assertFalse(result.financial_values_known)
        self.assertIsNone(result.financial_values["total_component_value_at_risk"])
        self.assertNotIn("$", result.recommended_action)
        with patch.object(shop_skus, "load_skus_for_shop", return_value=[sku(days_since_last_sale=100), sku(sku_id="ANCHOR")]):
            pairings = bundle_opportunities.recommend_dead_stock_pairings(None, 1)
        self.assertEqual(len(pairings.pairings), 1)
        self.assertFalse(pairings.financial_values_known)
        self.assertIsNone(pairings.pairings[0].financial_values["bundle_margin_pct"])
        self.assertNotIn("$", pairings.pairings[0].explanation)

    def test_read_route_aggregate_flags_include_unknown_costs(self):
        catalog = [sku(inventory=0, vendor="")]
        with patch.object(reorder, "load_skus_for_shop", return_value=catalog), \
             patch.object(reorder, "load_effective_shop_settings_map", return_value={}), \
             patch.object(reorder, "load_daily_history_for_shop_skus", return_value={"FIXTURE": [2] * 90}), \
             patch.object(reorder, "list_saved_purchase_orders", return_value=[]):
            user = SimpleNamespace(shop_id=1)
            feed = reorder.list_reorder_suggestions(user, None, .95, 35)
            self.assertIsNone(feed.known_vendor_totals[""])
            self.assertIsNone(feed.financial_values["total_extended_cost"])
            cash = reorder.read_cash_plan(user, None, .95, 35)
            self.assertIsNone(cash.financial_values["total_cost"])
            self.assertNotIn("$", cash.explanation)
            calendar = reorder.read_buying_calendar(user, None, .95, 35, 180)
            self.assertTrue(calendar.events)
            self.assertIsNone(calendar.financial_values["total_estimated_cost"])
            orders = reorder.list_po_drafts(user, None, .95, 35)
            self.assertIsNone(orders.financial_values["total_capital_required"])

    def test_report_and_alert_text_does_not_leak_compatibility_estimates(self):
        for report_type in ["actions", "dead-stock", "reorder"]:
            product = sku(days_since_last_sale=160) if report_type == "dead-stock" else sku(inventory=0)
            with patch.object(scheduled_reports, "load_skus_for_shop", return_value=[product]), \
                 patch.object(scheduled_reports, "load_effective_shop_settings_map", return_value={}), \
                 patch.object(scheduled_reports, "load_daily_history_for_shop_skus", return_value={"FIXTURE": [2] * 90}):
                content = scheduled_reports.build_report_email(None, shop_id=1, report_type=report_type)
            self.assertIsNotNone(content)
            self.assertIn("Unknown", str(content))
            self.assertNotIn("$", str(content))
        context = SimpleNamespace(actions=build_inventory_actions([sku(days_since_last_sale=160)]))
        self.assertEqual(alerts._dead_stock_events(SimpleNamespace(), context, None, False, {}, set()), [])

    def test_weekly_email_formats_unknown_and_real_zero_cost_without_a_live_provider(self):
        client = Mock()
        client.Emails.send.return_value = {"id": "fixture-only"}
        with patch.object(transactional_email, "_client", return_value=client):
            self.assertTrue(transactional_email.send_buy_list_email(email="fixture@example.invalid",
                items=[dict(name="Missing cost", vendor="Supplier", qty=3, cost=None, stockout_prob=.8, lead_time_days=14),
                       dict(name="Free item", vendor="Known", qty=1, cost=0, stockout_prob=.8, lead_time_days=14)],
                total_cost=None, vendor_totals={"Supplier": None, "Known": 0}))
        payload = client.Emails.send.call_args.args[0]
        self.assertIn("Unknown", payload["html"])
        self.assertIn("$0", payload["html"])
        self.assertNotIn("$0 required", payload["subject"])


class CostPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.shop = Shop(shopify_domain="cost-fixture.myshopify.com")
        self.db.add(self.shop)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_real_loader_preserves_missing_cost_evidence_across_db_and_action_boundary(self):
        now = datetime(2026, 9, 7, 12)
        product = Product(shop_id=self.shop.id, shopify_product_id="1", shopify_variant_id="1",
                          sku="COST-NULL", name="Missing cost", price=100, cost=None)
        self.db.add(product)
        self.db.flush()
        self.db.add(Inventory(shop_id=self.shop.id, product_id=product.id, shopify_location_id="all", quantity=500))
        for days, qty in [(60, 1), (1, 30)]:
            self.db.add(OrderLineItem(shop_id=self.shop.id, product_id=product.id, shopify_order_id=str(days),
                                     quantity=qty, price=100, created_at=now - timedelta(days=days)))
        self.db.commit()
        with patch.object(shop_skus, "_now_naive_utc", return_value=now):
            product_view = shop_skus.load_skus_for_shop(self.db, self.shop.id)[0]
        action = build_inventory_actions([product_view])[0]
        self.assertEqual(product_view.cost_source, "estimated_from_price")
        self.assertIsNone(action.financial_values["cash_tied_up"])
        self.assertEqual(action.cash_tied_up, 17000)
        self.assertTrue(product_view.sales_history_complete)

    def test_unknown_draft_cannot_be_saved_as_recorded_but_explicit_zero_can(self):
        unknown = build_purchase_order_drafts(suggestions(sku(inventory=0)))[0]
        with self.assertRaises(ValueError):
            save_purchase_order(self.db, shop_id=self.shop.id, draft=unknown)
        with self.assertRaises(HTTPException) as response:
            reorder.save_po_draft(SavePurchaseOrderRequest(draft=unknown), SimpleNamespace(shop_id=self.shop.id), self.db)
        self.assertEqual(response.exception.status_code, 422)
        self.assertEqual(self.db.scalars(select(PurchaseOrderRecord)).all(), [])
        explicit = build_purchase_order_drafts(suggestions(sku(inventory=0, cost=0, cost_source="recorded")))[0]
        saved = save_purchase_order(self.db, shop_id=self.shop.id, draft=explicit)
        self.assertTrue(saved.financial_values_known)
        self.assertEqual(saved.lines[0].financial_values["unit_cost"], 0)
        self.assertEqual(saved.financial_values["total_cost"], 35)

    def test_stocky_csv_distinguishes_explicit_zero_from_missing_and_invalid_cost(self):
        @contextmanager
        def local_session():
            yield self.db
            self.db.commit()

        def import_csv(body):
            with patch.object(stocky_import, "session_scope", local_session):
                stocky_import.import_stocky_products_csv(shopify_domain=self.shop.shopify_domain, csv_bytes=body.encode())

        import_csv("sku,product,price,cost,inventory\nZERO,Zero cost,100,0,5\nBLANK,Blank cost,100,,5\nBAD,Invalid cost,100,bad,5\nPAID,Positive cost,100,12,5\n")
        costs = {row.sku: row.cost for row in self.db.scalars(select(Product)).all()}
        self.assertEqual(costs, {"ZERO": 0, "BLANK": None, "BAD": None, "PAID": 12})
        import_csv("sku,product,price,cost,inventory\nPAID,Positive cost,100,0,5\nZERO,Zero cost,100,,5\n")
        self.assertEqual({row.sku: row.cost for row in self.db.scalars(select(Product)).all()},
                         {"ZERO": 0, "BLANK": None, "BAD": None, "PAID": 0})


if __name__ == "__main__":
    unittest.main()
