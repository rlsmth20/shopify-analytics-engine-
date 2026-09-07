"""Inventory alert setup and durable delivery tests. No real provider calls."""
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker

from app.api.routes import alerts as alert_routes
from app.db.models import Base, Shop, User, AlertRuleRecord, NotificationChannelRecord, AlertEventRecord, AlertDeliveryAttemptRecord, AuditLogRecord
from app.schemas import SkuDetail
from app.schemas_v2 import TestAlertRequest
from app.services import alert_delivery, alert_evaluation, alert_scheduler, alerts, notifications, transactional_email
from app.services.inventory_engine import build_inventory_actions
from app.services.notification_targets import NotificationHttpError, post_public_json, validate_target


def delivery(channel, *, status="accepted"):
    return notifications.DeliveryRecord(channel=channel, target="unused", subject="Fixture", body="Fixture",
        delivered=status == "accepted", status=status, error=None if status == "accepted" else "Fixture provider failure",
        provider_receipt="fixture-receipt" if status == "accepted" else None)


class DurableAlertTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        for module in [alerts, alert_delivery]:
            active_patch = patch.object(module, "SessionLocal", self.sessions)
            active_patch.start()
            self.addCleanup(active_patch.stop)
        self.now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        with self.sessions() as db:
            shop = Shop(shopify_domain="alert-fixture.myshopify.com")
            db.add(shop)
            db.flush()
            self.shop_id = shop.id
            user = User(shop_id=shop.id, email="fixture@example.invalid", is_admin=True)
            db.add(user)
            db.flush()
            self.user_id = user.id
            db.add(AlertRuleRecord(id="fixture-rule", shop_id=shop.id, name="Low stock", trigger="stockout_risk",
                                  severity="warning", channels=["email", "slack"], threshold=3, enabled=True))
            db.add_all([NotificationChannelRecord(channel=f"{shop.id}:email", target="fixture@example.invalid", enabled=True, verified=False),
                        NotificationChannelRecord(channel=f"{shop.id}:slack", target="https://hooks.slack.com/services/fixture/secret/token", enabled=True, verified=False)])
            db.commit()
        self.rule = alerts.list_rules(self.shop_id)[0]

    def tearDown(self):
        self.engine.dispose()

    def fire(self, *, now=None, sku_id="SKU-A"):
        with patch.object(alert_delivery, "utc_now", return_value=now or self.now):
            return alert_delivery.dispatch_alert(rule=self.rule, sku_id=sku_id, sku_name=sku_id,
                message="Fixture stockout warning", now=now or self.now, allowed_channels={"email", "slack"}, cooldown_seconds=21600)

    def test_partial_failure_retries_only_failed_channel_and_survives_new_sessions(self):
        def provider(**kwargs):
            return delivery(kwargs["channel"], status="failed" if kwargs["channel"] == "slack" else "accepted")
        with patch.object(alert_delivery, "deliver", side_effect=provider) as send:
            first = self.fire()
        self.assertEqual(first.delivery_status, "partial")
        self.assertEqual(first.channels_sent, ["email"])
        self.assertEqual(send.call_count, 2)
        self.assertEqual(alerts.list_recent_events(self.shop_id)[0].id, first.id)
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])) as send:
            second = self.fire(now=self.now + timedelta(minutes=2))
            self.assertEqual([call.kwargs["channel"] for call in send.call_args_list], ["slack"])
            self.assertEqual(second.delivery_status, "accepted")
            self.assertIsNone(self.fire(now=self.now + timedelta(minutes=15)))
        with self.sessions() as db:
            rows = db.scalars(select(AlertDeliveryAttemptRecord)).all()
            self.assertEqual({row.channel: row.attempts for row in rows}, {"email": 1, "slack": 2})
            self.assertEqual(len(db.scalars(select(AlertEventRecord)).all()), 1)
            self.assertNotIn("/services/fixture", json.dumps([row.attempt_history for row in rows]))

    def test_new_sku_does_not_wait_for_other_sku_rule_cooldown(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])) as send:
            self.fire()
            self.fire(now=self.now + timedelta(seconds=10), sku_id="SKU-B")
        self.assertEqual(send.call_count, 4)

    def test_migration_preserves_existing_cooldown_before_first_ledger_receipt(self):
        with self.sessions() as db:
            db.get(AlertRuleRecord, self.rule.id).last_fired_at = self.now
            db.commit()
        with patch.object(alert_delivery, "deliver") as send:
            self.assertIsNone(self.fire(now=self.now + timedelta(minutes=5)))
            send.assert_not_called()

    def test_failed_attempts_are_bounded_and_do_not_claim_delivered_or_last_fired(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"], status="failed")) as send:
            for minutes in [0, 1, 3, 10, 30]:
                self.fire(now=self.now + timedelta(minutes=minutes))
        self.assertEqual(send.call_count, 6)  # three attempts per channel, not per scheduler wake
        with self.sessions() as db:
            self.assertIsNone(db.get(AlertRuleRecord, self.rule.id).last_fired_at)
        self.assertFalse(alerts.list_recent_events(self.shop_id)[0].delivered)

    def test_crash_after_committed_lease_is_unknown_and_never_silently_resent(self):
        with patch.object(alert_delivery, "deliver", side_effect=SystemExit("fixture crash")):
            with self.assertRaises(SystemExit):
                self.fire()
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])) as send:
            result = self.fire(now=self.now + timedelta(hours=7))
            self.assertEqual([call.kwargs["channel"] for call in send.call_args_list], ["slack"])
            self.assertEqual(result.delivery_status, "partial")
            self.assertIn("email", result.delivery_errors)
            self.assertIsNone(self.fire(now=self.now + timedelta(hours=8)))

    def test_disabled_destination_and_unconfigured_channels_never_send(self):
        with self.sessions() as db:
            for row in db.scalars(select(NotificationChannelRecord)).all():
                row.enabled = False
            db.commit()
        with patch.object(alert_delivery, "deliver") as send:
            self.assertIsNone(self.fire())
            send.assert_not_called()

    def test_preview_is_not_delivery_and_does_not_persist_history(self):
        event = alerts._fire(self.rule, "SKU-A", "Fixture", "Preview", self.now, False, {}, None)
        self.assertEqual((event.preview, event.delivered, event.delivery_status), (True, False, "preview"))
        self.assertEqual(alerts.list_recent_events(self.shop_id), [])

    def test_saved_target_test_is_persisted_and_target_change_or_failed_retest_resets(self):
        target = "fixture@example.invalid"
        self.assertTrue(alerts.record_channel_test(shop_id=self.shop_id, channel="email", target=target, delivery=delivery("email")))
        self.assertTrue(next(c for c in alerts.list_channel_configs(self.shop_id) if c.channel == "email").verified)
        self.assertFalse(alerts.record_channel_test(shop_id=self.shop_id, channel="email", target=target, delivery=delivery("email", status="failed")))
        self.assertFalse(next(c for c in alerts.list_channel_configs(self.shop_id) if c.channel == "email").verified)
        alerts.record_channel_test(shop_id=self.shop_id, channel="email", target=target, delivery=delivery("email"))
        changed = alerts.update_channel_config(shop_id=self.shop_id, channel="email", target="new@example.invalid", enabled=True)
        self.assertFalse(changed.verified)
        self.assertFalse(alerts.record_channel_test(shop_id=self.shop_id, channel="email", target=target, delivery=delivery("email")))

    def test_category_and_vendor_scope_receive_actual_sku_metadata(self):
        product = SkuDetail(sku_id="SKU-A", name="Fixture", vendor="Supplier", category="Apparel", price=20, cost=10,
                            inventory=0, last_30_day_sales=30, last_7_day_sales=7, days_since_last_sale=1)
        context = alerts.EvaluationContext(build_inventory_actions([product]), [], [],
                            sku_metadata={"SKU-A": {"vendor": "Supplier", "category": "Apparel", "name": "Fixture"}})
        scoped = self.rule.model_copy(update={"scope": "custom", "suppliers": ["Supplier"], "categories": ["Apparel"]})
        self.assertEqual(len(alerts._evaluate_rule(scoped, context, self.now, False, {}, None)), 1)
        scoped = scoped.model_copy(update={"suppliers": ["Wrong supplier"]})
        self.assertEqual(alerts._evaluate_rule(scoped, context, self.now, False, {}, None), [])

    def test_history_is_tenant_scoped(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])):
            self.fire()
        self.assertTrue(alerts.list_recent_events(self.shop_id))
        self.assertEqual(alerts.list_recent_events(self.shop_id + 1), [])

    def test_uncertain_retry_requires_acknowledgment_owner_and_never_replays_accepted_channel(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"],
                status="unknown" if kwargs["channel"] == "slack" else "accepted")):
            first = self.fire()
        self.assertEqual(first.uncertain_channels, ["slack"])
        args = dict(shop_id=self.shop_id, user_id=self.user_id, event_id=first.id, channel="slack")
        with self.assertRaises(ValueError):
            alert_delivery.queue_uncertain_retry(**args, acknowledge_possible_duplicate=False)
        with self.assertRaises(LookupError):
            alert_delivery.queue_uncertain_retry(**{**args, "shop_id": self.shop_id + 1}, acknowledge_possible_duplicate=True)
        with self.assertRaises(ValueError):
            alert_delivery.queue_uncertain_retry(**{**args, "channel": "email"}, acknowledge_possible_duplicate=True)
        with patch.object(alert_delivery, "deliver") as send:
            alert_delivery.queue_uncertain_retry(**args, acknowledge_possible_duplicate=True)
            send.assert_not_called()  # Durable queue; the next fresh matching evaluation sends.
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])) as send:
            result = self.fire(now=self.now + timedelta(minutes=3))
        self.assertEqual(result.delivery_status, "accepted")
        self.assertEqual([call.kwargs["channel"] for call in send.call_args_list], ["slack"])
        with self.sessions() as db:
            audit = db.scalar(select(AuditLogRecord).where(AuditLogRecord.event_type == "alert_retry_requested"))
            self.assertEqual((audit.shop_id, audit.user_id), (self.shop_id, self.user_id))

    def test_resolved_unknown_incident_does_not_block_a_new_inventory_problem(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"], status="unknown")):
            first = self.fire()
        alert_delivery.resolve_absent_incidents(self.shop_id, self.rule.id, set(), self.now + timedelta(minutes=1))
        self.assertTrue(alerts.list_recent_events(self.shop_id)[0].resolved)
        with self.assertRaises(ValueError):
            alert_delivery.queue_uncertain_retry(shop_id=self.shop_id, user_id=self.user_id, event_id=first.id,
                                                  channel="email", acknowledge_possible_duplicate=True)
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"])) as send:
            fresh = self.fire(now=self.now + timedelta(minutes=2))
        self.assertNotEqual(first.id, fresh.id)
        self.assertEqual(send.call_count, 2)

    def test_each_claim_and_completion_uses_a_fresh_clock_after_slow_prior_work(self):
        clock_values = [self.now, self.now + timedelta(minutes=5), self.now + timedelta(minutes=6),
                        self.now + timedelta(minutes=7), self.now + timedelta(minutes=8)]
        def provider(**kwargs):
            with self.sessions() as db:
                row = db.scalar(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.channel == kwargs["channel"]))
                self.assertGreater(alert_delivery._utc(row.lease_until), self.now + timedelta(minutes=5))
            return delivery(kwargs["channel"])
        with patch.object(alert_delivery, "utc_now", side_effect=clock_values), patch.object(alert_delivery, "deliver", side_effect=provider):
            alert_delivery.dispatch_alert(rule=self.rule, sku_id="SKU-A", sku_name="Fixture", message="Fixture",
                now=self.now - timedelta(minutes=10), allowed_channels={"email", "slack"}, cooldown_seconds=21600)
        with self.sessions() as db:
            accepted = sorted(alert_delivery._utc(row.accepted_at) for row in db.scalars(select(AlertDeliveryAttemptRecord)).all())
        self.assertEqual(accepted, [self.now + timedelta(minutes=6), self.now + timedelta(minutes=8)])

    def test_no_enabled_destination_skips_forecast_work_but_preserves_preview(self):
        with self.sessions() as db:
            for row in db.scalars(select(NotificationChannelRecord)).all():
                row.enabled = False
            db.commit()
            user = db.get(User, self.user_id)
            with patch.object(alert_evaluation, "seed_default_rules_and_channels"), \
                 patch.object(alert_evaluation, "allowed_alert_channels", return_value={"email", "slack"}), \
                 patch.object(alert_evaluation, "build_evaluation_context", return_value=None) as build:
                self.assertEqual(alert_evaluation.evaluate_shop_alerts(db, user, dry_run=False), [])
                build.assert_not_called()
                alert_evaluation.evaluate_shop_alerts(db, user, dry_run=True)
                build.assert_called_once()

    def test_unsupported_new_scopes_are_rejected_and_legacy_seed_rename_preserves_threshold(self):
        for field in ["tags", "collections", "locations"]:
            with self.assertRaises(ValueError):
                alerts.validate_rule_configuration(trigger="stockout_risk", **{field: ["Fixture"]})
        with self.sessions() as db:
            rule = db.get(AlertRuleRecord, self.rule.id)
            rule.name, rule.trigger, rule.threshold = "Forecast miss > 20%", "forecast_miss", 20
            db.commit()
        alerts.seed_default_rules_and_channels(self.shop_id)
        changed = alerts.list_rules(self.shop_id)[0]
        self.assertEqual((changed.name, changed.threshold), ("High stockout probability", 20))

    def test_deleted_rules_are_not_silently_recreated_when_channels_remain(self):
        with self.sessions() as db:
            db.execute(delete(AlertRuleRecord))
            db.commit()
        alerts.seed_default_rules_and_channels(self.shop_id)
        self.assertEqual(alerts.list_rules(self.shop_id), [])

    def test_old_evaluation_cannot_resolve_a_newer_incident(self):
        with patch.object(alert_delivery, "deliver", side_effect=lambda **kwargs: delivery(kwargs["channel"], status="unknown")):
            event = self.fire(now=self.now + timedelta(minutes=5))
        alert_delivery.resolve_absent_incidents(self.shop_id, self.rule.id, set(), self.now)
        self.assertFalse(alerts.list_recent_events(self.shop_id)[0].resolved)
        with patch.object(alert_delivery, "deliver") as send:
            self.assertIsNone(self.fire(now=self.now + timedelta(hours=7)))
            send.assert_not_called()
        self.assertEqual(alerts.list_recent_events(self.shop_id)[0].id, event.id)

    def test_resolved_incident_cannot_claim_a_pending_delivery(self):
        with patch.object(alert_delivery, "_attempt", return_value=False):
            self.fire()
        alert_delivery.resolve_absent_incidents(self.shop_id, self.rule.id, set(), self.now + timedelta(minutes=1))
        with self.sessions() as db:
            delivery_id = db.scalar(select(AlertDeliveryAttemptRecord.id))
        with patch.object(alert_delivery, "deliver") as send:
            self.assertFalse(alert_delivery._attempt(delivery_id))
            send.assert_not_called()
        with self.sessions() as db:
            self.assertEqual(db.get(AlertDeliveryAttemptRecord, delivery_id).attempts, 0)

    def test_old_destination_test_cannot_verify_edited_destination(self):
        alerts.update_channel_config(shop_id=self.shop_id, channel="email", enabled=True, target="new@example.invalid")
        self.assertFalse(alerts.record_channel_test(shop_id=self.shop_id, channel="email", target="fixture@example.invalid",
                                                   delivery=delivery("email"), user_id=self.user_id))
        with self.sessions() as db:
            config = db.get(NotificationChannelRecord, f"{self.shop_id}:email")
            self.assertEqual(config.target, "new@example.invalid")
            self.assertFalse(config.verified)

    def test_stale_worker_cannot_overwrite_an_acknowledged_retry_receipt(self):
        def delayed_original(**kwargs):
            with patch.object(alert_delivery, "deliver", side_effect=lambda **inner: delivery(inner["channel"])):
                self.fire(now=self.now + timedelta(minutes=3))
                alert_delivery.queue_uncertain_retry(shop_id=self.shop_id, user_id=self.user_id,
                    event_id=alerts.list_recent_events(self.shop_id)[0].id, channel="email",
                    acknowledge_possible_duplicate=True)
                fresh = self.fire(now=self.now + timedelta(minutes=4))
            self.assertEqual(fresh.delivery_status, "accepted")
            return delivery(kwargs["channel"], status="unknown")
        with patch.object(alert_delivery, "deliver", side_effect=delayed_original):
            self.fire()
        event = alerts.list_recent_events(self.shop_id)[0]
        self.assertEqual(event.delivery_status, "accepted")
        self.assertEqual(event.uncertain_channels, [])
        with self.sessions() as db:
            email = db.scalar(select(AlertDeliveryAttemptRecord).where(AlertDeliveryAttemptRecord.channel == "email"))
            self.assertEqual(email.provider_receipt, "fixture-receipt")
            self.assertEqual(email.attempt_history[-1]["status"], "accepted")


