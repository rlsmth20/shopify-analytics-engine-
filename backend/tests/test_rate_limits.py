"""Public endpoints and the admin token gate stop abuse loops with 429s."""
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth as auth_routes, contact as contact_routes, waitlist as waitlist_routes
from app.api.routes import inventory_risk_snapshot as leads_routes
from app.db.base import Base
from app.db.session import get_db_session
from app.services import rate_limit


def request_from(address, forwarded=None):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                    "headers": headers, "client": (address, 1234)})


class LimiterTests(unittest.TestCase):
    def setUp(self):
        rate_limit.reset()
        self.addCleanup(rate_limit.reset)
        self.now = 1000.0
        clock = patch.object(rate_limit, "_clock", lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def test_window_slides_and_retry_after_counts_down(self):
        with patch.dict(os.environ, {"RATE_LIMIT_CONTACT_IP": "2/60"}):
            for _ in range(2):
                rate_limit.record("contact_ip", "a")
            self.assertEqual(rate_limit.retry_after("contact_ip", "a"), 61)
            self.now += 30
            self.assertEqual(rate_limit.retry_after("contact_ip", "a"), 31)
            self.now += 31
            self.assertIsNone(rate_limit.retry_after("contact_ip", "a"))
            self.assertIsNone(rate_limit.retry_after("contact_ip", "b"))

    def test_invalid_override_keeps_default_and_disable_switch_turns_limits_off(self):
        with patch.dict(os.environ, {"RATE_LIMIT_CONTACT_IP": "lots"}):
            self.assertEqual(rate_limit.policy("contact_ip"), rate_limit.DEFAULT_POLICIES["contact_ip"])
        with patch.dict(os.environ, {"RATE_LIMITS_ENABLED": "false"}):
            for _ in range(50):
                rate_limit.record("contact_ip", "a")
            self.assertIsNone(rate_limit.retry_after("contact_ip", "a"))
            rate_limit.enforce(request_from("1.1.1.1"), ("contact_ip", None))

    def test_client_address_is_the_proxy_appended_forwarded_hop(self):
        self.assertEqual(rate_limit.client_ip(request_from("10.0.0.1", "9.9.9.9, 203.0.113.5")), "203.0.113.5")
        self.assertEqual(rate_limit.client_ip(request_from("10.0.0.1")), "10.0.0.1")

    def test_blocked_request_does_not_consume_other_buckets(self):
        request = request_from("1.1.1.1")
        with patch.dict(os.environ, {"RATE_LIMIT_MAGIC_LINK_IP": "1/60"}):
            rate_limit.enforce(request, ("magic_link_ip", None), ("magic_link_email", "a@x"))
            with self.assertRaises(HTTPException) as caught:
                rate_limit.enforce(request, ("magic_link_ip", None), ("magic_link_email", "a@x"))
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.headers["Retry-After"], "61")
        self.assertEqual(len(rate_limit._hits[("magic_link_email", "a@x")]), 1)

    def test_idle_keys_are_swept_so_address_scans_cannot_grow_memory(self):
        rate_limit.record("lead_ip", "scan-1")
        self.now += 3601
        rate_limit.retry_after("lead_ip", "other")
        self.assertNotIn(("lead_ip", "scan-1"), rate_limit._hits)


