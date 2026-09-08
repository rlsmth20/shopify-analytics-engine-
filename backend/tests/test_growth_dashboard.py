"""Owner projections preserve receipts, cohort identity and missing evidence."""
import time
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.dashboard import dashboard, outreach_projection
from app.growth.models import Contact, FirstContact, Message, Usage
from app.growth.store import record, remember


class GrowthDashboardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.now = time.time()
        self.sent = self.now - 60

    def tearDown(self):
        self.engine.dispose()

    def contact(self, db, suffix, *, channel="shopify_community", version=2, shop_id=None, status="sent", experiment="exp-a"):
        c = Contact(identity="dashboard:" + suffix, organization="Merchant " + suffix, source="https://example.test",
            shop_id=shop_id, qualification={"qualified": True})
        db.add(c)
        db.flush()
        db.add(FirstContact(contact_id=c.id, action_key=suffix, channel=channel, experiment_id=experiment,
            cohort={"icp": "apparel", "offer": "health_check", "message_version": version}, body_hash="fixture",
            status=status, sent_at=self.sent if status == "sent" else None, reserved_at=self.sent,
            receipt="https://example.test/receipt" if status == "sent" else None))
        db.flush()
        return c

    def test_empty_projection_does_not_invent_customers_costs_or_rates(self):
        with self.factory() as db:
            db.add(Usage(key="unknown-cost", model="codex", task="review", estimated_usd=None, reserved_usd=0))
            db.flush()
            result = dashboard(db)
            self.assertEqual(result["outreach"]["cohorts"], [])
            self.assertEqual(len(result["outreach"]["activity"]), 7)
            self.assertIsNone(result["economics"]["customers"])
            self.assertIsNone(result["economics"]["mrr"])
            self.assertEqual(result["economics"]["unknown_cost_records"], 1)
            self.assertEqual(result["agent"]["first_contact_capacity"]["limit"], 20)

    def test_qualification_policy_does_not_mix_identical_message_cohorts(self):
        with self.factory() as db:
            self.contact(db, "legacy")
            c = self.contact(db, "market")
            row = db.scalar(select(FirstContact).where(FirstContact.contact_id == c.id))
            row.cohort = {**row.cohort, "qualification_policy": "market_discovery_v1"}
            db.flush()
            groups = outreach_projection(db, self.now)["cohorts"]
            self.assertEqual(len(groups), 2)
            self.assertEqual({g["qualification_policy"] for g in groups}, {"legacy", "market_discovery_v1"})

    def test_cohorts_keep_channel_offer_version_and_experiment_separate(self):
        with self.factory() as db:
            self.contact(db, "public-a")
            self.contact(db, "public-b")
            self.contact(db, "form", channel="contact_form")
            self.contact(db, "old-message", version=1)
            self.contact(db, "other-experiment", experiment="exp-b")
            c = self.contact(db, "unresolved", status="uncertain")
            projection = outreach_projection(db, self.now)
            self.assertEqual(len(projection["cohorts"]), 4)
            self.assertEqual(projection["sent"], 5)
            self.assertEqual(projection["pending"], 1)
            group = next(g for g in projection["cohorts"] if g["sent"] == 2)
            self.assertEqual(group["pending"], 1)
            self.assertEqual(group["linked_contacts"], 0)
            self.assertFalse(group["outcome_linkage_complete"])
            self.assertIsNone(group["email_delivered"])
            self.assertIsNone(group["email_bounced"])
            self.assertEqual(projection["activity"][-1]["first_contacts"], 5)
            c.suppressed = True
            db.flush()
            self.assertEqual(dashboard(db)["pipeline"]["qualified_prospects"], 5)

    def test_post_contact_verified_store_outcomes_are_distinct_and_baseline_is_separate(self):
        with self.factory() as db:
            remember(db, "strategic", "identity", {"started_at": self.sent - 60})
            self.contact(db, "one", shop_id=42)
            self.contact(db, "two", shop_id=42)
            self.contact(db, "unlinked")
            for kind in ("SIGNUP", "SHOPIFY_CONNECTION"):
                record(db, "baseline-" + kind, kind, "shop:42", {"verified": True}, occurred_at=self.sent - 86400)
            for i in range(2):
                record(db, f"analysis-{i}", "INVENTORY_ANALYSIS_VIEWED", "shop:42", {"verified": True}, occurred_at=self.now - 5)
            record(db, "fake-payment", "SUBSCRIPTION_PURCHASED", "shop:42", {"verified": False}, occurred_at=self.now - 5)
            record(db, "calculator", "CALCULATOR_USED", "visitor:1", {}, occurred_at=self.now - 5)
            with patch("app.growth.dashboard.time.time", return_value=self.now):
                result = dashboard(db)
            group = result["outreach"]["cohorts"][0]
            self.assertEqual(group["outcomes"]["SIGNUP"], 0)
            self.assertEqual(group["outcomes"]["SHOPIFY_CONNECTION"], 0)
            self.assertEqual(group["outcomes"]["INVENTORY_ANALYSIS_VIEWED"], 1)
            self.assertEqual(group["outcomes"]["SUBSCRIPTION_PURCHASED"], 0)
            self.assertEqual(group["linked_contacts"], 2)
            self.assertEqual(result["measurement"]["mission_funnel"]["SIGNUP"], 0)
            self.assertEqual(result["funnel"]["SIGNUP"], 1)
            self.assertEqual(result["mission"]["qualified_users"], 0)
            self.assertEqual(result["today"]["activations"], 1)
            self.assertEqual(result["today"]["purchases"], 0)
            self.assertEqual(result["funnel"]["SUBSCRIPTION_PURCHASED"], 0)

    def test_classification_and_daily_counts_exclude_automated_mail_and_duplicate_replies(self):
        with self.factory() as db:
            merchant = self.contact(db, "merchant")
            for index, classification in enumerate(("QUESTION", "QUESTION", "AUTOMATED", "UNKNOWN")):
                msg = Message(key=f"incoming-{index}", contact_id=merchant.id, experiment_id="exp-a", direction="in",
                    body="fixture", classification=classification, created_at=self.now - 5)
                db.add(msg)
                db.flush()
                record(db, f"reply-{index}", "REPLY_RECEIVED", merchant.id,
                    {"message_id": msg.id, "classification": "UNKNOWN", "experiment_id": "exp-a"}, occurred_at=self.now - 5)
            other = self.contact(db, "unrelated")
            record(db, "wrong-cohort", "REPLY_RECEIVED", other.id,
                {"classification": "SUBSTANTIVE_POSITIVE", "experiment_id": "exp-other"}, occurred_at=self.now - 5)
            result = outreach_projection(db, self.now)
            group = result["cohorts"][0]
            self.assertEqual(group["substantive_replies"], 1)
            self.assertEqual(group["positive_interest"], 0)
            self.assertEqual(group["substantive_reply_rate"], .5)
            self.assertEqual(result["activity"][-1]["substantive_replies"], 2)

    def test_signed_delivery_receipt_survives_replied_status_and_bounce_remains_separate(self):
        with self.factory() as db:
            merchant = self.contact(db, "mail", channel="email")
            db.add(Message(key="first-email", contact_id=merchant.id, experiment_id="exp-a", direction="out",
                body="fixture", status="replied", provider_id="provider-1", sent_at=self.sent))
            record(db, "delivered", "PROVIDER_EVENT", "mailbox", {"type": "email.delivered", "data": {"email_id": "provider-1"}},
                source="resend_signed_webhook")
            second = self.contact(db, "bounced", channel="email")
            db.add(Message(key="bounced-email", contact_id=second.id, experiment_id="exp-a", direction="out",
                body="fixture", status="bounced", provider_id="provider-2", sent_at=self.sent))
            self.contact(db, "unknown-email", channel="email")
            db.flush()
            group = outreach_projection(db, self.now)["cohorts"][0]
            self.assertEqual(group["email_delivered"], 1)
            self.assertEqual(group["email_bounced"], 1)
            self.assertEqual(group["delivery_unknown"], 1)

    def test_qualification_milestone_requires_first_verified_progress_after_mission_start(self):
        with self.factory() as db:
            remember(db, "strategic", "identity", {"started_at": self.sent})
            for kind in ("SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_VIEWED", "SUBSCRIPTION_PURCHASED"):
                record(db, "new-" + kind, kind, "shop:1", {"verified": True}, occurred_at=self.now - 10)
            record(db, "false-connected", "SHOPIFY_CONNECTION", "shop:2", {"verified": False}, occurred_at=self.now - 10)
            self.assertEqual(dashboard(db)["mission"]["qualified_users"], 1)


if __name__ == "__main__":
    unittest.main()
