"""Organic tools retain their own campaign and page cohorts; no live effects."""
import time
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.learning import evaluate_organic
from app.growth.models import Contact, Evidence, Experiment
from app.growth.store import record, remember

HEALTH_PAGE = "/tools/inventory-health-check"
REORDER_PAGE = "/tools/reorder-point-calculator"


class OrganicGrowthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.started = time.time() - 60

    def tearDown(self):
        self.engine.dispose()

    def experiment(self, db, key, **spec):
        row = Experiment(key=key, specification={"channel": "organic_search", **spec},
            started_at=self.started, stop_at=self.started + 86400)
        db.add(row)
        db.flush()
        return row

    def use(self, db, key, path, campaign=None, visitor=None, at=None):
        return record(db, key, "CALCULATOR_USED", visitor or "visitor:" + key,
            {"landing_page": path, "attribution": {"utm_campaign": campaign} if campaign else {}},
            source="first_party_browser", occurred_at=at)

    def test_untagged_health_and_legacy_reorder_uses_stay_in_their_own_page_cohorts(self):
        with self.factory() as db:
            legacy = self.experiment(db, "reorder-calculator-v1")
            health = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            self.use(db, "reorder", REORDER_PAGE)
            self.use(db, "health", HEALTH_PAGE)
            self.use(db, "health-repeat", HEALTH_PAGE, visitor="visitor:health")
            for experiment, expected_page in ((legacy, REORDER_PAGE), (health, HEALTH_PAGE)):
                result = evaluate_organic(db, experiment)
                self.assertEqual(result["calculator_users"], 1)
                self.assertEqual(result["landing_page"], expected_page)
                self.assertTrue(result["landing_page_config_valid"])
                self.assertEqual(result["qualified_stores"], 0)
                self.assertEqual(result["outcome"], "inconclusive")

    def test_explicit_campaign_takes_precedence_over_tool_path_without_double_attribution(self):
        with self.factory() as db:
            reorder = self.experiment(db, "reorder-calculator-v1")
            health = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            self.use(db, "tagged-reorder", HEALTH_PAGE, campaign=reorder.key)
            self.assertEqual(evaluate_organic(db, reorder)["calculator_users"], 1)
            self.assertEqual(evaluate_organic(db, health)["calculator_users"], 0)
            self.use(db, "tagged-other", HEALTH_PAGE, campaign="different-offer-v1")
            self.assertEqual(evaluate_organic(db, health)["calculator_users"], 0)

    def test_matching_campaign_survives_navigation_and_trailing_slash_is_normalized(self):
        with self.factory() as db:
            health = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE + "/")
            self.use(db, "on-next-page", "/inventory-risk-snapshot", campaign=health.key)
            self.use(db, "slash", HEALTH_PAGE + "/")
            result = evaluate_organic(db, health)
            self.assertEqual(result["calculator_users"], 2)
            self.assertEqual(result["landing_page"], HEALTH_PAGE)

    def test_invalid_config_fails_closed_instead_of_borrowing_legacy_reorder_users(self):
        invalid = [None, 42, {}, "", "https://skubase.io" + HEALTH_PAGE, "//other.test/tools",
            "/tools/../inventory-health-check", HEALTH_PAGE + "?utm_campaign=other", HEALTH_PAGE + "#results",
            "/tools/%2e%2e/check", "/" + "a" * 200]
        with self.factory() as db:
            self.use(db, "reorder", REORDER_PAGE)
            self.use(db, "health", HEALTH_PAGE)
            for index, page in enumerate(invalid):
                experiment = self.experiment(db, f"invalid-{index}", landing_page=page)
                result = evaluate_organic(db, experiment)
                self.assertIsNone(result["landing_page"])
                self.assertFalse(result["landing_page_config_valid"])
                self.assertEqual(result["calculator_users"], 0)

    def test_start_window_and_idempotent_evaluation_preserve_raw_evidence(self):
        with self.factory() as db:
            experiment = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            old = self.use(db, "pre-enrollment", HEALTH_PAGE, campaign=experiment.key, at=self.started - 1)
            self.use(db, "after-enrollment", HEALTH_PAGE)
            result = evaluate_organic(db, experiment)
            repeated = evaluate_organic(db, experiment)
            self.assertEqual(result, repeated)
            self.assertEqual(result["sample_size"], 1)
            self.assertIsNotNone(db.get(Evidence, old.id))
            self.assertEqual(len(list(db.scalars(select(Evidence).where(Evidence.kind == "EXPERIMENT_EVALUATED")))), 1)

    def request(self, db, suffix, campaign, *, shop_id=None, at=None):
        contact = Contact(identity="organic:" + suffix, source="skubase_form", shop_id=shop_id)
        db.add(contact)
        db.flush()
        record(db, "request:" + suffix, "ACCESS_REQUESTED", contact.id, {"utm_campaign": campaign},
            source="skubase_form", occurred_at=at or self.started + 10)
        return contact

    def connection(self, db, suffix, shop_id, at, verified=True):
        return record(db, "connection:" + suffix, "SHOPIFY_CONNECTION", f"shop:{shop_id}", {"verified": verified},
            source="skubase_backend", epistemic="FACT", occurred_at=at)

    def test_only_first_verified_connection_after_own_campaign_request_counts_once_per_store(self):
        with self.factory() as db:
            experiment = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            self.request(db, "first-person", experiment.key, shop_id=7, at=self.started + 10)
            self.request(db, "second-person", experiment.key, shop_id=7, at=self.started + 20)
            self.connection(db, "first", 7, self.started + 30)
            self.connection(db, "duplicate", 7, self.started + 40)
            result = evaluate_organic(db, experiment)
            self.assertEqual(result["qualified_stores"], 1)
            self.assertEqual(result["health_check_requests"], 2)
            self.assertEqual(result["baseline_connected_stores"], 0)
            self.assertEqual(result["outcome"], "winning")

    def test_pre_request_connections_and_reconnects_remain_baseline(self):
        with self.factory() as db:
            experiment = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            for shop_id, first_at in ((1, self.started - 86400), (2, self.started + 5), (3, self.started + 10)):
                self.connection(db, f"original-{shop_id}", shop_id, first_at)
                self.request(db, f"existing-{shop_id}", experiment.key, shop_id=shop_id, at=self.started + 10)
                self.connection(db, f"reconnect-{shop_id}", shop_id, self.started + 30)
            result = evaluate_organic(db, experiment)
            self.assertEqual(result["qualified_stores"], 0)
            self.assertEqual(result["baseline_connected_stores"], 3)
            self.assertEqual(result["outcome"], "inconclusive")

    def test_campaign_memory_and_other_campaign_requests_cannot_claim_a_connection(self):
        with self.factory() as db:
            experiment = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            self.request(db, "other-offer", "reorder-calculator-v1", shop_id=9)
            remember(db, "attribution", "shop:9", {"utm_campaign": experiment.key})
            self.connection(db, "other-offer-store", 9, self.started + 30)
            result = evaluate_organic(db, experiment)
            self.assertEqual(result["qualified_stores"], 0)
            self.assertEqual(result["health_check_requests"], 0)

    def test_unverified_connections_and_unlinked_requests_cannot_become_wins(self):
        with self.factory() as db:
            experiment = self.experiment(db, "inventory-health-check-v1", landing_page=HEALTH_PAGE)
            self.request(db, "unlinked", experiment.key)
            self.request(db, "unverified-store", experiment.key, shop_id=8)
            self.connection(db, "unverified", 8, self.started + 30, verified=False)
            self.connection(db, "unrelated", 12, self.started + 30)
            result = evaluate_organic(db, experiment)
            self.assertEqual(result["qualified_stores"], 0)
            self.assertEqual(result["unlinked_requests"], 1)
            self.assertEqual(result["linked_stores_awaiting_connection"], 1)
            self.assertEqual(result["outcome"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
