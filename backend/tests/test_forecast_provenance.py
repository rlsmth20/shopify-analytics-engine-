"""CSV-only inventory forecasts use actual observation history, never padding."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import csv
import io
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes import actions, forecast, reorder, shipstation_import as shipment_route, stocky_import as stocky_route
from app.db.base import Base
from app.db.models import Inventory, OrderLineItem, Product, ShopifyConnection
from app.db.session import get_db_session
from app.schemas_v2 import AlertRule
from app.services import alerts, auth, shipstation_import, shop_skus, stocky_import
from app.services.forecast_accuracy import backtest_forecast
from app.services.forecasting import ForecastInputs, forecast_sku


def inputs(history, observed=None):
    return ForecastInputs(sku_id="FIXTURE", daily_history=history, on_hand=30,
                          start_weekday=0, observed_history_days=observed)


class ForecastProvenanceTests(unittest.TestCase):
    def test_missing_history_is_unavailable_and_has_no_backtest_score(self):
        for value in (inputs([]), inputs([0] * 90), inputs([0] * 90, 0)):
            with self.subTest(observed=value.observed_history_days):
                result = forecast_sku(value)
                self.assertFalse(result.forecast_available)
                self.assertEqual((result.demand_signal, result.history_days, result.confidence),
                                 ("missing_history", 0, "low"))
                self.assertEqual((result.points, result.weekly_index), ([], []))
                self.assertNotIn("covers", result.explain)
                score = backtest_forecast(value)
                self.assertEqual((score.mae_14d, score.mape_14d, score.bias_14d), (None, None, None))

    def test_recorded_zero_sales_window_stays_distinct_without_false_accuracy_claims(self):
        value = inputs([0] * 90, 120)
        result = forecast_sku(value)
        self.assertTrue(result.forecast_available)
        self.assertEqual((result.demand_signal, result.history_days, result.confidence), ("no_recent_sales", 90, "low"))
        self.assertEqual(result.projected_30_day_demand, 0)
        self.assertNotIn("3000", result.explain)
        score = backtest_forecast(value)
        self.assertEqual((score.mae_14d, score.mape_14d, score.bias_14d), (0, None, None))
        self.assertNotIn("error is low", " ".join(score.trust_reasons))

    def test_short_and_sparse_history_do_not_gain_confidence_from_padding(self):
        for value in (inputs([0] * 65 + [2] * 25), inputs([0] * 65 + [2] * 25, 25),
                      inputs([2 if index % 15 == 0 else 0 for index in range(90)], 90)):
            with self.subTest(observed=value.observed_history_days):
                result = forecast_sku(value)
                self.assertTrue(result.forecast_available)
                self.assertEqual(result.confidence, "low")
        self.assertEqual(forecast_sku(inputs([0] * 65 + [2] * 25)).history_days, 25)
        self.assertIsNone(backtest_forecast(inputs([0] * 65 + [2] * 25)).mae_14d)
        self.assertIn("sparse", " ".join(backtest_forecast(
            inputs([2 if index % 15 == 0 or index == 89 else 0 for index in range(90)], 90)).trust_reasons))

    def test_established_regular_history_keeps_supported_high_confidence(self):
        result = forecast_sku(inputs([2] * 90, 120))
        self.assertEqual((result.confidence, result.history_days, result.projected_30_day_demand), ("high", 90, 60))
        self.assertEqual(backtest_forecast(inputs([2] * 90, 120)).mape_14d, 0)

    def test_known_leading_zero_sales_days_are_preserved_after_padding_removal(self):
        history = [0] * 80 + [2] * 10
        known = forecast_sku(inputs(history, 120))
        unknown = forecast_sku(inputs(history))
        self.assertEqual((known.history_days, known.forecast_available, known.confidence), (90, True, "low"))
        self.assertEqual(unknown.history_days, 10)

    def test_source_quality_warning_limits_forecast_and_backtest_trust(self):
        value = ForecastInputs(sku_id="FIXTURE", daily_history=[2] * 90, on_hand=30,
            start_weekday=0, observed_history_days=120,
            source_warnings=("The latest Shopify sync did not complete successfully; verify order-history coverage.",))
        result = forecast_sku(value)
        self.assertTrue(result.forecast_available)
        self.assertEqual(result.confidence, "low")
        self.assertIn(value.source_warnings[0], result.data_quality_warnings)
        self.assertIn("sync did not complete", result.explain)
        score = backtest_forecast(value)
        self.assertNotIn("error is low", " ".join(score.trust_reasons))
        self.assertIn(value.source_warnings[0], score.trust_reasons)

    def test_forecast_prose_qualifies_saturated_and_low_confidence_risk(self):
        established = forecast_sku(inputs([30] * 90, 120))
        self.assertIn("model estimates over 99%", established.explain)
        self.assertNotIn("100%", established.explain)
        limited = forecast_sku(inputs([30] * 25, 25))
        self.assertEqual(limited.confidence, "low")
        self.assertIn("Stockout likelihood is uncertain", limited.explain)
        self.assertNotIn("%", limited.explain)

    def test_unavailable_forecast_cannot_emit_even_a_zero_threshold_alert(self):
        result = forecast_sku(inputs([0] * 90, 0))
        context = alerts.EvaluationContext(actions=[], forecasts=[result], supplier_scores=[])
        rule = AlertRule(id="fixture", name="Any risk", trigger="forecast_miss", threshold=0,
                         severity="warning", channels=["email"], enabled=True, created_at=datetime.now(timezone.utc))
        self.assertEqual(alerts._forecast_events(rule, context, datetime.now(timezone.utc), False, {}, {"email"}), [])


class CsvOnlyForecastApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="skubase-csv-forecast-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "fixture.db"),
                                   connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)
        @contextmanager
        def scope():
            with self.factory() as db:
                try:
                    yield db
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
        self.patches = [patch.object(stocky_import, "session_scope", scope),
                        patch.object(shipstation_import, "session_scope", scope),
                        patch.object(shop_skus, "_now_naive_utc", return_value=self.now)]
        for value in self.patches:
            value.start()
        with self.factory() as db:
            self.user = auth.get_or_create_user_for_email(db, email="csv_fixture+owner@example.invalid")
            token = auth.create_session(db, user_id=self.user.id)
        def sessions():
            with self.factory() as db:
                yield db
        app = FastAPI()
        for module in (stocky_route, shipment_route, actions, reorder, forecast):
            app.include_router(module.router)
        app.dependency_overrides[get_db_session] = sessions
        self.client = TestClient(app)
        self.client.cookies.set(auth.SESSION_COOKIE_NAME, token)

    def tearDown(self):
        self.client.close()
        for value in reversed(self.patches):
            value.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def upload(self, path, content, data=None):
        response = self.client.post(path, files={"csv_file": ("fixture.csv", content, "text/csv")}, data=data)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_csv_only_trial_imports_match_skus_forecast_and_replay_without_inflation(self):
        self.assertEqual(self.client.get("/actions").json()["actions"], [])
        stock = b"SKU,Product,Inventory,Price,Cost,LeadTimeDays\nFAST,Fast fixture,4,20,10,21\nNEVER,No history,30,10,4,7\nZERO,Old sales,40,10,4,7\nTODAY,First sale today,5,20,10,14\n"
        first = self.upload("/integrations/stocky/import", stock)
        self.assertEqual((first["inventory_source"], first["products_inserted"]), ("csv", 4))
        self.assertTrue(first["shopify_domain"].startswith("pending-"))
        self.assertTrue(first["shopify_domain"].endswith(".skubase.invalid"))
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["SKU", "ShipDate", "Quantity", "UnitPrice", "Source", "ShipmentId", "LineItemId"])
        for days in range(1, 46):
            writer.writerow(["FAST", (self.now - timedelta(days=days)).isoformat(), 2, 20, "Etsy", f"shipment-{days}", "line"])
        writer.writerow(["ZERO", (self.now - timedelta(days=120)).isoformat(), 1, 10, "Etsy", "old-shipment", "line"])
        writer.writerow(["TODAY", self.now.isoformat(), 1, 20, "Etsy", "today-shipment", "line"])
        shipments = stream.getvalue().encode()
        imported = self.upload("/integrations/shipstation/import", shipments, {"source_scope": "non_shopify"})
        self.assertEqual((imported["line_items_inserted"], imported["rows_held"]), (47, 0))
        response = self.client.get("/forecast")
        self.assertEqual(response.status_code, 200, response.text)
        forecasts = {row["sku_id"]: row for row in response.json()["forecasts"]}
        self.assertEqual((forecasts["FAST"]["history_days"], forecasts["FAST"]["confidence"]), (45, "medium"))
        self.assertEqual((forecasts["NEVER"]["forecast_available"], forecasts["NEVER"]["history_days"]), (False, 0))
        self.assertIsNone(forecasts["NEVER"]["backtest_mae_14d"])
        self.assertEqual((forecasts["ZERO"]["forecast_available"], forecasts["ZERO"]["demand_signal"]), (True, "no_recent_sales"))
        self.assertEqual((forecasts["TODAY"]["forecast_available"], forecasts["TODAY"]["history_days"]), (False, 0))
        self.assertIn("newly recorded sales may still appear", forecasts["TODAY"]["explain"])
        detail = self.client.get("/forecast/NEVER").json()
        self.assertEqual((detail["forecast_available"], detail["points"]), (False, []))
        suggestions = self.client.get("/reorder").json()["suggestions"]
        self.assertTrue(any(row["sku_id"] == "FAST" and row["recommended_order_qty"] > 0 and row["lead_time_days"] == 21 for row in suggestions))
        self.upload("/integrations/stocky/import", stock)
        replay = self.upload("/integrations/shipstation/import", shipments, {"source_scope": "non_shopify"})
        self.assertEqual((replay["replayed"], replay["line_items_inserted"]), (True, 0))
        with self.factory() as db:
            self.assertFalse(self.user.is_admin)
            self.assertEqual(db.scalar(select(func.count()).select_from(ShopifyConnection)), 0)
            today_sku = next(sku for sku in shop_skus.load_skus_for_shop(db, self.user.shop_id) if sku.sku_id == "TODAY")
            self.assertEqual((today_sku.last_30_day_sales, today_sku.observed_history_days), (1, 0))
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 4)
            self.assertEqual(db.scalar(select(func.sum(Inventory.quantity))), 79)
            self.assertEqual(db.scalar(select(func.sum(OrderLineItem.quantity))), 92)
            self.assertEqual(db.scalar(select(func.sum(OrderLineItem.quantity * OrderLineItem.price))), 1830)

    def test_yesterday_evening_sale_counts_as_a_completed_utc_bucket(self):
        self.upload("/integrations/stocky/import", b"SKU,Product,Inventory,Price,Cost\nLATE,Late fixture,10,20,10\n")
        with self.factory() as db:
            product = db.scalar(select(Product).where(Product.sku == "LATE"))
            db.add(OrderLineItem(shop_id=self.user.shop_id, product_id=product.id, sku="LATE",
                quantity=2, price=20, shopify_order_id="synthetic-late-sale", created_at=datetime(2026, 9, 6, 20)))
            db.commit()
        with patch.object(shop_skus, "_now_naive_utc", return_value=datetime(2026, 9, 7, 12)):
            result = self.client.get("/forecast/LATE")
        self.assertEqual(result.status_code, 200)
        self.assertEqual((result.json()["forecast_available"], result.json()["history_days"]), (True, 1))

    def test_forecast_horizon_rejects_unbounded_and_negative_allocations(self):
        for path in ("/forecast", "/forecast/FAST"):
            for days in (-1, 0, 91, 1000000000):
                with self.subTest(path=path, days=days):
                    self.assertEqual(self.client.get(path, params={"horizon_days": days}).status_code, 422)
        for days in (1, 30, 90):
            self.assertEqual(self.client.get("/forecast", params={"horizon_days": days}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
