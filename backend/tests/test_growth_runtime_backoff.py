"""A rejected Codex startup is a runtime incident, not a failed merchant search."""
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth import browser_executor as executor
from app.growth.engine import bootstrap
from app.growth.models import Contact, Evidence, FirstContact, Usage
from app.growth.operator import offer, NAMESPACE
from app.growth.store import get_memory, record, remember


def rejected_trace(extra=None):
    message = "You've hit your usage limit. Try again at September 12th, 2035 4:15 PM."
    events = [{'type': 'thread.started', 'thread_id': 'fixture'}, {'type': 'turn.started'}]
    events.extend(extra or [])
    events += [{'type': 'error', 'message': message}, {'type': 'turn.failed', 'error': {'message': message}}]
    return '\n'.join(json.dumps(e) for e in events) + '\n'


class RuntimeBackoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / 'docs/growth').mkdir(parents=True)
        (self.repo / 'docs/growth/executor-instructions.md').write_text('Isolated fixture instruction.')
        self.engine = create_engine('sqlite:///' + str(self.repo / 'runtime.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            evidence = record(db, 'fixture-source', 'OBSERVATION', 'merchant', {'text': 'Fixture source'})
            self.task = offer(db, key='fixture-discovery', source='https://fixture.test/store',
                decision='Discover reasonable merchants', evidence_id=evidence.id, stage='discover')
            db.commit()

    def tearDown(self):
        self.engine.dispose(); self.temp.cleanup()

    def rejected_cycle(self, owner='fixture-executor', trace=None):
        child = Mock()
        child.stdin = io.StringIO()
        child.stdout = io.StringIO(trace or rejected_trace())
        child.poll.return_value = 1
        child.returncode = 1
        with patch('app.growth.executable.resolve_codex', return_value='fixture-codex'), \
             patch.object(executor.subprocess, 'Popen', return_value=child), \
             patch.object(executor, 'ProcessJob', return_value=Mock()):
            return executor.runtime_cycle(self.factory, owner, codex='fixture-codex', repo=self.repo)

    def test_classifier_requires_complete_trace_without_tools_or_output(self):
        path = self.repo / 'trace.jsonl'
        output = self.repo / 'result.json'
        path.write_text(rejected_trace())
        self.assertIsNotNone(executor.pre_execution_usage_rejection(path, output))
        for extra in (
            [{'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'fixture'}}],
            [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Prepared a message'}}],
            [{'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}}],
            [{'type': 'unknown.future.event'}],
        ):
            path.write_text(rejected_trace(extra))
            self.assertIsNone(executor.pre_execution_usage_rejection(path, output))
        path.write_text(rejected_trace() + 'truncated or unstructured output')
        self.assertIsNone(executor.pre_execution_usage_rejection(path, output))
        path.write_text(rejected_trace())
        output.write_text('{}')
        self.assertIsNone(executor.pre_execution_usage_rejection(path, output))

    def test_startup_rejection_refunds_claim_and_gates_every_task_across_restart(self):
        started = time.time()
        self.assertTrue(self.rejected_cycle())
        with self.factory() as db:
            item = get_memory(db, NAMESPACE, self.task['id'])
            self.assertEqual((item['status'], item['attempts']), ('pending', 0))
            self.assertIsNone(item['lease_token'])
            backoff = get_memory(db, 'working', 'browser_runtime_backoff')
            self.assertGreaterEqual(backoff['retry_at'], started + 900)
            self.assertLess(backoff['retry_at'], time.time() + 901)
            usage = db.scalar(select(Usage).where(Usage.result['task_id'].as_string() == self.task['id']))
            self.assertEqual(usage.outcome, executor.RUNTIME_UNAVAILABLE)
            self.assertEqual(usage.result['budget_charged_ms'], 0)
            self.assertFalse(usage.result['execution_began'])
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == 'EXECUTION_FAULT')), 0)
            proof = record(db, 'priority-reply', 'OBSERVATION', 'merchant', {})
            another = offer(db, key='priority-reply', source='https://fixture.test/thread', stage='reply',
                decision='Answer existing merchant', evidence_id=proof.id, priority=1000)
            db.commit()
        self.engine.dispose()
        self.assertIsNone(executor.take(self.factory, 'new-process'))
        with self.factory() as db:
            self.assertEqual(get_memory(db, NAMESPACE, another['id'])['attempts'], 0)
            runtime = get_memory(db, 'working', 'browser_executor')
            self.assertEqual(runtime['blocker'], 'CODEX_RUNTIME_USAGE_WAIT')
            self.assertEqual(runtime['next_retry_at'], backoff['retry_at'])

    def test_repeated_runtime_refusals_are_capped_at_one_hour_without_research_debt(self):
        for index, seconds in enumerate((900, 1800, 3600, 3600)):
            if index:
                with self.factory() as db:
                    prior = get_memory(db, 'working', 'browser_runtime_backoff')
                    remember(db, 'working', 'browser_runtime_backoff', {**prior, 'retry_at': 0})
                    item = get_memory(db, NAMESPACE, self.task['id'])
                    remember(db, NAMESPACE, self.task['id'], {**item, 'retry_at': 0})
                    # Real runtime latency is retained but must never become research debt.
                    for usage in db.scalars(select(Usage)):
                        usage.latency_ms = 900000
                    db.commit()
            before = time.time()
            self.assertTrue(self.rejected_cycle())
            with self.factory() as db:
                backoff = get_memory(db, 'working', 'browser_runtime_backoff')
                self.assertEqual(backoff['failures'], index + 1)
                self.assertGreaterEqual(backoff['retry_at'], before + seconds)
                self.assertLess(backoff['retry_at'], time.time() + seconds + 1)
                self.assertEqual(get_memory(db, NAMESPACE, self.task['id'])['attempts'], 0)
        with self.factory() as db:
            prior = get_memory(db, 'working', 'browser_runtime_backoff')
            remember(db, 'working', 'browser_runtime_backoff', {**prior, 'retry_at': 0})
            item = get_memory(db, NAMESPACE, self.task['id'])
            remember(db, NAMESPACE, self.task['id'], {**item, 'retry_at': 0})
            db.commit()
        task = executor.take(self.factory, 'recovered-executor')
        executor.accept(self.factory, 'recovered-executor', task, {'outcome': 'done', 'observation': 'Fixture search completed',
            'sources': ['https://fixture.test/store'], 'next_step': 'Choose adjacent search', 'successors': [],
            'stop_reason': 'NO_CURRENT_QUALIFIED_PROSPECTS'})
        with self.factory() as db:
            self.assertEqual(get_memory(db, 'working', 'browser_runtime_backoff')['failures'], 0)

    def test_usage_error_after_possible_action_is_not_refunded_or_retried_as_fresh(self):
        with self.factory() as db:
            item = get_memory(db, NAMESPACE, self.task['id'])
            db.add(Contact(id='contact', identity='merchant:fixture', source='https://fixture.test'))
            remember(db, NAMESPACE, self.task['id'], {**item, 'stage': 'send', 'contact_id': 'contact'})
            db.add(FirstContact(contact_id='contact', action_key='uncertain-fixture', channel='contact_form',
                experiment_id='fixture', cohort={}, body_hash='fixture', status='uncertain', reserved_at=time.time()))
            db.commit()
        # Directly exercising the failed execution avoids selecting its already-due receipt recovery first.
        task = {**self.task, 'stage': 'send', 'contact_id': 'contact'}
        from app.growth.operator import claim
        with self.factory() as db:
            task = claim(db, task['id'], executor='fixture-executor')
            remember(db, 'working', 'browser_executor', {'owner': 'fixture-executor'})
            db.commit()
        trace = self.repo / 'acted.jsonl'
        trace.write_text(rejected_trace([{'type': 'item.completed', 'item': {'type': 'tool_call', 'name': 'submit_form'}}]))
        self.assertIsNone(executor.pre_execution_usage_rejection(trace))
        executor.failed(self.factory, 'fixture-executor', task, 'Usage error after a possible action')
        with self.factory() as db:
            self.assertEqual(get_memory(db, NAMESPACE, task['id'])['attempts'], 1)
            self.assertEqual(get_memory(db, NAMESPACE, task['id'])['status'], 'blocked')
            self.assertEqual(db.scalar(select(FirstContact)).status, 'uncertain')
            self.assertFalse(get_memory(db, 'working', 'browser_runtime_backoff'))
