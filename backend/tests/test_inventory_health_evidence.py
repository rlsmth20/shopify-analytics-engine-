"""Inventory risk must distinguish missing history from observed zero demand."""
import unittest

from app.schemas import SkuDetail
from app.services.forecasting import ForecastInputs, forecast_sku
from app.services.inventory_health import build_inventory_health


def product(sku_id="A", **changes):
    values = dict(sku_id=sku_id, name=f"Fixture {sku_id}", vendor="Fixture vendor", category="Apparel",
                  price=20, cost=10, inventory=10, last_30_day_sales=0, last_7_day_sales=0,
                  days_since_last_sale=0, sales_history_complete=False)
    return SkuDetail(**{**values, **changes})


def forecast(sku, history, observed=None):
    return forecast_sku(ForecastInputs(sku_id=sku.sku_id, daily_history=history, on_hand=sku.inventory,
                                     start_weekday=0, observed_history_days=observed))


def metric(health, label):
    return next(row for row in health.kpis if row.label == label)


class InventoryHealthEvidenceTests(unittest.TestCase):
    def test_missing_history_keeps_exposure_and_cover_unknown_without_false_triage(self):
        sku = product()
        for forecasts in ([], [forecast(sku, [0] * 90)]):
            with self.subTest(forecast_count=len(forecasts)):
                health = build_inventory_health(skus=[sku], forecasts=forecasts)
                risk = metric(health, "Stockout revenue risk")
                self.assertFalse(risk.value_known)
                self.assertIsNone(risk.model_dump()["known_value"])
                self.assertEqual(risk.tone, "neutral")
                self.assertNotIn("$0", risk.note)
                self.assertEqual(health.forecast_coverage.model_dump(), dict(total_skus=1, available_skus=0,
                    unavailable_skus=1, low_confidence_skus=0, no_recent_sales_skus=0))
                self.assertEqual(health.top_stockout_risk, [])
                self.assertIsNone(metric(health, "Average days of cover").known_value)
                self.assertEqual(next(row.value for row in health.forecast_confidence if row.label == "Unavailable"), 1)
                self.assertFalse(any(row.title == "Catalog needs triage" for row in health.insights))

    def test_explicit_unavailability_overrides_positive_numeric_placeholders(self):
        sku = product()
        unavailable = forecast(sku, [30] * 90).model_copy(update={"forecast_available": False})
        health = build_inventory_health(skus=[sku], forecasts=[unavailable])
        self.assertIsNone(metric(health, "Stockout revenue risk").known_value)
        self.assertEqual(health.top_stockout_risk, [])
        self.assertEqual(next(row.value for row in health.health_buckets if row.label == "Stockout risk"), 0)
        self.assertEqual(next(row.value for row in health.forecast_confidence if row.label == "High"), 0)

    def test_partial_catalog_keeps_valid_estimate_as_clearly_labeled_subtotal(self):
        assessed, missing = product("assessed"), product("missing")
        valid_forecast = forecast(assessed, [30] * 90)
        known = build_inventory_health(skus=[assessed], forecasts=[valid_forecast])
        partial = build_inventory_health(skus=[assessed, missing], forecasts=[valid_forecast, forecast(missing, [])])
        risk = metric(partial, "Stockout revenue risk")
        self.assertIsNone(risk.known_value)
        self.assertEqual(risk.value, metric(known, "Stockout revenue risk").known_value)
        self.assertGreater(risk.value, 0)
        self.assertIn("subtotal", risk.note)
        self.assertIn("1 of 2 SKUs", risk.note)
        self.assertIn("total revenue and gross margin exposure are unknown", risk.note)
        self.assertEqual([row.sku_id for row in partial.top_stockout_risk], [assessed.sku_id])
        self.assertEqual(next(row.metric_label for row in partial.insights if row.title == "Protect revenue first"),
                         "Estimated revenue-risk subtotal")

    def test_short_and_sparse_forecasts_keep_uncertainty_next_to_estimated_risk(self):
        sku = product()
        cases = [forecast(sku, [30]), forecast(sku, ([0] * 9 + [30]) * 9)]
        for estimate in cases:
            with self.subTest(history=estimate.history_days):
                health = build_inventory_health(skus=[sku], forecasts=[estimate])
                self.assertEqual(health.forecast_coverage.low_confidence_skus, 1)
                note = health.top_stockout_risk[0].note
                self.assertIn("Low-confidence", note)
                self.assertIn("Verify recent sales", note)
                self.assertNotIn("%", note)
                self.assertNotIn("units forecast", note)
                self.assertIn("low confidence", metric(health, "Stockout revenue risk").note)
        self.assertIn("Only 1 day of usable sales history", build_inventory_health(skus=[sku], forecasts=[cases[0]]).top_stockout_risk[0].note)

    def test_observed_zero_sales_are_known_zero_estimate_without_finite_cover_claim(self):
        sku = product(sales_history_complete=True)
        estimate = forecast(sku, [0] * 90, observed=90)
        health = build_inventory_health(skus=[sku], forecasts=[estimate])
        risk = metric(health, "Stockout revenue risk")
        self.assertEqual((risk.value_known, risk.known_value), (True, 0))
        self.assertEqual((health.forecast_coverage.available_skus, health.forecast_coverage.no_recent_sales_skus), (1, 1))
        self.assertIn("do not guarantee zero future demand", risk.note)
        self.assertIsNone(metric(health, "Average days of cover").known_value)
        self.assertEqual(health.top_stockout_risk, [])

    def test_full_history_retains_estimates_without_rounding_probability_to_certainty(self):
        sku = product(last_30_day_sales=900, sales_history_complete=True)
        health = build_inventory_health(skus=[sku], forecasts=[forecast(sku, [30] * 90)])
        risk = metric(health, "Stockout revenue risk")
        self.assertTrue(risk.value_known)
        self.assertGreater(risk.known_value, 0)
        self.assertEqual(health.forecast_coverage.low_confidence_skus, 0)
        self.assertIn("over 99% estimated stockout risk", health.top_stockout_risk[0].note)
        self.assertNotIn("100%", health.top_stockout_risk[0].note)
        self.assertAlmostEqual(metric(health, "Average days of cover").known_value, .3)

    def test_forecasts_outside_catalog_and_duplicate_rows_do_not_inflate_coverage(self):
        sku, foreign = product(), product("foreign")
        own_forecast = forecast(sku, [30] * 90)
        health = build_inventory_health(skus=[sku], forecasts=[own_forecast, own_forecast, forecast(foreign, [30] * 90)])
        self.assertEqual((health.forecast_coverage.total_skus, health.forecast_coverage.available_skus), (1, 1))
        self.assertEqual(metric(health, "High-confidence forecasts").known_value, 1)
        self.assertEqual(sum(row.value for row in health.forecast_confidence), 1)


if __name__ == "__main__":
    unittest.main()
