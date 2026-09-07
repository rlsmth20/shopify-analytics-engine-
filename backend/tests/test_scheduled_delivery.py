"""Durable report delivery against isolated SQLite, with no provider/network calls."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, DigestSendLog, ReportScheduleRecord, ScheduledEmailDeliveryRecord, Shop
from app.services import scheduled_delivery as delivery
from app.services import transactional_email


class ScheduledDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="skubase-report-delivery-test-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "synthetic.sqlite"),
                                    connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        with self.sessions() as db:
            shop = Shop(shopify_domain="delivery-fixture.myshopify.com")
            db.add(shop)
            db.flush()
            self.shop_id = shop.id
            schedule = ReportScheduleRecord(shop_id=shop.id, report_type="actions", cadence="weekly",
                channel="email", recipient_email="ops@example.invalid", enabled=True)
            db.add(schedule)
            db.commit()
            self.schedule_id = schedule.id
        for active in [patch.object(delivery, "SessionLocal", self.sessions),
                       patch.object(delivery, "utc_now", side_effect=lambda: self.now),
                       patch.object(delivery, "shop_may_send_scheduled_report", return_value=True)]:
            active.start()
            self.addCleanup(active.stop)
        self.payload = {"from": "info@skubase.io", "to": ["ops@example.invalid"], "subject": "Synthetic report",
                        "html": "<p>Original inventory findings</p>", "text": "Original inventory findings"}
        self.build = Mock(return_value=self.payload)

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def send(self, **kwargs):
        return delivery.deliver_scheduled_email(self.schedule_id, self.build, **kwargs)

    def records(self):
        with self.sessions() as db:
            return db.scalars(select(ScheduledEmailDeliveryRecord).order_by(ScheduledEmailDeliveryRecord.created_at)).all()

    def test_definite_failure_retries_frozen_payload_with_same_key_and_one_success(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=[ConnectionRefusedError(), "provider-id"]) as sender:
            self.assertFalse(self.send())
            self.build.return_value = {**self.payload, "html": "Changed inventory data"}
            self.now += timedelta(minutes=2)
            self.assertTrue(self.send())
            self.assertFalse(self.send())
        self.assertEqual(self.build.call_count, 1)
        self.assertEqual(sender.call_args_list[0], sender.call_args_list[1])
        row = self.records()[0]
        self.assertEqual((row.status, row.attempts, row.provider_receipt), ("accepted", 2, "provider-id"))
        self.assertEqual(len(row.attempt_history), 2)
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(DigestSendLog)).all()), 1)

    def test_lost_provider_response_is_held_and_never_automatically_replayed(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=TimeoutError("private provider details")) as sender:
            self.assertFalse(self.send())
            self.now += timedelta(hours=2)
            self.assertFalse(self.send())
        self.assertEqual(sender.call_count, 1)
        row = self.records()[0]
        self.assertEqual(row.status, "unknown")
        self.assertNotIn("private", row.last_error)
        self.assertIsNone(row.accepted_at)

    def test_crash_after_committed_lease_is_unknown_without_resending(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=SystemExit("synthetic crash")):
            with self.assertRaises(SystemExit):
                self.send()
        self.now += timedelta(minutes=3)
        with self.sessions() as db:
            summary = delivery.schedule_delivery_summaries(db, [self.schedule_id])[self.schedule_id]
            self.assertEqual(summary["last_delivery_status"], "unknown")
            self.assertIsNone(summary["last_sent_at"])
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send())
            sender.assert_not_called()
        self.assertEqual(self.records()[0].status, "unknown")
        self.assertEqual(self.records()[0].attempt_history[-1]["status"], "unknown")

    def test_provider_acceptance_followed_by_commit_failure_does_not_duplicate(self):
        count = 0
        def sessions():
            nonlocal count
            count += 1
            db = self.sessions()
            if count == 2:
                db.commit = Mock(side_effect=RuntimeError("synthetic lost database connection"))
            return db
        with patch.object(delivery, "SessionLocal", sessions), \
             patch.object(delivery, "send_prepared_email_receipt", return_value="accepted-before-crash") as sender:
            with self.assertRaises(RuntimeError):
                self.send()
        self.assertEqual(sender.call_count, 1)
        self.now += timedelta(minutes=3)
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send())
            sender.assert_not_called()
        self.assertEqual(self.records()[0].status, "unknown")

    def test_coincident_workers_claim_one_delivery_before_provider_io(self):
        barrier = threading.Barrier(2)
        provider_started, release_provider = threading.Event(), threading.Event()
        def authorized(*args, **kwargs):
            barrier.wait(timeout=5)
            return True
        def accepted(*args, **kwargs):
            provider_started.set()
            if not release_provider.wait(timeout=5):
                raise RuntimeError("Synthetic test timed out")
            return "provider-id"
        with patch.object(delivery, "shop_may_send_scheduled_report", side_effect=authorized), \
             patch.object(delivery, "send_prepared_email_receipt", side_effect=accepted) as sender, \
             ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(self.send), workers.submit(self.send)]
            try:
                self.assertTrue(provider_started.wait(timeout=5))
                completed, _ = wait(futures, timeout=5, return_when=FIRST_COMPLETED)
                self.assertEqual(len(completed), 1)
                self.assertFalse(next(iter(completed)).result())
            finally:
                release_provider.set()
            self.assertEqual(sorted(future.result(timeout=5) for future in futures), [False, True])
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.build.call_count, 1)
        self.assertEqual(len(self.records()), 1)

    def test_concurrent_schedule_changes_are_refreshed_after_entitlement_work(self):
        for change in [{"enabled": False}, {"cadence": "unsupported"}, {"report_type": "weekly_buy_list", "cadence": "monthly"},
                       {"report_type": "reorder"}]:
            with self.subTest(change=change):
                with self.sessions() as db:
                    schedule = db.get(ReportScheduleRecord, self.schedule_id)
                    schedule.enabled, schedule.cadence, schedule.report_type = True, "weekly", "actions"
                    db.commit()
                def concurrent_edit(*args, **kwargs):
                    with self.sessions() as db:
                        schedule = db.get(ReportScheduleRecord, self.schedule_id)
                        for key, value in change.items():
                            setattr(schedule, key, value)
                        db.commit()
                    return True
                with patch.object(delivery, "shop_may_send_scheduled_report", side_effect=concurrent_edit), \
                     patch.object(delivery, "send_prepared_email_receipt") as sender:
                    self.assertFalse(self.send())
                    sender.assert_not_called()
        self.build.assert_not_called()
        self.assertEqual(self.records(), [])

    def test_concurrent_recipient_change_is_used_when_new_period_is_prepared(self):
        def concurrent_edit(*args, **kwargs):
            with self.sessions() as db:
                db.get(ReportScheduleRecord, self.schedule_id).recipient_email = "new@example.invalid"
                db.commit()
            return True
        self.build.side_effect = lambda db, schedule: {**self.payload, "to": [schedule.recipient_email]}
        with patch.object(delivery, "shop_may_send_scheduled_report", side_effect=concurrent_edit), \
             patch.object(delivery, "send_prepared_email_receipt", return_value="new-recipient") as sender:
            self.assertTrue(self.send())
        self.assertEqual(sender.call_args.args[0]["to"], ["new@example.invalid"])

    def test_slow_report_build_starts_a_fresh_send_lease(self):
        def slow_build(db, schedule):
            self.now += timedelta(minutes=5)
            return self.payload
        def accepted(*args, **kwargs):
            row = self.records()[0]
            self.assertEqual(delivery._utc(row.first_attempt_at), self.now)
            self.assertEqual(delivery._utc(row.lease_until), self.now + timedelta(seconds=delivery.LEASE_SECONDS))
            return "fresh-lease"
        self.build.side_effect = slow_build
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=accepted):
            self.assertTrue(self.send())

    def test_report_finishing_after_eligible_day_or_period_is_not_sent(self):
        for start, force in [(datetime(2026, 9, 7, 23, 59, tzinfo=timezone.utc), False),
                             (datetime(2026, 9, 6, 23, 59, tzinfo=timezone.utc), True)]:
            with self.subTest(start=start, force=force):
                self.now = start
                def slow_build(db, schedule):
                    self.now += timedelta(minutes=2)
                    return self.payload
                self.build.side_effect = slow_build
                with patch.object(delivery, "send_prepared_email_receipt") as sender:
                    self.assertFalse(self.send(force=force))
                    sender.assert_not_called()
                self.assertEqual(self.records(), [])

    def test_retry_after_provider_key_window_is_held_even_with_force(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=ConnectionRefusedError()) as sender:
            self.assertFalse(self.send())
            self.now += timedelta(hours=24)
            self.assertFalse(self.send(force=True))
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.records()[0].status, "unknown")
        self.assertIn("retry window", self.records()[0].last_error)

    def test_retries_are_bounded_and_new_calendar_period_has_a_new_identity(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=ConnectionRefusedError()) as sender:
            for _ in range(6):
                self.send()
                self.now += timedelta(minutes=10)
        self.assertEqual(sender.call_count, 3)
        self.assertIsNone(self.records()[0].next_attempt_at)
        self.assertIn("retry limit", self.records()[0].last_error)
        self.now += timedelta(days=7)
        with patch.object(delivery, "send_prepared_email_receipt", return_value="next-period") as sender:
            self.assertTrue(self.send())
        self.assertEqual(len(self.records()), 2)
        self.assertNotEqual(self.records()[0].id, self.records()[1].id)
        self.assertNotEqual(self.records()[0].period_key, self.records()[1].period_key)

    def test_missing_provider_configuration_does_not_exhaust_actual_send_attempts(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=transactional_email.EmailProviderUnavailable()) as sender:
            for _ in range(4):
                self.assertFalse(self.send())
                self.now += timedelta(minutes=15)
        row = self.records()[0]
        self.assertEqual((row.attempts, row.status), (0, "unavailable"))
        self.assertIsNone(row.first_attempt_at)
        with patch.object(delivery, "send_prepared_email_receipt", return_value="configured-now"):
            self.assertTrue(self.send())

    def test_recipient_change_never_replays_old_payload_to_a_different_destination(self):
        with patch.object(delivery, "send_prepared_email_receipt", side_effect=ConnectionRefusedError()):
            self.assertFalse(self.send())
        with self.sessions() as db:
            db.get(ReportScheduleRecord, self.schedule_id).recipient_email = "new@example.invalid"
            db.commit()
        self.now += timedelta(minutes=5)
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send())
            sender.assert_not_called()
        self.assertIn("recipient changed", self.records()[0].last_error)

    def test_legacy_success_stops_resends_in_same_calendar_period(self):
        with self.sessions() as db:
            db.add(DigestSendLog(shop_id=self.shop_id, digest_type="report_actions",
                                recipient_email="ops@example.invalid", sent_at=self.now))
            db.commit()
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send())
            sender.assert_not_called()
        self.build.assert_not_called()

    def test_only_due_enabled_schedules_run_and_monthly_period_is_calendar_based(self):
        self.now += timedelta(days=1)
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send())
            sender.assert_not_called()
        self.assertEqual(delivery.calendar_period("monthly", self.now)[0], "monthly:2026-09")
        self.assertEqual(delivery.calendar_period("weekly", self.now)[0], "weekly:2026-09-07")
        with self.sessions() as db:
            db.get(ReportScheduleRecord, self.schedule_id).enabled = False
            db.commit()
        with patch.object(delivery, "send_prepared_email_receipt") as sender:
            self.assertFalse(self.send(force=True))
            sender.assert_not_called()


class PreparedEmailTests(unittest.TestCase):
    def test_frozen_parameters_escape_inventory_content_and_require_a_real_receipt(self):
        params = transactional_email.build_scheduled_report_email_params(email="ops@example.invalid",
            title="<report>", intro="<script>untrusted</script>", headers=["<SKU>"],
            rows=[["<img src=x>"]], cta_path="/reports", cadence="weekly")
        self.assertNotIn("<script>", params["html"])
        self.assertNotIn("<img src=x>", params["html"])
        self.assertIn("&lt;img src=x&gt;", params["html"])
        client = Mock()
        client.Emails.send.return_value = {"id": "receipt"}
        with patch.object(transactional_email, "_client", return_value=client):
            self.assertEqual(transactional_email.send_prepared_email_receipt(params, idempotency_key="stable-key"), "receipt")
            self.assertEqual(client.Emails.send.call_args.args[1], {"idempotency_key": "stable-key"})
            client.Emails.send.return_value = {}
            with self.assertRaises(RuntimeError):
                transactional_email.send_prepared_email_receipt(params, idempotency_key="stable-key")


if __name__ == "__main__":
    unittest.main()
