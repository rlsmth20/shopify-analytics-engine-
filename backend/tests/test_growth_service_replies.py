"""Requested analysis fulfills a real request without requiring an app install."""
import time
import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Base
from app.growth.models import Contact, Evidence, Experiment, Message
from app.growth.policy import GrowthError
from app.growth.service_replies import (
    APP_REVIEW_DISCLOSURE, HEALTH_CHECK_SOURCES, HEALTH_CHECK_URL, SERVICE_TEMPLATE_REVISION,
    answer_request, draft_requested_check, validate_permit,
)
from app.growth.skills import bootstrap_skills
from app.growth.store import record


class RequestedServiceReplyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        bootstrap_skills(self.db)
        self.contact = Contact(identity="requested:fixture", email="merchant@example.test", source="fixture")
        self.experiment = Experiment(key="requested-service-fixture", specification={}, stop_at=time.time() + 86400)
        self.db.add_all([self.contact, self.experiment])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def request(self):
        return record(self.db, "request:fixture", "ACCESS_REQUESTED", self.contact.id,
                      {"issue": "Inventory planning"}, source="skubase_form")

    def assert_service_scope(self, message):
        self.assertIn(HEALTH_CHECK_URL, message.body)
        self.assertIn(APP_REVIEW_DISCLOSURE, message.body)
        self.assertIn("info@skubase.io", message.body)
        self.assertIn("Reply", message.body)
        self.assertNotIn("/store-sync", message.body)
        self.assertNotIn("/login", message.body)
        self.assertNotIn("automated assistant", message.body)
        self.assertNotIn("we reviewed your", message.body.lower())
        self.assertLess(len(message.body.split()), 215)

    def test_requested_check_uses_local_tool_and_preserves_request_authority(self):
        request = self.request()
        message = draft_requested_check(self.db, self.contact, self.experiment, "cash")
        self.assert_service_scope(message)
        self.assertIn("no account or Shopify installation needed", message.body)
        self.assertIn("Your SKU entries are not sent to Skubase", message.body)
        self.assertIn("cost when unit costs are provided", message.body)
        self.assertIn("not an order quantity", message.body)
        permit = validate_permit(self.db, message, self.contact)
        self.assertEqual(permit.data["request_evidence_id"], request.id)
        self.assertEqual(permit.data["template_revision"], SERVICE_TEMPLATE_REVISION)
        self.assertTrue(set(HEALTH_CHECK_SOURCES).issubset(permit.data["knowledge_sources"]))

    def test_reorder_variant_describes_triggers_without_promising_optimized_orders(self):
        self.request()
        message = draft_requested_check(self.db, self.contact, self.experiment, "reorder")
        self.assert_service_scope(message)
        self.assertIn("possible stockout risks and reorder triggers", message.body)
        self.assertNotIn("optimized order", message.body)

    def test_no_request_and_stale_request_still_cannot_authorize_outreach(self):
        with self.assertRaises(GrowthError):
            draft_requested_check(self.db, self.contact, self.experiment, "cash")
        request = self.request()
        request.occurred_at = time.time() - 15 * 86400
        self.db.flush()
        with self.assertRaises(GrowthError):
            draft_requested_check(self.db, self.contact, self.experiment, "cash")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Message)), 0)

    def test_existing_delivered_first_contact_is_not_rewritten_or_duplicated(self):
        self.request()
        old = Message(key="first-contact:" + self.contact.id, contact_id=self.contact.id,
                      experiment_id=self.experiment.id, direction="out", variant="cash",
                      subject="Original subject", body="Original delivered message", status="delivered",
                      provider_id="fixture-delivered-receipt")
        self.db.add(old)
        self.db.flush()
        message = draft_requested_check(self.db, self.contact, self.experiment, "reorder")
        self.assertEqual(message.id, old.id)
        self.assertEqual(message.body, "Original delivered message")
        self.assertEqual(message.status, "delivered")
        self.assertEqual(message.variant, "cash")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Message)), 1)

    def test_connection_and_data_questions_offer_browser_tool_with_scoped_support_fallback(self):
        self.request()
        for index, text in enumerate((
            "How do I connect my Shopify store to Skubase?",
            "Will Skubase change my store inventory?",
            "Should I email my password for the health check?",
        )):
            with self.subTest(question=text):
                event = record(self.db, f"question:{index}", "REPLY_RECEIVED", self.contact.id,
                               {"text": text}, source="requested_service_fixture")
                message = answer_request(self.db, self.contact, event, text)
                self.assertIsNotNone(message)
                self.assert_service_scope(message)
                validate_permit(self.db, message, self.contact)
                duplicate = answer_request(self.db, self.contact, event, text)
                # The per-week reply ceiling may decline the third duplicate;
                # no second response to an already fulfilled request is created.
                self.assertTrue(duplicate is None or duplicate.id == message.id)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Message)), 3)

    def test_suppression_and_body_integrity_remain_enforced(self):
        request = self.request()
        self.contact.suppressed = True
        self.assertIsNone(answer_request(self.db, self.contact, request, "How do I connect my store to Skubase?"))
        self.contact.suppressed = False
        message = draft_requested_check(self.db, self.contact, self.experiment, "cash")
        message.body += " Buy a subscription now."
        with self.assertRaises(GrowthError):
            validate_permit(self.db, message, self.contact)


if __name__ == "__main__":
    unittest.main()
