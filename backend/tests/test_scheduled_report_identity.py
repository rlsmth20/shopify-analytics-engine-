"""Report email rows preserve recorded stock without presenting held planning estimates."""
import unittest
from unittest.mock import patch

from app.schemas import SkuDetail
from app.services import scheduled_reports
from app.services.inventory_engine import build_inventory_actions


def sku(name, **changes):
    return SkuDetail(**{**dict(sku_id=name, name=name, vendor="Fixture supplier", category="Apparel",
        price=20, cost=5, inventory=4, last_30_day_sales=60, last_7_day_sales=14,
        days_since_last_sale=1, sales_history_complete=True), **changes})


class ScheduledReportIdentityTests(unittest.TestCase):
    def build(self, products, actions=None):
        with patch.object(scheduled_reports, "load_skus_for_shop", return_value=products), \
             patch.object(scheduled_reports, "load_effective_shop_settings_map", return_value={}):
            if actions is None:
                return scheduled_reports.build_report_email(None, shop_id=1, report_type="actions")
            with patch.object(scheduled_reports, "build_inventory_actions", return_value=actions):
                return scheduled_reports.build_report_email(None, shop_id=1, report_type="actions")

    def test_ambiguous_product_keeps_actual_stock_but_email_requires_review(self):
        content = self.build([sku("Held item", identity_ambiguous=True), sku("Unique item")])
        rows = {row[0]: row for row in content[3]}
        self.assertEqual(rows["Held item"][1:5], ["REVIEW", "4", "Unknown", "Unknown"])
        self.assertIn("Review", rows["Held item"][5])
        self.assertEqual(rows["Unique item"][1:4], ["URGENT", "4", "2d"])
        self.assertTrue(rows["Unique item"][4].startswith("$"))

    def test_explicit_planning_hold_overrides_legacy_numeric_values_and_status(self):
        product = sku("Planning held")
        action = build_inventory_actions([product])[0].model_copy(update={"planning_values_known": False})
        self.assertFalse(action.identity_ambiguous)
        self.assertTrue(action.financial_values_known)
        self.assertGreater(action.days_of_inventory, 0)
        row = self.build([product], [action])[3][0]
        self.assertEqual(row[1:5], ["REVIEW", "4", "Unknown", "Unknown"])
        self.assertIn("Review", row[5])
        self.assertNotEqual(row[5], action.recommended_action)


if __name__ == "__main__":
    unittest.main()
