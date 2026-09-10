"""Workspace admission, accounting and reply integration without browser sends."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth.models import Contact, Experiment, FirstContact, Message
from app.growth import outbound, outreach_email, workspace_mail
from app.growth.messaging import ingest_reply
from app.growth.policy import GrowthError
from app.growth.store import digest, get_memory, record, remember


class WorkspaceTests(unittest.TestCase):
    def test_gmail_layout_preserves_words_and_escapes_merchant_text(self):
        body = 'We noticed A & B sells <special> products. Skubase helps prioritize reorders. Would a free check be useful?'
        plain, html = workspace_mail.format_message(body, {'name': 'Skubase', 'postal_address': 'Fixture address'})
        self.assertIn('\n\nWould a free check be useful?\n\nRainer\nSkubase\n\nFixture address', plain)
        self.assertEqual(' '.join(plain.split())[:len(body)], body)
        self.assertIn('A &amp; B sells &lt;special&gt;', html)
        self.assertNotIn('<special>', html)
        self.assertIn('<div><br></div><div>Would a free check be useful?</div>', html)
        self.assertIn('<div>Rainer</div><div>Skubase</div>', html)

    def setUp(self):
        self.env = patch.dict('os.environ', {'GROWTH_MAILBOX': 'info@skubase.io'})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'mail.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            proof = record(db, 'auth-fixture', 'EMAIL_AUTHENTICATION_TEST', 'info@skubase.io', {})
            remember(db, 'strategic', 'email_transport', {'provider': 'google_workspace', 'enabled': True,
                'sender': 'info@skubase.io', 'transport_test_evidence_id': proof.id})
            remember(db, 'strategic', 'email_business_identity', {'name': 'Fixture', 'postal_address': 'Test address'})
            remember(db, 'strategic', 'email_authentication', {'identities': {'info@skubase.io': {
                'spf': True, 'dkim': True, 'dmarc': True, 'source': 'received headers',
                'verified_at': time.time(), 'evidence_id': proof.id}}})
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': None})
            exp = Experiment(key='workspace-fixture', specification={'channel': 'email'}, stop_at=time.time()+86400)
            db.add(exp); db.flush(); self.exp = exp.id
            db.commit()

    def tearDown(self):
        self.env.stop(); self.engine.dispose(); self.temp.cleanup()

    def reserve(self, n, **overrides):
        with self.factory() as db:
            result = outbound.operator_action(db, 'outreach-reserve', {
                'identity': f'https://merchant{n}.test', 'organization': f'Merchant {n}',
                'source': f'https://merchant{n}.test', 'qualified': True,
                'facts': [{'verified': True, 'source': f'https://merchant{n}.test', 'text': 'Sells physical goods'}],
                'relevance_evidence': 'Shopify physical goods store', 'channel_rules_source': 'https://merchant.test/contact',
                'channel': 'email', 'action_key': f'workspace-{n}', 'experiment_id': self.exp,
                'body': 'Is reordering a problem for your store?', 'subject': 'Inventory question',
                'recipient': f'hello@merchant{n}.test', 'email_source': f'https://merchant{n}.test/contact',
                'cohort': {'icp': 'physical', 'offer': 'discovery', 'message_version': '1'}, **overrides})
            db.commit(); return result

    def finish(self, result, outcome='sent'):
        with self.factory() as db:
            outbound.authorize_submission(db, result['reservation_id'])
            outbound.complete(db, result['reservation_id'], outcome=outcome,
                receipt='https://mail.google.com/mail/u/4/#sent/' + result['message_id'] if outcome == 'sent' else None)
            db.commit()

    def test_full_ledger_flow_starts_ramp_only_after_real_receipt(self):
        result = self.reserve(1)
        self.assertEqual(result['email']['sender'], 'info@skubase.io')
        self.assertIn('Rainer\nFixture\n\nTest address\n\nTo opt out, reply unsubscribe.', result['email']['body'])
        with self.factory() as db:
            self.assertIsNone(workspace_mail.status(db)['ramp']['start_at'])
            message = db.get(Message, result['message_id'])
            self.assertEqual(db.get(Contact, message.contact_id).email, 'hello@merchant1.test')
        self.finish(result)
        with self.factory() as db:
            view = outreach_email.readiness(db)
            self.assertTrue(view['ready'])
            self.assertEqual(view['provider'], 'google_workspace')
            self.assertEqual(view['ramp']['actual_first_contacts_today'], 1)
            self.assertIsNotNone(view['ramp']['start_at'])
            self.assertEqual(db.get(Message, result['message_id']).body, result['email']['body'])
        with self.assertRaises(GrowthError): self.reserve(1)

    def test_email_cap_defers_without_a_model_turn_and_other_work_continues(self):
        from app.growth import browser_executor, operator
        with self.factory() as db:
            for n in range(5):
                db.add(FirstContact(contact_id='sent-'+str(n), action_key='sent-'+str(n),
                    channel='email', experiment_id=self.exp, cohort={}, body_hash='fixture',
                    status='sent', sent_at=time.time()))
            proof=record(db,'defer-fixture','OBSERVATION','fixture',{})
            email=operator.offer(db,key='email-next',source='https://fixture.test',stage='send',
                decision='channel=email; Send the prepared business inquiry.',priority=100,evidence_id=proof.id)
            discovery=operator.offer(db,key='other-discovery',source='https://fixture.test',stage='discover',
                decision='Explore another channel',priority=10,evidence_id=proof.id)
            db.commit()
        task=browser_executor.take(self.factory,'worker')
        self.assertEqual(task['id'],discovery['id'])
        with self.factory() as db:
            deferred=get_memory(db,'operator_task',email['id'])
            self.assertEqual(deferred['attempts'],0)
            self.assertEqual(deferred['defer_reason'],'EMAIL_DAILY_CAP_REACHED')
            self.assertEqual(workspace_mail.defer_capped_tasks(db),0)
            self.assertEqual(outbound.status(db)['sent'],5)
        browser_executor.accept(self.factory,'worker',task,{'outcome':'done','observation':'Fixture channel search complete',
            'sources':['https://fixture.test'],'next_step':'Select another hypothesis','stop_reason':None,'successors':[]})
        self.assertEqual(browser_executor.take(self.factory,'planner')['stage'],'plan')
        with patch('time.time',return_value=deferred['retry_at']+1), self.factory() as db:
            packet=operator.export_packet(db)
            self.assertIn(email['id'],[t['id'] for t in packet['tasks']])

    def test_email_deferral_preserves_replies_forms_and_uncertain_intents(self):
        from app.growth import operator
        with self.factory() as db:
            for n in range(5):
                db.add(FirstContact(contact_id='sent-'+str(n), action_key='sent-'+str(n),
                    channel='email', experiment_id=self.exp, cohort={}, body_hash='fixture',status='sent',sent_at=time.time()))
            db.add(FirstContact(contact_id='unknown',action_key='unknown',channel='email',
                experiment_id=self.exp,cohort={},body_hash='fixture',status='uncertain'))
            proof=record(db,'defer-fixture','OBSERVATION','fixture',{})
            tasks=[]
            for key,stage,decision,cid in [('reply','reply','channel=email','engaged'),
                    ('form','send','channel=contact_form',None),('receipt','send','channel=email','unknown')]:
                tasks.append(operator.offer(db,key=key,stage=stage,source='https://fixture.test',
                    decision=decision,contact_id=cid,evidence_id=proof.id))
            db.commit()
            self.assertEqual(workspace_mail.defer_capped_tasks(db),0)
            for task in tasks:
                self.assertNotIn('defer_reason',get_memory(db,'operator_task',task['id']))

    def test_email_ceiling_does_not_cap_other_channels(self):
        for n in range(5): self.finish(self.reserve(n))
        with self.assertRaisesRegex(GrowthError, 'EMAIL_RAMP_DAILY_CEILING'): self.reserve(5)
        self.reserve(6, channel='contact_form')

    def test_uncertain_contacts_do_not_consume_capacity_or_allow_retry(self):
        first = self.reserve(1); self.finish(first, 'uncertain')
        with self.factory() as db:
            self.assertEqual(workspace_mail.status(db)['ramp']['remaining'], 5)
            with self.assertRaises(GrowthError): outbound.authorize_submission(db, first['reservation_id'])
        with self.assertRaises(GrowthError): self.reserve(1)
        self.finish(self.reserve(2))

    def test_final_authorization_rechecks_optout_and_authentication(self):
        item = self.reserve(1)
        with self.factory() as db:
            outreach_email.suppress(db, 'hello@merchant1.test', 'unsubscribe', 'fixture'); db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError): outbound.authorize_submission(db, item['reservation_id'])

    def test_optout_threading_and_permanent_suppression(self):
        item = self.reserve(1); self.finish(item)
        with self.factory() as db:
            reply = ingest_reply(db, provider_id='fixture-reply', sender='hello@merchant1.test',
                recipients=['info@skubase.io'], text='unsubscribe')
            db.commit()
            self.assertEqual(reply.reply_to_id, item['message_id'])
            self.assertEqual(reply.experiment_id, self.exp)
            self.assertTrue(get_memory(db, 'email_suppression', digest('hello@merchant1.test')))
            self.assertTrue(db.get(Contact, reply.contact_id).suppressed)
            self.assertTrue(workspace_mail.status(db)['ramp']['increase_paused'])

    def test_wrong_sender_invalid_address_and_missing_proof_fail_closed(self):
        for override in ({'sender': 'personal@gmail.com'}, {'recipient': 'bad'}, {'recipient': 'support@skubase.io'}):
            with self.subTest(override=override), self.assertRaises(GrowthError): self.reserve(1, **override)
        with self.factory() as db:
            remember(db, 'strategic', 'email_authentication', {}); db.commit()
        with self.assertRaisesRegex(GrowthError, 'AUTHENTICATION'): self.reserve(1)

    def test_no_fallback_to_paid_provider(self):
        transport = Mock()
        with self.assertRaises(GrowthError): outreach_email.send(self.factory, None, transport=transport)
        transport.assert_not_called()
        with self.factory() as db:
            with self.assertRaises(GrowthError): outreach_email.queue_email(db, {})

    def test_invalid_receipt_is_not_counted(self):
        item = self.reserve(1)
        with self.factory() as db:
            with self.assertRaises(GrowthError):
                outbound.complete(db, item['reservation_id'], receipt='https://merchant1.test/contact')
            db.rollback()
            self.assertEqual(outbound.status(db)['sent'], 0)

    def test_late_confirmation_blocks_pending_email_at_final_authorization(self):
        uncertain = self.reserve(0); self.finish(uncertain, 'uncertain')
        for n in range(1, 5): self.finish(self.reserve(n))
        pending = self.reserve(5)
        with self.factory() as db:
            outbound.complete(db, uncertain['reservation_id'],
                receipt='https://mail.google.com/mail/u/4/#sent/reconciled'); db.commit()
        with self.factory() as db:
            with self.assertRaisesRegex(GrowthError, 'EMAIL_RAMP_DAILY_CEILING'):
                outbound.authorize_submission(db, pending['reservation_id'])

    def test_proven_no_effect_releases_intent_without_erasing_history(self):
        item = self.reserve(1); self.finish(item, 'uncertain')
        with self.factory() as db:
            evidence = record(db, 'no-effect-fixture', 'OUTREACH_NOT_SENT_VERIFIED', item['reservation_id'],
                {'no_external_effect': True, 'reason': 'Fixture: draft never submitted'}, source='owner_operator')
            outbound.reconcile_not_sent(db, item['reservation_id'], evidence.id); db.commit()
            self.assertEqual(db.get(Message, item['message_id']).status, 'not_sent')
        self.reserve(1)


if __name__ == '__main__':
    unittest.main()
