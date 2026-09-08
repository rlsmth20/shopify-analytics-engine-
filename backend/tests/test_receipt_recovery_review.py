"""Independent durability, existing-deployment and privacy checks for receipts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4
import unittest

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.db import init_db
from app.db.base import Base
from app.db.models import (
    AuditLogRecord, PurchaseOrderLineRecord, PurchaseOrderReceiptRecord,
    PurchaseOrderReceiptSubmissionRecord, PurchaseOrderRecord, Shop,
)
from app.services import purchase_order_records as orders
from app.services.shopify_privacy import redact_shop


class ReceiptRecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="skubase-receipt-recovery-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "fixture.db"))
        # Simulate an existing deployment: all old tables exist, the new ledger does not.
        Base.metadata.create_all(self.engine, tables=[table for table in Base.metadata.sorted_tables
            if table.name != PurchaseOrderReceiptSubmissionRecord.__tablename__])
        self.sessions = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.shop_id = self.seed_shop("receipt-recovery-fixture.myshopify.com")

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def seed_shop(self, domain):
        with self.sessions() as db:
            shop = Shop(shopify_domain=domain)
            db.add(shop)
            db.flush()
            po = PurchaseOrderRecord(shop_id=shop.id, po_id="PO-FIXTURE", vendor="Fixture supplier",
                status="sent", subtotal_cost=30, shipping_cost=0, total_cost=30,
                expected_arrival_date="2026-10-01", rationale="Merchant recorded order")
            db.add(po)
            db.flush()
            db.add(PurchaseOrderLineRecord(shop_id=shop.id, purchase_order_id=po.id,
                sku_id="MERCHANT-SKU", name="Fixture line", qty=10, unit_cost=3,
                extended_cost=30, received_qty=0))
            db.commit()
            return shop.id

    def initialize(self):
        with patch.object(init_db, "engine", self.engine):
            init_db.init_db()

    def submit(self, db, request_id, shop_id=None):
        return orders.receive_purchase_order_submission(db, shop_id=shop_id or self.shop_id,
            po_id="PO-FIXTURE", request_id=request_id, received_lines={"MERCHANT-SKU": (2, None)})

    def counts(self, db, shop_id):
        return tuple(db.scalar(select(func.count()).select_from(model).where(model.shop_id == shop_id))
            for model in (PurchaseOrderReceiptSubmissionRecord, PurchaseOrderReceiptRecord, AuditLogRecord))

    def test_existing_database_gains_ledger_idempotently_without_changing_saved_order(self):
        self.assertNotIn("purchase_order_receipt_submissions", inspect(self.engine).get_table_names())
        self.initialize()
        self.initialize()
        self.assertIn("purchase_order_receipt_submissions", inspect(self.engine).get_table_names())
        unique_constraints = inspect(self.engine).get_unique_constraints("purchase_order_receipt_submissions")
        self.assertTrue(any(set(row["column_names"]) == {"shop_id", "purchase_order_id", "request_id"}
                            for row in unique_constraints))
        with self.sessions() as db:
            po = db.scalar(select(PurchaseOrderRecord))
            line = db.scalar(select(PurchaseOrderLineRecord))
            self.assertEqual((po.status, po.total_cost, line.qty, line.received_qty), ("sent", 30, 10, 0))
            result = self.submit(db, uuid4())
            self.assertFalse(result.replayed)
            self.assertEqual(self.counts(db, self.shop_id), (1, 1, 1))

    def test_commit_acknowledgement_loss_replays_from_a_fresh_session_without_more_units(self):
        self.initialize()
        request_id = uuid4()
        with self.sessions() as db:
            real_commit = db.commit
            def commit_then_lose_acknowledgement():
                real_commit()
                raise RuntimeError("Synthetic connection loss after database commit")
            with patch.object(db, "commit", side_effect=commit_then_lose_acknowledgement):
                with self.assertRaisesRegex(RuntimeError, "after database commit"):
                    self.submit(db, request_id)
        # There is no in-memory session state or caller response available to the retry.
        with self.sessions() as db:
            self.assertEqual(self.counts(db, self.shop_id), (1, 1, 1))
            result = self.submit(db, request_id)
            self.assertTrue(result.replayed)
            self.assertEqual(result.request_id, str(request_id))
            self.assertEqual(result.po.lines[0].received_qty, 2)
            self.assertEqual(len(result.po.receipts), 1)
            self.assertEqual(self.counts(db, self.shop_id), (1, 1, 1))

    def test_privacy_purge_removes_ledger_and_receipts_only_for_the_signed_shop(self):
        self.initialize()
        other_id = self.seed_shop("other-receipt-recovery-fixture.myshopify.com")
        request_id = uuid4()
        with self.sessions() as db:
            self.submit(db, request_id)
            self.submit(db, request_id, other_id)
            self.assertEqual(self.counts(db, self.shop_id), (1, 1, 1))
            self.assertEqual(self.counts(db, other_id), (1, 1, 1))
            # Explicit privacy deletion also works when SQLite FK enforcement is off.
            result = redact_shop(db, shop_domain="receipt-recovery-fixture.myshopify.com", triggered_at=None)
            self.assertEqual(result["shops_redacted"], 1)
        with self.sessions() as db:
            self.assertEqual(self.counts(db, self.shop_id), (0, 0, 0))
            self.assertEqual(self.counts(db, other_id), (1, 1, 1))
            replay = self.submit(db, request_id, other_id)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.po.lines[0].received_qty, 2)


if __name__ == "__main__":
    unittest.main()
