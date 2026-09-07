"""Dashboard backtests compare the same forecast and observed time window."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas import SkuDetail
from app.services import dashboard
from app.services.forecasting import ForecastInputs, forecast_sku


def build(history):
    sku = SkuDetail(
        sku_id="SKU-1", name="Test product", vendor="Supplier", category="Apparel",
        price=20, cost=10, inventory=1000, last_30_day_sales=30,
        last_7_day_sales=7, days_since_last_sale=1,
        sales_history_complete=True, sales_history_warnings=[],
    )
    return dashboard.build_dashboard(
        [sku], shop_id=1, daily_history_fn=lambda sku_id, days: history[-days:],
        recent_revenue_fn=lambda days: [], start_weekday=0,
    )


class DashboardForecastVarianceTests(unittest.TestCase):
    def setUp(self):
        history_patch = patch.object(dashboard, "list_recent_events", return_value=[])
        history_patch.start()
        self.addCleanup(history_patch.stop)

    def test_matching_held_out_week_is_zero_variance_even_when_monthly_average_differs(self):
        training = [10] * 83
        forecast = SimpleNamespace(
            projected_30_day_demand=3000,
            points=[SimpleNamespace(expected_units=10) for _ in range(7)],
        )
        with patch.object(dashboard, "forecast_sku", return_value=forecast) as predict:
            result = build(training + [10] * 7)
        self.assertEqual(result.forecast_vs_actual_7d[0].value, 0)
        self.assertEqual(predict.call_args.args[0].daily_history, training)
        self.assertEqual(predict.call_args.kwargs["horizon_days"], 7)

    def test_real_rising_demand_forecast_is_compared_to_its_first_week(self):
        training = [10 + day for day in range(83)]
        forecast = forecast_sku(
            ForecastInputs(sku_id="SKU-1", daily_history=training, on_hand=1000, start_weekday=0),
            horizon_days=7,
        )
        held_out = [100] * 7
        weekly_prediction = sum(point.expected_units for point in forecast.points)
        expected = round((sum(held_out) - weekly_prediction) / weekly_prediction * 100, 1)
        wrong_monthly_average = forecast.projected_30_day_demand / 30 * 7
        wrong_variance = round((sum(held_out) - wrong_monthly_average) / wrong_monthly_average * 100, 1)
        self.assertNotEqual(expected, wrong_variance)
        self.assertEqual(build(training + held_out).forecast_vs_actual_7d[0].value, expected)

    def test_zero_forecast_has_no_percentage_comparison_with_zero_or_positive_actuals(self):
        for held_out in ([0] * 7, [10] * 7):
            with self.subTest(actual=sum(held_out)):
                self.assertEqual(build([0] * 83 + held_out).forecast_vs_actual_7d, [])

    def test_zero_actuals_remain_a_real_negative_variance_when_forecast_is_positive(self):
        result = build([10] * 83 + [0] * 7)
        self.assertEqual(result.forecast_vs_actual_7d[0].value, -100)


if __name__ == "__main__":
    unittest.main()
