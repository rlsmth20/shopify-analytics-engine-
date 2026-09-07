"""Contact acknowledgement regressions. Delivery is mocked in every test."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.contact import router


class ContactTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        delivery = patch("app.api.routes.contact.send_contact_notification", return_value=True)
        self.send = delivery.start()
        self.addCleanup(delivery.stop)
        self.payload = {
            "name": "Test merchant",
            "email": "merchant@example.com",
            "type": "billing",
            "message": "Please help me review my account.",
        }

    def test_acknowledges_successful_delivery_without_changing_response_contract(self):
        response = self.client.post("/contact/submit", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.send.assert_called_once_with(
            name=self.payload["name"],
            email=self.payload["email"],
            contact_type=self.payload["type"],
            message=self.payload["message"],
        )

    def test_failed_delivery_returns_recoverable_error_instead_of_success(self):
        self.send.return_value = False
        response = self.client.post("/contact/submit", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("ok", response.json())
        self.assertIn("info@skubase.io", response.json()["detail"])
        self.send.assert_called_once()

    def test_synthetic_shopify_identities_cannot_be_used_as_reply_addresses(self):
        for email in (
            "shopify-admin+42@fixture.myshopify.com",
            "shopify-owner@fixture.myshopify.com",
            "Shopify-Admin+42@fixture.myshopify.com",
        ):
            with self.subTest(email=email):
                response = self.client.post("/contact/submit", json={**self.payload, "email": email})
                self.assertEqual(response.status_code, 422)
                self.send.assert_not_called()

    def test_normal_reply_address_with_plus_tag_is_accepted(self):
        response = self.client.post(
            "/contact/submit", json={**self.payload, "email": "buyer+shopify@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.send.call_args.kwargs["email"], "buyer+shopify@example.com")


if __name__ == "__main__":
    unittest.main()
