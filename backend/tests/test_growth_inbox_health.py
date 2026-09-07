"""Synthetic receiving evidence: no mail, credentials, DNS or external providers."""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth import engine, inbox_health, messaging
from app.growth.dashboard import dashboard
from app.growth.models import Contact, Evidence, Message
from app.growth.policy import GrowthError
from app.growth.store import get_memory, record, remember


NOW = 1_800_000_000.0


def receipt(provider_id="self-check", sender="info@skubase.io", at=NOW - 100, to=None):
    return {"id": provider_id, "from": sender, "to": to or ["info@skubase.io"],
            "created_at": datetime.fromtimestamp(at, timezone.utc).isoformat(),
            "subject": "Synthetic mailbox check", "text": "Can I get access?"}


class GrowthInboxHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbengine = create_engine("sqlite:///" + str(Path(self.temp.name) / "inbox.db"),
            connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.dbengine)
        self.factory = sessionmaker(self.dbengine, expire_on_commit=False, autoflush=False)
        self.env = patch.dict(os.environ, {"GROWTH_MAILBOX": "info@skubase.io",
            "GROWTH_INBOUND_ENABLED": "true", "GROWTH_RESEND_API_KEY": "fixture",
            "GROWTH_MODEL_ENABLED": "false", "GROWTH_DISCOVERY_ENABLED": "false"})
        self.env.start()
        engine.bootstrap(self.factory)

    def tearDown(self):
        self.env.stop()
        self.dbengine.dispose()
        self.temp.cleanup()

    def poll(self, rows, at=NOW, has_more=False):
        calls = []
        def provider(path):
            calls.append(path)
            if "?" in path:
                return {"data": rows, "has_more": has_more}
            return next(row for row in rows if path.endswith("/" + row["id"]))
        with patch("app.growth.messaging.time.time", return_value=at):
            result = messaging.poll_replies(self.factory, provider=provider)
        return result, calls

    def view(self, now=NOW):
        with self.factory() as db:
            return inbox_health.projection(db, now=now)

    def proof(self, at=NOW - 100, key="proof"):
        with self.factory() as db:
            evidence = record(db, key, "MAILBOX_BRIDGE_VERIFIED", "info@skubase.io",
                {"mailbox": "info@skubase.io", "verified": True, "receipt_ids": ["proof-receipt"],
                 "source_reference": "synthetic fixture"}, source="owner_verified_transport",
                epistemic="FACT", occurred_at=at)
            inbox_health.record_bridge_verification(db, evidence.id, now=NOW)
            db.commit()
            return evidence.id

    def test_empty_poll_is_normal_but_never_proof(self):
        result, _ = self.poll([])
        self.assertEqual(result, {"replies_ingested": 0})
        view = self.view()
        self.assertEqual(view["status"], "verification_unrecorded")
        self.assertEqual(view["last_successful_poll_at"], NOW)
        self.assertEqual(view["latest_poll_replies_ingested"], 0)
        self.assertIsNone(view["last_approved_receipt_at"])
        self.assertIsNone(view["last_bridge_verified_at"])
        with self.factory() as db:
            self.assertEqual(dashboard(db)["agent"]["inbox_transport"]["last_successful_poll_at"], NOW)
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 0)

    def test_self_receipt_and_replayed_pages_do_not_create_customer_metrics_or_refresh_age(self):
        rows = [receipt(), receipt("foreign", "outside@example.test", to=["someone@example.test"])]
        result, calls = self.poll(rows)
        self.assertEqual(result["replies_ingested"], 0)
        self.assertEqual(len(calls), 1)
        first = self.view()
        self.dbengine.dispose()  # Persist across connection/process recreation.
        self.poll(rows, at=NOW + 300)
        latest = self.view(NOW + 300)
        self.assertEqual(latest["last_approved_receipt_at"], NOW - 100)
        self.assertEqual(latest["last_approved_receipt_observed_at"], first["last_approved_receipt_observed_at"])
        self.assertEqual(latest["last_successful_poll_at"], NOW + 300)
        self.assertIsNone(latest["last_bridge_verified_at"])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Contact)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "REPLY_RECEIVED")), 0)
            retained = list(db.scalars(select(Evidence).where(Evidence.kind == "INBOUND_TRANSPORT_RECEIPT")))
            self.assertEqual(len(retained), 1)
            self.assertTrue(retained[0].data["self_check"])
            self.assertEqual(retained[0].data["provider_id"], "self-check")

    def test_real_reply_ingests_once_and_old_pages_do_not_move_receipt_time_backwards(self):
        row = receipt("merchant", "merchant@example.test")
        result, _ = self.poll([row])
        self.assertEqual(result["replies_ingested"], 1)
        result, calls = self.poll([row, receipt("older", at=NOW - 1000)], at=NOW + 300)
        self.assertEqual(result["replies_ingested"], 0)
        self.assertEqual(len(calls), 1)
        view = self.view(NOW + 300)
        self.assertEqual(view["last_approved_receipt_at"], NOW - 100)
        self.assertEqual(view["last_approved_receipt_observed_at"], NOW + 300)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "REPLY_RECEIVED")), 1)

    def test_malformed_seen_receipt_metadata_does_not_block_a_new_reply(self):
        seen = receipt("already-ingested", "first@example.test")
        self.poll([seen])
        malformed_replay = {**seen, "to": None}
        new_reply = receipt("new-merchant", "second@example.test")
        result, calls = self.poll([malformed_replay, new_reply], at=NOW + 100, has_more=True)
        self.assertEqual(result["replies_ingested"], 1)
        self.assertEqual(calls, ["emails/receiving?limit=20", "emails/receiving/new-merchant"])
        self.assertEqual(self.view(NOW + 100)["last_poll_status"], "success")
        with self.factory() as db:
            self.assertEqual(get_memory(db, "working", "inbound_cursor"), {"after": "new-merchant"})
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 2)

    def test_observer_declines_malformed_shapes_without_swallowing_new_message_failure(self):
        with self.factory() as db:
            for row in (None, [], "invalid", {}, {**receipt(), "id": None},
                        {**receipt(), "id": ""}, {**receipt(), "to": None},
                        {**receipt(), "to": [None]}, {**receipt(), "from": None}):
                with self.subTest(row=row):
                    self.assertFalse(inbox_health.observe_receipt(db, row, observed_at=NOW))
            db.commit()
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(
                Evidence.kind == "INBOUND_TRANSPORT_RECEIPT")), 0)
        with self.assertRaises(TypeError):
            self.poll([{**receipt("new-malformed", "merchant@example.test"), "to": None}])
        self.assertEqual(self.view()["status"], "poll_failed")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 0)
            self.assertEqual(get_memory(db, "working", "inbound_cursor"), {})

    def test_failed_poll_preserves_success_cursor_and_original_exception(self):
        self.poll([receipt()], has_more=True)
        error = GrowthError("Synthetic confidential provider response", "configuration")
        with patch("app.growth.messaging.time.time", return_value=NOW + 60):
            with self.assertRaises(GrowthError) as caught:
                messaging.poll_replies(self.factory, provider=lambda _: (_ for _ in ()).throw(error))
        self.assertIs(caught.exception, error)
        view = self.view(NOW + 60)
        self.assertEqual(view["status"], "poll_failed")
        self.assertEqual(view["last_successful_poll_at"], NOW)
        self.assertIsNone(view["latest_poll_replies_ingested"])
        self.assertNotIn("confidential", str(view))
        with self.factory() as db:
            self.assertEqual(get_memory(db, "working", "inbound_cursor"), {"after": "self-check"})
            self.assertNotIn("confidential", str(inbox_health._state(db)))
        self.poll([], at=NOW + 300)
        self.assertEqual(self.view(NOW + 300)["status"], "verification_unrecorded")

    def test_receipt_survives_detail_failure_and_retry_ingests_once(self):
        row = receipt("retry", "merchant@example.test")
        def provider(path):
            if "?" in path:
                return {"data": [row]}
            raise TimeoutError("fixture")
        with patch("app.growth.messaging.time.time", return_value=NOW):
            with self.assertRaises(TimeoutError):
                messaging.poll_replies(self.factory, provider=provider)
        self.assertEqual(self.view()["status"], "poll_failed")
        self.assertEqual(self.view()["last_approved_receipt_at"], NOW - 100)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 0)
        result, _ = self.poll([row], at=NOW + 100)
        self.assertEqual(result["replies_ingested"], 1)
        self.assertEqual(self.view(NOW + 100)["last_approved_receipt_observed_at"], NOW)

    def test_malformed_page_is_failure_and_missing_arrival_date_stays_unknown(self):
        with self.assertRaises(GrowthError):
            messaging.poll_replies(self.factory, provider=lambda _: {})
        row = receipt()
        row["created_at"] = "unavailable"
        self.poll([row])
        self.assertIsNone(self.view()["last_approved_receipt_at"])
        self.assertEqual(self.view()["last_approved_receipt_observed_at"], NOW)

    def test_independent_verification_is_historical_auditable_and_not_inferred_from_receipts(self):
        self.poll([receipt()])
        self.assertIsNone(self.view()["last_bridge_verified_at"])
        proof_id = self.proof()
        self.proof(NOW - 200, "old-proof")
        with self.factory() as db:
            inbox_health.record_bridge_verification(db, proof_id, now=NOW + 1000)
            db.commit()
            raw_receipt = db.scalar(select(Evidence).where(Evidence.kind == "INBOUND_TRANSPORT_RECEIPT"))
            with self.assertRaises(ValueError):
                inbox_health.record_bridge_verification(db, raw_receipt.id, now=NOW)
        self.assertEqual(self.view()["last_bridge_verified_at"], NOW - 100)
        self.assertEqual(self.view()["status"], "verified")

    def test_dashboard_statuses_distinguish_configuration_polling_and_old_proof(self):
        self.assertEqual(self.view()["status"], "not_checked")
        self.assertIsNone(self.view()["latest_poll_replies_ingested"])
        with patch.dict(os.environ, {"GROWTH_INBOUND_ENABLED": "false"}):
            self.assertEqual(self.view()["status"], "disabled")
        with patch.dict(os.environ, {"GROWTH_RESEND_API_KEY": ""}):
            self.assertEqual(self.view()["status"], "configuration_required")
        self.poll([])
        self.proof(NOW - 8 * 86400)
        self.assertEqual(self.view()["status"], "verification_stale")
        self.assertIn("not evidence of lost mail", self.view()["explanation"])
        self.assertEqual(self.view(NOW + 901)["status"], "poll_stale")

    def test_concurrent_out_of_order_poll_completions_keep_monotonic_projection(self):
        def write(at, failure=None):
            with self.factory() as db:
                inbox_health.record_poll(db, completed_at=at, replies_ingested=0, failure_class=failure)
                db.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda value: write(*value), [(NOW + 10, "transient"), (NOW, None)]))
        view = self.view(NOW + 10)
        self.assertEqual(view["last_poll_at"], NOW + 10)
        self.assertEqual(view["last_poll_status"], "failed")
        self.assertEqual(view["last_successful_poll_at"], NOW)
        write(NOW - 100)
        self.assertEqual(self.view()["last_successful_poll_at"], NOW)
        write(NOW + 20)
        self.assertEqual(self.view(NOW + 20)["last_poll_status"], "success")


if __name__ == "__main__":
    unittest.main()
