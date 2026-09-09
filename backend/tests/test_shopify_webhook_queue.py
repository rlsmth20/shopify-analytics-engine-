"""Durability and acknowledgement boundaries, using synthetic webhook receipts."""
import base64
import hashlib
import hmac
import json
import os
import time
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import shopify_privacy_webhooks as routes
from app.db.webhook_models import ShopifyWebhookJob as Job
from app.services import shopify_webhook_queue as queue


class WebhookQueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Job.__table__.create(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.app = FastAPI()
        self.app.include_router(routes.router)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.secret = patch.dict(os.environ, SHOPIFY_CLIENT_SECRET='fixture-secret')
        self.secret.start()
        self.factory_patch = patch.object(routes, 'SessionLocal', self.factory)
        self.factory_patch.start()

    def tearDown(self):
        self.client.close()
        self.factory_patch.stop()
        self.secret.stop()
        self.engine.dispose()

    def post(self, topic='shop/redact', payload=None, valid=True):
        raw = json.dumps(payload or {'shop_domain': 'synthetic.myshopify.com'}).encode()
        signature = base64.b64encode(hmac.new(b'fixture-secret', raw, hashlib.sha256).digest()).decode()
        return self.client.post('/webhooks/' + topic, content=raw, headers={
            'X-Shopify-Hmac-Sha256': signature if valid else 'invalid',
            'X-Shopify-Webhook-Id': 'fixture-delivery', 'Content-Type': 'application/json'})

    def jobs(self):
        with self.factory() as db:
            return list(db.scalars(select(Job)))

    def test_acknowledges_durable_receipt_without_executing_privacy_work(self):
        with patch.object(queue.privacy, 'redact_shop', return_value={'shops_redacted': 0}) as work:
            self.assertEqual(self.post().status_code, 200)
            work.assert_not_called()
            self.assertEqual(self.jobs()[0].status, 'pending')
            self.assertTrue(queue.process_one(self.factory))
            work.assert_called_once()
            job = self.jobs()[0]
            self.assertEqual((job.status, job.payload, job.domain), ('done', {}, ''))
            self.assertEqual(self.post().status_code, 200)
            self.assertFalse(queue.process_one(self.factory))
            self.assertEqual(len(self.jobs()), 1)
            work.assert_called_once()

    def test_invalid_signature_and_invalid_order_list_are_not_saved(self):
        self.assertEqual(self.post(valid=False).status_code, 401)
        self.assertEqual(self.post('customers/redact', {'shop_domain': 'synthetic.myshopify.com',
            'orders_to_redact': 'not-a-list'}).status_code, 400)
        self.assertEqual(self.jobs(), [])

    def test_failed_persistence_is_not_acknowledged(self):
        with patch.object(queue, 'enqueue', side_effect=RuntimeError('unavailable')):
            self.assertEqual(self.post().status_code, 500)
        self.assertEqual(self.jobs(), [])

    def test_receipt_minimizes_payload_and_deduplicates_before_processing(self):
        payload = {'shop_domain': 'synthetic.myshopify.com', 'orders_requested': [123],
            'customer': {'email': 'private@example.test', 'address': 'private'}, 'data_request': {'id': 456}}
        self.assertEqual(self.post('customers/data_request', payload).status_code, 200)
        self.assertEqual(self.post('customers/data_request', payload).status_code, 200)
        self.assertEqual(len(self.jobs()), 1)
        self.assertEqual(self.jobs()[0].payload, {'orders_requested': ['123'], 'data_request': {'id': '456'}})

    def test_failure_retries_are_delayed_and_bounded(self):
        self.post()
        now = time.time() + 1
        with patch.object(queue.privacy, 'redact_shop', side_effect=RuntimeError('sensitive text')):
            for attempt in range(1, queue.MAX_ATTEMPTS + 1):
                self.assertTrue(queue.process_one(self.factory, now=now))
                job = self.jobs()[0]
                self.assertEqual(job.attempts, attempt)
                self.assertEqual(job.error, 'RuntimeError')
                self.assertFalse(queue.process_one(self.factory, now=now))
                now = job.due_at + 1
            self.assertEqual(job.status, 'failed')
            self.assertFalse(queue.process_one(self.factory, now=now + 10000))

    def test_restart_recovers_expired_lease_but_does_not_steal_active_work(self):
        self.post()
        now = time.time() + 1
        with self.factory() as db:
            job = db.scalar(select(Job))
            job.status, job.attempts, job.lease_until, job.lease_token = 'running', 1, now + 60, 'old-worker'
            db.commit()
        with patch.object(queue.privacy, 'redact_shop', return_value={}):
            self.assertFalse(queue.process_one(self.factory, now=now))
            self.assertTrue(queue.process_one(self.factory, now=now + 61))
        self.assertEqual((self.jobs()[0].status, self.jobs()[0].attempts), ('done', 2))

    def test_final_attempt_crash_is_marked_failed(self):
        self.post()
        with self.factory() as db:
            job = db.scalar(select(Job))
            job.status, job.attempts, job.lease_until = 'running', queue.MAX_ATTEMPTS, 0
            db.commit()
        self.assertFalse(queue.process_one(self.factory))
        self.assertEqual((self.jobs()[0].status, self.jobs()[0].error), ('failed', 'lease_expired'))

    def test_concurrent_workers_only_execute_one_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine('sqlite:///' + directory + '/queue.db')
            Job.__table__.create(engine)
            factory = sessionmaker(engine, expire_on_commit=False)
            queue.enqueue(factory, topic='shop/redact', domain='synthetic.myshopify.com',
                          payload={}, webhook_id='concurrent-test')
            def work(*args, **kwargs):
                time.sleep(0.05)
                return {}
            with patch.object(queue.privacy, 'redact_shop', side_effect=work) as action:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda _: queue.process_one(factory), range(4)))
                self.assertEqual(sum(results), 1)
                action.assert_called_once()
            engine.dispose()
