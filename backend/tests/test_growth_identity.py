"""History must expose the exact recipient protection used by outbound sends."""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.growth.identity import merchant_view
from app.growth.models import Contact, Message
from app.growth.store import digest, remember


class IdentityHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_email_lookup_finds_storefront_history_and_suppression(self):
        contact = Contact(identity="store.test", email="Support@MailBrand.test",
                          source="https://store.test/contact", suppressed=True)
        self.db.add(contact)
        self.db.flush()
        reply = Message(key="opt-out", contact_id=contact.id, direction="in",
                        body="Unsubscribe", classification="UNSUBSCRIBE", status="received")
        self.db.add(reply)
        self.db.flush()
        view = merchant_view(self.db, "email:support@mailbrand.test")
        self.assertEqual(view["contact_ids"], [contact.id])
        self.assertTrue(view["suppressed"])
        self.assertEqual(view["recent_messages"][0]["id"], reply.id)
        self.assertEqual(view["next_action"], "SUPPRESSED")
        self.assertEqual(merchant_view(self.db, "other@mailbrand.test")["contact_ids"], [])

    def test_address_suppression_is_visible_without_a_contact_row(self):
        remember(self.db, "email_suppression", digest("bad@store.test"),
                 {"identifier": "bad@store.test", "reason": "bounce", "source": "fixture"})
        self.db.flush()
        view = merchant_view(self.db, "bad@store.test")
        self.assertEqual(view["contact_ids"], [])
        self.assertTrue(view["suppressed"])
        self.assertEqual(view["email_suppression"]["reason"], "bounce")
        self.assertEqual(view["next_action"], "SUPPRESSED")
        self.assertFalse(merchant_view(self.db, "other@store.test")["suppressed"])
