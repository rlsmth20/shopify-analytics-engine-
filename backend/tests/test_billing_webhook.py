"""Stripe webhook verification uses real SDK signatures and synthetic storage.

These tests never call Stripe's network API or create financial transactions.
"""
import asyncio
import hashlib
import hmac
import json
import os
import time
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event as sqlalchemy_event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.billing import stripe_webhook, webhook_router
from app.db.models import Base, Shop, Subscription, User
from app.db.session import get_db_session
from app.growth import billing_events
from app.growth.models import Evidence, Memory, Work
from app.growth.store import get_memory, record
from app.services import billing

SIGNING_SECRET = "whsec_synthetic_fixture_only"


class BillingWebhookTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_synthetic_fixture_only",
                                          "STRIPE_WEBHOOK_SECRET": SIGNING_SECRET})
        self.env.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        # SQLite's legacy savepoint behavior can commit before an outer BEGIN;
        # use actual transactions so rollback assertions match PostgreSQL.
        @sqlalchemy_event.listens_for(self.engine, "connect")
        def disable_legacy_transactions(connection, _):
            connection.isolation_level = None
        @sqlalchemy_event.listens_for(self.engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")
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
        self.real_lookup = billing._current_webhook_subscription
        self.lookup_patch = patch.object(billing, "_current_webhook_subscription", return_value={
            "id": "sub_fixture", "customer": "cus_fixture", "status": "active",
            "current_period_end": 1_800_000_000,
            "items": {"data": [{"price": {"id": "price_fixture"}}]},
        })
        self.lookup = self.lookup_patch.start()

    def tearDown(self):
        self.lookup_patch.stop()
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

    def send_event(self, kind, obj, event_id="evt_payment", created=1_800_000_000, livemode=True):
        payload = json.dumps({"id": event_id, "type": kind, "created": created, "livemode": livemode,
                              "data": {"object": obj}}).encode()
        return self.post(payload, self.signature(payload))

    def seed_customer(self, status="active", subscription_id="sub_fixture"):
        with self.sessions() as db:
            db.add(User(shop_id=self.first_id, email="merchant@example.test"))
            db.add(Subscription(shop_id=self.first_id, stripe_customer_id="cus_fixture",
                                stripe_subscription_id=subscription_id, status=status, plan="growth_monthly"))
            db.commit()

    def invoice(self, receipt_id="in_fixture", subscription_id="sub_fixture", period_end=1_800_000_000, amount=3900):
        return {"id": receipt_id, "customer": "cus_fixture", "subscription": subscription_id,
                "paid": True, "amount_paid": amount, "currency": "usd", "period_end": period_end,
                "lines": {"data": [{"quantity": 1, "price": {"unit_amount": amount,
                    "recurring": {"interval": "month", "interval_count": 1}}}]}}

    def cancellation(self, subscription_id="sub_fixture"):
        return {"id": subscription_id, "customer": "cus_fixture", "status": "canceled"}

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

    def test_handler_failure_returns_retryable_error_and_rolls_back_without_leaking_details(self):
        self.seed_customer()
        def fail(db, *, event):
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            sub.status = "canceled"
            db.flush()
            raise RuntimeError("synthetic private database detail")
        with patch("app.api.routes.billing.handle_webhook_event", side_effect=fail), self.assertLogs(level="ERROR"):
            response = self.send_event("customer.subscription.deleted", self.cancellation())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", response.text)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Subscription.status).where(Subscription.shop_id == self.first_id)), "active")

    def test_synchronous_provider_and_persistence_stages_run_off_the_api_event_loop(self):
        api_thread = threading.get_ident()
        stage_threads = []
        def capture_thread(*args, **kwargs):
            stage_threads.append(threading.get_ident())
        request = MagicMock()
        request.body = AsyncMock(return_value=self.payload())
        with patch("app.api.routes.billing.handle_webhook_event", side_effect=capture_thread), \
             patch.object(billing_events, "stripe_event", side_effect=capture_thread):
            result = asyncio.run(stripe_webhook(request, MagicMock(), self.signature(self.payload())))
        self.assertEqual(result, {"received": True})
        self.assertEqual(len(stage_threads), 2)
        self.assertTrue(all(worker_thread != api_thread for worker_thread in stage_threads))

    def test_projection_failure_after_subscription_commit_is_recovered_by_replay(self):
        self.seed_customer()
        with patch.object(billing_events, "stripe_event", side_effect=RuntimeError("projection unavailable")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation()).status_code, 503)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Subscription.status).where(Subscription.shop_id == self.first_id)), "canceled")
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence)), 0)
        for _ in range(2):
            self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation()).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "CANCELLATION")), 1)
            economics = get_memory(db, "economics", f"shop:{self.first_id}")
            self.assertFalse(economics["active"])
            self.assertEqual(economics["monthly_recurring_usd"], 0)
        self.lookup.assert_not_called()

    def test_invoice_commit_failure_is_retryable_and_replay_records_one_receipt_and_wake(self):
        self.seed_customer()
        with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("commit unavailable")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.send_event("invoice.paid", self.invoice()).status_code, 503)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory)), 0)
        for event_id in ("evt_payment", "evt_payment", "evt_same_invoice_again"):
            self.assertEqual(self.send_event("invoice.paid", self.invoice(), event_id).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "SUBSCRIPTION_PURCHASED")), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Work)), 1)
            economics = get_memory(db, "economics", f"shop:{self.first_id}")
            self.assertTrue(economics["active"])
            self.assertEqual(economics["monthly_recurring_usd"], 39)
        self.lookup.assert_not_called()

    def test_delayed_payment_and_checkout_cannot_reactivate_cancelled_subscription(self):
        self.seed_customer()
        self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation(), "evt_cancel").status_code, 200)
        for event_id in ("evt_payment", "evt_payment_again"):
            # Identical creation timestamps cannot imply that the payment happened later.
            self.assertEqual(self.send_event("invoice.paid", self.invoice(), event_id).status_code, 200)
        payload = self.payload()
        self.assertEqual(self.post(payload, self.signature(payload)).status_code, 200)
        self.assertEqual(self.send_event("customer.subscription.updated", {
            **self.cancellation(), "status": "active"}, "evt_old_update").status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Subscription.status).where(Subscription.shop_id == self.first_id)), "canceled")
            self.assertFalse(get_memory(db, "economics", f"shop:{self.first_id}")["active"])
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "SUBSCRIPTION_PURCHASED")), 1)
        self.lookup.assert_not_called()

    def test_delayed_previous_subscription_events_do_not_cancel_replacement(self):
        self.seed_customer(subscription_id="sub_replacement")
        self.assertEqual(self.send_event("invoice.paid", self.invoice(subscription_id="sub_replacement")).status_code, 200)
        for event_id in ("evt_old_cancel", "evt_old_cancel_duplicate"):
            self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation(), event_id).status_code, 200)
        self.assertEqual(self.send_event("invoice.paid", self.invoice("in_old"), "evt_old_payment").status_code, 200)
        self.assertEqual(self.send_event("customer.subscription.updated", self.cancellation(), "evt_old_update").status_code, 200)
        with self.sessions() as db:
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            self.assertEqual((sub.stripe_subscription_id, sub.status), ("sub_replacement", "active"))
            economics = get_memory(db, "economics", f"shop:{self.first_id}")
            self.assertTrue(economics["active"])
            self.assertEqual(economics["source_receipt"], "in_fixture")
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "CANCELLATION")), 1)
        self.lookup.assert_not_called()

    def test_old_checkout_for_terminated_subscription_does_not_replace_new_active_contract(self):
        self.seed_customer(subscription_id="sub_replacement")
        self.lookup.return_value = {"id": "sub_fixture", "customer": "cus_fixture", "status": "canceled"}
        payload = self.payload()
        self.assertEqual(self.post(payload, self.signature(payload)).status_code, 200)
        with self.sessions() as db:
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            self.assertEqual((sub.stripe_subscription_id, sub.status), ("sub_replacement", "active"))
        self.lookup.assert_called_once_with("sub_fixture")

    def test_verified_stripe_checkout_does_not_replace_shopify_subscription(self):
        payload = self.payload(self.second_id)
        self.assertEqual(self.post(payload, self.signature(payload)).status_code, 200)
        with self.sessions() as db:
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.second_id))
            self.assertEqual((sub.stripe_subscription_id, sub.status), ("shopify:existing", "active"))
        self.lookup.assert_not_called()

    def test_new_checkout_can_replace_terminal_contract_using_provider_state(self):
        self.seed_customer(status="canceled", subscription_id="sub_previous")
        payload = self.payload()
        self.assertEqual(self.post(payload, self.signature(payload)).status_code, 200)
        with self.sessions() as db:
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            self.assertEqual((sub.stripe_subscription_id, sub.status), ("sub_fixture", "active"))
        self.lookup.assert_called_once_with("sub_fixture")

    def test_conflicting_active_checkout_returns_retryable_failure_without_replacing_contract(self):
        self.seed_customer(subscription_id="sub_existing")
        payload = self.payload()
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.post(payload, self.signature(payload)).status_code, 503)
        with self.sessions() as db:
            sub = db.scalar(select(Subscription).where(Subscription.shop_id == self.first_id))
            self.assertEqual(sub.stripe_subscription_id, "sub_existing")

    def test_cancellation_replay_recognizes_receipt_persisted_by_previous_handler(self):
        self.seed_customer(status="canceled")
        with self.sessions() as db:
            record(db, "funnel:cancel:evt_old_handler", "CANCELLATION", f"shop:{self.first_id}",
                   {"provider_event_id": "evt_old_handler"}, occurred_at=1_800_000_000)
            db.commit()
        self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation(), "evt_old_handler").status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "CANCELLATION")), 1)
            self.assertFalse(get_memory(db, "economics", f"shop:{self.first_id}")["active"])

    def test_nonterminal_snapshots_use_current_provider_state_even_when_timestamps_tie(self):
        self.seed_customer()
        self.lookup.return_value = {"id": "sub_fixture", "customer": "cus_fixture", "status": "past_due"}
        for event_id, status in (("evt_latest", "past_due"), ("evt_stale", "active")):
            response = self.send_event("customer.subscription.updated", {
                "id": "sub_fixture", "customer": "cus_fixture", "status": status}, event_id)
            self.assertEqual(response.status_code, 200, response.text)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Subscription.status).where(Subscription.shop_id == self.first_id)), "past_due")
        self.assertEqual(self.lookup.call_count, 2)

    def test_unavailable_provider_read_is_retryable_and_never_applies_stale_snapshot(self):
        self.seed_customer()
        with patch.object(billing, "_current_webhook_subscription", side_effect=RuntimeError("lookup failed")), self.assertLogs(level="ERROR"):
            response = self.send_event("customer.subscription.updated", {
                "id": "sub_fixture", "customer": "cus_fixture", "status": "past_due"})
        self.assertEqual(response.status_code, 503)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Subscription.status).where(Subscription.shop_id == self.first_id)), "active")

    def test_current_subscription_fetch_has_timeout_and_no_sdk_retries(self):
        provider = MagicMock()
        provider.api_key = "synthetic"
        client = provider.StripeClient.return_value
        client.subscriptions.retrieve.return_value = {"id": "sub_fixture", "status": "active"}
        with patch.object(billing, "_stripe", return_value=provider):
            self.assertEqual(self.real_lookup("sub_fixture")["id"], "sub_fixture")
        provider.http_client.new_default_http_client.assert_called_once_with(timeout=10)
        self.assertEqual(provider.StripeClient.call_args.kwargs["max_network_retries"], 0)
        client.subscriptions.retrieve.assert_called_once_with("sub_fixture")

    def test_late_invoice_does_not_replace_later_billing_period_price(self):
        self.seed_customer()
        self.assertEqual(self.send_event("invoice.paid", self.invoice("in_new", period_end=200, amount=4900)).status_code, 200)
        self.assertEqual(self.send_event("invoice.paid", self.invoice("in_old", period_end=100), "evt_old").status_code, 200)
        with self.sessions() as db:
            economics = get_memory(db, "economics", f"shop:{self.first_id}")
            self.assertEqual(economics["source_receipt"], "in_new")
            self.assertEqual(economics["monthly_recurring_usd"], 49)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "SUBSCRIPTION_PURCHASED")), 2)

    def test_test_mode_invoice_is_not_customer_or_revenue_evidence(self):
        self.seed_customer()
        self.assertEqual(self.send_event("invoice.paid", self.invoice(), livemode=False).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory)), 0)

    def test_one_off_invoice_does_not_count_as_subscription_purchase(self):
        self.seed_customer()
        invoice = self.invoice()
        invoice["subscription"] = None
        invoice["parent"] = {"subscription_details": None}
        self.assertEqual(self.send_event("invoice.paid", invoice).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence)), 0)

    def test_payment_between_cancellation_commit_and_retry_clears_obsolete_active_mrr(self):
        self.seed_customer()
        self.assertEqual(self.send_event("invoice.paid", self.invoice()).status_code, 200)
        with patch.object(billing_events, "stripe_event", side_effect=RuntimeError("projection unavailable")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation()).status_code, 503)
        self.assertEqual(self.send_event("invoice.paid", self.invoice("in_delayed"), "evt_delayed").status_code, 200)
        with self.sessions() as db:
            economics = get_memory(db, "economics", f"shop:{self.first_id}")
            self.assertFalse(economics["active"])
            self.assertEqual(economics["monthly_recurring_usd"], 0)
        self.assertEqual(self.send_event("customer.subscription.deleted", self.cancellation()).status_code, 200)

    def test_conflicting_same_period_prices_remain_unknown(self):
        self.seed_customer()
        self.assertEqual(self.send_event("invoice.paid", self.invoice()).status_code, 200)
        self.assertEqual(self.send_event("invoice.paid", self.invoice("in_other", amount=4900), "evt_other").status_code, 200)
        with self.sessions() as db:
            self.assertIsNone(get_memory(db, "economics", f"shop:{self.first_id}")["monthly_recurring_usd"])


if __name__ == "__main__":
    unittest.main()
