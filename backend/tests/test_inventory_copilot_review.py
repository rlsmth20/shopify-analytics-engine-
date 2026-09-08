"""Independent local checks of Ask Skubase's durable spending boundary."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import init_db  # Register existing growth tables used by real privacy cleanup.
from app.db.copilot_models import CopilotBudgetDay, CopilotUsage
from app.db.models import Shop
from app.services import copilot_usage as budget
from app.services.shopify_privacy import redact_shop


class InventoryCopilotReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="skubase-copilot-review-")
        self.url = "sqlite:///" + str(Path(self.directory.name) / "fixture.db")
        self.engine = create_engine(self.url, connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, autoflush=False, expire_on_commit=False)
        self.now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        self.clock = patch.object(budget, "utc_now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        with self.sessions() as db:
            shops = [Shop(shopify_domain=f"copilot-review-{index}.myshopify.com") for index in range(2)]
            db.add_all(shops)
            db.commit()
            self.shop_id, self.other_id = [shop.id for shop in shops]
        self.maximum = Decimal("0.00086000")  # 1,000 input tokens plus bounded 550 output.
        self.policy = budget.ChatPolicy(enabled=True, daily_usd=Decimal("1"),
            shop_daily_usd=Decimal("1"), shop_daily_requests=30, shop_per_minute=30,
            monthly_usd=Decimal("50"))

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def reserve(self, *, shop_id=None, policy=None):
        return budget.reserve(self.sessions, shop_id=shop_id or self.shop_id,
            input_token_bound=1000, policy=policy or self.policy)

    def state(self, key=None):
        with self.sessions() as db:
            day = db.get(CopilotBudgetDay, self.now.date().isoformat())
            count = db.scalar(select(func.count()).select_from(CopilotUsage))
            row = db.get(CopilotUsage, key) if key else None
            return (day.charged_usd if day else Decimal("0"), count,
                    (row.outcome, row.estimated_usd) if row else None)

    def test_concurrent_shops_cannot_each_reserve_the_last_global_allowance(self):
        policy = replace(self.policy, daily_usd=self.maximum)
        barrier = Barrier(2)

        def attempt(shop_id):
            barrier.wait(timeout=5)
            try:
                return ("reserved", self.reserve(shop_id=shop_id, policy=policy))
            except budget.BudgetError as error:
                return (error.reason, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, shop_id) for shop_id in (self.shop_id, self.other_id)]
            results = [future.result(timeout=15) for future in futures]
        self.assertCountEqual([status for status, _ in results], ["reserved", "global_budget_exhausted"])
        self.assertEqual(self.state()[:2], (self.maximum, 1))

    def test_crash_and_unknown_usage_keep_the_reservation_across_new_sessions(self):
        policy = replace(self.policy, daily_usd=self.maximum)
        key = self.reserve(policy=policy)
        # No completion occurred; a new request/session cannot rediscover a free budget.
        with self.assertRaises(budget.BudgetError) as error:
            self.reserve(shop_id=self.other_id, policy=policy)
        self.assertEqual(error.exception.reason, "global_budget_exhausted")
        budget.finish(self.sessions, key, usage=None, outcome="transport_unknown", latency_ms=15000)
        self.assertEqual(self.state(key), (self.maximum, 1, ("transport_unknown", None)))
        # An accidental second completion must not refund a previously uncertain call.
        budget.finish(self.sessions, key, usage={"input_tokens": 1, "output_tokens": 1},
            outcome="completed", latency_ms=1)
        self.assertEqual(self.state(key), (self.maximum, 1, ("transport_unknown", None)))

    def test_two_shops_cannot_each_claim_the_last_monthly_allowance_after_daily_reset(self):
        with self.sessions() as db:
            db.add(CopilotBudgetDay(day="2026-09-06", charged_usd=Decimal("50") - self.maximum))
            db.commit()
        barrier = Barrier(2)

        def attempt(shop_id):
            barrier.wait(timeout=5)
            try:
                self.reserve(shop_id=shop_id)
                return "reserved"
            except budget.BudgetError as error:
                return error.reason

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt, shop_id) for shop_id in (self.shop_id, self.other_id)]
            results = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(results, ["reserved", "monthly_budget_exhausted"])
        self.assertEqual(self.state()[:2], (self.maximum, 1))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.sum(CopilotBudgetDay.charged_usd))), Decimal("50"))

    def test_prior_day_unknown_and_privacy_deleted_usage_blocks_until_the_next_month(self):
        policy = replace(self.policy, monthly_usd=self.maximum)
        key = self.reserve(policy=policy)
        budget.finish(self.sessions, key, usage=None, outcome="transport_unknown", latency_ms=15000)
        with self.sessions() as db:
            redact_shop(db, shop_domain="copilot-review-0.myshopify.com", triggered_at=None)
        tomorrow = self.now + timedelta(days=1)
        with patch.object(budget, "utc_now", return_value=tomorrow):
            with self.assertRaises(budget.BudgetError) as error:
                self.reserve(shop_id=self.other_id, policy=policy)
            self.assertEqual(error.exception.reason, "monthly_budget_exhausted")
        with self.sessions() as db:
            self.assertIsNone(db.get(CopilotUsage, key))
            self.assertIsNone(db.get(CopilotBudgetDay, tomorrow.date().isoformat()))
            self.assertEqual(db.get(CopilotBudgetDay, self.now.date().isoformat()).charged_usd, self.maximum)
        with patch.object(budget, "utc_now", return_value=datetime(2026, 10, 1, tzinfo=timezone.utc)):
            self.reserve(shop_id=self.other_id, policy=policy)
        with self.sessions() as db:
            self.assertEqual(db.get(CopilotBudgetDay, "2026-09-07").charged_usd, self.maximum)
            self.assertEqual(db.get(CopilotBudgetDay, "2026-10-01").charged_usd, self.maximum)

    def test_late_settlement_of_last_month_does_not_refill_this_month(self):
        policy = replace(self.policy, monthly_usd=self.maximum)
        previous_key = self.reserve(policy=policy)
        with patch.object(budget, "utc_now", return_value=datetime(2026, 10, 1, tzinfo=timezone.utc)):
            self.reserve(policy=policy)
            budget.finish(self.sessions, previous_key, usage={"input_tokens": 100, "output_tokens": 10},
                outcome="completed", latency_ms=50)
            with self.assertRaises(budget.BudgetError) as error:
                self.reserve(shop_id=self.other_id, policy=policy)
            self.assertEqual(error.exception.reason, "monthly_budget_exhausted")
        with self.sessions() as db:
            self.assertEqual(db.get(CopilotBudgetDay, "2026-09-07").charged_usd, Decimal("0.00003200"))
            self.assertEqual(db.get(CopilotBudgetDay, "2026-10-01").charged_usd, self.maximum)

    def test_verified_cost_settles_once_and_malformed_usage_never_refunds(self):
        key = self.reserve()
        usage = {"input_tokens": 100, "output_tokens": 10, "input_tokens_details": {"cached_tokens": 20}}
        budget.finish(self.sessions, key, usage=usage, outcome="completed", latency_ms=50)
        expected = Decimal("0.00002840")
        self.assertEqual(self.state(key), (expected, 1, ("completed", expected)))
        budget.finish(self.sessions, key, usage={"input_tokens": 0, "output_tokens": 0},
            outcome="completed", latency_ms=1)
        self.assertEqual(self.state(key), (expected, 1, ("completed", expected)))
        bad_usage = [None, {}, {"input_tokens": True, "output_tokens": 0},
            {"input_tokens": 1.5, "output_tokens": 0},
            {"input_tokens": 1, "output_tokens": 0, "input_tokens_details": {"cached_tokens": 2}},
            {"input_tokens": 1, "output_tokens": -1}]
        for index, usage in enumerate(bad_usage, start=1):
            with self.subTest(usage=usage):
                key = self.reserve()
                budget.finish(self.sessions, key, usage=usage, outcome="usage_unknown", latency_ms=5)
                self.assertEqual(self.state(key), (expected + self.maximum * index,
                    index + 1, ("usage_unknown", None)))

    def test_shop_rate_limit_is_shared_across_sessions_but_not_other_shops(self):
        policy = replace(self.policy, shop_per_minute=1)
        self.reserve(policy=policy)
        with self.assertRaises(budget.BudgetError) as error:
            self.reserve(policy=policy)
        self.assertEqual(error.exception.reason, "shop_rate_limited")
        self.reserve(shop_id=self.other_id, policy=policy)
        with patch.object(budget, "utc_now", return_value=self.now + timedelta(seconds=61)):
            self.reserve(policy=policy)
        self.assertEqual(self.state()[:2], (self.maximum * 3, 3))

    def test_privacy_deletion_does_not_refill_the_global_spending_ceiling(self):
        policy = replace(self.policy, daily_usd=self.maximum * 2)
        deleted_key = self.reserve(policy=policy)
        other_key = self.reserve(shop_id=self.other_id, policy=policy)
        with self.sessions() as db:
            result = redact_shop(db, shop_domain="copilot-review-0.myshopify.com", triggered_at=None)
            self.assertEqual(result["shops_redacted"], 1)
        self.assertEqual(self.state(deleted_key), (self.maximum * 2, 1, None))
        self.assertEqual(self.state(other_key)[2], ("reserved", None))
        # Completion after privacy deletion has no row to reconcile; retain the maximum.
        budget.finish(self.sessions, deleted_key, usage={"input_tokens": 0, "output_tokens": 0},
            outcome="completed", latency_ms=1)
        self.assertEqual(self.state()[0], self.maximum * 2)
        with self.assertRaises(budget.BudgetError) as error:
            self.reserve(shop_id=self.other_id, policy=policy)
        self.assertEqual(error.exception.reason, "global_budget_exhausted")

    def test_fresh_initializer_registers_new_tables_for_existing_deployments(self):
        # Remove only synthetic new tables; a fresh Python process cannot rely on
        # this test's imports accidentally registering their metadata.
        CopilotUsage.__table__.drop(self.engine)
        CopilotBudgetDay.__table__.drop(self.engine)
        environment = {**os.environ, "DATABASE_URL": self.url}
        result = subprocess.run([sys.executable, "-c", "from app.db.init_db import init_db; init_db(); init_db()"],
            cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue({"copilot_usage", "copilot_budget_days"}.issubset(inspect(self.engine).get_table_names()))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Shop)), 2)


if __name__ == "__main__":
    unittest.main()
