"""Stripe webhook verification uses real SDK signatures and synthetic storage.

These tests never call Stripe's network API or create financial transactions.
"""
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.billing import webhook_router
from app.db.models import Base, Shop, Subscription
from app.db.session import get_db_session
from app.services import billing

SIGNING_SECRET = "whsec_synthetic_fixture_only"


class BillingWebhookTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_synthetic_fixture_only",
                                          "STRIPE_WEBHOOK_SECRET": SIGNING_SECRET})
        self.env.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        with self.sessions() as db:
            first, second = Shop(shopify_domain="first.myshopify.com"), Shop(shopify_domain="second.myshopify.com")
            db.add_all([first, second])
            db.flush()
            self.first_id, self.second_id = first.id, second.id
            db.add(Subscription(shop_id=second.id, stripe_subscription_id="shopify:existing",
                                status="active", plan="scale_monthly"))
            db.commit()
        self.app = FastAPI()
        self.app.include_router(webhook_router)
        def session():
            with self.sessions() as db:
                yield db
        self.app.dependency_overrides[get_db_session] = session
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.env.stop()

    def payload(self, shop_id=None):
        return json.dumps({"id": "evt_fixture", "object": "event", "type": "checkout.session.completed",
                           "data": {"object": {"client_reference_id": str(shop_id or self.first_id),
                                               "subscription": "sub_fixture", "customer": "cus_fixture"}}}).encode()

    def signature(self, payload, timestamp=None):
        timestamp = int(time.time()) if timestamp is None else timestamp
        digest = hmac.new(SIGNING_SECRET.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={digest}"

    def post(self, payload, signature=None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["Stripe-Signature"] = signature
        return self.client.post("/stripe/webhook", content=payload, headers=headers)

    def assert_subscriptions_unchanged(self):
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id)))
            existing = db.scalar(select(Subscription).where(Subscription.shop_id == self.second_id))
            self.assertEqual((existing.stripe_subscription_id, existing.status, existing.plan),
                             ("shopify:existing", "active", "scale_monthly"))

    def test_missing_signing_secret_rejects_unsigned_and_claimed_signed_events(self):
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            for shop_id in (self.first_id, self.second_id):
                payload = self.payload(shop_id)
                for signature in (None, self.signature(payload)):
                    response = self.post(payload, signature)
                    self.assertEqual(response.status_code, 400, response.text)
        self.assert_subscriptions_unchanged()

    def test_unavailable_stripe_sdk_rejects_even_a_signed_event(self):
        payload = self.payload()
        with patch.object(billing, "_stripe", return_value=None):
            self.assertEqual(self.post(payload, self.signature(payload)).status_code, 400)
        self.assert_subscriptions_unchanged()

    def test_missing_stripe_api_configuration_does_not_bypass_signature_checks(self):
        payload = self.payload()
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}):
            self.assertEqual(self.post(payload, self.signature(payload)).status_code, 400)
        self.assert_subscriptions_unchanged()

    def test_invalid_missing_tampered_and_expired_signatures_do_not_activate_subscription(self):
        payload = self.payload()
        invalid = [None, "invalid", self.signature(payload + b" "), self.signature(payload, int(time.time()) - 600)]
        for signature in invalid:
            with self.subTest(signature_kind=invalid.index(signature)):
                response = self.post(payload, signature)
                self.assertEqual(response.status_code, 400, response.text)
        self.assert_subscriptions_unchanged()

    def test_valid_signature_reaches_existing_handler_without_changing_other_shop(self):
        payload = self.payload()
        response = self.post(payload, self.signature(payload))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"received": True})
        with self.sessions() as db:
            subscription = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            self.assertEqual((subscription.status, subscription.stripe_subscription_id), ("active", "sub_fixture"))
            existing = db.scalar(select(Subscription).where(Subscription.shop_id == self.second_id))
            self.assertEqual(existing.stripe_subscription_id, "shopify:existing")


if __name__ == "__main__":
    unittest.main()
