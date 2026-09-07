"""Cohort maturity and distinct-store outcomes, with no network or real sends."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth import engine, learning
from app.growth.models import Contact, Evidence, Experiment, Message
from app.growth.store import enqueue, get_memory, record


class GrowthLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbengine = create_engine("sqlite:///" + str(Path(self.temp.name) / "growth.sqlite"))
        Base.metadata.create_all(self.dbengine)
        self.factory = sessionmaker(self.dbengine, expire_on_commit=False, autoflush=False)
        engine.bootstrap(self.factory)
        self.now = time.time()
        with self.factory() as db:
            exp = learning.ensure_experiment(db)
            self.experiment_id = exp.id
            exp.stop_at = self.now + 14 * 86400
            db.commit()

    def tearDown(self):
        self.dbengine.dispose()
        self.temp.cleanup()

    def cohort(self, count=20, unknown_last=False, shared_shop=False):
        with self.factory() as db:
            for n in range(count):
                contact = Contact(identity=f"learning:{n}", source="fixture", shop_id=42 if shared_shop else None)
                db.add(contact)
                db.flush()
                unknown = unknown_last and n == count - 1
                db.add(Message(key=f"learning-send:{n}", contact_id=contact.id, experiment_id=self.experiment_id,
                               direction="out", variant="cash" if n % 2 else "reorder", body="fixture",
                               status="unknown" if unknown else "sent", sent_at=None if unknown else self.now))
            db.commit()

    def test_full_cohort_keeps_observing_across_restart_and_periodic_wake(self):
        self.cohort()
        with self.factory() as db, patch("app.growth.learning.time.time", return_value=self.now + 1):
            old = db.get(Experiment, self.experiment_id)
            result = learning.evaluate(db, old.id)
            self.assertEqual(old.status, "observing")
            self.assertTrue(result["observation_pending"])
            self.assertIsNone(result["response_winner"])
            new = learning.ensure_experiment(db)
            self.assertNotEqual(new.id, old.id)
            self.assertEqual(new.specification["cash_allocation"], old.specification["cash_allocation"])
            db.commit()
        # The observation state survives restart and does not depend on a reply
        # arriving or an individual delayed evaluation task remaining available.
        self.dbengine.dispose()
        with self.factory() as db:
            enqueue(db, "learning-observe", "observe", priority=75, due_at=self.now)
            db.commit()
        with patch("app.growth.learning.time.time", return_value=self.now + 7 * 86400 + 1):
            self.assertTrue(engine.run_once(self.factory, schedule_wakes=False))
        with self.factory() as db:
            old = db.get(Experiment, self.experiment_id)
            self.assertEqual(old.status, "losing")
            self.assertFalse(old.result["observation_pending"])
            self.assertEqual(sum(a["mature"] for a in old.result["arms"].values()), 20)
            self.assertNotIn("next_experiment_framing", get_memory(db, "strategic", "strategy"))

    def test_unknown_send_does_not_become_silent_failure_at_window_end(self):
        self.cohort(unknown_last=True)
        with self.factory() as db, patch("app.growth.learning.time.time", return_value=self.now + 21 * 86400):
            exp = db.get(Experiment, self.experiment_id)
            result = learning.evaluate(db, exp.id)
            self.assertEqual(exp.status, "observing")
            self.assertEqual(result["unresolved_sends"], 1)
            self.assertEqual(result["sample_size"], 19)
            self.assertEqual(result["outcome"], "inconclusive")

    def test_two_contacts_for_one_store_do_not_produce_a_two_store_win(self):
        self.cohort(count=2, shared_shop=True)
        with self.factory() as db:
            record(db, "learning-connection", "SHOPIFY_CONNECTION", "shop:42", {}, occurred_at=self.now + 1)
            result = learning.evaluate(db, self.experiment_id)
            self.assertEqual(result["qualified_stores"], 1)
            self.assertEqual(result["outcome"], "inconclusive")

    def test_enrollment_deadline_does_not_close_late_contacts_observation(self):
        self.cohort(count=1)
        with self.factory() as db, patch("app.growth.learning.time.time", return_value=self.now + 1):
            exp = db.get(Experiment, self.experiment_id)
            exp.stop_at = self.now
            result = learning.evaluate(db, exp.id)
            self.assertEqual(exp.status, "observing")
            self.assertTrue(result["enrollment_closed"])
            self.assertEqual(result["arms"]["reorder"]["mature"], 0)

    def test_template_revision_rolls_enrollment_without_rewriting_old_messages(self):
        from app.growth.service_replies import SERVICE_TEMPLATE_REVISION
        self.cohort(count=2, unknown_last=True)
        with self.factory() as db:
            old = db.get(Experiment, self.experiment_id)
            old.specification = {key: value for key, value in old.specification.items() if key != "template_revision"}
            messages = list(db.scalars(select(Message).where(Message.experiment_id == old.id)))
            before = {message.id: (message.body, message.status, message.sent_at, message.experiment_id) for message in messages}
            next_cohort = learning.ensure_experiment(db)
            self.assertNotEqual(next_cohort.id, old.id)
            self.assertEqual(old.status, "observing")
            self.assertEqual(next_cohort.specification["template_revision"], SERVICE_TEMPLATE_REVISION)
            self.assertEqual(next_cohort.specification["workflow"], "browser_health_check")
            self.assertEqual(next_cohort.specification["cash_allocation"], old.specification["cash_allocation"])
            self.assertIsNone(old.specification.get("template_revision"))
            self.assertIsNotNone(db.scalar(select(Evidence).where(Evidence.kind == "EXPERIMENT_ENROLLMENT_CLOSED", Evidence.subject == old.id)))
            self.assertEqual(learning.ensure_experiment(db).id, next_cohort.id)
            for message in messages:
                self.assertEqual((message.body, message.status, message.sent_at, message.experiment_id), before[message.id])
            # An explicitly older revision gets the same separation, not an
            # in-place spec edit or reassignment of an existing message.
            next_cohort.specification = {**next_cohort.specification, "template_revision": "connection-required-v0"}
            db.flush()
            third_cohort = learning.ensure_experiment(db)
            self.assertNotEqual(third_cohort.id, next_cohort.id)
            self.assertEqual(next_cohort.status, "observing")
            self.assertEqual(third_cohort.specification["template_revision"], SERVICE_TEMPLATE_REVISION)
