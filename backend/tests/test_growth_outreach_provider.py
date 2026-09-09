"""Provider protocol tests: all HTTP is mocked; no live mail is sent."""
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch

import requests

from app.growth import outreach_provider as provider
from app.growth.policy import GrowthError


class Response:
    def __init__(self, status=200, body=None, headers=None, raw=None):
        self.status_code = status
        self.headers = headers or {}
        self.content = json.dumps(body or {}).encode() if raw is None else raw
        self.raw = self

    def read(self, size, **kwargs):
        return self.content[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class OutreachProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "OUTREACH_PROVIDER": "emailpal", "OUTREACH_EMAILPAL_API_KEY": "secret-for-test-only",
            "OUTREACH_EMAILPAL_MAILBOX_ID": "mbx_fixture", "OUTREACH_EMAILPAL_WEBHOOK_SECRET": "webhook-test-only"})
        self.env.start()
        self.payload = {"sender": "rainer@outreach.skubase.io", "sender_name": "Rainer from Skubase",
                        "reply_to": "rainer@outreach.skubase.io", "recipient": "merchant@example.test",
                        "subject": "Inventory question", "body": "Test only", "idempotency_key": "outreach:fixture"}
        self.mailbox = {"id": "mbx_fixture", "email": self.payload["sender"],
                        "display_name": self.payload["sender_name"], "status": "active"}

    def tearDown(self):
        self.env.stop()

    def test_202_is_queued_not_sent_and_transport_is_fixed(self):
        with patch.object(provider.requests, "request", side_effect=[Response(body=self.mailbox), Response(202, {"id": "out_one", "job_id": "job_one"})]) as http:
            result = provider.send_message(self.payload)
        self.assertEqual(result, {"provider_id": "out_one", "queued": True, "job_id": "job_one"})
        self.assertNotIn("sent", result)
        args, kw = http.call_args
        self.assertEqual(args, ("POST", provider.BASE_URL + "/inbox/send"))
        self.assertFalse(kw["allow_redirects"])
        self.assertEqual(kw["timeout"], 20)
        self.assertEqual(kw["headers"]["Idempotency-Key"], "outreach:fixture")
        self.assertEqual(kw["json"]["to"], ["merchant@example.test"])
        self.assertNotIn("reply_to", kw["json"])

    def test_sender_mismatch_never_reaches_post(self):
        with patch.object(provider.requests, "request", return_value=Response(body={**self.mailbox, "email": "other@example.test"})) as http:
            with self.assertRaises(provider.ProviderRejected):
                provider.send_message(self.payload)
        self.assertEqual(http.call_count, 1)

    def test_reply_to_mismatch_and_header_injection_rejected_locally(self):
        for field, value in [("reply_to", "info@skubase.io"), ("recipient", "a@b.test\r\nBcc: bad@b.test"), ("subject", "Hi\nBcc:bad"), ("idempotency_key", "key\r\nLeak: secret")]:
            with self.subTest(field=field), patch.object(provider.requests, "request") as http:
                with self.assertRaises(provider.ProviderRejected):
                    provider.send_message({**self.payload, field: value})
                http.assert_not_called()

    def test_reply_uses_provider_inbound_message_id(self):
        with patch.object(provider.requests, "request", side_effect=[Response(body=self.mailbox), Response(202, {"id": "out_one", "job_id": "job_one"})]) as http:
            provider.send_message({**self.payload, "parent_provider_id": "msg_parent"})
        self.assertEqual(http.call_args.kwargs["json"]["reply_to_id"], "msg_parent")

    def test_followup_uses_rfc_thread_and_reply_id_takes_precedence(self):
        for extra in [{"parent_rfc_message_id": "<first@outreach.skubase.io>"},
                      {"parent_rfc_message_id": "<first@outreach.skubase.io>", "parent_provider_id": "msg_parent"}]:
            with patch.object(provider.requests, "request", side_effect=[Response(body=self.mailbox), Response(202, {"id": "out_one", "job_id": "job_one"})]) as http:
                provider.send_message({**self.payload, **extra})
            body = http.call_args.kwargs["json"]
            if "parent_provider_id" in extra:
                self.assertEqual(body["reply_to_id"], "msg_parent")
                self.assertNotIn("in_reply_to", body)
            else:
                self.assertEqual(body["in_reply_to"], "<first@outreach.skubase.io>")
                self.assertEqual(body["references"], ["<first@outreach.skubase.io>"])
                self.assertNotIn("reply_to_id", body)

    def test_definite_rejection_and_rate_limit_are_no_effect(self):
        for status in [400, 401, 403, 404, 409, 422, 429]:
            with self.subTest(status=status), patch.object(provider.requests, "request", return_value=Response(status, {"secret": "do-not-print"}, {"Retry-After": "120"})):
                with self.assertRaises(provider.ProviderRejected) as caught:
                    provider.request("/inbox/send", method="POST", data={})
                self.assertTrue(caught.exception.definitive)
                self.assertNotIn("do-not-print", str(caught.exception))
                self.assertEqual(caught.exception.retry_after, 120)

    def test_timeout_or_5xx_is_ambiguous_without_post_retry(self):
        for result in [requests.Timeout("secret-for-test-only"), Response(503), Response(202, raw=b"invalid")]:
            with self.subTest(result=type(result).__name__), patch.object(provider.requests, "request", side_effect=[Response(body=self.mailbox), result]) as http:
                with self.assertRaises(GrowthError) as caught:
                    provider.send_message(self.payload)
                self.assertEqual(caught.exception.category, "ambiguous")
                self.assertFalse(getattr(caught.exception, "definitive", False))
                self.assertEqual(http.call_count, 2)
                self.assertNotIn("secret-for-test-only", str(caught.exception))

    def test_preflight_timeout_is_definite_no_send(self):
        with patch.object(provider.requests, "request", side_effect=requests.Timeout()) as http:
            with self.assertRaises(provider.ProviderRejected) as caught:
                provider.send_message(self.payload)
        self.assertTrue(caught.exception.definitive)
        self.assertEqual(http.call_count, 1)

    def test_malformed_or_oversized_acceptance_never_claims_sent(self):
        for response in [Response(202, {"id": "out_only"}), Response(202, raw=b" " * 256001), Response(201, {"id": "out_one", "job_id": "job_one"})]:
            with patch.object(provider.requests, "request", side_effect=[Response(body=self.mailbox), response]):
                with self.assertRaises(GrowthError) as caught:
                    provider.send_message(self.payload)
                self.assertEqual(caught.exception.category, "ambiguous")

    def test_resource_ids_cannot_change_host_or_query(self):
        for resource in ["https://other.test", "../secret", "foo?key=bad", "foo/bar"]:
            with patch.object(provider.requests, "request") as http:
                with self.assertRaises(provider.ProviderRejected):
                    provider.read_send(resource)
                http.assert_not_called()

    def test_read_delivery_and_pending_inbound_preserve_meaning(self):
        with patch.object(provider.requests, "request", return_value=Response(body={"status": "sent", "delivery_status": "bounced", "bounce_type": "hard"})):
            self.assertEqual(provider.read_send("out_one")["delivery_status"], "bounced")
        with patch.object(provider.requests, "request", return_value=Response(202, {"poll": "/inbox/msg_one"})):
            self.assertEqual(provider.read_inbound("msg_one")["status"], "pending")

    def test_list_inbound_is_one_bounded_mailbox_page_with_warming_excluded(self):
        page = {"data": [{"id": "msg_one", "seen": True, "warming": False}],
                "has_more": True, "next_cursor": "2026-09-09T12:00:00.000Z"}
        with patch.object(provider.requests, "request", return_value=Response(body=page)) as http:
            self.assertEqual(provider.list_inbound("previous-cursor"), page)
        self.assertEqual(http.call_count, 1)
        args, kwargs = http.call_args
        self.assertEqual(args, ("GET", provider.BASE_URL + "/inbox"))
        self.assertEqual(kwargs["params"], {"mailbox_id": "mbx_fixture", "include_warming": "false", "limit": 50, "cursor": "previous-cursor"})
        self.assertNotIn("unread", kwargs["params"])

    def test_list_inbound_rejects_bad_cursor_and_malformed_page(self):
        with patch.object(provider.requests, "request") as http:
            with self.assertRaises(provider.ProviderRejected):
                provider.list_inbound("\r\nwrong")
            http.assert_not_called()
        for page in [{"data": {}, "has_more": False}, {"data": [{}] * 51, "has_more": False},
                     {"data": [], "has_more": "yes"}, {"data": [], "has_more": True, "next_cursor": 123}]:
            with patch.object(provider.requests, "request", return_value=Response(body=page)):
                with self.assertRaises(GrowthError):
                    provider.list_inbound()

    def signature(self, raw, timestamp=None):
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        digest = hmac.new(b"webhook-test-only", timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return {"EmailPal-Signature": f"t={timestamp},v1={digest}"}

    def test_webhook_authenticates_raw_bytes_and_returns_event(self):
        raw = b'{"id":"evt_one", "type":"message.received"}'
        event = provider.verify_webhook(raw, self.signature(raw))
        self.assertEqual(event["id"], "evt_one")
        # Replay identity is preserved so the durable event store can deduplicate.
        self.assertEqual(provider.verify_webhook(raw, self.signature(raw)), event)

    def test_webhook_rejects_modified_stale_future_and_duplicate_signature_fields(self):
        raw = b'{"id":"evt_one"}'
        cases = [(raw + b" ", self.signature(raw)), (raw, self.signature(raw, int(time.time()) - 301)),
                 (raw, self.signature(raw, int(time.time()) + 301)), (raw, {"EmailPal-Signature": "t=1,t=1,v1=bad"}),
                 (b"[]", self.signature(b"[]")), (b"{}", self.signature(b"{}"))]
        for body, headers in cases:
            with self.subTest(body=body, headers=headers), self.assertRaises(GrowthError):
                provider.verify_webhook(body, headers)


if __name__ == "__main__":
    unittest.main()