class ConcurrentSeedTests(unittest.TestCase):
    def test_simultaneous_initial_reads_seed_one_default_set(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine("sqlite:///" + os.path.join(directory, "alerts.db"))
            sessions = sessionmaker(engine, expire_on_commit=False)
            Base.metadata.create_all(engine)
            with sessions() as db:
                shop = Shop(shopify_domain="concurrent-alert-fixture.myshopify.com")
                db.add(shop)
                db.commit()
                shop_id = shop.id
            barrier = threading.Barrier(2)
            def seed():
                barrier.wait(timeout=5)
                alerts.seed_default_rules_and_channels(shop_id)
            try:
                with patch.object(alerts, "SessionLocal", sessions), ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(seed) for _ in range(2)]
                    for future in futures:
                        future.result(timeout=10)
                with sessions() as db:
                    self.assertEqual(len(db.scalars(select(AlertRuleRecord)).all()), 5)
                    self.assertEqual(len(db.scalars(select(NotificationChannelRecord)).all()), 4)
            finally:
                engine.dispose()


class ChannelDriverTests(unittest.TestCase):
    def test_promised_channel_readiness_and_sms_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(notifications.channel_availability("email")[0])
            self.assertFalse(notifications.channel_availability("sms")[0])
            self.assertTrue(notifications.channel_availability("slack")[0])
        with patch.dict(os.environ, {"RESEND_API_KEY": "fixture-only"}, clear=True):
            self.assertTrue(notifications.channel_availability("email")[0])
        with patch.object(notifications, "post_public_json") as post:
            result = notifications.deliver(channel="sms", target="+15550000000", subject="Fixture", body="Fixture")
            self.assertEqual((result.delivered, result.status), (False, "unavailable"))
            post.assert_not_called()

    def test_public_destinations_only_and_no_internal_network_request(self):
        for channel, target in [("webhook", "http://example.com"), ("webhook", "https://127.0.0.1"),
                                ("webhook", "https://169.254.169.254"), ("webhook", "https://user:pass@example.com"),
                                ("slack", "https://example.com/services/token"), ("email", "shopify-admin+1@skubase.io"),
                                ("email", "owner;other@shop.test"), ("email", "owner,other@shop.test")]:
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    validate_target(channel, target)
        with patch("app.services.notification_targets.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]), \
             patch("app.services.notification_targets.socket.create_connection") as connect:
            with self.assertRaises(ValueError):
                post_public_json("https://example.com/hook", {})
            connect.assert_not_called()

    def test_http_rejection_retryable_but_lost_response_unknown_and_no_secret_error(self):
        for failure, expected in [(NotificationHttpError(503), "failed"), (NotificationHttpError(403), "unavailable"),
                                   (TimeoutError("secret-url-token"), "unknown"),
                                   (ConnectionResetError("secret-url-token"), "unknown"),
                                   (BrokenPipeError("secret-url-token"), "unknown")]:
            with patch.object(notifications, "post_public_json", side_effect=failure):
                result = notifications.deliver(channel="slack", target="https://hooks.slack.com/services/fixture/secret/token",
                                               subject="Fixture", body="Fixture")
            self.assertEqual(result.status, expected)
            self.assertFalse(result.delivered)
            self.assertNotIn("secret", result.error)

    def test_email_returns_real_provider_receipt_and_stable_idempotency_key(self):
        client = Mock()
        client.Emails.send.return_value = {"id": "fixture-accepted"}
        with patch.object(transactional_email, "_client", return_value=client):
            receipt = transactional_email.send_alert_email_receipt(to="fixture@example.invalid", subject="<alert>",
                        body="<script>untrusted catalog name</script>", idempotency_key="alert-fixture")
        self.assertEqual(receipt, "fixture-accepted")
        self.assertEqual(client.Emails.send.call_args.args[1], {"idempotency_key": "alert-fixture"})
        self.assertNotIn("<script>", client.Emails.send.call_args.args[0]["html"])

    def test_installed_resend_exception_codes_distinguish_rejection_from_lost_response(self):
        from resend.exceptions import ResendError
        for code, error_type, expected in [("429", "rate_limit_exceeded", "failed"),
                                          ("403", "invalid_api_key", "unavailable"),
                                          (500, "HttpClientError", "unknown")]:
            failure = ResendError(code=code, error_type=error_type, message="sensitive provider detail", suggested_action="")
            with patch.dict(os.environ, {"RESEND_API_KEY": "fixture-only"}, clear=True), \
                 patch.object(transactional_email, "send_alert_email_receipt", side_effect=failure):
                record = notifications.deliver(channel="email", target="fixture@example.invalid", subject="Fixture", body="Fixture")
            self.assertEqual(record.status, expected)
            self.assertNotIn("sensitive", record.error)

    def test_daily_jobs_revisit_failed_email_sends_without_repeating_snapshot(self):
        with patch.object(alert_scheduler, "_last_snapshot_date", None), \
             patch.object(alert_scheduler, "capture_all_inventory_snapshots", return_value=1) as snapshot, \
             patch.object(alert_scheduler, "run_weekly_digests_once", return_value=0) as weekly, \
             patch.object(alert_scheduler, "run_scheduled_reports_once", return_value=0) as reports:
            alert_scheduler._run_daily_jobs()
            alert_scheduler._run_daily_jobs()
        self.assertEqual(snapshot.call_count, 1)
        self.assertEqual((weekly.call_count, reports.call_count), (2, 2))

    def test_scheduler_rolls_back_failed_shop_and_continues_next_shop(self):
        db = Mock()
        db.scalars.return_value.all.return_value = [SimpleNamespace(shop_id=1), SimpleNamespace(shop_id=2)]
        session = Mock()
        session.__enter__ = Mock(return_value=db)
        session.__exit__ = Mock(return_value=False)
        def evaluate(_db, user, **kwargs):
            if user.shop_id == 1:
                raise RuntimeError("Fixture evaluation failed")
            db.rollback.assert_called_once()
            return [SimpleNamespace(id="fixture-event")]
        with patch.object(alert_scheduler, "SessionLocal", return_value=session), \
             patch.object(alert_scheduler, "has_enabled_delivery_route", return_value=True), \
             patch.object(alert_scheduler, "user_has_active_access", return_value=True), \
             patch.object(alert_scheduler, "evaluate_shop_alerts", side_effect=evaluate), \
             self.assertLogs(alert_scheduler.logger, level="ERROR"):
            self.assertEqual(alert_scheduler.run_alert_evaluation_once(cooldown_seconds=21600), 1)
        db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