class PublicRouteLimitTests(unittest.TestCase):
    def setUp(self):
        rate_limit.reset()
        self.addCleanup(rate_limit.reset)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        sessions = sessionmaker(self.engine, expire_on_commit=False)

        @contextmanager
        def scope():
            with sessions() as db:
                try:
                    yield db
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

        def dependency():
            with scope() as db:
                yield db

        app = FastAPI()
        for router in (auth_routes.router, contact_routes.router, waitlist_routes.router, leads_routes.router):
            app.include_router(router)
        app.dependency_overrides[get_db_session] = dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.addCleanup(self.client.close)
        for target, name in [(auth_routes, "send_magic_link_email"), (contact_routes, "send_contact_notification"),
                             (waitlist_routes, "send_waitlist_confirmation")]:
            mock = patch.object(target, name, return_value=True)
            setattr(self, name, mock.start())
            self.addCleanup(mock.stop)
        scope_patch = patch.object(waitlist_routes, "session_scope", scope)
        scope_patch.start()
        self.addCleanup(scope_patch.stop)

    def magic_link(self, email, **headers):
        return self.client.post("/auth/magic-link/request", json={"email": email}, headers=headers)

    def test_fourth_magic_link_for_one_address_is_refused_without_sending(self):
        for _ in range(3):
            self.assertEqual(self.magic_link("victim@example.com").status_code, 200)
        response = self.magic_link("VICTIM@example.com")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "rate_limited")
        self.assertIn("inbox", response.json()["detail"]["message"])
        self.assertTrue(int(response.headers["Retry-After"]) > 0)
        self.assertEqual(self.send_magic_link_email.call_count, 3)
        # Another address from the same client is still served.
        self.assertEqual(self.magic_link("other@example.com").status_code, 200)

    def test_magic_link_requests_are_capped_per_client_address(self):
        with patch.dict(os.environ, {"RATE_LIMIT_MAGIC_LINK_IP": "2/900"}):
            for index in range(2):
                self.assertEqual(self.magic_link(f"user{index}@example.com").status_code, 200)
            self.assertEqual(self.magic_link("user2@example.com").status_code, 429)
            # A different client, identified by the proxy-appended hop, is unaffected.
            response = self.magic_link("user2@example.com", **{"X-Forwarded-For": "198.51.100.7"})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.send_magic_link_email.call_count, 3)

    def test_contact_submissions_are_capped_per_client(self):
        payload = {"name": "Merchant", "type": "general", "message": "Please help me review my account."}
        for index in range(5):
            response = self.client.post("/contact/submit", json={**payload, "email": f"m{index}@example.com"})
            self.assertEqual(response.status_code, 200)
        response = self.client.post("/contact/submit", json={**payload, "email": "m5@example.com"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Please wait", response.json()["detail"])
        self.assertEqual(self.send_contact_notification.call_count, 5)

    def test_waitlist_and_lead_capture_are_capped_per_client(self):
        lead = {"first_name": "Pat", "company_name": "Demo store", "store_url": "demo-store.myshopify.com",
                "approximate_sku_count": "75-100", "biggest_inventory_issue": "Stockouts"}
        with patch.dict(os.environ, {"RATE_LIMIT_WAITLIST_IP": "2/600", "RATE_LIMIT_LEAD_IP": "2/3600"}):
            for index in range(2):
                response = self.client.post("/waitlist/signup", json={"email": f"w{index}@example.com"})
                self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.client.post("/waitlist/signup", json={"email": "w2@example.com"}).status_code, 429)
            for index in range(2):
                response = self.client.post("/inventory-risk-snapshot/leads", json={**lead, "email": f"l{index}@example.com"})
                self.assertEqual(response.status_code, 200, response.text)
            response = self.client.post("/inventory-risk-snapshot/leads", json={**lead, "email": "l2@example.com"})
            self.assertEqual(response.status_code, 429)
        self.assertEqual(self.send_waitlist_confirmation.call_count, 2)

    def test_repeated_wrong_admin_tokens_lock_the_address_out(self):
        with patch.dict(os.environ, {"ADMIN_BOOTSTRAP_TOKEN": "fixture-admin-token"}):
            for _ in range(10):
                response = self.client.get("/inventory-risk-snapshot/leads", headers={"X-Admin-Token": "guess"})
                self.assertEqual(response.status_code, 403)
            self.assertEqual(self.client.get("/inventory-risk-snapshot/leads", headers={"X-Admin-Token": "guess"}).status_code, 429)
            # The lockout also covers the correct token from that address...
            locked = self.client.get("/inventory-risk-snapshot/leads", headers={"X-Admin-Token": "fixture-admin-token"})
            self.assertEqual(locked.status_code, 429)
            # ...but not the operator elsewhere, and correct tokens never count toward it.
            for _ in range(15):
                response = self.client.get("/inventory-risk-snapshot/leads",
                                           headers={"X-Admin-Token": "fixture-admin-token", "X-Forwarded-For": "198.51.100.9"})
                self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
