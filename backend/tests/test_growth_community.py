"""Forum evidence is useful without authorizing a send or invoking a model."""
import copy
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # Register product foreign-key targets.
from app.growth.community import Discussion, export, retain, synthesize
from app.growth.models import Evidence, FirstContact
from app.growth.executive import REVIEW_FIELDS, export_packet, import_review
from app.growth.store import get_memory


def post(thread=100, number=1):
    url = f"https://community.shopify.com/t/test-thread/{thread}/{number}"
    return {"url": url, "posted_date": None, "merchant_store": None,
        "problem": "Manual bundle replenishment", "underlying_need": {"url": url, "quote": "We reorder bundle parts manually."},
        "categories": ["bundle components"], "shopify": "UNKNOWN", "commercial_relevance": "UNKNOWN",
        "competitors": [], "existing_solution_limitations": [], "solution_status": "UNKNOWN", "solution_evidence": None,
        "skubase_fit": "UNKNOWN", "capability_evidence": None, "potential_missing_feature": None,
        "acquisition_potential": "MEDIUM", "strategic_learning_value": "HIGH", "vendor_crowding": "HIGH",
        "useful_answer": None, "response_decision": "LEARN_ONLY"}


def app(url, role="MENTION"):
    return {"name": "Example Inventory", "appearance": {"url": url, "quote": "Example Inventory"},
        "role": role, "affiliation_evidence": None, "claimed_problems": ["replenishment"],
        "praise": [], "complaints": [], "unmet_capabilities": [], "pricing_complaints": []}


class CommunityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "community.db"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, autoflush=False)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_unknowns_new_categories_and_learning_only_do_not_authorize_outreach(self):
        with self.factory() as db:
            retain(db, post())
            self.assertEqual(export(db)["recent_posts"][0]["categories"], ["bundle components"])
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 0)

    def test_repeated_read_url_query_and_restart_are_idempotent(self):
        item = post()
        with self.factory() as db:
            first = retain(db, item)
            db.commit()
        item["url"] += "?u=skubase"
        with self.factory() as db:
            again = retain(db, item)
            self.assertTrue(again["unchanged"])
            self.assertEqual(first["evidence_id"], again["evidence_id"])
            self.assertEqual(export(db)["batch"]["pending_threads"], ["100"])

    def test_revisions_preserved_but_one_thread_never_triggers_batch(self):
        with self.factory() as db:
            for i in range(12):
                item = post()
                item["problem"] = f"Observed revision {i}"
                self.assertIsNone(retain(db, item)["synthesis"])
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "COMMUNITY_DISCUSSION")), 12)
            self.assertEqual(len(export(db)["recent_posts"]), 1)

    def test_ten_distinct_threads_trigger_once_and_feed_planner_memory(self):
        with self.factory() as db:
            for i in range(9):
                self.assertIsNone(retain(db, post(100+i))["synthesis"])
            result = retain(db, post(109))
            self.assertEqual(result["synthesis"]["threads"], 10)
            self.assertEqual(get_memory(db, "learning", "shopify-community")["evidence_id"], result["synthesis"]["evidence_id"])
            self.assertEqual(export(db)["batch"]["pending_threads"], [])
            self.assertIsNone(retain(db, post(109))["synthesis"])

    def test_competitor_mentions_deduplicate_and_conflicting_roles_remain_unknown(self):
        with self.factory() as db:
            first = post()
            mention = app(first["url"], "SELF_PROMOTION")
            mention["affiliation_evidence"] = {"url": first["url"], "quote": "I built Example Inventory."}
            mention["complaints"] = [{"url": first["url"], "quote": "I still need a spreadsheet for bundle parts."}]
            first["competitors"] = [mention]
            retain(db, first)
            duplicate = post(number=2)
            duplicate["competitors"] = [copy.deepcopy(mention)]
            retain(db, duplicate)
            for i in range(101, 110):
                retain(db, post(i))
            summary = export(db)["synthesis"]
            self.assertEqual(summary["common_problems"][0]["threads"], 10)
            counted = summary["competitors"][0]
            self.assertEqual(counted["appearances"], 1)
            self.assertEqual(counted["self_promotions"], 1)
            self.assertEqual(counted["organic_recommendations"], 0)
            self.assertEqual(len(counted["complaints"]), 1)
            duplicate["competitors"][0]["role"] = "ORGANIC_RECOMMENDATION"
            duplicate["competitors"][0]["affiliation_evidence"] = None
            retain(db, duplicate)
            synthesize(db)
            conflicting = export(db)["synthesis"]["competitors"][0]
            self.assertEqual(conflicting["appearances"], 1)
            self.assertEqual(conflicting["unknown_or_mentions"], 1)
            self.assertEqual(conflicting["self_promotions"], 0)
            self.assertEqual(conflicting["organic_recommendations"], 0)

    def test_claims_and_responses_require_evidence(self):
        for changes in ({"solution_status": "MERCHANT_CONFIRMED"}, {"skubase_fit": "GAP"},
                        {"skubase_fit": "VERIFIED"}, {"response_decision": "ANSWER"},
                        {"response_decision": "ANSWER_WITH_BRIEF_SKUBASE", "useful_answer": "Calculate lead-time demand."}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                Discussion.model_validate({**post(), **changes})

    def test_self_promotion_requires_affiliation_evidence(self):
        item = post()
        item["competitors"] = [app(item["url"], "SELF_PROMOTION")]
        with self.assertRaises(ValidationError):
            Discussion.model_validate(item)

    def test_reject_nonforum_and_cross_thread_need_sources(self):
        for changes in ({"url": "https://evil.example/t/topic/100/1"},
                        {"underlying_need": {"url": post(200)["url"], "quote": "Different merchant"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Discussion.model_validate({**post(), **changes})

    def test_unconfirmed_solution_is_not_reported_as_an_explicit_failure(self):
        with self.factory() as db:
            for i in range(10):
                item = post(100+i)
                item["solution_status"] = "PROPOSED_UNCONFIRMED"
                retain(db, item)
            self.assertEqual(export(db)["synthesis"]["unresolved_problems"], [])

    def test_new_synthesis_enters_daily_review_once_when_cited(self):
        with self.factory() as db:
            for i in range(10):
                retain(db, post(100+i))
            db.commit()
            now = datetime.fromisoformat("2026-09-10T17:00:00+00:00").timestamp()
            with patch("app.growth.executive.time.time", return_value=now):
                packet = export_packet(db)
                evidence_id = packet["community_learning"]["evidence_id"]
                result = {k: "Test interpretation" for k in REVIEW_FIELDS}
                result.update(day=packet["day"], evidence_ids=[evidence_id], next_action="evaluate")
                import_review(db, result)
            with patch("app.growth.executive.time.time", return_value=now+86400):
                self.assertIsNone(export_packet(db)["community_learning"])


if __name__ == "__main__":
    unittest.main()
