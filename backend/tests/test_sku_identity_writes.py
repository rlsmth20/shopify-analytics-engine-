"""Ambiguous SKU aliases cannot silently reset settings or rewrite PO evidence."""
import unittest
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import reorder, shop_settings as settings_route
from app.db.models import (Base, Inventory, Product, PurchaseOrderRecord, PurchaseOrderLineRecord,
                           PurchaseOrderReceiptRecord, Shop, AuditLogRecord)
from app.schemas import SkuLeadTimeEntry, UpdateSkuLeadTimesRequest
from app.schemas_v2 import (PurchaseOrderDraft, PurchaseOrderLine, SavePurchaseOrderRequest,
                            ReceivePurchaseOrderRequest, ReceivePurchaseOrderLineRequest)
from app.services import purchase_order_records as orders, shop_settings


class SkuIdentityWriteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False, autoflush=False)
        self.shop = Shop(shopify_domain="identity-write-fixture.myshopify.com")
        self.other = Shop(shopify_domain="other-identity-write-fixture.myshopify.com")
        self.db.add_all([self.shop, self.other]); self.db.commit()
        self.counter = 0

        @contextmanager
        def local_scope():
            yield self.db
            self.db.commit()

        self.scope_patch = patch.object(shop_settings, "session_scope", local_scope)
        self.scope_patch.start()

    def tearDown(self):
        self.scope_patch.stop()
        self.db.close()
        self.engine.dispose()

    def product(self, sku, *, active=True, lead=14, shop=None):
        self.counter += 1
        shop = shop or self.shop
        row = Product(shop_id=shop.id, shopify_product_id=str(self.counter),
                      shopify_variant_id=str(self.counter), sku=sku, name=f"Fixture {self.counter}",
                      price=20, cost=3, sku_lead_time_days=lead)
        self.db.add(row); self.db.flush()
        if active:
            self.db.add(Inventory(shop_id=shop.id, product_id=row.id, shopify_location_id="fixture", quantity=0))
        self.db.commit()
        return row

    def line(self, sku="SAFE", **changes):
        return PurchaseOrderLine(**{**dict(sku_id=sku, name=f"Original {sku}", qty=10, unit_cost=3,
                                         extended_cost=30, received_qty=0), **changes})

    def draft(self, lines=None, **changes):
        lines = [self.line()] if lines is None else lines
        return PurchaseOrderDraft(**{**dict(po_id="PO-FIXTURE", vendor="Original vendor",
            created_at=datetime.now(timezone.utc), status="draft", lines=lines,
            subtotal_cost=sum(line.extended_cost for line in lines), shipping_cost=5,
            total_cost=sum(line.extended_cost for line in lines) + 5,
            expected_arrival_date="2026-10-01", rationale="Original merchant wording"), **changes})

    def legacy(self, lines, *, shop=None):
        shop = shop or self.shop
        row = PurchaseOrderRecord(shop_id=shop.id, po_id="PO-FIXTURE", vendor="Original vendor", status="draft",
            subtotal_cost=Decimal("60"), shipping_cost=Decimal("5"), total_cost=Decimal("65"),
            expected_arrival_date="2026-10-01", rationale="Original merchant wording")
        self.db.add(row); self.db.flush()
        for line in lines:
            self.db.add(PurchaseOrderLineRecord(shop_id=shop.id, purchase_order_id=row.id,
                sku_id=line.sku_id, name=line.name, qty=line.qty, unit_cost=Decimal(str(line.unit_cost)),
                extended_cost=Decimal(str(line.extended_cost)), received_qty=line.received_qty))
        self.db.commit()
        return row

    def snapshot(self):
        return {model.__tablename__: list(self.db.execute(select(model.__table__).order_by(model.__table__.c.id)))
                for model in (Product, Inventory, PurchaseOrderRecord, PurchaseOrderLineRecord, PurchaseOrderReceiptRecord, AuditLogRecord)}

    def assert_no_mutation(self, before):
        # Even a caller committing after a rejected write must not persist a
        # partially reset override, a changed line, or an invented receipt.
        self.db.commit(); self.db.expire_all()
        self.assertEqual(self.snapshot(), before)

    def overrides(self, pairs):
        return shop_settings.upsert_sku_lead_times(shopify_domain=self.shop.shopify_domain,
            items=[shop_settings.LeadTimeOverrideValue(name=key, lead_time_days=value) for key, value in pairs])

    def test_ambiguous_override_rejects_before_any_safe_override_is_reset(self):
        self.product("SAFE", lead=21)
        self.product("DUP", lead=10); self.product("DUP", lead=20)
        before = self.snapshot()
        with self.assertRaises(shop_settings.ShopSettingsIdentityError):
            self.overrides([("SAFE", 31), ("DUP", 40)])
        self.assert_no_mutation(before)

    def test_unknown_override_is_validated_before_reset(self):
        self.product("SAFE", lead=21)
        before = self.snapshot()
        with self.assertRaises(shop_settings.ShopSettingsInputError):
            self.overrides([("NOT-IN-CATALOG", 30)])
        self.assert_no_mutation(before)

    def test_retired_stub_does_not_take_current_override_and_clear_is_explicit(self):
        old = self.product("SAME", active=False, lead=99)
        current = self.product("SAME", lead=14)
        result = self.overrides([("SAME", 28)])
        self.assertEqual((old.sku_lead_time_days, current.sku_lead_time_days), (99, 28))
        self.assertEqual([(item.name, item.lead_time_days) for item in result[2]], [("SAME", 28)])
        self.assertIn("retired", " ".join(result[3]))
        result = self.overrides([])
        self.assertEqual((old.sku_lead_time_days, current.sku_lead_time_days), (99, None))
        self.assertEqual(result[2], [])
        self.assertIn("retained", " ".join(result[3]))

    def test_unchanged_ambiguous_override_can_accompany_safe_edit(self):
        a, b = self.product("DUP", lead=20), self.product("DUP", lead=20)
        safe = self.product("SAFE", lead=10)
        result = self.overrides([("DUP", 20), ("SAFE", 30)])
        self.assertEqual((a.sku_lead_time_days, b.sku_lead_time_days, safe.sku_lead_time_days), (20, 20, 30))
        self.assertIn("unresolved", " ".join(result[3]))
        before = self.snapshot()
        with self.assertRaises(shop_settings.ShopSettingsIdentityError):
            self.overrides([("DUP", 21), ("SAFE", 40)])
        self.assert_no_mutation(before)
        cleared = self.overrides([])
        self.assertEqual((a.sku_lead_time_days, b.sku_lead_time_days, safe.sku_lead_time_days), (20, 20, None))
        self.assertIn("retained", " ".join(cleared[3]))

    def test_cross_tenant_duplicate_codes_do_not_block_unique_override_or_po(self):
        current = self.product("SAFE", lead=14)
        self.product("SAFE", shop=self.other); self.product("SAFE", shop=self.other)
        self.overrides([("SAFE", 26)])
        saved = orders.save_purchase_order(self.db, shop_id=self.shop.id, draft=self.draft())
        self.assertEqual(current.sku_lead_time_days, 26)
        self.assertEqual(saved.lines[0].product_id, current.id)
        self.assertFalse(saved.lines[0].identity_ambiguous)

    def test_new_po_ambiguity_ignores_spoofed_identity_flags_and_leaves_no_header(self):
        self.product("DUP"); self.product("DUP")
        before = self.snapshot()
        unsafe = self.line("DUP", identity_ambiguous=False, product_id=123456)
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.save_purchase_order(self.db, shop_id=self.shop.id, draft=self.draft([unsafe]))
        self.assert_no_mutation(before)

    def test_unsafe_saved_line_change_keeps_ids_text_amounts_and_other_lines(self):
        self.product("SAFE"); self.product("DUP"); self.product("DUP")
        self.legacy([self.line(), self.line("DUP", received_qty=2)])
        saved = orders.list_saved_purchase_orders(self.db, self.shop.id)[0]
        before = self.snapshot()
        changed = saved.model_copy(update={"rationale": "Should not persist", "lines": [
            saved.lines[0].model_copy(update={"name": "Should not persist"}),
            saved.lines[1].model_copy(update={"qty": 99})]})
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.save_purchase_order(self.db, shop_id=self.shop.id, draft=changed)
        self.assert_no_mutation(before)

    def test_unchanged_ambiguous_legacy_lines_allow_metadata_and_safe_line_changes(self):
        self.product("SAFE"); self.product("DUP"); self.product("DUP")
        self.legacy([self.line(), self.line("DUP", received_qty=2)])
        saved = orders.list_saved_purchase_orders(self.db, self.shop.id)[0]
        old_lines = self.snapshot()["purchase_order_lines"]
        changed = saved.model_copy(update={"rationale": "Reviewed merchant note", "lines": [
            saved.lines[0].model_copy(update={"name": "Updated safe line"}), saved.lines[1]]})
        result = orders.save_purchase_order(self.db, shop_id=self.shop.id, draft=changed)
        new_lines = self.snapshot()["purchase_order_lines"]
        self.assertEqual(new_lines[1], old_lines[1])
        self.assertEqual(new_lines[0].id, old_lines[0].id)
        self.assertEqual((result.rationale, result.total_cost), ("Reviewed merchant note", saved.total_cost))
        self.assertTrue(result.lines[1].identity_ambiguous)

    def test_duplicate_po_aliases_remain_readable_but_cannot_be_changed_or_received(self):
        self.product("SAME")
        self.legacy([self.line("SAME", name="First legacy item", received_qty=1), self.line("SAME", name="Second legacy item", received_qty=3)])
        saved = orders.list_saved_purchase_orders(self.db, self.shop.id)[0]
        self.assertEqual([line.received_qty for line in saved.lines], [1, 3])
        self.assertTrue(all(line.identity_ambiguous for line in saved.lines))
        before = self.snapshot()
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id=saved.po_id, received_lines={"SAME": (1, None)})
        self.assert_no_mutation(before)
        changed = saved.model_copy(update={"lines": [saved.lines[0].model_copy(update={"qty": 12}), saved.lines[1]]})
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.save_purchase_order(self.db, shop_id=self.shop.id, draft=changed)
        self.assert_no_mutation(before)
        result = orders.save_purchase_order(self.db, shop_id=self.shop.id,
            draft=saved.model_copy(update={"rationale": "Reviewed without remapping"}))
        self.assertEqual([line.received_qty for line in result.lines], [1, 3])
        self.assertEqual(self.snapshot()["purchase_order_lines"], before["purchase_order_lines"])

    def test_receipt_preflight_is_atomic_and_unrelated_unique_line_still_receives(self):
        current = self.product("SAFE")
        self.product("DUP"); self.product("DUP")
        self.legacy([self.line(), self.line("DUP")])
        before = self.snapshot()
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                          received_lines={"SAFE": (1, None), "DUP": (1, None)})
        self.assert_no_mutation(before)
        saved = orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE", received_lines={"SAFE": (1, 4)})
        self.assertEqual([line.received_qty for line in saved.lines], [1, 0])
        self.assertEqual((saved.receipts[0].sku_id, saved.receipts[0].received_unit_cost), ("SAFE", 4))
        self.assertEqual(saved.lines[0].product_id, current.id)

    def test_retired_stub_unique_active_receipt_and_status_preserve_raw_alias(self):
        self.product("SAME", active=False)
        current = self.product("SAME")
        self.legacy([self.line("SAME")])
        saved = orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE", received_lines={"SAME": (2, None)})
        self.assertEqual((saved.lines[0].sku_id, saved.lines[0].product_id, saved.lines[0].received_qty), ("SAME", current.id, 2))
        result = orders.update_purchase_order_status(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE", status="cancelled")
        self.assertEqual((result.status, result.rationale, result.total_cost), ("cancelled", "Original merchant wording", 65))
        self.assertEqual(len(result.receipts), 1)

    def test_unknown_duplicate_or_zero_only_receipt_rejects_without_audit_success(self):
        self.product("SAFE"); self.legacy([self.line()])
        before = self.snapshot()
        with self.assertRaises(orders.PurchaseOrderIdentityError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE", received_lines={"UNKNOWN": (1, None)})
        self.assert_no_mutation(before)
        with self.assertRaises(orders.PurchaseOrderReceiptError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE", received_lines={"SAFE": (0, None)})
        self.assert_no_mutation(before)
        with self.assertRaises(HTTPException) as empty:
            reorder.receive_po("PO-FIXTURE", ReceivePurchaseOrderRequest(request_id=uuid4(), lines=[
                ReceivePurchaseOrderLineRequest(sku_id="SAFE", received_qty=0)]),
                SimpleNamespace(shop_id=self.shop.id, id=1), self.db)
        self.assertEqual(empty.exception.status_code, 409)
        self.assert_no_mutation(before)
        payload = ReceivePurchaseOrderRequest(request_id=uuid4(), lines=[ReceivePurchaseOrderLineRequest(sku_id="SAFE", received_qty=1),
                                                     ReceivePurchaseOrderLineRequest(sku_id="SAFE", received_qty=2)])
        with self.assertRaises(HTTPException) as raised:
            reorder.receive_po("PO-FIXTURE", payload, SimpleNamespace(shop_id=self.shop.id, id=1), self.db)
        self.assertEqual(raised.exception.status_code, 409)
        self.assert_no_mutation(before)

    def test_over_remaining_receipt_rejects_entire_batch_then_exact_remaining_logs_applied_delta(self):
        self.product("SAFE"); self.product("PARTIAL")
        self.legacy([self.line(), self.line("PARTIAL", received_qty=8)])
        before = self.snapshot()
        payload = ReceivePurchaseOrderRequest(request_id=uuid4(), lines=[
            ReceivePurchaseOrderLineRequest(sku_id="SAFE", received_qty=1),
            ReceivePurchaseOrderLineRequest(sku_id="PARTIAL", received_qty=3)])
        with self.assertRaises(HTTPException) as raised:
            reorder.receive_po("PO-FIXTURE", payload, SimpleNamespace(shop_id=self.shop.id, id=1), self.db)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("2 unreceived units", raised.exception.detail["message"])
        self.assert_no_mutation(before)

        saved = orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                             received_lines={"PARTIAL": (2, 4.25)})
        self.assertEqual([line.received_qty for line in saved.lines], [0, 10])
        self.assertEqual([(row.sku_id, row.received_qty, row.received_unit_cost) for row in saved.receipts],
                         [("PARTIAL", 2, 4.25)])
        after_exact = self.snapshot()
        with self.assertRaises(orders.PurchaseOrderReceiptError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                          received_lines={"PARTIAL": (1, None)})
        self.assert_no_mutation(after_exact)

    def test_receipt_reloads_remaining_after_another_session_received_units(self):
        self.product("SAFE"); self.legacy([self.line()])
        cached = self.db.scalar(select(PurchaseOrderLineRecord))
        self.assertEqual(cached.received_qty, 0)
        with Session(self.engine, expire_on_commit=False, autoflush=False) as other_session:
            orders.receive_purchase_order(other_session, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                          received_lines={"SAFE": (8, None)})
        self.assertEqual(cached.received_qty, 0)  # This session still holds the older object.
        before = self.snapshot()
        with self.assertRaises(orders.PurchaseOrderReceiptError):
            orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                          received_lines={"SAFE": (3, None)})
        self.assert_no_mutation(before)
        saved = orders.receive_purchase_order(self.db, shop_id=self.shop.id, po_id="PO-FIXTURE",
                                             received_lines={"SAFE": (2, None)})
        self.assertEqual(saved.lines[0].received_qty, 10)
        self.assertEqual(sum(row.received_qty for row in saved.receipts), 10)

    def test_write_routes_report_conflict_without_audit_success(self):
        self.product("DUP"); self.product("DUP")
        before = self.snapshot()
        user = SimpleNamespace(shop_id=self.shop.id, id=1)
        with self.assertRaises(HTTPException) as settings_error:
            settings_route.update_sku_lead_times(UpdateSkuLeadTimesRequest(shopify_domain=self.other.shopify_domain,
                items=[SkuLeadTimeEntry(sku_id="DUP", lead_time_days=50)]), user, self.db)
        self.assertEqual(settings_error.exception.status_code, 409)
        with self.assertRaises(HTTPException) as po_error:
            reorder.save_po_draft(SavePurchaseOrderRequest(draft=self.draft([self.line("DUP")])), user, self.db)
        self.assertEqual(po_error.exception.status_code, 409)
        self.assert_no_mutation(before)


if __name__ == "__main__":
    unittest.main()
