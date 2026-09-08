"""Synthetic receipt transactions remain exactly once through retries and failures."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes import reorder
from app.db.models import (Base, Shop, AuditLogRecord, PurchaseOrderRecord,
    PurchaseOrderLineRecord, PurchaseOrderReceiptRecord, PurchaseOrderReceiptSubmissionRecord)
from app.schemas_v2 import PurchaseOrderDraft, PurchaseOrderLine, ReceivePurchaseOrderRequest
from app.services import purchase_order_records as orders


class ReceiptIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="skubase-receipt-test-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "fixture.db"),
            connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.date = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        with self.sessions() as db:
            shops = [Shop(shopify_domain=f"receipt-{i}.myshopify.com") for i in range(2)]
            db.add_all(shops); db.commit()
            self.shop_id, self.other_id = [row.id for row in shops]
            for shop in shops:
                orders.save_purchase_order(db, shop_id=shop.id, draft=self.draft())

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def draft(self, **changes):
        return PurchaseOrderDraft(**{**dict(po_id="PO-TEST", vendor="Fixture supplier", created_at=self.date,
            status="draft", lines=[PurchaseOrderLine(sku_id="SAFE", name="Fixture", qty=10, unit_cost=3, extended_cost=30)],
            subtotal_cost=30, shipping_cost=0, total_cost=30, expected_arrival_date="2026-09-07", rationale="Fixture"), **changes})

    def receive(self, request_id, *, shop_id=None, lines=None, date=None, db=None):
        values = dict(shop_id=shop_id or self.shop_id, po_id="PO-TEST", request_id=request_id,
            received_lines={"SAFE": (3, 3)} if lines is None else lines, received_at=date or self.date)
        if db is not None:
            return orders.receive_purchase_order_submission(db, **values)
        with self.sessions() as session:
            return orders.receive_purchase_order_submission(session, **values)

    def state(self, shop_id=None):
        with self.sessions() as db:
            scope = shop_id or self.shop_id
            po = orders.list_saved_purchase_orders(db, scope)[0]
            counts = [db.scalar(select(func.count(model.id)).where(model.shop_id == scope))
                      for model in (PurchaseOrderReceiptRecord, PurchaseOrderReceiptSubmissionRecord, AuditLogRecord)]
            return po.model_dump(mode="json"), counts

    def test_replay_has_one_increment_receipt_submission_and_audit(self):
        key = uuid4()
        first, replay = self.receive(key), self.receive(str(key).upper())
        self.assertFalse(first.replayed)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.request_id, str(key))
        self.assertEqual(replay.po.lines[0].received_qty, 3)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_new_key_allows_identical_second_shipment_and_old_key_returns_current_state(self):
        first = uuid4()
        self.receive(first); self.receive(uuid4())
        replay = self.receive(first)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.po.lines[0].received_qty, 6)
        self.assertEqual(self.state()[1], [2, 2, 2])

    def test_changed_payload_reusing_key_conflicts_without_mutation(self):
        key = uuid4(); self.receive(key)
        before = self.state()
        for change in [dict(lines={"SAFE": (2, 3)}), dict(lines={"SAFE": (3, 4)}), dict(date=self.date + timedelta(days=1))]:
            with self.subTest(change=change), self.assertRaises(orders.PurchaseOrderReceiptError) as error:
                self.receive(key, **change)
            self.assertNotIsInstance(error.exception, orders.ReceiptSubmissionNotAppliedError)
            self.assertEqual(self.state(), before)

    def test_canonical_numeric_and_timezone_representation_replays(self):
        key = uuid4(); self.receive(key, lines={"SAFE": (3, 3.0)})
        replay = self.receive(key, lines={"SAFE": (3, 3)}, date=self.date.astimezone(timezone(timedelta(hours=-7))))
        self.assertTrue(replay.replayed)
        # Order of a multi-line payload is not a new operation.
        self.assertEqual(orders._receipt_payload_hash({"B": (1, 2.0), "A": (2, None)}, None),
                         orders._receipt_payload_hash({"A": (2, None), "B": (1, 2)}, None))

    def test_replay_after_full_receipt_does_not_fail_remaining_guard(self):
        key = uuid4(); self.receive(key, lines={"SAFE": (10, 3)})
        replay = self.receive(key, lines={"SAFE": (10, 3)})
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.po.status, "received")
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_same_key_concurrent_submissions_apply_once(self):
        key, barrier = uuid4(), Barrier(2)
        def send():
            barrier.wait(timeout=5)
            return self.receive(key)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(result.replayed for result in results), [False, True])
        self.assertEqual(self.state()[0]["lines"][0]["received_qty"], 3)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_distinct_concurrent_keys_respect_remaining_quantity(self):
        barrier = Barrier(2)
        def send():
            barrier.wait(timeout=5)
            try:
                return self.receive(uuid4(), lines={"SAFE": (7, 3)}).replayed
            except orders.ReceiptSubmissionNotAppliedError:
                return "not_applied"
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(results, [False, "not_applied"])
        self.assertEqual(self.state()[0]["lines"][0]["received_qty"], 7)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_audit_failure_rolls_back_quantities_receipts_and_submission(self):
        key, before = uuid4(), self.state()
        original = orders.record_audit_event
        def fail_after_flush(db, **kwargs):
            original(db, **kwargs)
            db.flush()
            raise RuntimeError("synthetic failure before commit")
        with patch.object(orders, "record_audit_event", side_effect=fail_after_flush):
            with self.assertRaises(RuntimeError):
                self.receive(key)
        self.assertEqual(self.state(), before)
        self.assertFalse(self.receive(key).replayed)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_key_is_scoped_to_authenticated_tenant_and_purchase_order(self):
        key = uuid4()
        self.receive(key)
        self.assertFalse(self.receive(key, shop_id=self.other_id).replayed)
        self.assertEqual(self.state()[1], [1, 1, 1])
        self.assertEqual(self.state(self.other_id)[1], [1, 1, 1])
        with self.sessions() as db:
            orders.save_purchase_order(db, shop_id=self.shop_id, draft=self.draft(po_id="PO-SEPARATE"))
            distinct = orders.receive_purchase_order_submission(db, shop_id=self.shop_id, po_id="PO-SEPARATE",
                request_id=key, received_lines={"SAFE": (1, 3)}, received_at=self.date)
            self.assertFalse(distinct.replayed)
            self.assertIsNone(orders.receive_purchase_order_submission(db, shop_id=self.other_id, po_id="PO-SEPARATE",
                request_id=key, received_lines={"SAFE": (1, 3)}, received_at=self.date))

    def test_http_requires_uuid_and_marks_only_definite_preflight_rejection(self):
        user = SimpleNamespace(shop_id=self.shop_id, id=None)
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as missing:
                reorder.receive_po("PO-TEST", ReceivePurchaseOrderRequest(lines=[]), user, db)
            self.assertEqual(missing.exception.status_code, 422)
            self.assertIn("Reload", missing.exception.detail)
            with self.assertRaises(ValidationError):
                ReceivePurchaseOrderRequest(request_id="not-a-uuid", lines=[])
            key = uuid4()
            payload = ReceivePurchaseOrderRequest(request_id=key, lines=[dict(sku_id="SAFE", received_qty=11)])
            with self.assertRaises(HTTPException) as rejected:
                reorder.receive_po("PO-TEST", payload, user, db)
            self.assertEqual(rejected.exception.status_code, 409)
            self.assertEqual(rejected.exception.detail["receipt_status"], "not_applied")
            self.assertEqual(rejected.exception.detail["request_id"], str(key))
        self.assertEqual(self.state()[1], [0, 0, 0])
        self.receive(key)
        with self.sessions() as db, self.assertRaises(HTTPException) as conflict:
            reorder.receive_po("PO-TEST", payload, user, db)
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertIsInstance(conflict.exception.detail, str)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_http_json_roundtrip_returns_replay_marker_and_rejects_nonfinite_cost(self):
        app = FastAPI()
        app.include_router(reorder.router)
        def database():
            with self.sessions() as db:
                yield db
        route = next(route for route in app.routes if getattr(route, "path", "").endswith("/{po_id}/receive"))
        for dependency in route.dependant.dependencies:
            if dependency.name == "user":
                app.dependency_overrides[dependency.call] = lambda: SimpleNamespace(shop_id=self.shop_id, id=None)
            elif dependency.name == "db":
                app.dependency_overrides[dependency.call] = database
        payload = dict(request_id=str(uuid4()), lines=[dict(sku_id="SAFE", received_qty=3, received_unit_cost=3)],
                       received_at=self.date.isoformat())
        with TestClient(app) as client:
            missing = client.post("/reorder/purchase-orders/PO-TEST/receive", json={"lines": []})
            self.assertEqual(missing.status_code, 422)
            first = client.post("/reorder/purchase-orders/PO-TEST/receive", json=payload)
            replay = client.post("/reorder/purchase-orders/PO-TEST/receive", json=payload)
            self.assertEqual((first.status_code, replay.status_code), (200, 200))
            self.assertFalse(first.json()["replayed"])
            self.assertTrue(replay.json()["replayed"])
            self.assertEqual(replay.json()["request_id"], payload["request_id"])
            self.assertEqual(replay.json()["po"]["lines"][0]["received_qty"], 3)
            payload["lines"][0]["received_unit_cost"] = "Infinity"
            rejected = client.post("/reorder/purchase-orders/PO-TEST/receive", json=payload)
            self.assertEqual(rejected.status_code, 422)
        self.assertEqual(self.state()[1], [1, 1, 1])

    def test_stale_draft_cannot_revert_receipt_lifecycle_or_invent_received_units(self):
        with self.sessions() as db:
            stale = orders.list_saved_purchase_orders(db, self.shop_id)[0]
        self.receive(uuid4())
        before = self.state()
        with self.sessions() as db:
            stale.lines[0].received_qty = 9
            saved = orders.save_purchase_order(db, shop_id=self.shop_id, draft=stale)
            self.assertEqual(saved.lines[0].received_qty, 3)
            self.assertEqual(saved.status, "partially_received")
            self.assertEqual(saved.received_at.replace(tzinfo=timezone.utc), self.date)
        self.assertEqual(self.state()[1], before[1])

    def test_new_line_received_counts_are_ignored_and_order_cannot_shrink_below_receipts(self):
        with self.sessions() as db:
            draft = self.draft(po_id="PO-NEW")
            draft.lines[0].received_qty = 9
            saved = orders.save_purchase_order(db, shop_id=self.shop_id, draft=draft)
            self.assertEqual(saved.lines[0].received_qty, 0)
        self.receive(uuid4())
        with self.sessions() as db:
            saved = next(po for po in orders.list_saved_purchase_orders(db, self.shop_id) if po.po_id == "PO-TEST")
            for lines in [[saved.lines[0].model_copy(update={"qty": 2})], []]:
                before = self.state()
                with self.assertRaises(orders.PurchaseOrderReceiptError):
                    orders.save_purchase_order(db, shop_id=self.shop_id, draft=saved.model_copy(update={"lines": lines, "rationale": "Must not persist"}))
                db.commit()
                self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
