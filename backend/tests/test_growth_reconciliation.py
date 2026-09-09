"""No network: exercise occupied-cap recovery and its lease/evidence fences."""
import time
import unittest
from sqlalchemy import select
import test_growth_execution
from app.growth import browser_executor as executor
from app.growth.execution import state
from app.growth.models import Contact, Evidence, FirstContact
from app.growth.operator import offer
from app.growth.outbound import status
from app.growth.policy import GrowthError
from app.growth.store import get_memory, record, remember


class ReconciliationTests(unittest.TestCase):
    setUp = test_growth_execution.ExecutionTests.setUp
    tearDown = test_growth_execution.ExecutionTests.tearDown
    result = test_growth_execution.ExecutionTests.result
    def reserve_fixture(self, n, sent=False, uncertain=False):
        with self.factory() as db:
            contact = Contact(identity=f'fixture:{n}', source='https://example.com/contact')
            db.add(contact); db.flush()
            row = FirstContact(contact_id=contact.id, action_key=f'fixture:{n}', channel='contact_form',
                experiment_id='fixture', cohort={}, body_hash='fixture', reserved_at=time.time()-1200,
                status='sent' if sent else 'uncertain' if uncertain else 'reserved',
                sent_at=time.time()-1000 if sent else None)
            db.add(row); db.flush()
            intent = record(db, 'first-contact-intent:' + row.id, 'FIRST_CONTACT_RESERVED', contact.id,
                {'reservation_id': row.id}, occurred_at=row.reserved_at)
            task = offer(db, key=f'send:{n}', source=contact.source, decision='Fixture send',
                contact_id=contact.id, stage='send', evidence_id=intent.id)
            proof = record(db, 'browser-stage:fixture' + str(n), 'ACQUISITION_STAGE_RESULT', task['id'],
                {'observation':'Fixture trace verifies no submission', 'stage':'send'})
            remember(db, 'operator_task', task['id'], {**task, 'status':'blocked', 'result_evidence_id':proof.id})
            db.commit()
            return row.id, proof.id

    def recovered(self, task, proof_id, outcome='not_sent'):
        result = self.result()
        result.update(stop_reason=None, submission={'reservation_id':task['reservation_id'],
            'outcome':outcome, 'reason':'Fixture action trace reviewed', 'evidence_ids':[proof_id], 'receipt':None})
        return result

    def test_full_capacity_selects_recovery_then_acquisition_after_restart(self):
        reservation, proof = self.reserve_fixture(0)
        self.reserve_fixture(1, uncertain=True)
        for n in range(2,20): self.reserve_fixture(n, sent=True)
        with self.factory() as db:
            self.assertEqual(state(db)['current_blocker'], 'OUTREACH_OUTCOMES_UNRESOLVED')
        task = executor.take(self.factory, 'recovery-process')
        self.assertEqual(task['stage'], 'reconcile')
        executor.accept(self.factory, 'recovery-process', task, self.recovered(task,proof))
        self.engine.dispose()
        successor = executor.take(self.factory, 'restarted-process')
        self.assertEqual(successor['stage'], 'prepare')
        self.assertEqual(successor['key'], 'after-release:' + reservation)
        with self.factory() as db:
            self.assertIsNone(db.get(FirstContact,reservation))
            self.assertEqual(status(db)['remaining'],1)
            self.assertEqual(status(db)['sent'],18)

    def test_uncertainty_never_releases_capacity_or_busy_loops(self):
        reservation, proof = self.reserve_fixture(0, uncertain=True)
        for n in range(1,20): self.reserve_fixture(n, sent=True)
        task = executor.take(self.factory, 'worker')
        with self.assertRaises(GrowthError):
            executor.accept(self.factory, 'worker', task, self.recovered(task,proof))
        executor.accept(self.factory, 'worker', task, self.recovered(task,proof,'uncertain'))
        successor = executor.take(self.factory,'worker')
        self.assertIsNone(successor)
        with self.factory() as db:
            self.assertEqual(db.get(FirstContact,reservation).status,'uncertain')
            self.assertEqual(status(db)['remaining'],0)

    def test_unrelated_evidence_cannot_release_and_live_owner_is_not_reconciled(self):
        reservation, proof = self.reserve_fixture(0)
        for n in range(1,20): self.reserve_fixture(n, sent=True)
        task = executor.take(self.factory, 'worker')
        with self.assertRaises(GrowthError):
            executor.accept(self.factory,'worker',task,self.recovered(task,99999))
        with self.factory() as db:
            self.assertIsNotNone(db.get(FirstContact,reservation))
        self.assertIsNone(executor.take(self.factory,'competitor'))

    def test_twenty_confirmed_reports_actual_cap(self):
        for n in range(20): self.reserve_fixture(n,sent=True)
        with self.factory() as db:
            self.assertEqual(state(db)['current_blocker'],'DAILY_CAP_REACHED')
            self.assertEqual(status(db)['sent'],20)
        self.assertIsNone(executor.take(self.factory,'worker'))

    def test_newly_failed_form_releases_capacity_without_regenerating_itself(self):
        from app.growth.operator import claim
        reservation, proof = self.reserve_fixture(0)
        with self.factory() as db:
            row = db.get(FirstContact,reservation)
            fresh = offer(db,key='fresh-send',source='https://example.com/contact',decision='Fixture new send',
                contact_id=row.contact_id,stage='send',evidence_id=proof)
            task = claim(db,fresh['id'],executor='worker')
            remember(db,'working','browser_executor',{'owner':'worker'})
            db.commit()
        result = self.recovered({**task,'reservation_id':reservation},proof)
        result.update(outcome='blocked',stop_reason='CHANNEL_BLOCKED')
        executor.accept(self.factory,'worker',task,result)
        with self.factory() as db:
            self.assertIsNone(db.get(FirstContact,reservation))
            from app.growth.store import digest
            self.assertFalse(get_memory(db,'operator_task',digest('after-release:'+reservation)))

    def test_post_admission_failure_hands_off_to_receipt_recovery_before_other_acquisition(self):
        from app.growth.operator import claim
        reservation, proof = self.reserve_fixture(0)
        with self.factory() as db:
            row=db.get(FirstContact,reservation)
            fresh=offer(db,key='receipt-needed',source='https://example.com/contact',decision='Fixture send',
                contact_id=row.contact_id,stage='send',evidence_id=proof)
            task=claim(db,fresh['id'],executor='worker')
            remember(db,'working','browser_executor',{'owner':'worker'})
            db.commit()
        result=self.result(); result.update(stop_reason=None,submission=None)
        with self.assertRaises(GrowthError): executor.accept(self.factory,'worker',task,result)
        executor.failed(self.factory,'worker',task,'Receipt not persisted')
        recovery=executor.take(self.factory,'worker')
        self.assertEqual(recovery['stage'],'reconcile')
        self.assertTrue(recovery['receipt_completion'])
        self.assertEqual(recovery['first_contact']['reservation_id'],reservation)
        result=self.recovered(recovery,proof,'sent')
        result['submission']['receipt']='https://example.com/contact?contact_posted=true'
        executor.accept(self.factory,'worker',recovery,result)
        with self.factory() as db:
            self.assertEqual(db.get(FirstContact,reservation).status,'sent')
        self.assertEqual(executor.take(self.factory,'worker')['stage'],'discover')

    def test_legacy_receipt_task_is_not_treated_as_a_customer_reply(self):
        reservation, _ = self.reserve_fixture(0)
        with self.factory() as db:
            row = db.get(FirstContact,reservation)
            row.reserved_at=time.time()-60
            source=record(db,'legacy-receipt','ACQUISITION_STAGE_RESULT','old-send',
                {'stop_reason':'OUTREACH_OUTCOMES_UNRESOLVED'})
            legacy=offer(db,key='legacy-receipt-task',source='https://example.com/contact',decision='Reconcile prior send',
                contact_id=row.contact_id,stage='reply',evidence_id=source.id)
            remember(db,'operator_task',legacy['id'],{**legacy,'status':'blocked','attempts':3,'lease_until':0})
            db.commit()
        task=executor.take(self.factory,'worker')
        self.assertEqual(task['id'],legacy['id'])
        self.assertEqual(task['stage'],'reconcile')
        self.assertEqual(task['prior_reply_attempts'],3)
        self.assertEqual(task['attempts'],1)
