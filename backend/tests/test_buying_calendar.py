"""Next-buy planning nets timely issued stock without hiding arrival risk."""
import unittest
from datetime import date, datetime, timedelta, timezone

from app.config.lead_time import MOCK_LEAD_TIME_CONFIG
from app.schemas import SkuDetail
from app.schemas_v2 import PurchaseOrderDraft, PurchaseOrderLine
from app.services.buying_calendar import build_buying_calendar_events


class BuyingCalendarTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 7)
        self.sent_at = datetime(2026, 9, 7, tzinfo=timezone.utc)
        self.sku = SkuDetail(sku_id="AUDIT", name="Incoming stock", vendor="Vendor", category="General",
            price=20, cost=10, inventory=5, last_30_day_sales=60, last_7_day_sales=14, days_since_last_sale=1)
        self.history = [2] * 90

    def po(self, *, qty=37, received=0, status="sent", arrival_days=1, sku_id="AUDIT", po_id="PO-1"):
        return PurchaseOrderDraft(po_id=po_id, vendor="Vendor", created_at=self.sent_at, status=status, source="saved",
            lines=[PurchaseOrderLine(sku_id=sku_id, name="Incoming stock", qty=qty, received_qty=received,
                                     unit_cost=10, extended_cost=qty * 10)],
            subtotal_cost=qty * 10, total_cost=qty * 10, sent_at=self.sent_at,
            expected_arrival_date=(self.today + timedelta(days=arrival_days)).isoformat(), rationale="Fixture PO")

    def calendar(self, orders=None, *, sku=None, history=None, order_cost=0, horizon_days=180):
        return build_buying_calendar_events([sku or self.sku], lambda _id: self.history if history is None else history,
            lead_time_config=MOCK_LEAD_TIME_CONFIG, saved_purchase_orders=orders or [], today=self.today,
            order_cost=order_cost, horizon_days=horizon_days)

    def recommended(self, events):
        return [event for event in events if event.source == "recommended"]

    def test_timely_sent_po_covers_next_buy_without_double_counting_370_dollars(self):
        baseline = self.calendar()
        self.assertEqual((baseline[0].total_units, baseline[0].estimated_cost), (37, 370))
        po = self.po()
        before = po.model_dump()
        events = self.calendar([po])
        self.assertEqual(self.recommended(events), [])
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].source, events[0].total_units, sum(e.estimated_cost for e in events)), ("saved", 37, 370))
        self.assertEqual(po.model_dump(), before)

    def test_partial_receipts_offset_only_remaining_stock(self):
        events = self.calendar([self.po(received=12, status="partially_received")])
        recommendation = self.recommended(events)[0]
        saved = next(event for event in events if event.source == "saved")
        self.assertEqual((recommendation.total_units, recommendation.estimated_cost), (12, 120))
        self.assertEqual((saved.total_units, saved.lines[0].qty), (25, 25))
        self.assertEqual(saved.estimated_cost, 370)  # Original commitment, not an invented unpaid balance.
        self.assertIn("25 unreceived units", recommendation.rationale)

    def test_unissued_and_closed_statuses_never_offset_new_buys(self):
        for status in ("draft", "ready", "approved", "received", "cancelled"):
            with self.subTest(status=status):
                events = self.calendar([self.po(status=status)])
                self.assertEqual(self.recommended(events)[0].total_units, 37)
                self.assertEqual(len([event for event in events if event.source == "saved"]), int(status not in {"received", "cancelled"}))

    def test_overdue_undated_invalid_or_unconfirmed_orders_do_not_mask_demand(self):
        variants = [self.po(arrival_days=-1)]
        for eta in ("", "not-a-date"):
            po = self.po()
            po.expected_arrival_date = eta
            variants.append(po)
        for sent_at in (None, self.sent_at + timedelta(days=1)):
            po = self.po()
            po.sent_at = sent_at
            variants.append(po)
        for po in variants:
            with self.subTest(eta=po.expected_arrival_date, sent_at=po.sent_at):
                events = self.calendar([po])
                self.assertEqual(self.recommended(events)[0].total_units, 37)
                if po.expected_arrival_date in ("", "not-a-date"):
                    saved = next(event for event in events if event.source == "saved")
                    self.assertEqual(saved.expected_arrival_date, "")
                    self.assertIn("verify a new ETA", saved.rationale)

    def test_arrival_on_last_covered_day_counts_but_day_after_stockout_does_not(self):
        # Five units at two/day remain nonnegative at the start of day two;
        # day three has an uncovered unit before the new stock can arrive.
        self.assertEqual(self.recommended(self.calendar([self.po(arrival_days=2)])), [])
        self.assertEqual(self.recommended(self.calendar([self.po(arrival_days=3)]))[0].total_units, 37)
        self.assertEqual(self.recommended(self.calendar([self.po(arrival_days=0)])), [])

    def test_earlier_arrival_extends_runway_for_a_later_po_regardless_of_input_order(self):
        early = self.po(qty=10, arrival_days=2, po_id="EARLY")
        later = self.po(qty=27, arrival_days=7, po_id="LATER")
        events = self.calendar([later, early])
        self.assertEqual(self.recommended(events), [])
        self.assertEqual(sum(event.total_units for event in events), 37)
        self.assertEqual(sum(event.estimated_cost for event in events), 370)

    def test_arrival_after_relevant_buying_cycle_cannot_offset_it_even_with_enough_runway(self):
        sku = self.sku.model_copy(update={"inventory": 100})
        history = [0, 4] * 45  # Safety stock brings the arrival horizon before depletion.
        original = self.recommended(self.calendar(sku=sku, history=history))[0]
        arrival_day = (date.fromisoformat(original.expected_arrival_date) - self.today).days
        covered = self.po(qty=original.total_units, arrival_days=arrival_day)
        too_late = self.po(qty=original.total_units, arrival_days=arrival_day + 1)
        self.assertEqual(self.recommended(self.calendar([covered], sku=sku, history=history)), [])
        self.assertEqual(self.recommended(self.calendar([too_late], sku=sku, history=history))[0].total_units, original.total_units)

    def test_other_skus_fully_received_lines_and_negative_receipt_values_do_not_inflate_inbound(self):
        self.assertEqual(self.recommended(self.calendar([self.po(sku_id="OTHER")]))[0].total_units, 37)
        for received in (37, 50):
            events = self.calendar([self.po(received=received, status="partially_received")])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].total_units, 37)
        # A malformed negative received count must not fabricate extra inbound.
        events = self.calendar([self.po(qty=20, received=-100)])
        self.assertEqual(self.recommended(events)[0].total_units, 17)

    def test_economic_order_quantity_cannot_force_another_buy_after_need_is_covered(self):
        self.assertGreater(self.recommended(self.calendar(order_cost=35))[0].total_units, 37)
        self.assertEqual(self.recommended(self.calendar([self.po()], order_cost=35)), [])

    def test_unknown_unit_cost_does_not_drive_eoq_or_claim_known_planned_spend(self):
        sku = self.sku.model_copy(update={"cost_source": "estimated_from_price"})
        recommendation = self.recommended(self.calendar(sku=sku, order_cost=35))[0]
        self.assertEqual(recommendation.total_units, 37)
        self.assertFalse(recommendation.financial_values_known)
        self.assertIsNone(recommendation.financial_values["estimated_cost"])
        self.assertEqual(recommendation.lines[0].cost_source, "estimated_from_price")
        self.assertIsNone(recommendation.lines[0].financial_values["unit_cost"])

    def test_unknown_in_memory_po_amounts_are_not_promoted_to_recorded_costs(self):
        po = self.po()
        po.lines[0] = po.lines[0].model_copy(update={"cost_source": "estimated_from_price", "financial_values_known": False})
        po.financial_values_known = False
        event = self.calendar([po])[0]
        self.assertEqual(event.source, "saved")
        self.assertFalse(event.financial_values_known)
        self.assertIsNone(event.financial_values["estimated_cost"])
        self.assertEqual(event.lines[0].cost_source, "estimated_from_price")
        self.assertIsNone(event.lines[0].financial_values["unit_cost"])

    def test_recorded_zero_cost_goods_still_include_configured_freight(self):
        sku = self.sku.model_copy(update={"cost": 0, "cost_source": "recorded"})
        recommendation = self.recommended(self.calendar(sku=sku, order_cost=35))[0]
        self.assertEqual(recommendation.total_units, 37)
        self.assertEqual(recommendation.lines[0].extended_cost, 0)
        self.assertTrue(recommendation.financial_values_known)
        self.assertEqual(recommendation.financial_values["estimated_cost"], 35)

    def test_existing_order_and_inventory_inputs_remain_unchanged_and_horizon_stays_bounded(self):
        sku = self.sku.model_copy(update={"inventory": 1000})
        po = self.po(qty=37)
        before = (sku.model_dump(), po.model_dump())
        events = self.calendar([po], sku=sku, horizon_days=30)
        self.assertEqual(self.recommended(events), [])
        self.assertEqual(len(events), 1)
        self.assertEqual((sku.model_dump(), po.model_dump()), before)


if __name__ == "__main__":
    unittest.main()
