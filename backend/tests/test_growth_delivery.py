"""Delivery ordering and opt-out regressions; isolated storage, no real sends."""
import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes.growth import router
from app.db.base import Base
from app.db.session import get_db_session
from app.growth import engine, learning, messaging
from app.growth.models import Contact, Evidence, Message
from app.growth.policy import GrowthError, classify_reply
from app.growth.service_replies import draft_requested_check
from app.growth.store import claim, enqueue, finish, record


class GrowthDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbengine = create_engine("sqlite:///" + str(Path(self.temp.name) / "delivery.db"),
                                      connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.dbengine)
        self.factory = sessionmaker(self.dbengine, expire_on_commit=False, autoflush=False)
        self.secret = b"delivery-test-secret"
        self.env = patch.dict(os.environ, {
            "GROWTH_MAILBOX": "info@skubase.io", "GROWTH_EMAIL_ENABLED": "true",
            "GROWTH_RESEND_API_KEY": "fixture", "GROWTH_INBOUND_ENABLED": "true",
            "GROWTH_DAILY_USD": "0", "GROWTH_MODEL_ENABLED": "false",
            "GROWTH_DISCOVERY_ENABLED": "false",
            "GROWTH_RESEND_WEBHOOK_SECRET": "whsec_" + base64.b64encode(self.secret).decode(),
        })
        self.env.start()
        engine.bootstrap(self.factory)
        app = FastAPI()
        app.include_router(router)

        def sessions():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db_session] = sessions
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.dbengine.dispose()
        self.temp.cleanup()

    def requested_message(self, suffix):
        with self.factory() as db:
            contact = Contact(identity="delivery:" + suffix, email=suffix + "@example.test",
                              source="fixture", qualification={"qualified": True})
            db.add(contact)
            db.flush()
            record(db, "request:" + suffix, "ACCESS_REQUESTED", contact.id, {}, source="skubase_form")
            message = draft_requested_check(db, contact, learning.ensure_experiment(db), "cash")
            enqueue(db, "send:" + message.id, "send", {"message_id": message.id}, priority=95)
            db.commit()
            return contact.id, message.id

    def webhook(self, event_id, kind, provider_id=None):
        event = {"type": kind, "data": {"email_id": provider_id} if provider_id else {}}
        body = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        signed = event_id.encode() + b"." + timestamp.encode() + b"." + body
        signature = base64.b64encode(hmac.new(self.secret, signed, hashlib.sha256).digest()).decode()
        response = self.client.post("/growth/webhooks/resend", content=body, headers={
            "svix-id": event_id, "svix-timestamp": timestamp, "svix-signature": "v1," + signature,
        })
        self.assertEqual(response.status_code, 200)

    def test_signed_events_arriving_before_receipt_are_applied(self):
        for suffix, expected in (("bounced", "bounced"), ("complained", "complained"), ("delivered", "delivered")):
            with self.subTest(kind=suffix):
                contact_id, message_id = self.requested_message(suffix)
                work = claim(self.factory)

                def provider(*args, **kwargs):
                    with self.factory() as db:
                        self.assertIsNone(db.get(Message, message_id).provider_id)
                    self.webhook("early-" + suffix, "email." + suffix, "receipt-" + suffix)
                    return {"id": "receipt-" + suffix}

                result = messaging.send(self.factory, work, provider=provider)
                finish(self.factory, work, result=result)
                with self.factory() as db:
                    self.assertEqual(db.get(Message, message_id).status, expected)
                    self.assertEqual(db.get(Contact, contact_id).suppressed, suffix != "delivered")

                # Redelivery and out-of-order delivery cannot undo a bounce/complaint.
                self.webhook("early-" + suffix, "email." + suffix, "receipt-" + suffix)
                self.webhook("late-delivery-" + suffix, "email.delivered", "receipt-" + suffix)
                with self.factory() as db:
                    self.assertEqual(db.get(Message, message_id).status, expected)
                    self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(
                        Evidence.key == "provider-event:early-" + suffix)), 1)

    def test_unmatched_event_does_not_make_uncertain_send_replayable(self):
        contact_id, message_id = self.requested_message("uncertain")
        work = claim(self.factory)
        calls = []

        def provider(*args, **kwargs):
            calls.append(1)
            self.webhook("unknown-receipt-event", "email.bounced", "unreturned-receipt")
            raise TimeoutError("fixture receipt lost")

        for _ in range(2):
            with self.assertRaises(GrowthError) as error:
                messaging.send(self.factory, work, provider=provider)
            self.assertEqual(error.exception.category, "ambiguous")
        self.assertEqual(len(calls), 1)
        with self.factory() as db:
            self.assertEqual(db.get(Message, message_id).status, "unknown")
            self.assertIsNotNone(db.scalar(select(Evidence).where(Evidence.key == "provider-event:unknown-receipt-event")))

    def test_event_without_provider_id_does_not_match_an_unsent_draft(self):
        contact_id, message_id = self.requested_message("draft")
        self.webhook("missing-id", "email.bounced")
        with self.factory() as db:
            self.assertEqual(db.get(Message, message_id).status, "draft")
            self.assertFalse(db.get(Contact, contact_id).suppressed)

    def test_explicit_opt_out_prevents_assistance_reply(self):
        contact_id, _ = self.requested_message("decline")
        calls = []

        def provider(*args, **kwargs):
            calls.append(1)
            return {"id": "original-receipt"}

        engine.run_once(self.factory, schedule_wakes=False, provider=provider)
        with self.factory() as db:
            messaging.ingest_reply(db, provider_id="refusal", sender="decline@example.test",
                recipients=["info@skubase.io"], text="I don't want a health check. Please leave us alone.")
            db.commit()
        for _ in range(3):
            engine.run_once(self.factory, schedule_wakes=False, provider=provider)
        self.assertEqual(len(calls), 1)
        with self.factory() as db:
            self.assertTrue(db.get(Contact, contact_id).suppressed)
            self.assertEqual(db.scalar(select(func.count()).select_from(Message).where(
                Message.contact_id == contact_id, Message.direction == "out")), 1)

    def test_clear_declines_precede_positive_words_and_service_questions(self):
        for text in (
            "Please stop contacting us. How do I connect my Shopify store to Skubase?",
            "Leave me alone. I don't want a health check.",
            "Take us off your list.",
            "No more emails please.",
        ):
            with self.subTest(text=text):
                self.assertEqual(classify_reply(text), "UNSUBSCRIBE")
        self.assertEqual(classify_reply("I don\u2019t want a health check."), "SUBSTANTIVE_NEGATIVE")
        self.assertEqual(classify_reply("Can Skubase help me stop stockouts?"), "QUESTION")
        self.assertEqual(classify_reply("Yes, please send me the health check."), "SUBSTANTIVE_POSITIVE")
