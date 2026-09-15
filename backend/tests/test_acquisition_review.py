import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.growth import acquisition_review as review
from app.growth.models import Evidence
from app.growth.store import get_memory, remember


def packet(n=5, mature=0, replies=0, paid=None):
    return {"metrics": {"confirmed_contacts": n, "paying_customers": paid, "mrr": None},
            "cohorts": [{"id": "email:cash:a", "experiment_id": "exp1",
                "confirmed_contacts": n, "mature_contacts": mature,
                "response_observation_available": True,
                "substantive_responses": replies, "positive_responses": 0,
                "paid": paid, "shopify_connected": None, "evidence_ids": [1]}]}


class AcquisitionReviewTests(unittest.TestCase):
    def test_no_rewrite_after_five_contacts_and_unknown_is_not_zero(self):
        result = review.assess(packet())
        self.assertFalse(result["review_due"])
        self.assertIsNone(result["metrics"]["mrr"])
        self.assertIsNone(result["cohort_decisions"][0]["results"]["paid"])
        self.assertEqual(result["cohort_decisions"][0]["action"], "CONTINUE_CONTROLLED_LEARNING")

    def test_fresh_hundred_contacts_are_not_negative_demand_evidence(self):
        result = review.assess(packet(100, mature=3))
        self.assertTrue(result["checkpoint_due"])
        self.assertEqual(result["cohort_decisions"][0]["action"], "CONTINUE_CONTROLLED_LEARNING")

    def test_mature_zero_reply_cohort_requests_changed_approach_not_global_hold(self):
        result = review.assess(packet(80, mature=75))
        self.assertEqual(result["cohort_decisions"][0]["action"], "CHANGE_CURRENT_APPROACH")
        self.assertTrue(result["changes"][0]["new_negative_signal"])
        self.assertNotIn("paused", result)
        self.assertNotIn("daily_limit", result)

    def test_unknown_responses_cannot_trigger_negative_conclusion(self):
        result = review.assess(packet(100, mature=100, replies=None))
        self.assertEqual(result["cohort_decisions"][0]["action"], "CONTINUE_CONTROLLED_LEARNING")

    def test_absent_reply_monitoring_prevents_zero_reply_inference(self):
        context = packet(100, mature=100)
        context["cohorts"][0]["response_observation_available"] = False
        result = review.assess(context)
        self.assertEqual(result["cohort_decisions"][0]["action"], "CONTINUE_CONTROLLED_LEARNING")

    def test_payment_dominates_missing_recorded_replies(self):
        result = review.assess(packet(100, mature=100, paid=1))
        self.assertEqual(result["cohort_decisions"][0]["action"], "EXPLORE_CUSTOMER_PATTERN")

    def test_repeated_bounces_trigger_early_scoped_diagnostic(self):
        context = packet(10)
        context["cohorts"][0]["bounced"] = 3
        result = review.assess(context)
        self.assertTrue(result["review_due"])
        self.assertEqual(result["cohort_decisions"][0]["action"], "INVESTIGATE_AFFECTED_COHORT_DELIVERY")
        self.assertNotIn("paused", result)

    def test_new_paid_customer_triggers_review_without_contact_threshold(self):
        result = review.assess(packet(5, paid=1))
        self.assertTrue(result["review_due"])
        self.assertEqual(result["cohort_decisions"][0]["action"], "EXPLORE_CUSTOMER_PATTERN")
        self.assertEqual(result["cohort_decisions"][0]["confidence"], "low")

    def test_cohorts_remain_separate_and_contact_thresholds_do_not_imply_winners(self):
        context = packet(100, 100, 0)
        good = packet(10, 7, 2, 1)["cohorts"][0]
        good["id"] = "reddit:check:b"
        good["experiment_id"] = "exp2"
        context["cohorts"].append(good)
        result = review.assess(context)
        self.assertEqual([d["action"] for d in result["cohort_decisions"]],
                         ["CHANGE_CURRENT_APPROACH", "EXPLORE_CUSTOMER_PATTERN"])

    def test_review_idempotent_restarts_preserve_owner_policy_and_beliefs(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        # Stub projection rather than invent product history to exercise durable
        # review behavior independently of the attribution module's own tests.
        with Session(engine) as db, patch("app.growth.outcomes.review_context", return_value=packet(100, 100)) as project:
            remember(db, "strategic", "outreach_policy", {"daily_new_contact_limit": 1000})
            first = review.refresh(db, now=1000)
            db.commit()
            self.assertEqual(get_memory(db, "strategic", "outreach_policy")["daily_new_contact_limit"], 1000)
            self.assertEqual(first["north_star"], "PAYING_CUSTOMERS_AND_MRR")
            self.assertEqual(review.refresh(db, now=1100), first)
            self.assertEqual(project.call_count, 1)
            review.refresh(db, now=1400)
            db.commit()
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(
                Evidence.kind == "ACQUISITION_OUTCOME_REVIEW")), 1)
            belief = get_memory(db, "experiment_beliefs", "acquisition:email:cash:a")
            self.assertEqual(belief["sample_size"], 100)
            self.assertEqual(belief["source_experiments"], ["exp1"])
            self.assertIn("contradictory_evidence", belief)
            self.assertEqual(belief["last_updated"], 1000)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
