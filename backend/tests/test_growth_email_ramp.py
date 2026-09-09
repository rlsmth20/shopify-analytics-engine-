"""Real local ledger/dispatch integration; no external addresses or providers."""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth import email_ramp as ramp, outreach_email as mail
from app.growth.engine import bootstrap
from app.growth.models import Contact, Evidence, Experiment, FirstContact, Message, Work
from app.growth.outbound import status as outreach_status
from app.growth.policy import GrowthError
from app.growth.review_calendar import REVIEW_TIMEZONE, review_day
from app.growth.store import digest, finish, get_memory, remember

SENDER = 'rainer@outreach.skubase.io'


class EmailRampTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'ramp.db'), connect_args={'timeout': 15})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        self.env = patch.dict('os.environ', {
            'OUTREACH_PROVIDER': 'fixture', 'OUTREACH_EMAIL_ENABLED': 'true',
            'OUTREACH_SAFE_TEST_MODE': 'false', 'OUTREACH_SENDER': SENDER, 'OUTREACH_REPLY_TO': SENDER,
            'OUTREACH_TEST_ADDRESSES': 'test@fixture.test', 'BUSINESS_NAME': 'Test Only',
            'BUSINESS_POSTAL_ADDRESS': 'Fixture, not real', 'OUTREACH_UNSUBSCRIBE_SECRET': '0' * 40})
        self.env.start()
        with self.factory() as db:
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': None})
            remember(db, 'strategic', 'outreach_provider_approval', {
                'provider': 'fixture', 'terms_verified': True, 'source': 'fixture', 'account_verified': True,
                'cost_authorized': True, 'domain_verified': True, 'inbound_verified': True, 'safe_test_verified': True})
            remember(db, 'strategic', 'email_authentication', {'identities': {SENDER: {
                'spf': True, 'dkim': True, 'dmarc': True, 'verified_at': time.time(), 'source': 'fixture headers'}}})
            remember(db, 'strategic', 'outreach_email_pilot', {'active': True, 'max_messages': 100, 'started_at': 1})
            remember(db, 'working', 'outreach_inbox_cursor', {'checked_at': time.time()})
            exp = Experiment(key='ramp-fixture', specification={}, stop_at=time.time() + 100 * 86400)
            db.add(exp); db.flush(); self.campaign = exp.id
            for n in range(30):
                db.add(Contact(id=str(n), identity='fixture:' + str(n), email=f'merchant{n}@fixture.test',
                    source='https://fixture.test', qualification={'eligible': True, 'qualified': True},
                    facts=[{'verified': True, 'source': 'https://fixture.test', 'text': 'Physical products'}]))
            db.commit()

    def tearDown(self):
        self.env.stop(); self.engine.dispose(); self.temp.cleanup()

    def prepared(self, n, **extra):
        with self.factory() as db:
            result = mail.queue_email(db, {'prospect_id': str(n), 'recipient': f'merchant{n}@fixture.test',
                'campaign_id': self.campaign, 'subject': 'Inventory question', 'body': 'Which inventory issue matters?',
                'cohort': {'icp': 'physical', 'offer': 'discovery', 'message_version': '1', 'hook': 'inventory', 'source': 'fixture'}, **extra})
            work = db.scalar(select(Work).where(Work.key == 'outreach-send:' + result['message_id']))
            work.status = 'running'; work.lease_token = 'fixture'; work.lease_until = time.time() + 300; work.attempts = 1
            remember(db, 'working', 'outreach_email_pacing', {'next_send_at': 0})
            db.commit()
            return work

    def sent(self, n):
        work = self.prepared(n)
        mail.send(self.factory, work, transport=lambda _: {'provider_id': 'fixture-' + str(n)})
        return work.payload['message_id']

    def ledger(self, db, n, at, *, channel='email', status='sent', sender=SENDER, kind='first_contact', safe=False):
        db.add(FirstContact(contact_id='ledger-' + str(n), action_key='ledger-' + str(n), channel=channel,
            experiment_id=self.campaign, cohort={}, body_hash='fixture', reserved_at=at,
            sent_at=at if status == 'sent' else None, status=status, receipt='fixture' if status == 'sent' else None))
        row = Message(key='ledger-' + str(n), contact_id='ledger-' + str(n), experiment_id=self.campaign,
                      direction='out', body='fixture', status='delivered', sent_at=at)
        db.add(row); db.flush()
        remember(db, mail.META, row.id, {'kind': kind, 'safe_test': safe, 'sender': sender})

    def test_cap_defers_without_spending_retries_or_reserving_prospect(self):
        for n in range(5):
            self.sent(n)
        work = self.prepared(5)
        transport = Mock()
        result = mail.send(self.factory, work, transport=transport)
        self.assertEqual(result['decision'], 'email_ramp_daily_ceiling')
        self.assertEqual(result['confirmed_first_contacts'], 5)
        finish(self.factory, work, result=result)
        transport.assert_not_called()
        with self.factory() as db:
            self.assertEqual(db.get(Work, work.id).attempts, 0)
            self.assertEqual(db.get(Work, work.id).status, 'ready')
            self.assertEqual(db.get(Message, work.payload['message_id']).status, 'draft')
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 5)
            self.assertEqual(ramp.status(db, SENDER)['actual_first_contacts_today'], 5)

    def test_midnight_counts_only_actual_email_not_forms_or_uncertainty(self):
        now = datetime(2026, 9, 10, 0, 5, tzinfo=REVIEW_TIMEZONE).timestamp()
        with self.factory() as db:
            self.ledger(db, 0, review_day(now).start - 1)
            self.ledger(db, 1, now - 1)
            self.ledger(db, 2, now - 1, channel='contact_form')
            self.ledger(db, 3, now - 1, status='uncertain')
            self.ledger(db, 4, now - 1, status='reserved')
            db.commit()
            result = ramp.status(db, SENDER, now, persist=True)
            db.commit()
        with self.factory() as db:
            self.assertEqual(ramp.status(db, SENDER, now)['actual_first_contacts_today'], 1)
            self.assertEqual(result['remaining'], 4)
            self.assertEqual(get_memory(db, ramp.NAMESPACE, digest(SENDER))['day'], '2026-09-10')

    def test_idle_does_not_advance_and_each_tier_requires_new_evidence(self):
        start = datetime(2026, 8, 1, 12, tzinfo=REVIEW_TIMEZONE).timestamp()
        with self.factory() as db:
            ramp.status(db, SENDER, start, persist=True, confirmed_at=start)
            db.commit()
            idle = ramp.status(db, SENDER, start + 30 * 86400, persist=True)
            self.assertEqual(idle['daily_ceiling'], 5)
            db.commit()
            tier_start = start + 30 * 86400
            for stage, (duration, expected) in enumerate(zip((3, 3, 4, 4), (8, 12, 15, 20))):
                for offset in range(3):
                    self.ledger(db, stage * 3 + offset, tier_start + offset * 86400)
                now = tier_start + duration * 86400
                remember(db, 'working', 'outreach_inbox_cursor', {'checked_at': now})
                db.flush()
                result = ramp.status(db, SENDER, now, persist=True)
                self.assertEqual(result['daily_ceiling'], expected)
                self.assertEqual(ramp.status(db, SENDER, now, persist=True)['daily_ceiling'], expected)
                db.commit()
                tier_start = now
            self.assertTrue(result['complete'])
            self.assertEqual(result['normal_daily_ceiling'], 20)

    def test_new_sender_never_inherits_gmail_evidence_and_unknown_auth_fails_closed(self):
        now = time.time()
        with self.factory() as db:
            for n in range(3):
                self.ledger(db, n, now - (n + 1) * 86400, sender='info@skubase.io')
            ramp.status(db, 'info@skubase.io', now - 10 * 86400, persist=True, confirmed_at=now - 10 * 86400)
            db.commit()
            result = ramp.status(db, SENDER, now, persist=True)
            self.assertIsNone(result['start_at'])
            self.assertEqual(result['stage_evidence']['confirmed'], 0)
            remember(db, 'strategic', 'email_authentication', {'identities': {}}); db.commit()
            self.assertIn('EMAIL_AUTHENTICATION_NOT_VERIFIED', mail.readiness(db)['blockers'])
        work = self.prepared(0); transport = Mock()
        with self.assertRaisesRegex(GrowthError, 'EMAIL_AUTHENTICATION_NOT_VERIFIED'):
            mail.send(self.factory, work, transport=transport)
        transport.assert_not_called()

    def test_every_adverse_signal_freezes_increases_and_replay_is_idempotent(self):
        start = time.time() - 4 * 86400
        with self.factory() as db:
            ramp.status(db, SENDER, start, persist=True, confirmed_at=start)
            for n in range(3): self.ledger(db, n, start + n * 86400)
            for kind in ('bounce', 'unsubscribe', 'delivery_failure', 'provider_warning'):
                ramp.signal(db, SENDER, kind, kind, time.time())
                ramp.signal(db, SENDER, kind, kind, time.time() + 1)
            result = ramp.status(db, SENDER, persist=True); db.commit()
            self.assertTrue(result['increase_paused'])
            self.assertEqual(result['daily_ceiling'], 5)
            self.assertEqual(len(result['recent_indicators']), 4)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == 'EMAIL_RAMP_SIGNAL')), 4)

    def test_bounce_is_permanent_suppression_and_freezes_increases(self):
        mid = self.sent(0)
        with self.factory() as db:
            mail.process_event(db, 'hard-bounce', {'type': 'bounce', 'provider_id': 'fixture-0', 'recipient': 'merchant0@fixture.test'})
            db.commit()
            self.assertTrue(db.get(Contact, '0').suppressed)
            self.assertEqual(db.get(Message, mid).status, 'bounced')
            self.assertIn('bounce', ramp.status(db, SENDER)['recent_indicators'])

    def test_reply_and_safe_test_do_not_use_cap_and_pilot_completion_is_explicit(self):
        first = self.sent(0)
        for n in range(1, 5): self.sent(n)
        with self.factory() as db:
            reply = mail.ingest_reply(db, 'inbound', provider_id='inbound', parent_provider_id='fixture-0',
                sender='merchant0@fixture.test', recipient=SENDER, subject='Question', body='Can I try it?')
            remember(db, 'strategic', 'outreach_email_pilot', {'active': True, 'max_messages': 1, 'started_at': 1})
            db.commit()
        replywork = self.prepared(0, kind='reply', reply_to_id=reply['message_id'])
        result = mail.send(self.factory, replywork, transport=lambda _: {'provider_id': 'reply-sent'})
        self.assertEqual(result['decision'], 'provider_accepted')
        with patch.dict('os.environ', {'OUTREACH_SAFE_TEST_MODE': 'true'}):
            testwork = self.prepared(6)
            mail.send(self.factory, testwork, transport=lambda _: {'provider_id': 'test-sent'})
        with self.factory() as db:
            self.assertEqual(ramp.status(db, SENDER)['actual_first_contacts_today'], 5)
            self.assertFalse(ramp.pilot_completed({'completed': True}))
            remember(db, 'strategic', 'outreach_email_pilot', {'active': False, 'completed': True, 'successful': True,
                'completed_at': time.time(), 'source': 'owner-reviewed actual pilot receipts'})
            db.commit()
            self.assertNotIn('LIVE_PILOT_NOT_ACTIVE', mail.readiness(db)['blockers'])

    def test_concurrent_dispatch_cannot_take_two_last_slots(self):
        for n in range(4): self.sent(n)
        first, second = self.prepared(4), self.prepared(5)
        entered, release = threading.Event(), threading.Event()
        def transport(_):
            entered.set()
            self.assertTrue(release.wait(10))
            return {'provider_id': 'last-slot'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(mail.send, self.factory, first, transport=transport)
            self.assertTrue(entered.wait(10))
            with self.factory() as db:
                remember(db, 'working', 'outreach_email_pacing', {'next_send_at': 0}); db.commit()
            denied_transport = Mock()
            result = mail.send(self.factory, second, transport=denied_transport)
            self.assertEqual(result['decision'], 'SEND_IN_FLIGHT')
            denied_transport.assert_not_called()
            release.set(); future.result(timeout=10)
        with self.factory() as db:
            self.assertEqual(ramp.status(db, SENDER)['actual_first_contacts_today'], 5)

    def test_late_uncertain_confirmation_counts_once_and_blocks_future_dispatch(self):
        work = self.prepared(0)
        mail.send(self.factory, work, transport=lambda _: {'provider_id': 'uncertain', 'queued': True})
        for n in range(1, 6): self.sent(n)
        with self.factory() as db:
            self.assertEqual(ramp.status(db, SENDER)['actual_first_contacts_today'], 5)
            self.assertEqual(outreach_status(db)['uncertain_contact_count'], 1)
            for _ in range(2):
                mail.process_event(db, 'late', {'type': 'accepted', 'provider_id': 'uncertain', 'recipient': 'merchant0@fixture.test'})
            db.commit()
            self.assertEqual(ramp.status(db, SENDER)['late_confirmation_overage'], 1)
        denied = Mock()
        result = mail.send(self.factory, self.prepared(6), transport=denied)
        self.assertEqual(result['decision'], 'email_ramp_daily_ceiling')
        denied.assert_not_called()

    def test_signed_provider_failure_work_reaches_ramp_and_ignores_other_mailbox(self):
        work = self.prepared(0)
        with self.factory() as db:
            event = Evidence(key='provider-warning-fixture', kind='OUTREACH_WEBHOOK', subject='fixture',
                source='signature_verified_fixture', data={'id': 'evt_fail', 'type': 'mailbox.failed', 'data': {'id': 'mb_fixture'}})
            db.add(event); db.flush()
            row = db.get(Work, work.id); row.payload = {'evidence_id': event.id}; db.commit(); work = row
        with patch.dict('os.environ', {'OUTREACH_EMAILPAL_MAILBOX_ID': 'mb_other'}):
            self.assertEqual(mail.handle_webhook(self.factory, work)['receipt_checks_queued'], 0)
        with patch.dict('os.environ', {'OUTREACH_EMAILPAL_MAILBOX_ID': 'mb_fixture'}):
            self.assertEqual(mail.handle_webhook(self.factory, work)['signal_recorded'], 'provider_restriction')
            self.assertTrue(mail.handle_webhook(self.factory, work)['duplicate'])
        with self.factory() as db:
            self.assertIn('PROVIDER_RESTRICTION', mail.readiness(db)['blockers'])

    def test_unrelated_setup_bounce_does_not_contaminate_outreach_health(self):
        with self.factory() as db:
            mail.suppress(db, 'support@emailpal.io', 'bounce', 'fixture unrelated Gmail setup query')
            db.commit()
            self.assertEqual(ramp.status(db, SENDER)['recent_indicators'], {})

    def test_bounce_receipt_never_advances_tier_before_its_negative_is_applied(self):
        work = self.prepared(0)
        mail.send(self.factory, work, transport=lambda _: {'provider_id': 'queued-bounce', 'queued': True})
        now = time.time()
        with self.factory() as db:
            state = get_memory(db, ramp.NAMESPACE, digest(SENDER))
            remember(db, ramp.NAMESPACE, digest(SENDER), {**state, 'start_at': now - 4 * 86400, 'stage_started_at': now - 4 * 86400})
            for n in range(3): self.ledger(db, n, now - (n + 1) * 86400)
            db.flush()
            mail.process_event(db, 'bounce-at-increase', {'type': 'bounce', 'provider_id': 'queued-bounce', 'recipient': 'merchant0@fixture.test'})
            db.commit()
            result = ramp.status(db, SENDER, persist=True)
            self.assertEqual(result['daily_ceiling'], 5)
            self.assertIn('bounce', result['recent_indicators'])

    def test_invalid_recipient_syntax_rejected_without_paid_enrichment(self):
        for invalid in ('user@store..com', '.user@store.com', 'user..name@store.com', 'user@-store.com', 'user@store-.com', 'x' * 65 + '@store.com'):
            with self.subTest(recipient=invalid), self.assertRaisesRegex(GrowthError, 'INVALID_ADDRESS'):
                mail.address(invalid)
        self.assertEqual(mail.address('team+inventory@shop.fixture.test'), 'team+inventory@shop.fixture.test')
