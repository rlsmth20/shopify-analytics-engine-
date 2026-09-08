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
from app.growth.models import Evidence, Memory, Work
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
