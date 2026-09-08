"""Exact public evidence and identity-safe discovery handoffs; no real IO."""
import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.discovery import ingest_opportunity, research_contact, vendor_promotion
from app.growth.engine import bootstrap
from app.growth.models import Contact, Evidence, Experiment, FirstContact, Memory
from app.growth.operator import NAMESPACE, export_packet
from app.growth.outbound import operator_action, reserve_contact
from app.growth.policy import GrowthError
from app.growth.store import claim, enqueue, finish, remember


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "research.db"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def opportunity(self, author="Merchant", post=94):
        with self.factory() as db:
            event = ingest_opportunity(db, url=f"https://community.shopify.com/t/example/12345/{post}",
                text="My Shopify store needs help with reorder planning.", author=author, published_at=time.time())
            db.commit()
            return event

    def research(self, event, fetch, key="research"):
        with self.factory() as db:
            enqueue(db, key, "research_contact", {"evidence_id": event.id}, priority=999)
            db.commit()
        item = claim(self.factory)
        result = research_contact(self.factory, item, fetch=fetch)
        finish(self.factory, item, result=result)
        return result

    @staticmethod
    def post(author="Merchant", number=94):
        return {"post_stream": {"posts": [{"username": author, "post_number": number,
            "cooked": "My store needs help with reorder planning and stockout forecasts."}]}}

    def test_later_reply_is_fetched_exactly_and_durably_queued_without_draft_or_send(self):
        event = self.opportunity()
        urls = []
        result = self.research(event, lambda url: urls.append(url) or self.post())
        self.assertEqual(urls, ["https://community.shopify.com/t/12345/94.json"])
        self.assertEqual(result["decision"], "operator_outreach_review_queued")
        with self.factory() as db:
            packet = export_packet(db)
            self.assertEqual(len(packet["tasks"]), 1)
            self.assertFalse(packet["tasks"][0]["send_authorized"])
            self.assertEqual(packet["tasks"][0]["contact_id"], event.subject)
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "COMMUNITY_RESPONSE_DRAFTED")), 0)

    def test_topic_cache_does_not_hide_second_participant_and_repeated_handoff_dedupes(self):
        first, second = self.opportunity(), self.opportunity("Other_Person", 95)
        with self.factory() as db:
            remember(db, "channel", "topic:12345", {"next_at": time.time() + 21600})
            db.commit()
        self.research(first, lambda url: self.post(), "first")
        self.research(second, lambda url: self.post("Other_Person", 95), "second")
        result = self.research(first, lambda url: self.fail("Repeat source must be cached"), "repeated")
        self.assertTrue(result["cached"])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory).where(Memory.namespace == NAMESPACE)), 2)
            # Remove the cache and reset just the research-window fixture. A
            # later re-observation must not reset/duplicate the durable handoff.
            for row in db.scalars(select(Memory).where(Memory.namespace == "channel", Memory.key.like("post:%"))):
                row.value = {}
            for row in db.scalars(select(Evidence).where(Evidence.kind == "RESEARCH_FETCH_INTENT")):
                row.occurred_at = time.time() - 21601
            db.commit()
        self.research(first, lambda url: self.post(), "new-window")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory).where(Memory.namespace == NAMESPACE)), 2)

    def test_wrong_author_or_post_never_substitutes_original_poster(self):
        for author, number, source_number in (("SomeoneElse", 94, 94), ("Merchant", 1, 95)):
            event = self.opportunity(post=source_number)
            result = self.research(event, lambda url: self.post(author, number), f"mismatch:{number}")
            self.assertEqual(result["decision"], "exact_post_not_in_bounded_source")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory).where(Memory.namespace == NAMESPACE)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence).where(Evidence.kind == "RESEARCH_SOURCE_UNRESOLVED")), 2)

    def test_ingestion_reuses_manual_identity_and_retains_suppression(self):
        with self.factory() as db:
            manual = Contact(identity="shopify-community:merchant", source="https://community.shopify.com/t/12345",
                             suppressed=True, status="declined")
            db.add(manual); db.commit()
            manual_id = manual.id
        event = self.opportunity()
        self.assertEqual(event.subject, manual_id)
        result = self.research(event, lambda url: self.fail("Suppressed source must not be researched"))
        self.assertEqual(result["decision"], "do_not_contact")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Contact)), 1)
            self.assertEqual(db.get(Contact, manual_id).status, "declined")

    def test_old_mixed_case_identity_remains_the_same_contact(self):
        with self.factory() as db:
            old = Contact(identity="shopify_community:MerChant", source="https://community.shopify.com/t/12345")
            db.add(old); db.commit(); old_id = old.id
        self.assertEqual(self.opportunity().subject, old_id)
        with self.factory() as db:
            self.assertEqual(db.get(Contact, old_id).identity, "shopify_community:MerChant")
            self.assertEqual(db.scalar(select(func.count()).select_from(Contact)), 1)

    def test_legacy_sent_alias_blocks_handoff_and_new_admission(self):
        event = self.opportunity()
        with self.factory() as db:
            legacy = Contact(identity="shopify_community:MERCHANT", source=event.source)
            db.add(legacy); db.flush()
            exp = Experiment(key="identity-fixture", specification={}, stop_at=time.time() + 86400)
            db.add(exp); db.flush(); experiment_id = exp.id
            db.add(FirstContact(contact_id=legacy.id, action_key="old", channel="shopify_community",
                experiment_id=exp.id, cohort={}, body_hash="old", status="sent", sent_at=time.time() - 100000))
            db.commit()
        result = self.research(event, lambda url: self.post())
        self.assertEqual(result["decision"], "already_contacted")
        with self.factory() as db:
            with self.assertRaisesRegex(GrowthError, "already contacted"):
                reserve_contact(db, db.get(Contact, event.subject), action_key="new", channel="shopify_community",
                    experiment_id=experiment_id, body="Skubase promotion", cohort={"icp":"fixture", "offer":"check", "message_version":3})
            self.assertEqual(db.scalar(select(func.count()).select_from(Memory).where(Memory.namespace == NAMESPACE)), 0)

    def test_operator_cannot_bypass_suppressed_legacy_alias(self):
        self.opportunity()
        with self.factory() as db:
            db.add(Contact(identity="shopify_community:MERCHANT", source="https://community.shopify.com/t/12345", suppressed=True))
            db.commit()
        with self.factory() as db:
            with self.assertRaisesRegex(GrowthError, "Suppressed"):
                operator_action(db, "outreach-reserve", {"identity":"shopify-community:merchant", "channel":"shopify_community",
                    "channel_rules_source":"https://community.shopify.com/guidelines", "relevance_evidence":"Exact merchant statement"})

    def test_merchant_who_built_a_tool_can_reach_review_but_explicit_app_promotion_cannot(self):
        self.assertFalse(vendor_promotion("My apparel store needs reorder help; our approach is a spreadsheet."))
        merchant_text = "My Shopify store needs help with stockout forecasts. I built a spreadsheet but need reorder planning."
        vendor_text = "My Shopify store needs reorder planning. Try our app which handles all stockouts."
        for index, (body, eligible) in enumerate(((merchant_text, True), (vendor_text, False))):
            with self.factory() as db:
                event = ingest_opportunity(db, url=f"https://community.shopify.com/t/example/12345/{94+index}",
                    text=body, author=f"merchant{index}", published_at=time.time())
                self.assertEqual(event.data["qualification"]["qualified"], eligible)
                db.commit()
            payload = {"post_stream":{"posts":[{"username":f"merchant{index}", "post_number":94+index, "cooked":body}]}}
            result = self.research(event, lambda url: payload, f"role:{index}")
            self.assertEqual(result["decision"], "operator_outreach_review_queued" if eligible else "not_qualified")
        with self.factory() as db:
            packet = export_packet(db)
            self.assertEqual(len(packet["tasks"]), 1)
            self.assertFalse(packet["tasks"][0]["send_authorized"])
