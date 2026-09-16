"""Regression tests for acquisition outcome attribution and honest missing data."""
import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.models import Contact, Experiment, FirstContact, Message, Usage
from app.growth.outcomes import decision_context, review_context, snapshot
from app.growth.store import record, remember


class OutcomeTests(unittest.TestCase):
    def focus(self):
        from app.growth.validation import KEY, VERSION, LABELS
        exp = Experiment(id="focus", key=KEY, specification={"cohort_labels": LABELS, "max_contacts": 50},
                         started_at=self.now - 864000, stop_at=self.now + 864000)
        self.db.add(exp)
        remember(self.db, "strategic", "focused_validation", {"version": VERSION, "active": True, "experiment_id": exp.id})
        self.db.flush()
        return exp

    def test_focused_grouping_ignores_industry_and_wording_but_preserves_channels_and_history(self):
        from app.growth.validation import LABELS, VERSION
        self.focus()
        for i, channel in enumerate(["email", "email", "shopify_community"]):
            _, row = self.merchant("focused" + str(i), experiment="focus", channel=channel)
            row.cohort = {**LABELS, "cohort_policy": VERSION, "industry": "category" + str(i), "cta": "wording" + str(i)}
        self.merchant("old-a", variant="A")
        self.merchant("old-b", variant="B")
        s = snapshot(self.db, self.now)
        cohorts = [c for c in s["cohorts"] if c["experiment_id"] == "focus"]
        self.assertEqual(sorted(c["metrics"]["confirmed_contacts"] for c in cohorts), [1, 2])
        self.assertEqual(len(s["cohorts"]), 4)
        self.assertEqual(s["next_decision_point"]["target"], 50)
        self.assertEqual(s["focused_validation"]["metrics"]["confirmed_contacts"], 3)

    def test_tagged_visit_and_authenticated_conversions_without_claiming_prospect_identity(self):
        from app.growth.validation import KEY
        self.focus()
        contact, row = self.merchant("new-merchant", experiment="focus", age=60)
        tags = {"utm_source": "email", "utm_medium": "outreach", "utm_campaign": KEY, "utm_content": "outreach-" + contact.id}
        record(self.db, "visit", "VISITOR", "visitor:opaque", {"attribution": tags, "verified": False},
               source="first_party_browser", occurred_at=self.now - 30)
        self.assertEqual(snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]["SITE_VISIT"], 1)
        record(self.db, "auth", "IDENTITY_LINK", "visitor:opaque", {"shop_id": 42}, source="authenticated_session", occurred_at=self.now - 10)
        for kind in ["SIGNUP", "SHOPIFY_CONNECTION", "INVENTORY_ANALYSIS_COMPLETED", "TRIAL_STARTED", "SUBSCRIPTION_PURCHASED"]:
            record(self.db, kind, kind, "shop:42", {"verified": True, "payment_verified": kind == "SUBSCRIPTION_PURCHASED"}, occurred_at=self.now - 15)
        f = snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]
        self.assertEqual(f["SITE_VISIT"], 1)
        for stage in ["ACCOUNT_CREATED", "SHOPIFY_CONNECTED", "INVENTORY_ANALYSIS_COMPLETED", "TRIAL_STARTED", "PAID"]:
            self.assertEqual(f[stage], 1, stage)
        self.assertIsNone(contact.shop_id)

    def test_uncertain_wrong_campaign_and_pre_send_links_do_not_attribute(self):
        from app.growth.validation import KEY
        self.focus()
        for i, (status, campaign, age) in enumerate([("uncertain", KEY, 5), ("sent", "wrong", 5), ("sent", KEY, 120)]):
            contact, _ = self.merchant("bad" + str(i), experiment="focus", status=status, age=60)
            record(self.db, "v" + str(i), "VISITOR", "visitor:" + str(i), {"attribution": {
                "utm_source": "email", "utm_medium": "outreach", "utm_campaign": campaign, "utm_content": "outreach-" + contact.id}},
                source="first_party_browser", occurred_at=self.now - age)
        self.assertIsNone(snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]["SITE_VISIT"])

    def test_focused_checkpoint_waits_for_responses_then_requires_material_change(self):
        self.focus()
        for i in range(50):
            self.merchant("sample" + str(i), experiment="focus", age=60)
        self.assertEqual(snapshot(self.db, self.now)["focused_validation"]["decision"], "OBSERVE_RESPONSES")
        self.assertEqual(snapshot(self.db, self.now + 8 * 86400)["focused_validation"]["decision"], "CHANGE_ONE_MAJOR_VARIABLE")

    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(self.engine, expire_on_commit=False)()
        self.now = 1789516800.0

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def merchant(self, name, *, status="sent", channel="email", shop=None, age=60, experiment="exp", variant="C", source=None):
        c = Contact(identity=name, organization=name, source="https://" + name, shop_id=shop, created_at=self.now - age,
                    qualification={"qualified": True})
        self.db.add(c)
        self.db.flush()
        row = FirstContact(contact_id=c.id, action_key=name, channel=channel, experiment_id=experiment,
            cohort={"icp": "apparel", "offer": "health_check", "message_variant": variant, "source": source},
            body_hash="test", status=status, reserved_at=self.now - age,
            sent_at=self.now - age if status == "sent" else None, receipt="https://receipt.test" if status == "sent" else None)
        self.db.add(row)
        self.db.flush()
        return c, row

    def event(self, c, kind, *, at=None, data=None, key=None):
        return record(self.db, key or kind + c.id, kind, f"shop:{c.shop_id}" if c.shop_id else c.id,
                      data or {"verified": True}, occurred_at=at or self.now - 5)

    def test_unknown_does_not_become_zero_delivery_activation_payment_or_spend(self):
        c, row = self.merchant("shop")
        self.event(c, "IMPORT_COMPLETED")
        self.event(c, "INVENTORY_ANALYSIS_VIEWED")
        self.event(c, "SUBSCRIPTION_STARTED")
        self.db.add(Usage(key="paid-api", model="small", task="qualify", estimated_usd=.02, created_at=self.now - 10))
        self.db.add(Usage(key="subscription", model="astra", category="codex_subscription", task="review", estimated_usd=None, created_at=self.now - 10))
        s = snapshot(self.db, self.now)["periods"]["all_time"]
        self.assertEqual(s["metrics"]["confirmed_contacts"], 1)
        self.assertEqual(s["metrics"]["substantive_responses"], 0)
        for field in ("PAID", "ACTIVATED", "INVENTORY_ANALYSIS_COMPLETED", "DELIVERED"):
            self.assertIsNone(s["funnel"][field])
        self.assertIsNone(s["metrics"]["mrr"])
        self.assertIsNone(s["costs"]["model_api_cost"])
        self.assertEqual(s["costs"]["known_model_api_cost"], .02)

    def test_uncertainty_pending_failure_and_confirmed_channels_are_separate(self):
        for name, status, age in (("sent", "sent", 30), ("pending", "reserved", 30), ("expired", "reserved", 900), ("unknown", "uncertain", 50), ("failed", "failed", 50)):
            self.merchant(name, status=status, age=age, channel="contact_form")
        a = snapshot(self.db, self.now)["periods"]["all_time"]["accounting"]
        self.assertEqual(a["confirmed_contacts"], 1)
        self.assertEqual(a["form_submissions"], 1)
        self.assertEqual(a["uncertain_submissions"], 2)
        self.assertEqual(a["pending_reservations"], 1)
        self.assertEqual(a["failed_attempts"], 1)

    def test_old_unverified_and_unlinked_product_activity_cannot_be_attributed(self):
        c, row = self.merchant("linked", shop=42)
        self.event(c, "SIGNUP", at=row.sent_at - 1)
        self.event(c, "SHOPIFY_CONNECTION", data={"verified": False})
        record(self.db, "unrelated", "SUBSCRIPTION_PURCHASED", "shop:99", {"verified": True, "payment_verified": True}, occurred_at=self.now - 1)
        self.event(c, "SUBSCRIPTION_PURCHASED", data={"verified": True, "payment_verified": False})
        f = snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]
        for stage in ("ACCOUNT_CREATED", "SHOPIFY_CONNECTED", "PAID"):
            self.assertIsNone(f[stage])
        self.event(c, "SUBSCRIPTION_PURCHASED", key="actual-pay", data={"verified": True, "payment_verified": True})
        remember(self.db, "economics", "shop:42", {"active": True, "monthly_recurring_usd": 19})
        s = snapshot(self.db, self.now)
        self.assertEqual(s["periods"]["all_time"]["metrics"]["paying_customers"], 1)
        self.assertEqual(s["periods"]["all_time"]["metrics"]["mrr"], 19)
        self.assertEqual(s["best_signal"]["kind"], "PAID")

    def test_thread_identity_excludes_foreign_experiment_and_automated_responses(self):
        c, row = self.merchant("thread")
        original = Message(key="out", contact_id=c.id, experiment_id="other", direction="out", body="fixture", sent_at=row.sent_at)
        self.db.add(original)
        self.db.flush()
        for key, classification, exp, parent in (("wrong-thread", "SUBSTANTIVE_POSITIVE", "exp", original.id),
            ("automatic", "AUTOMATED", "exp", None), ("unattributed", "SUBSTANTIVE_POSITIVE", None, None),
            ("question", "QUESTION", "exp", None), ("question-repeat", "QUESTION", "exp", None)):
            self.db.add(Message(key=key, contact_id=c.id, experiment_id=exp, reply_to_id=parent,
                direction="in", classification=classification, body="fixture", created_at=self.now - 1))
        metrics = snapshot(self.db, self.now)["periods"]["all_time"]["metrics"]
        self.assertEqual(metrics["substantive_responses"], 1)
        self.assertEqual(metrics["positive_responses"], 0)

    def test_source_urls_do_not_fragment_stable_experiment_cohorts(self):
        self.merchant("a", source="https://a.test/contact")
        self.merchant("b", source="https://b.test/contact")
        self.merchant("c", variant="A")
        s = snapshot(self.db, self.now)
        self.assertEqual(len(s["cohorts"]), 2)
        self.assertEqual(max(c["metrics"]["confirmed_contacts"] for c in s["cohorts"]), 2)
        self.assertTrue(all(v is None for v in s["best"].values()))

    def test_first_party_visits_need_unambiguous_authenticated_identity_link(self):
        c, row = self.merchant("visitor-shop", shop=43)
        record(self.db, "visit", "VISITOR", "visitor:linked", {"verified": False}, source="first_party_browser", occurred_at=self.now - 4)
        record(self.db, "price", "PRICING_VIEWED", "visitor:linked", {"verified": False}, source="first_party_browser", occurred_at=self.now - 3)
        record(self.db, "impression", "VISITOR", "visitor:unknown", {"verified": False}, source="first_party_browser", occurred_at=self.now - 4)
        record(self.db, "link", "IDENTITY_LINK", "visitor:linked", {"shop_id": 43}, source="authenticated_session", occurred_at=self.now - 1)
        f = snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]
        self.assertEqual(f["SITE_VISIT"], 1)
        self.assertEqual(f["PRICING_VIEWED"], 1)
        record(self.db, "conflicting-link", "IDENTITY_LINK", "visitor:linked", {"shop_id": 99}, source="authenticated_session", occurred_at=self.now - 1)
        self.assertIsNone(snapshot(self.db, self.now)["periods"]["all_time"]["funnel"]["SITE_VISIT"])

    def test_verified_organic_request_can_convert_without_fabricating_contact(self):
        c = Contact(identity="organic", source="https://shop.test", shop_id=90, created_at=self.now - 100)
        exp = Experiment(key="organic-tool", specification={"channel": "organic_search", "offer": "health_check"},
                         started_at=self.now - 200, stop_at=self.now + 500)
        self.db.add_all([c, exp])
        self.db.flush()
        record(self.db, "request", "ACCESS_REQUESTED", c.id, {"verified": True, "utm_campaign": exp.key}, occurred_at=self.now - 50)
        self.event(c, "SHOPIFY_CONNECTION")
        self.event(c, "SUBSCRIPTION_PURCHASED", data={"verified": True, "payment_verified": True})
        s = snapshot(self.db, self.now)
        self.assertEqual(s["periods"]["all_time"]["metrics"]["confirmed_contacts"], 0)
        self.assertEqual(s["periods"]["all_time"]["metrics"]["paying_customers"], 1)
        self.assertEqual(s["best"]["channel"], "organic_search")
        organic = next(ch for ch in s["channels"] if ch["channel"] == "organic_search")
        self.assertEqual(organic["metrics"]["positive_responses"], 1)
        self.assertIsNone(organic["rates"]["contact_to_positive_response"])

    def test_address_scoped_bounce_evidence_updates_correct_contact_and_time(self):
        c, row = self.merchant("bounce")
        self.merchant("okay")
        record(self.db, "bounce-suppression", "OUTREACH_SUPPRESSED", "bad@shop.test",
               {"contact_ids": [c.id], "reason": "bounce"}, source="verified_business_mailbox", occurred_at=self.now - 1)
        s = snapshot(self.db, self.now)["periods"]["all_time"]
        self.assertEqual(s["accounting"]["bounced_emails"], 1)
        self.assertEqual(s["rates"]["bounce_rate"], .5)

    def test_today_response_from_yesterday_does_not_inflate_today_contact_rate(self):
        c, row = self.merchant("prior", age=86400)
        self.db.add(Message(key="reply", contact_id=c.id, experiment_id="exp", direction="in", body="yes",
                            classification="SUBSTANTIVE_POSITIVE", created_at=self.now - 1))
        s = snapshot(self.db, self.now)["periods"]
        self.assertEqual(s["today"]["metrics"]["confirmed_contacts"], 0)
        self.assertEqual(s["today"]["metrics"]["positive_responses"], 1)
        self.assertIsNone(s["today"]["rates"]["contact_to_positive_response"])
        self.assertEqual(s["all_time"]["rates"]["contact_to_positive_response"], 1)

    def test_seventy_five_mature_zero_replies_requires_monitor_and_preserves_paid_signal(self):
        for i in range(75):
            self.merchant(f"merchant{i}", age=8*86400)
        self.assertEqual(snapshot(self.db, self.now)["bottleneck"]["stage"], "insufficient_evidence")
        monitor = record(self.db, "monitor", "CHANNEL_MONITOR", "task", {"mailbox": "info@skubase.io", "requires_attention": False},
                         source="authenticated_browser_executor", occurred_at=self.now - 30)
        remember(self.db, "working", "browser_safety_check", {"evidence_id": monitor.id})
        s = snapshot(self.db, self.now)
        self.assertEqual(s["bottleneck"]["stage"], "contact_to_response")
        self.assertEqual(s["next_decision_point"]["target"], 100)
        self.assertEqual(s["cohorts"][0]["maturity"], "REVIEW")
        context = review_context(self.db, self.now)
        self.assertTrue(context["cohorts"][0]["response_observation_available"])
        self.assertIn("costs", context)

    def test_historical_intent_not_a_customer_and_planner_context_bounded(self):
        record(self.db, "historical", "HISTORICAL_PURCHASE_INTENT", "historical", {"sample_size": 1}, occurred_at=self.now - 500)
        for i in range(50):
            self.merchant(f"cohort{i}", experiment=f"experiment{i}")
        s = snapshot(self.db, self.now)
        self.assertIsNone(s["periods"]["all_time"]["metrics"]["paying_customers"])
        self.assertEqual(s["best_signal"]["kind"], "PURCHASE_INTENT_EVIDENCE")
        context = decision_context(self.db, self.now)
        self.assertLessEqual(len(json.dumps(context)), 4000)
        self.assertGreater(context["cohorts_omitted"], 0)


if __name__ == "__main__":
    unittest.main()
