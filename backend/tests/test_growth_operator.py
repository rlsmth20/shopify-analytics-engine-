"""Durable browser handoffs recover safely without granting send authority."""
import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth.models import FirstContact
from app.growth.operator import offer, claim, complete, export_packet, LEASE_SECONDS
from app.growth.policy import GrowthError
from app.growth.store import record, remember


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'operator.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            self.evidence = record(db, 'source', 'OBSERVATION', 'source', {'pain': 'reorder planning'}).id
            self.task = offer(db, key='merchant-post', source='https://example.com/post',
                decision='Verify channel rules and merchant fit before proposing the health check.', evidence_id=self.evidence)
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_restart_duplicate_claim_recovery_and_stale_completion(self):
        now = time.time()
        with self.factory() as db:
            first = claim(db, self.task['id'], now=now)
            db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError):
                claim(db, self.task['id'], now=now + 1)
            db.rollback()
            recovered = claim(db, self.task['id'], now=now + LEASE_SECONDS + 1)
            db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError):
                complete(db, task_id=self.task['id'], lease_token=first['lease_token'], evidence_id=self.evidence,
                    outcome='done', next_step='Next source', now=now + LEASE_SECONDS + 2)
            db.rollback()
            self.assertNotEqual(first['lease_token'], recovered['lease_token'])
            claim(db, self.task['id'], now=now + LEASE_SECONDS * 2 + 2)
            db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError):
                claim(db, self.task['id'], now=now + LEASE_SECONDS * 3 + 3)

    def test_completion_requires_new_evidence_is_idempotent_and_never_counts_a_send(self):
        with self.factory() as db:
            item = claim(db, self.task['id'])
            with self.assertRaises(GrowthError):
                complete(db, task_id=item['id'], lease_token=item['lease_token'], evidence_id=self.evidence,
                    outcome='excluded', next_step='Find a different qualified merchant')
            result = record(db, 'screened', 'SOURCE_SCREENED', item['id'], {'reason': 'resolved problem'})
            done = complete(db, task_id=item['id'], lease_token=item['lease_token'], evidence_id=result.id,
                outcome='excluded', next_step='Find a different qualified merchant')
            again = complete(db, task_id=item['id'], lease_token=item['lease_token'], evidence_id=result.id,
                outcome='excluded', next_step='Find a different qualified merchant')
            self.assertEqual(done, again)
            db.commit()
        with self.factory() as db:
            duplicate = offer(db, key='merchant-post', source='https://example.com/post',
                decision='Repeated research must not reset the outcome', evidence_id=self.evidence)
            self.assertEqual(duplicate['status'], 'excluded')
            self.assertFalse(duplicate['send_authorized'])
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 0)

    def test_terminal_history_and_claimed_tasks_do_not_hide_old_pending_work(self):
        with self.factory() as db:
            for n in range(110):
                remember(db, 'operator_task', 'terminal-' + str(n), {'status': 'done'})
            for n in range(8):
                queued = offer(db, key='busy-' + str(n), source=None, decision='Research another permitted channel',
                    evidence_id=self.evidence, priority=100)
                claim(db, queued['id'])
            db.commit()
        with self.factory() as db:
            packet = export_packet(db)
            self.assertEqual([t['id'] for t in packet['tasks']], [self.task['id']])
            self.assertEqual(packet['claimed_tasks'], 8)
            self.assertEqual(packet['next_action'], 'claim_next_task')


if __name__ == '__main__':
    unittest.main()
