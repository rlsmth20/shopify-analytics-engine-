"""Schedule authorization and retry tests use synthetic storage and mocked sends only."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import require_active_access
from app.api.routes.report_schedules import router
from app.db.models import Base, DigestSendLog, ReportScheduleRecord, Shop, User
from app.db.session import get_db_session
from app.schemas_v2 import ReorderSuggestion
from app.services import billing, report_schedule_access, scheduled_delivery, scheduled_reports, weekly_digest


class ReportScheduleAccessTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.now = datetime.now(timezone.utc)
        self.delivery_sessions = patch.object(scheduled_delivery, "SessionLocal", self.sessions)
        self.delivery_sessions.start()
        self.addCleanup(self.delivery_sessions.stop)
        self.delivery_clock = patch.object(scheduled_delivery, "utc_now", side_effect=lambda: self.now)
        self.delivery_clock.start()
        self.addCleanup(self.delivery_clock.stop)
        with self.sessions() as db:
            shop = Shop(shopify_domain="schedule-fixture.myshopify.com")
            db.add(shop)
            db.flush()
            self.user = User(shop_id=shop.id, email="merchant@example.com", is_admin=False,
                             trial_ends_at=self.now - timedelta(days=5))
            db.add(self.user)
            db.commit()
            self.shop_id = shop.id
        self.raw = {"plan": "scale_monthly", "status": "active", "shopify_installed": False,
                    "billing_provider": "stripe", "current_period_end": (self.now + timedelta(days=20)).isoformat()}
        self.billing_patch = patch.object(billing, "current_subscription_summary", side_effect=lambda *args, **kwargs: dict(self.raw))
        self.billing_patch.start()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[require_active_access] = lambda: self.user
        def session():
            with self.sessions() as db:
                yield db
        self.app.dependency_overrides[get_db_session] = session
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.billing_patch.stop()
        self.engine.dispose()

    def payload(self, **changes):
        return {"report_type": "actions", "cadence": "weekly", "channel": "email",
                "recipient_email": "ops@example.com", "enabled": True, **changes}

    def schedule(self, report_type="actions", **changes):
        with self.sessions() as db:
            db.add(ReportScheduleRecord(shop_id=self.shop_id, report_type=report_type,
                                       cadence="weekly", channel=changes.get("channel", "email"),
                                       recipient_email="ops@example.com", enabled=changes.get("enabled", True)))
            db.commit()

    def logs(self):
        with self.sessions() as db:
            return db.scalar(select(func.count()).select_from(DigestSendLog))

    def test_starter_and_growth_cannot_enable_or_list_scale_email_schedules(self):
        for plan in ["starter_monthly", "growth_monthly"]:
            with self.subTest(plan=plan):
                self.raw["plan"] = plan
                self.assertEqual(self.client.get("/reports/schedules").status_code, 403)
                response = self.client.post("/reports/schedules", json=self.payload())
                self.assertEqual(response.status_code, 403)
                self.assertIn("Scale", response.json()["detail"])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ReportScheduleRecord)), 0)

    def test_weekly_buy_list_can_be_saved_and_arbitrary_types_and_bad_recipients_are_rejected(self):
        response = self.client.post("/reports/schedules", json=self.payload(report_type="weekly_buy_list", recipient_email="  ops@example.com  "))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recipient_email"], "ops@example.com")
        self.assertEqual(self.client.get("/reports/schedules").json()["schedules"][0]["report_type"], "weekly_buy_list")
        invalid = [self.payload(report_type="unsupported"), self.payload(report_type="weekly_buy_list", cadence="monthly"),
                   self.payload(recipient_email="not-email"), self.payload(recipient_email="ops@example.com\nBcc: another@example.com")]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/reports/schedules", json=payload).status_code, 422)

    def test_inactive_stale_or_unverified_billing_never_enables_schedules(self):
        cases = [({"status": "canceled"}, 402),
                 ({"current_period_end": (self.now - timedelta(days=4)).isoformat()}, 402),
                 ({"current_period_end": "unparseable"}, 503),
                 ({"shopify_installed": True, "billing_status_error": "shopify_unauthorized"}, 503)]
        original = dict(self.raw)
        for changes, expected in cases:
            with self.subTest(changes=changes):
                self.raw = {**original, **changes}
                self.assertEqual(self.client.post("/reports/schedules", json=self.payload()).status_code, expected)

    def test_direct_trial_remains_allowed_and_shopify_starter_trial_does_not_gain_scale_access(self):
        self.user.trial_ends_at = self.now + timedelta(days=2)
        self.raw.update(plan="none", status="inactive", current_period_end=(self.now - timedelta(days=20)).isoformat())
        self.assertEqual(self.client.post("/reports/schedules", json=self.payload()).status_code, 200)
        self.raw.update(plan="starter_monthly", status="trialing", shopify_installed=True,
                        current_period_end=(self.now + timedelta(days=10)).isoformat())
        self.assertEqual(self.client.post("/reports/schedules", json=self.payload()).status_code, 403)

    def test_per_report_capability_is_checked_even_with_schedule_capability(self):
        summary = {"billing_status_loaded": True, "subscription_status": "active", "plan_id": "scale",
                   "capabilities": ["scheduled_reports", "action_queue_basic"]}
        with self.sessions() as db, patch.object(report_schedule_access, "current_entitlements_summary", return_value=summary):
            self.assertIsNone(report_schedule_access.report_schedule_access_error(db, self.user, "actions"))
            self.assertEqual(report_schedule_access.report_schedule_access_error(db, self.user, "reorder")[0], 403)
            self.assertEqual(report_schedule_access.report_schedule_access_error(db, self.user, "weekly_buy_list")[0], 403)
            self.assertEqual(report_schedule_access.report_schedule_access_error(db, self.user, "unknown")[0], 422)

    def test_saved_report_is_not_sent_after_downgrade_or_cancellation_even_when_forced(self):
        self.schedule()
        with patch.object(scheduled_reports, "SessionLocal", self.sessions), \
             patch.object(scheduled_reports, "build_report_email") as build, \
             patch.object(scheduled_delivery, "send_prepared_email_receipt") as send:
            for plan, status in [("starter_monthly", "active"), ("scale_monthly", "canceled")]:
                self.raw.update(plan=plan, status=status)
                self.assertEqual(scheduled_reports.run_scheduled_reports_once(force=True), 0)
            build.assert_not_called()
            send.assert_not_called()
        self.assertEqual(self.logs(), 0)

    def test_failed_report_delivery_can_retry_but_success_is_durable_and_deduplicated(self):
        self.schedule()
        built = ("Inventory Action Report", "Synthetic findings", ["SKU"], [["shirt"]], "/actions")
        with patch.object(scheduled_reports, "SessionLocal", self.sessions), \
             patch.object(scheduled_reports, "build_report_email", return_value=built), \
             patch.object(scheduled_delivery, "send_prepared_email_receipt", side_effect=[ConnectionRefusedError(), "fixture-accepted"]) as send:
            self.assertEqual(scheduled_reports.run_scheduled_reports_once(force=True), 0)
            self.assertEqual(self.logs(), 0)
            self.now += timedelta(minutes=2)
            self.assertEqual(scheduled_reports.run_scheduled_reports_once(force=True), 1)
            self.assertEqual(self.logs(), 1)
            self.assertEqual(scheduled_reports.run_scheduled_reports_once(force=True), 0)
            self.assertEqual(send.call_count, 2)

    def test_weekly_digest_checks_entitlements_before_building_or_sending(self):
        self.schedule("weekly_buy_list")
        self.raw["plan"] = "growth_monthly"
        with patch.object(weekly_digest, "SessionLocal", self.sessions), \
             patch.object(weekly_digest, "build_buy_list") as build, \
             patch.object(scheduled_delivery, "send_prepared_email_receipt") as send:
            self.assertEqual(weekly_digest.run_weekly_digests_once(force=True), 0)
            build.assert_not_called()
            send.assert_not_called()
        self.assertEqual(self.logs(), 0)

    def test_weekly_digest_failed_delivery_retries_then_records_one_success(self):
        self.schedule("weekly_buy_list")
        item = ReorderSuggestion(sku_id="shirt", name="Shirt", vendor="Fixture", current_on_hand=1,
            lead_time_days=14, safety_stock=1, order_up_to=30, economic_order_qty=29, service_level_target=0.95,
            reorder_point=15, recommended_order_qty=29, unit_cost=2,
            extended_cost=58, landed_extended_cost=58, landed_unit_cost=2, freight_share_pct=0,
            expected_stockout_prob=0.8, rationale="Synthetic test")
        with patch.object(weekly_digest, "SessionLocal", self.sessions), \
             patch.object(weekly_digest, "build_buy_list", return_value=([item], 58, {"Fixture": 58})), \
             patch.object(scheduled_delivery, "send_prepared_email_receipt", side_effect=[ConnectionRefusedError(), "fixture-accepted"]) as send:
            self.assertEqual(weekly_digest.run_weekly_digests_once(force=True), 0)
            self.assertEqual(self.logs(), 0)
            self.now += timedelta(minutes=2)
            self.assertEqual(weekly_digest.run_weekly_digests_once(force=True), 1)
            self.assertEqual(weekly_digest.run_weekly_digests_once(force=True), 0)
            self.assertEqual(send.call_count, 2)
        self.assertEqual(self.logs(), 1)

    def test_non_email_weekly_schedule_does_not_send(self):
        self.schedule("weekly_buy_list", channel="slack")
        with patch.object(weekly_digest, "SessionLocal", self.sessions), patch.object(scheduled_delivery, "send_prepared_email_receipt") as send:
            self.assertEqual(weekly_digest.run_weekly_digests_once(force=True), 0)
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
