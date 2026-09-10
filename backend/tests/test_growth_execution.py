"""Execution invariants: priority, durable continuation, restart, and false progress."""
import tempfile
import time
import unittest
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth import browser_executor as executor
from app.growth.execution import state
from app.growth.models import Contact, Evidence, FirstContact, Memory, Work
from app.growth.operator import offer
from app.growth.policy import GrowthError
from app.growth.store import claim, enqueue, finish, get_memory, record, remember


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'execution.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            evidence = record(db, 'source', 'OBSERVATION', 'merchant', {'text': 'fixture'}).id
            self.task = offer(db, key='source', source='https://example.com/need', decision='Discover relevant source', evidence_id=evidence)
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def result(self, stage=None):
        return {'outcome': 'done', 'observation': 'isolated fixture observation',
                'sources': ['https://example.com/need'], 'next_step': stage or 'Current source exhausted',
                'stop_reason': None if stage else 'NO_CURRENT_QUALIFIED_PROSPECTS',
                'successors': [{'key': 'source:' + stage, 'source': 'https://example.com/need',
                    'decision': stage + ' the observed source', 'stage': stage}] if stage else []}

    def test_runtime_wait_is_reported_without_false_starvation(self):
        with self.factory() as db:
            task = get_memory(db, 'operator_task', self.task['id'])
            remember(db, 'operator_task', self.task['id'], {**task, 'created_at': time.time() - 3600})
            retry = time.time() + 900
            remember(db, 'working', 'browser_runtime_backoff', {'retry_at': retry})
            db.commit()
            view = state(db)
            self.assertIsNone(view['operational_fault'])
            self.assertEqual(view['current_blocker'], 'CODEX_USAGE_LIMIT')
            self.assertEqual(view['next_wake_retry'], retry)

    def test_completed_reply_without_successor_resumes_existing_acquisition(self):
        with self.factory() as db:
            reply = offer(db, key='automatic-reply', source='https://example.com/thread',
                stage='reply', decision='Classify an observed inbox reply', evidence_id=self.task['evidence_id'])
            db.commit()
        reviewed = []
        def classify(task):
            reviewed.append(task['id'])
            return {**self.result(), 'observation': 'Fixture automatic absence notice; no reply needed.',
                'stop_reason': None, 'next_step': 'Resume acquisition; await a new message in this thread.'}
        self.assertTrue(executor.cycle(self.factory, 'reply-worker', classify))
        self.assertEqual(reviewed, [reply['id']])
        with self.factory() as db:
            self.assertEqual(get_memory(db, 'operator_task', reply['id'])['status'], 'done')
            self.assertIsNone(get_memory(db, 'working', 'browser_executor')['blocker'])
            self.assertEqual(list(db.scalars(select(FirstContact))), [])
        following = executor.take(self.factory, 'next-process')
        self.assertEqual(following['id'], self.task['id'])
        self.assertEqual(following['stage'], 'discover')

    def test_reply_completion_still_requires_retained_observations(self):
        with self.factory() as db:
            offer(db, key='unverified-reply', source='https://example.com/thread',
                stage='reply', decision='Review the incoming message', evidence_id=self.task['evidence_id'])
            db.commit()
        task = executor.take(self.factory, 'reply-worker')
        with self.assertRaisesRegex(GrowthError, 'Retained real source observations'):
            executor.accept(self.factory, 'reply-worker', task,
                {**self.result(), 'stop_reason': None, 'sources': []})

    def test_uncertain_forms_do_not_filter_existing_send_work(self):
        with self.factory() as db:
            for n in range(10):
                db.add(FirstContact(contact_id='unknown-'+str(n), action_key='unknown-'+str(n),
                    channel='contact_form', experiment_id='fixture', body_hash='fixture',
                    cohort={}, status='uncertain', reserved_at=time.time()-700))
            sending = offer(db, key='eligible-send', source='https://example.com/contact',
                stage='send', priority=100, decision='Contact a different eligible merchant',
                evidence_id=self.task['evidence_id'])
            db.commit()
        task = executor.take(self.factory, 'restarted-process')
        self.assertEqual(task['id'], sending['id'])
        self.assertIsNone(task['outreach_policy']['blocker'])
        self.assertEqual(task['outreach_policy']['uncertain_contacts'], 10)
        self.assertIsNone(task['outreach_policy']['channels']['email']['blocker'])

    def test_kind_priority_overrides_legacy_scores_and_reply_preempts(self):
        with self.factory() as db:
            for n in range(25):
                enqueue(db, f'monitor:{n}', 'observe', priority=999)
            enqueue(db, 'discover', 'discover', priority=0)
            enqueue(db, 'reply', 'reply', priority=0)
            db.commit()
        self.assertEqual(claim(self.factory).kind, 'reply')
        self.assertEqual(claim(self.factory).kind, 'discover')

    def test_provider_window_defers_without_losing_research_or_exhausting_attempts(self):
        with self.factory() as db:
            item = enqueue(db, 'bounded-research', 'research_contact')
            item_id = item.id
            db.commit()
        task = claim(self.factory)
        due = time.time() + 600
        finish(self.factory, task, result={'decision': 'research_cap_reached', 'defer_until': due})
        with self.factory() as db:
            item = db.get(Work, item_id)
            self.assertEqual(item.status, 'ready')
            self.assertEqual(item.due_at, due)
            self.assertEqual(item.attempts, 0)
        self.assertIsNone(claim(self.factory))

    def test_two_sequential_stages_resume_with_new_executor_and_no_owner_message(self):
        seen = []
        def first(task):
            seen.append(task.get('stage'))
            return self.result('qualify')
        self.assertTrue(executor.cycle(self.factory, 'process-before-restart', first))
        self.engine.dispose()
        def second(task):
            seen.append(task['stage'])
            return self.result('prepare')
        self.assertTrue(executor.cycle(self.factory, 'process-after-restart', second))
        self.assertEqual(seen, ['discover', 'qualify'])
        with self.factory() as db:
            progress = list(db.scalars(select(Evidence).where(Evidence.kind == 'ACQUISITION_PROGRESS')))
            self.assertEqual(len(progress), 2)
            self.assertEqual(state(db)['qualified_ready'], 1)
        task = executor.take(self.factory, 'process-after-restart')
        self.assertEqual(task['stage'], 'prepare')
        self.assertIsNone(executor.take(self.factory, 'competing-process'))

    def test_stale_claim_is_fenced_and_recovered(self):
        old = executor.take(self.factory, 'old')
        with self.factory() as db:
            runtime = get_memory(db, 'working', 'browser_executor')
            remember(db, 'working', 'browser_executor', {**runtime, 'lease_until': 0})
            item = get_memory(db, 'operator_task', old['id'])
            remember(db, 'operator_task', old['id'], {**item, 'lease_until': 0})
            db.commit()
        new = executor.take(self.factory, 'new')
        self.assertEqual(new['attempts'], 2)
        with self.assertRaises(GrowthError):
            executor.accept(self.factory, 'old', old, self.result())
        executor.accept(self.factory, 'new', new, self.result())

    def test_failure_backoff_and_monitoring_are_not_success(self):
        task = executor.take(self.factory, 'executor')
        result = self.result()
        result['stop_reason'] = 'PERFORMED_MONITORING'
        with self.assertRaises(GrowthError):
            executor.accept(self.factory, 'executor', task, result)
        executor.failed(self.factory, 'executor', task, 'provider down')
        self.assertIsNone(executor.take(self.factory, 'executor'))
        with self.factory() as db:
            item = get_memory(db, 'operator_task', task['id'])
            self.assertEqual(item['attempts'], 1)
            self.assertGreater(item['retry_at'], time.time())
            self.assertIsNone(state(db)['last_acquisition_action'])

    def test_incomplete_check_autonomously_recovers_then_executes_queued_work(self):
        with self.factory() as db:
            proof = record(db, 'unattached', 'CHANNEL_MONITOR', self.task['id'], {'requires_attention': True})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': True, 'evidence_id': proof.id})
            db.commit()
        task = executor.take(self.factory, 'restarted')
        self.assertEqual(task['stage'], 'monitor')
        result = self.result()
        result['stop_reason'] = None
        # A successful model summary alone cannot clear a safety hold.
        with self.assertRaises(GrowthError):
            executor.accept(self.factory, 'restarted', task, result)
        with self.factory() as db:
            proof = record(db, 'fresh-clear', 'CHANNEL_MONITOR', task['id'], {'lease_token': task['lease_token']})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': False, 'evidence_id': proof.id})
            db.commit()
        executor.accept(self.factory, 'restarted', task, result)
        resumed = executor.take(self.factory, 'restarted')
        self.assertEqual(resumed['id'], self.task['id'])
        self.assertEqual(resumed['stage'], 'discover')

    def test_inaccessible_check_has_durable_cooldown_without_new_research(self):
        with self.factory() as db:
            proof = record(db, 'unattached', 'CHANNEL_MONITOR', self.task['id'], {})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': True, 'evidence_id': proof.id})
            db.commit()
        task = executor.take(self.factory, 'worker')
        with self.factory() as db:
            proof = record(db, 'still-unattached', 'CHANNEL_MONITOR', task['id'], {'lease_token': task['lease_token']})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': True, 'evidence_id': proof.id})
            db.commit()
        result = {**self.result(), 'outcome': 'blocked', 'stop_reason': 'SAFETY_BLOCKED'}
        executor.accept(self.factory, 'worker', task, result)
        self.assertIsNone(executor.take(self.factory, 'worker'))
        with self.factory() as db:
            recovery = get_memory(db, 'working', 'browser_monitor_recovery')
            self.assertEqual(recovery['generation'], 1)
            self.assertGreater(recovery['retry_at'], time.time() + 800)

    def test_recovery_never_replays_reserved_or_exhausted_sends(self):
        with self.factory() as db:
            proof = record(db, 'unattached', 'CHANNEL_MONITOR', self.task['id'], {})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': True, 'evidence_id': proof.id})
            for name, reserved, attempts in [('safe', False, 1), ('uncertain', True, 1), ('exhausted', False, 3)]:
                contact = Contact(identity=name, source='https://example.com')
                db.add(contact)
                db.flush()
                result = record(db, 'blocked:' + name, 'ACQUISITION_STAGE_RESULT', name, {'stop_reason': 'SAFETY_BLOCKED'})
                remember(db, 'operator_task', name, {'id': name, 'status': 'blocked', 'stage': 'send',
                    'contact_id': contact.id, 'attempts': attempts, 'result_evidence_id': result.id})
                if reserved:
                    db.add(FirstContact(contact_id=contact.id, action_key='reserved', channel='contact_form',
                        experiment_id='fixture', cohort={}, body_hash='fixture'))
            db.commit()
        task = executor.take(self.factory, 'worker')
        with self.factory() as db:
            proof = record(db, 'clear', 'CHANNEL_MONITOR', task['id'], {'lease_token': task['lease_token']})
            remember(db, 'working', 'browser_safety_check', {'requires_attention': False, 'evidence_id': proof.id})
            db.commit()
        executor.accept(self.factory, 'worker', task, {**self.result(), 'stop_reason': None})
        with self.factory() as db:
            self.assertEqual(get_memory(db, 'operator_task', 'safe')['status'], 'pending')
            self.assertEqual(get_memory(db, 'operator_task', 'safe')['attempts'], 1)
            self.assertEqual(get_memory(db, 'operator_task', 'uncertain')['status'], 'blocked')
            self.assertEqual(get_memory(db, 'operator_task', 'exhausted')['status'], 'blocked')

    def test_pending_zero_attempts_is_unhealthy_and_not_hidden_by_heartbeat(self):
        with self.factory() as db:
            item = get_memory(db, 'operator_task', self.task['id'])
            remember(db, 'operator_task', item['id'], {**item, 'created_at': time.time() - 800})
            remember(db, 'working', 'browser_executor', {'heartbeat_at': time.time()})
            db.commit()
            self.assertEqual(state(db)['operational_fault'], 'ACQUISITION_STARVED')
            remember(db, 'working', 'control', {'paused': True})
            db.commit()
            self.assertIsNone(state(db)['operational_fault'])
            self.assertEqual(state(db)['current_blocker'], 'SAFETY_BLOCKED')

    @unittest.skipUnless(os.name == 'nt', 'Windows supervisor containment')
    def test_supervisor_job_close_terminates_executor(self):
        from app.growth.process_job import ProcessJob
        job = ProcessJob()
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job.assign(process)
            self.assertIsNone(process.poll())
            job.close()
            process.wait(timeout=5)
            self.assertIsNotNone(process.returncode)
        finally:
            job.close()
            if process.poll() is None:
                process.kill()


if __name__ == '__main__':
    unittest.main()
