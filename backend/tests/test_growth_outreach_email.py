"""Dedicated cold-email workflow, entirely isolated from providers and merchants."""
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.api.deps import get_current_user
from app.api.routes.growth import router
from app.db.session import get_db_session
from app.growth.engine import bootstrap
from app.growth import engine as growth_engine
from app.growth.identity import link_merchant
from app.growth.models import Contact, Evidence, Experiment, FirstContact, Message, Usage, Work
from app.growth import outreach_email as mail
from app.growth.outbound import status
from app.growth.policy import GrowthError
from app.growth.store import get_memory, remember


class OutreachEmailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'email.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        self.env = patch.dict('os.environ', {
            'OUTREACH_PROVIDER': 'fixture', 'OUTREACH_EMAIL_ENABLED': 'true',
            'OUTREACH_SAFE_TEST_MODE': 'false', 'OUTREACH_SENDER': 'rainer@outreach.skubase.io',
            'OUTREACH_REPLY_TO': 'rainer@outreach.skubase.io', 'OUTREACH_TEST_ADDRESSES': 'test@fixture.test',
            'BUSINESS_NAME': 'Fixture Business', 'BUSINESS_POSTAL_ADDRESS': 'Fixture address, test only',
            'OUTREACH_UNSUBSCRIBE_SECRET': 'test-only-secret-never-a-real-credential-0000',
        })
        self.env.start()
        with self.factory() as db:
            remember(db, 'strategic', 'outreach_provider_approval', {
                'provider': 'fixture', 'terms_verified': True, 'source': 'https://fixture.test/terms',
                'account_verified': True, 'cost_authorized': True, 'domain_verified': True,
                'inbound_verified': True, 'safe_test_verified': True})
            remember(db, 'strategic', 'outreach_email_pilot', {'active': True, 'max_messages': 50, 'started_at': time.time() - 10})
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': None})
            remember(db, 'strategic', 'email_authentication', {'identities': {'rainer@outreach.skubase.io': {
                'spf': True, 'dkim': True, 'dmarc': True, 'verified_at': time.time(), 'source': 'fixture headers'}}})
            remember(db, 'working', 'outreach_inbox_cursor', {'checked_at': time.time()})
            exp = Experiment(key='email-fixture', specification={'followups_enabled': True}, stop_at=time.time() + 864000)
            db.add(exp); db.flush(); self.campaign = exp.id
            for n in range(4):
                db.add(Contact(id=str(n), identity='merchant:' + str(n), email=f'merchant{n}@fixture.test',
                    source='https://fixture.test/store', qualification={'eligible': True, 'qualified': True},
                    facts=[{'verified': True, 'source': 'https://fixture.test/store', 'text': 'Fixture physical store'}]))
            db.commit()

    def tearDown(self):
        self.env.stop(); self.engine.dispose(); self.temp.cleanup()

    def payload(self, n=0, **extra):
        return {'prospect_id': str(n), 'recipient': f'merchant{n}@fixture.test', 'campaign_id': self.campaign,
            'subject': 'Inventory question', 'body': 'Is stockout or overstock the bigger issue for your store?',
            'cohort': {'icp': 'physical-shopify', 'offer': 'discovery', 'message_version': 'fixture1',
                       'hook': 'inventory-risk', 'source': 'https://fixture.test/store'}, **extra}

    def queue(self, n=0, **extra):
        with self.factory() as db:
            result = mail.queue_email(db, self.payload(n, **extra)); db.commit()
            return result['message_id']

    def work(self, message_id):
        with self.factory() as db:
            row = db.scalar(select(Work).where(Work.key == 'outreach-send:' + message_id))
            row.status = 'running'; row.lease_token = 'fixture-lease-' + row.id[:12]
            row.lease_until = time.time() + 300; row.attempts = 1
            db.commit(); return row

    def clear_pacing(self):
        with self.factory() as db:
            remember(db, 'working', 'outreach_email_pacing', {'next_send_at': 0}); db.commit()

    def send(self, n=0, **extra):
        message_id = self.queue(n, **extra)
        mail.send(self.factory, self.work(message_id), transport=lambda _: {'provider_id': 'provider-' + message_id})
        return message_id

    def event(self, message_id, kind, key=None):
        with self.factory() as db:
            row = db.get(Message, message_id)
            result = mail.process_event(db, key or kind + '-' + message_id,
                {'provider_id': row.provider_id, 'recipient': f'merchant{row.contact_id}@fixture.test', 'type': kind})
            db.commit(); return result

    def api(self):
        app = FastAPI()
        app.include_router(router)
        def session():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db_session] = session
        return app

    def signed_webhook(self, client, event):
        raw = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(b'fixture-webhook-secret', timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return client.post('/growth/webhooks/emailpal', content=raw,
            headers={'EmailPal-Signature': 't=' + timestamp + ',v1=' + signature})

    def worker_step(self, expected_kind):
        # Advance local fixture timing, while the real queue selects and leases work.
        with self.factory() as db:
            db.execute(update(Work).where(Work.status == 'ready').values(due_at=0))
            remember(db, 'working', 'outreach_email_pacing', {'next_send_at': 0})
            db.commit()
        self.assertTrue(growth_engine.run_once(self.factory, schedule_wakes=False))
        with self.factory() as db:
            latest = db.scalar(select(Evidence).where(Evidence.kind == 'ACTION_RESULT').order_by(Evidence.id.desc()))
            self.assertEqual(latest.data['kind'], expected_kind)
            self.assertEqual(latest.data['status'], 'done', latest.data)
            return latest.data['result']

    def test_safe_mode_routes_only_to_test_address_without_merchant_accounting(self):
        with patch.dict('os.environ', {'OUTREACH_SAFE_TEST_MODE': 'true'}):
            message_id = self.queue()
            transport = Mock(return_value={'provider_id': 'safe-provider-id'})
            mail.send(self.factory, self.work(message_id), transport=transport)
            request = transport.call_args.args[0]
            self.assertEqual(request['recipient'], 'test@fixture.test')
            self.assertIn('Fixture address, test only', request['body'])
            self.assertIn('unsubscribe', request['body'])
        with self.factory() as db:
            row = db.get(Message, message_id)
            self.assertIsNone(row.sent_at)
            self.assertEqual(row.status, 'test_sent')
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 0)
            meta = get_memory(db, mail.META, row.id)
            self.assertEqual(meta['recipient'], 'merchant0@fixture.test')
            self.assertTrue(meta['safe_test'])
            self.assertFalse(db.get(Contact, '0').suppressed)
        # The isolated provider test must not permanently consume this merchant's live draft key.
        self.assertNotEqual(self.queue(), message_id)

    def test_missing_postal_identity_blocks_transport_without_reservation(self):
        message_id = self.queue()
        transport = Mock(return_value={'provider_id': 'must-not-send'})
        with patch.dict('os.environ', {'BUSINESS_POSTAL_ADDRESS': ''}):
            with self.assertRaisesRegex(GrowthError, 'BUSINESS_POSTAL_IDENTITY_REQUIRED'):
                mail.send(self.factory, self.work(message_id), transport=transport)
        transport.assert_not_called()
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 0)
            self.assertEqual(db.get(Message, message_id).status, 'draft')

    def test_queue_is_idempotent_and_preparation_does_not_consume_capacity(self):
        first = self.queue()
        second = self.queue(body='A new draft must not replace immutable queued copy')
        self.assertEqual(first, second)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Work).where(Work.kind == 'outreach_send')), 1)
            self.assertEqual(status(db)['sent'], 0)
            self.assertIn('stockout', db.get(Message, first).body)

    def test_signed_unsubscribe_suppresses_all_linked_routes_and_rejects_bad_token(self):
        with self.factory() as db:
            link_merchant(db, {'merchant_key': 'same-store', 'routes': [
                {'identity': 'merchant:' + str(n), 'channel': 'email', 'source': 'https://fixture.test/contact',
                 'relationship': 'Fixture store lists both business routes'} for n in (0, 1)]})
            db.commit()
        message_id = self.send()
        with self.factory() as db:
            with self.assertRaises(GrowthError): mail.unsubscribe(db, message_id, 'wrong-token')
            self.assertFalse(db.get(Contact, '0').suppressed)
            mail.unsubscribe(db, message_id, mail.unsubscribe_token(message_id)); db.commit()
            self.assertTrue(db.get(Contact, '0').suppressed)
            self.assertTrue(db.get(Contact, '1').suppressed)
            with self.assertRaisesRegex(GrowthError, 'SUPPRESSED'): mail.queue_email(db, self.payload(1))

    def test_timeout_retains_uncertain_contact_but_never_retries_external_effect(self):
        message_id = self.queue()
        work = self.work(message_id)
        transport = Mock(side_effect=TimeoutError('fixture timeout'))
        with self.assertRaisesRegex(GrowthError, 'reconciliation'):
            mail.send(self.factory, work, transport=transport)
        result = mail.send(self.factory, work, transport=transport)
        self.assertEqual(result['decision'], 'already_dispatched_or_uncertain')
        self.assertEqual(transport.call_count, 1)
        with self.factory() as db:
            self.assertEqual(status(db)['sent'], 0)
            self.assertEqual(status(db)['uncertain_contact_count'], 1)
        self.clear_pacing()
        other = self.send(1)
        with self.factory() as db:
            self.assertEqual(status(db)['sent'], 1)
            self.assertEqual(db.get(Message, other).status, 'sent')

    def test_confirmed_send_enforces_configured_ceiling_without_counting_drafts(self):
        with self.factory() as db:
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': 1}); db.commit()
        self.send()
        other = self.queue(1)
        self.clear_pacing()
        transport = Mock(return_value={'provider_id': 'must-not-send'})
        result = mail.send(self.factory, self.work(other), transport=transport)
        self.assertEqual(result['decision'], 'DAILY_CAP_REACHED')
        self.assertGreater(result['defer_until'], time.time())
        transport.assert_not_called()
        with self.factory() as db:
            self.assertEqual(status(db)['sent'], 1)
            self.assertEqual(db.get(Message, other).status, 'draft')

    def test_bounce_and_complaint_replays_preserve_terminal_suppression(self):
        for n, kind, terminal in ((0, 'bounce', 'bounced'), (1, 'complaint', 'complained')):
            with self.subTest(kind=kind):
                self.clear_pacing(); message_id = self.send(n)
                self.event(message_id, kind, key='terminal-' + str(n))
                replay = self.event(message_id, kind, key='terminal-' + str(n))
                self.assertTrue(replay['duplicate'])
                self.event(message_id, 'delivered', key='late-delivery-' + str(n))
                with self.factory() as db:
                    self.assertEqual(db.get(Message, message_id).status, terminal)
                    self.assertTrue(db.get(Contact, str(n)).suppressed)
        with self.factory() as db:
            self.assertIn('PROVIDER_COMPLAINT', mail.readiness(db)['blockers'])
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == 'OUTREACH_PROVIDER_EVENT')), 4)

    def test_threaded_reply_stops_prepared_followup_and_spoofed_sender_does_not_match(self):
        message_id = self.send(followup_body='Does that inventory question apply to your store?')
        with self.factory() as db:
            row = db.get(Message, message_id)
            row.sent_at = time.time() - 6 * 86400; db.commit()
            mail.schedule_followups(db); db.commit()
            followup = db.scalar(select(Message).where(Message.reply_to_id == message_id, Message.direction == 'out'))
            self.assertIsNotNone(followup); followup_id = followup.id
            args = {'provider_id': 'reply-1', 'parent_provider_id': row.provider_id,
                    'recipient': 'rainer@outreach.skubase.io', 'subject': 'Re: Inventory question',
                    'body': 'Does this handle stockouts?'}
            unmatched = mail.ingest_reply(db, 'spoofed', sender='wrong@fixture.test', **args)
            self.assertFalse(unmatched['matched'])
            reply = mail.ingest_reply(db, 'reply-event', sender='merchant0@fixture.test', **args)
            db.commit()
            self.assertEqual(reply['classification'], 'QUESTION')
            self.assertEqual(db.get(Message, reply['message_id']).reply_to_id, message_id)
            self.assertTrue(mail.ingest_reply(db, 'reply-event', sender='merchant0@fixture.test', **args)['duplicate'])
            db.commit()
        self.clear_pacing()
        transport = Mock(return_value={'provider_id': 'must-not-followup'})
        result = mail.send(self.factory, self.work(followup_id), transport=transport)
        self.assertEqual(result['decision'], 'followup_stopped')
        transport.assert_not_called()

    def test_provider_queue_receipt_is_not_sent_until_confirmed_event(self):
        message_id = self.queue()
        mail.send(self.factory, self.work(message_id), transport=lambda _: {'provider_id': 'queue-id', 'queued': True})
        with self.factory() as db:
            self.assertIsNone(db.get(Message, message_id).sent_at)
            self.assertEqual(status(db)['sent'], 0)
        self.event(message_id, 'accepted')
        with self.factory() as db:
            self.assertIsNotNone(db.get(Message, message_id).sent_at)
            self.assertEqual(status(db)['sent'], 1)

    def test_no_followup_promise_prevents_scheduled_followup(self):
        message_id = self.send(followup_body='Is this relevant?')
        with self.factory() as db:
            db.get(Message, message_id).sent_at = time.time() - 6 * 86400
            db.get(Contact, '0').characteristics = {'no_followup': True}
            db.commit()
            mail.schedule_followups(db)
            db.commit()
            self.assertIsNone(db.scalar(select(Message.id).where(Message.reply_to_id == message_id)))

    def test_metrics_exclude_test_intents_and_keep_unattributed_conversions_unknown(self):
        message_id = self.send()
        with self.factory() as db:
            row = db.get(Message, message_id)
            mail.ingest_reply(db, 'metrics-reply', provider_id='metrics-inbound', parent_provider_id=row.provider_id,
                sender='merchant0@fixture.test', recipient='rainer@outreach.skubase.io', subject='Re: Inventory question', body='Yes, send me access')
            db.commit()
            result = mail.metrics(db)['campaigns'][0]
            self.assertEqual(result['sent'], 1)
            self.assertEqual(result['reply_rate'], 1)
            self.assertIsNone(result['trials'])
            self.assertIsNone(result['customers'])
            meta = get_memory(db, mail.META, message_id)
            remember(db, mail.META, message_id, {**meta, 'safe_test_intent': True})
            db.commit()
            self.assertEqual(mail.metrics(db)['campaigns'], [])

    def test_signed_provider_delivery_can_race_http_receipt_without_double_count(self):
        message_id = self.queue()
        def transport(request):
            with self.factory() as db:
                mail.process_event(db, 'early-delivery', {'provider_id': 'racing-provider-id',
                    'client_id': request['idempotency_key'], 'recipient': request['recipient'], 'type': 'delivered'})
                db.commit()
            return {'provider_id': 'racing-provider-id'}
        mail.send(self.factory, self.work(message_id), transport=transport)
        with self.factory() as db:
            self.assertEqual(db.get(Message, message_id).status, 'delivered')
            self.assertEqual(status(db)['sent'], 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == 'OUTREACH_ACCEPTED')), 1)

    def test_queued_http_receipt_cannot_overwrite_racing_bounce(self):
        message_id = self.queue()
        def transport(request):
            with self.factory() as db:
                mail.process_event(db, 'early-bounce', {'provider_id': 'queued-race-id',
                    'client_id': request['idempotency_key'], 'recipient': request['recipient'], 'type': 'bounce'})
                db.commit()
            return {'provider_id': 'queued-race-id', 'queued': True, 'job_id': 'job-fixture'}
        mail.send(self.factory, self.work(message_id), transport=transport)
        with self.factory() as db:
            self.assertEqual(db.get(Message, message_id).status, 'bounced')
            self.assertTrue(db.get(Contact, '0').suppressed)
            self.assertEqual(status(db)['sent'], 1)

    def test_same_inbound_provider_message_under_new_event_id_is_idempotent(self):
        message_id = self.send()
        with self.factory() as db:
            row = db.get(Message, message_id)
            args = {'provider_id': 'same-inbound-id', 'parent_provider_id': row.provider_id,
                    'sender': 'merchant0@fixture.test', 'recipient': 'rainer@outreach.skubase.io',
                    'subject': 'Inventory', 'body': 'How much is it?'}
            first = mail.ingest_reply(db, 'delivery-1', **args); db.commit()
            second = mail.ingest_reply(db, 'delivery-2', **args); db.commit()
            self.assertTrue(second['duplicate'])
            self.assertEqual(first['message_id'], second['message_id'])

    def test_unthreaded_optout_from_known_merchant_still_suppresses(self):
        self.send()
        with self.factory() as db:
            mail.ingest_reply(db, 'unthreaded-optout', provider_id='inbound-no-thread', parent_provider_id=None,
                sender='merchant0@fixture.test', recipient='rainer@outreach.skubase.io', subject='Unsubscribe',
                body='Please unsubscribe me.')
            db.commit()
            self.assertTrue(db.get(Contact, '0').suppressed)

    def test_poll_preserves_actual_provider_send_time_in_confirmed_history(self):
        message_id = self.queue()
        work = self.work(message_id)
        mail.send(self.factory, work, transport=lambda _: {'provider_id': 'out-delayed', 'queued': True, 'job_id': 'job-delayed'})
        actual = int(time.time()) - 7200
        result = {'id': 'out-delayed', 'to': ['merchant0@fixture.test'], 'status': 'sent',
            'sent_at': datetime.fromtimestamp(actual, timezone.utc).isoformat(),
            'rfc_message_id': '<delayed@outreach.skubase.io>', 'delivery_status': 'delivered'}
        mail.poll(self.factory, work, fetch=lambda _: result)
        with self.factory() as db:
            self.assertEqual(db.get(Message, message_id).sent_at, actual)
            first_contact = db.scalar(select(FirstContact).where(FirstContact.contact_id == '0'))
            self.assertEqual(first_contact.sent_at, actual)

    def test_reply_unsubscribe_stops_future_email_and_does_not_queue_conversation_work(self):
        message_id = self.send()
        with self.factory() as db:
            row = db.get(Message, message_id)
            result = mail.ingest_reply(db, 'optout-reply', provider_id='unsubscribe-provider-id',
                parent_provider_id=row.provider_id, sender='merchant0@fixture.test',
                recipient='rainer@outreach.skubase.io', subject='Re: Inventory question', body='Please unsubscribe me.')
            db.commit()
            self.assertEqual(result['classification'], 'UNSUBSCRIBE')
            self.assertTrue(db.get(Contact, '0').suppressed)
            self.assertEqual(db.scalar(select(func.count()).select_from(Work).where(Work.kind == 'outreach_reply')), 0)

    def test_real_worker_queue_runs_send_reply_followup_stop_and_signed_optout_end_to_end(self):
        first_id = self.queue(followup_body='Is inventory planning something your team handles manually?')
        sent_requests = []
        def provider_send(request):
            sent_requests.append(request)
            return {'provider_id': 'out_' + str(len(sent_requests)), 'job_id': 'job_' + str(len(sent_requests)), 'queued': True}
        def provider_read(provider_id):
            return {'id': provider_id, 'to': ['merchant0@fixture.test'], 'status': 'sent',
                'sent_at': datetime.now(timezone.utc).isoformat(), 'delivery_status': 'delivered',
                'rfc_message_id': '<' + provider_id + '@outreach.skubase.io>'}
        inbound = {'id': 'msg_positive', 'status': 'ready', 'from': {'address': 'merchant0@fixture.test'},
            'to': ['rainer@outreach.skubase.io'], 'in_reply_to': '<out_1@outreach.skubase.io>',
            'subject': 'Re: Inventory question', 'body': {'text': 'Can I try it?'}, 'headers': {}}
        with patch('app.growth.outreach_provider.send_message', side_effect=provider_send), \
             patch('app.growth.outreach_provider.read_send', side_effect=provider_read), \
             patch('app.growth.outreach_provider.read_inbound', return_value=inbound), \
             patch.dict('os.environ', {'OUTREACH_EMAILPAL_WEBHOOK_SECRET': 'fixture-webhook-secret'}), \
             TestClient(self.api()) as client:
            self.assertEqual(self.worker_step('outreach_send')['decision'], 'provider_queued')
            with self.factory() as db:
                self.assertEqual(status(db)['sent'], 0)
            self.worker_step('outreach_poll')
            with self.factory() as db:
                self.assertEqual(status(db)['sent'], 1)
                db.get(Message, first_id).sent_at = time.time() - 6 * 86400
                db.commit()
                mail.schedule_followups(db); db.commit()
                followup = db.scalar(select(Message).where(Message.reply_to_id == first_id, Message.direction == 'out'))
                self.assertIsNotNone(followup); followup_id = followup.id
            event = {'id': 'evt_positive', 'type': 'message.received', 'data': {'id': 'msg_positive'}}
            for _ in range(2):
                self.assertEqual(self.signed_webhook(client, event).status_code, 202)
            with self.factory() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(Work).where(Work.key == 'emailpal-event:evt_positive')), 1)
            self.assertEqual(self.worker_step('outreach_event')['classification'], 'SUBSTANTIVE_POSITIVE')
            reply_id = self.worker_step('outreach_reply')['message_id']
            self.assertEqual(self.worker_step('outreach_send')['decision'], 'provider_queued')
            self.worker_step('outreach_poll')
            self.assertEqual(self.worker_step('outreach_send')['decision'], 'followup_stopped')
            self.assertEqual(len(sent_requests), 2)
            self.assertEqual(sent_requests[1]['parent_provider_id'], 'msg_positive')
            self.assertIn('inventory-health-check', sent_requests[1]['body'])
            with self.factory() as db:
                self.assertEqual(db.get(Message, reply_id).status, 'delivered')
                self.assertEqual(db.get(Message, followup_id).status, 'cancelled')
                self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(Usage)), 0)
            url = '/growth/outreach/unsubscribe/' + first_id + '?token=' + mail.unsubscribe_token(first_id)
            self.assertEqual(client.get(url).status_code, 200)
            with self.factory() as db:
                self.assertFalse(db.get(Contact, '0').suppressed)
            self.assertEqual(client.post(url).status_code, 200)
            with self.factory() as db:
                self.assertTrue(db.get(Contact, '0').suppressed)
                with self.assertRaisesRegex(GrowthError, 'SUPPRESSED'):
                    mail.queue_email(db, self.payload(body='Do not send another campaign'))

    def test_email_status_is_owner_only_and_unsigned_webhooks_never_enqueue(self):
        app = self.api()
        with TestClient(app) as client:
            self.assertEqual(client.get('/growth/email-status').status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)
            self.assertEqual(client.get('/growth/email-status').status_code, 403)
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=True)
            response = client.get('/growth/email-status')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['cache-control'])
            self.assertEqual(client.post('/growth/webhooks/emailpal', json={'id': 'fake'}).status_code, 401)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Work).where(Work.kind == 'outreach_event')), 0)
