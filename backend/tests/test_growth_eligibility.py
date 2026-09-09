import json
import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth.eligibility import CORE, POLICY, assess, evaluate
from app.growth.acquisition_usage import retain, route, efficiency
from app.growth.models import Contact, Evidence, Experiment, Usage
from app.growth.outbound import operator_action
from app.growth.policy import GrowthError
from app.growth.store import remember, record
from app.growth.browser_executor import redact_log


def checks(**overrides):
    return {k: {"value": overrides.get(k, True), "source": "https://merchant.test/contact",
                "text": "Sourced basic fact: " + k} for k in CORE}


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "test.db"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_unknown_optional_attributes_and_probable_shopify_are_medium_eligible(self):
        result = evaluate(checks(shopify="probable"), {"inventory_pain": None, "target_sku_range": None})
        self.assertTrue(result["eligible"])
        self.assertEqual(result["priority"], "MEDIUM")
        self.assertEqual(result["confidence"], "MEDIUM")
        self.assertIsNone(evaluate(checks(shopify=None))["eligible"])
        for key, reason in CORE.items():
            with self.subTest(key=key):
                self.assertEqual(evaluate(checks(**{key: False}))["reason"], reason)

    def test_cached_assessment_never_overrides_new_suppression(self):
        with self.factory() as db:
            first = assess(db, {"identity": "merchant:test", "checks": checks()})
            second = assess(db, {"identity": "merchant:test"})
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(first["evidence_id"], second["evidence_id"])
            db.get(Contact, first["contact_id"]).suppressed = True
            db.flush()
            self.assertEqual(assess(db, {"identity": "merchant:test"})["reason"], "BOUNCED_SUPPRESSED")

    def test_probable_basic_fit_is_eligible_but_contact_route_and_rules_need_evidence(self):
        basic = {key: 'probable' for key in ('merchant', 'ecommerce', 'physical_products', 'shopify')}
        result = evaluate(checks(**basic), {'inventory_pain': None, 'revenue': None, 'sku_count': None})
        self.assertTrue(result['eligible'])
        self.assertEqual(result['priority'], 'MEDIUM')
        for key in CORE.keys() - basic.keys():
            with self.subTest(key=key):
                self.assertIsNone(evaluate(checks(**basic, **{key: 'probable'}))['eligible'])
        unsourced = checks(**basic)
        unsourced['physical_products']['source'] = ''
        self.assertIsNone(evaluate(unsourced)['eligible'])

    def test_bare_community_handle_cannot_hide_suppressed_alias(self):
        with self.factory() as db:
            db.add(Contact(identity="shopify_community:merchant", source="https://community.shopify.com/t/123",
                           suppressed=True))
            db.flush()
            result = assess(db, {"identity": "merchant", "source": "https://community.shopify.com/t/456", "checks": checks()})
            self.assertFalse(result["eligible"])
            self.assertEqual(result["reason"], "BOUNCED_SUPPRESSED")

    def test_invalidated_browser_check_cannot_authorize_send_even_if_fresh(self):
        with self.factory() as db:
            e = record(db, "monitor", "CHANNEL_MONITOR", "browser", {})
            record(db, "invalid", "EVIDENCE_INVALIDATED", str(e.id), {"reason": "unobserved"})
            remember(db, "working", "browser_executor", {"owner": "executor"})
            remember(db, "working", "browser_safety_check", {"checked_at": time.time(), "evidence_id": e.id})
            with self.assertRaisesRegex(GrowthError, "Fresh essential"):
                operator_action(db, "outreach-reserve", {})

    def test_monitor_bridge_requires_real_time_window_and_task_lease(self):
        from app.growth.operator import offer, claim, operator_action as operator_cli
        with self.factory() as db:
            e = record(db, "source", "OBSERVATION", "merchant", {})
            task = offer(db, key="monitor-fixture", source="https://example.test",
                         decision="Fixture check", evidence_id=e.id)
            task = claim(db, task["id"])
            payload = {"task_id": task["id"], "lease_token": task["lease_token"], "checked_at": time.time(),
                       "mailbox": "info@skubase.io", "requires_attention": False,
                       "observations": [{"source": "https://mail.google.com/mail/u/4/", "observation": "Fixture business mailbox"},
                                        {"source": "https://www.reddit.com/notifications", "observation": "Fixture notifications"}]}
            proof = operator_cli(db, "operator-monitor", payload)
            self.assertEqual(db.get(Evidence, proof["evidence_id"]).kind, "CHANNEL_MONITOR")
            for changed in ({"checked_at": time.time()-301}, {"lease_token": "stale"}, {"mailbox": "personal@example.test"}):
                with self.assertRaises(GrowthError):
                    operator_cli(db, "operator-monitor", {**payload, **changed})

    def test_medium_without_pain_can_reserve_but_cannot_resend(self):
        with self.factory() as db:
            remember(db, "strategic", "qualification_policy", {"version": POLICY, "started_at": time.time()})
            result = assess(db, {"identity": "merchant:test", "checks": checks()})
            exp = Experiment(key="test", specification={}, stop_at=time.time() + 3600)
            db.add(exp)
            db.flush()
            payload = {"identity": "merchant:test", "organization": "Test", "source": "https://merchant.test",
                       "facts": [{"verified": True, "source": "https://merchant.test", "text": "Physical products"}],
                       "relevance_evidence": result["evidence_id"], "channel_rules_source": "https://merchant.test/contact",
                       "action_key": "test", "channel": "contact_form", "experiment_id": exp.id, "body": "Test",
                       "cohort": {"icp": "physical-shopify", "offer": "discovery", "message_version": 4,
                                  "qualification_policy": POLICY}}
            self.assertIn("reservation_id", operator_action(db, "outreach-reserve", payload))
            self.assertEqual(assess(db, {"identity": "merchant:test"})["reason"], "PREVIOUSLY_CONTACTED")
            with self.assertRaises(GrowthError):
                operator_action(db, "outreach-reserve", payload)

    def test_explicit_cheap_route_and_idempotent_usage_unknown_dollars(self):
        self.assertEqual(route("qualify"), ("gpt-5.6-luna", "low"))
        self.assertEqual(route("discover"), ("gpt-5.6-terra", "low"))
        log = json.dumps({"command": "DATABASE_URL='postgresql://user:fixture-secret@host/db'"})
        self.assertNotIn("fixture-secret", redact_log(log))
        self.assertIn("REDACTED_DATABASE_URL", json.loads(redact_log(log))["command"])
        path = Path(self.temp.name) / "result.jsonl"
        path.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}}))
        with self.factory() as db:
            remember(db, "strategic", "qualification_policy", {"version": POLICY, "started_at": time.time() - 1})
            assess(db, {"identity": "merchant:test", "checks": checks()})
            db.commit()
        task = {"lease_token": "one", "id": "task", "stage": "qualify"}
        for _ in range(2):
            retain(self.factory, task, route("qualify")[0], path, 2, "done")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Usage).where(Usage.key == "acquisition-cli:one")), 1)
            stats = efficiency(db)
            self.assertIsNone(stats["model_spend_usd"])
            self.assertEqual(stats["metrics"]["eligible_prospect"]["reported_tokens"], 120)
