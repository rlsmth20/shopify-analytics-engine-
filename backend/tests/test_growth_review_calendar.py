"""Pacific review scheduling: no live model calls, credentials or external sends."""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # Register product tables used by the evidence packet.
from app.growth import engine
from app.growth.executive import REVIEW_FIELDS, export_packet, import_review
from app.growth.models import Evidence, Memory, Usage, Work
from app.growth.review_calendar import review_day
from app.growth.store import claim, enqueue, get_memory, record


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class ReviewCalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "review.sqlite"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.env = patch.dict(os.environ, {"GROWTH_DISCOVERY_ENABLED": "false", "GROWTH_INBOUND_ENABLED": "false"})
        self.env.start()
        with self.factory() as db:
            record(db, "fixture-intent", "HISTORICAL_PURCHASE_INTENT", "fixture", {"sample_size": 1})
            db.commit()

    def tearDown(self):
        self.env.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def clock(self, value):
        return patch("time.time", return_value=timestamp(value))

    def review(self, packet):
        return {**{key: "Keep the offer provisional." for key in REVIEW_FIELDS},
                "day": packet["day"], "next_action": "service_obligations",
                "evidence_ids": [packet["evidence"][0]["id"]]}

    def legacy(self, at):
        with self.factory() as db:
            row = record(db, "executive-review:" + str(int(timestamp(at) // 86400)),
                         "EXECUTIVE_REVIEW", "mission", {"legacy": True}, occurred_at=timestamp(at))
            db.commit()
            return row.id

    def test_dst_days_and_next_nine_am_use_local_calendar(self):
        for at, hours, due, following_due in [
            ("2026-03-08T17:00:00Z", 23, "2026-03-08T16:00:00Z", "2026-03-09T16:00:00Z"),
            ("2026-11-01T18:00:00Z", 25, "2026-11-01T17:00:00Z", "2026-11-02T17:00:00Z"),
            ("2026-03-07T18:00:00Z", 24, "2026-03-07T17:00:00Z", "2026-03-08T16:00:00Z"),
            ("2026-10-31T18:00:00Z", 24, "2026-10-31T16:00:00Z", "2026-11-01T17:00:00Z"),
        ]:
            with self.subTest(at=at):
                day = review_day(timestamp(at))
                self.assertEqual(day.end - day.start, hours * 3600)
                self.assertEqual(day.due, timestamp(due))
                self.assertEqual(day.next_due, timestamp(following_due))

    def test_before_nine_does_not_export_context_or_allow_import(self):
        with self.clock("2026-09-08T15:59:59Z"), self.factory() as db:
            packet = export_packet(db)
            self.assertTrue(packet["not_due"])
            self.assertEqual(packet["next_due"], timestamp("2026-09-08T16:00:00Z"))
            self.assertFalse(db.scalar(select(Memory.id)))
            with self.assertRaisesRegex(ValueError, "not due"):
                import_review(db, {})
        with self.clock("2026-09-08T16:00:00Z"), self.factory() as db:
            self.assertEqual(export_packet(db)["day"], "2026-09-08")

    def test_packet_and_completion_survive_utc_midnight(self):
        with self.clock("2026-09-07T23:55:00Z"), self.factory() as db:
            packet = export_packet(db)
        with self.clock("2026-09-08T00:05:00Z"), self.factory() as db:
            self.assertEqual(export_packet(db), packet)
            result = import_review(db, self.review(packet))
            self.assertEqual(import_review(db, self.review(packet))["evidence_id"], result["evidence_id"])
            self.assertEqual(export_packet(db)["evidence_id"], result["evidence_id"])
            self.assertEqual(get_memory(db, "working", "executive")["next_due"], timestamp("2026-09-08T16:00:00Z"))
            self.assertEqual(len(list(db.scalars(select(Usage)))), 1)

    def test_stale_packet_cannot_be_imported_next_pacific_day(self):
        with self.clock("2026-09-08T06:55:00Z"), self.factory() as db:
            old_packet = export_packet(db)
        with self.clock("2026-09-08T16:00:00Z"), self.factory() as db:
            self.assertEqual(export_packet(db)["day"], "2026-09-08")
            with self.assertRaises(ValueError):
                import_review(db, self.review(old_packet))
            self.assertFalse(db.scalar(select(Usage.id)))

    def test_legacy_review_previous_pacific_day_does_not_skip_today(self):
        prior_id = self.legacy("2026-09-07T02:39:00Z")
        with self.clock("2026-09-07T18:00:00Z"), self.factory() as db:
            self.assertIn("evidence", export_packet(db))
            self.assertEqual(db.get(Evidence, prior_id).key, "executive-review:20703")

    def test_legacy_review_current_pacific_day_blocks_both_utc_dates(self):
        prior_id = self.legacy("2026-09-07T18:00:00Z")
        for at in ["2026-09-07T20:00:00Z", "2026-09-08T03:00:00Z"]:
            with self.subTest(at=at), self.clock(at), self.factory() as db:
                self.assertEqual(export_packet(db)["evidence_id"], prior_id)

    def test_evening_legacy_review_does_not_block_tomorrow(self):
        prior_id = self.legacy("2026-09-08T01:00:00Z")
        with self.clock("2026-09-08T02:00:00Z"), self.factory() as db:
            self.assertEqual(export_packet(db)["evidence_id"], prior_id)
        with self.clock("2026-09-08T16:00:00Z"), self.factory() as db:
            self.assertIn("evidence", export_packet(db))

    def test_schedule_waits_for_nine_and_retires_legacy_jobs(self):
        with self.factory() as db:
            stale = enqueue(db, "review:20704", "daily_review")
            stale.status = "blocked"
            db.commit()
        with self.clock("2026-09-08T08:00:00Z"):
            engine.schedule(self.factory)
            engine.schedule(self.factory)
        with self.factory() as db:
            self.assertEqual(db.get(Work, stale.id).status, "superseded")
            jobs = list(db.scalars(select(Work).where(Work.kind == "daily_review", Work.status == "ready")))
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].key, "review:pacific:2026-09-08")
            self.assertEqual(jobs[0].due_at, timestamp("2026-09-08T16:00:00Z"))

    def test_completed_day_enqueues_no_duplicate_and_stale_job_cannot_call_model(self):
        prior_id = self.legacy("2026-09-08T01:00:00Z")
        with self.factory() as db:
            old = enqueue(db, "review:20704", "daily_review")
            current = enqueue(db, "review:pacific:2026-09-07", "daily_review")
            db.commit()
        model = Mock(side_effect=AssertionError("An extra review must not call a model"))
        with self.clock("2026-09-08T02:00:00Z"):
            engine.schedule(self.factory)
            self.assertTrue(engine.daily_review(self.factory, old, model=model)["superseded"])
            for mode in ["api", "codex"]:
                with patch.dict(os.environ, {"GROWTH_REVIEW_MODE": mode}):
                    self.assertEqual(engine.daily_review(self.factory, current, model=model)["evidence_id"], prior_id)
        model.assert_not_called()
        with self.factory() as db:
            self.assertFalse(db.scalar(select(Work.id).where(Work.kind == "daily_review", Work.status == "ready")))
            self.assertEqual(get_memory(db, "working", "executive")["next_due"], timestamp("2026-09-08T16:00:00Z"))

    def test_early_current_job_cannot_call_a_model(self):
        with self.factory() as db:
            work = enqueue(db, "review:pacific:2026-09-08", "daily_review")
            db.commit()
        model = Mock()
        with self.clock("2026-09-08T15:59:00Z"):
            self.assertTrue(engine.daily_review(self.factory, work, model=model)["not_due"])
        model.assert_not_called()

    def test_api_review_completion_is_shared_with_codex(self):
        with self.clock("2026-09-07T18:00:00Z"):
            engine.bootstrap(self.factory)
            with self.factory() as db:
                enqueue(db, "review:pacific:2026-09-07", "daily_review", priority=999)
                db.commit()
            work = claim(self.factory)
            model = Mock(side_effect=lambda factory, task, data, **kwargs: {
                "next_action": "evaluate", "evidence_ids": [data["evidence"][0]["id"]],
                "icp": "Provisional Shopify purchasing operators", "positioning": "Free inventory health check"})
            with patch.dict(os.environ, {"GROWTH_REVIEW_MODE": "api"}):
                engine.daily_review(self.factory, work, model=model)
            with self.factory() as db:
                completion = export_packet(db)
                self.assertTrue(completion["already_reviewed"])
                self.assertEqual(db.get(Evidence, completion["evidence_id"]).source, "daily_model_review")
            with patch.dict(os.environ, {"GROWTH_REVIEW_MODE": "codex"}):
                self.assertTrue(engine.daily_review(self.factory, work, model=model)["already_reviewed"])
            self.assertEqual(model.call_count, 1)
