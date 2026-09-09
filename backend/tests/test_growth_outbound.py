"""Admission tests use isolated storage and never contact real merchants."""
import tempfile
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap, schedule
from app.growth.models import Contact, Experiment, FirstContact, Work
from app.growth.outbound import LIMIT, MAX_UNCERTAIN, authorize_submission, complete, reconcile_not_sent, reserve_contact, status
from app.growth.store import record, remember
from app.growth.policy import GrowthError
from app.growth.review_calendar import review_day


class OutboundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///'+str(Path(self.temp.name)/'cap.db'), connect_args={'timeout':30, 'check_same_thread':False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            exp = Experiment(key='fixture-outreach', specification={'channel':'shopify_community'}, stop_at=time.time()+864000)
            db.add(exp); db.flush(); self.exp = exp.id
            for n in range(40):
                db.add(Contact(id=str(n), identity='merchant:'+str(n), source='https://example.test/question',
                    qualification={'qualified':True}, facts=[{'verified':True,'source':'https://example.test','text':'Fixture store inventory question'}]))
            db.commit()

    def tearDown(self):
        self.engine.dispose(); self.temp.cleanup()

    def reserve(self, n, now=None):
        with self.factory() as db:
            result = reserve_contact(db, db.get(Contact,str(n)), action_key='contact:'+str(n),
                channel='contact_form' if n%2 else 'shopify_community', experiment_id=self.exp, body='Fixture '+str(n),
                cohort={'icp':'apparel','offer':'health_check','message_version':2}, now=now)
            db.commit(); return result

    def test_concurrent_channels_allow_only_one_live_permit_without_counting_it(self):
        def attempt(n):
            try: return self.reserve(n)
            except GrowthError: return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            admitted = [r for r in pool.map(attempt, range(25)) if r]
        self.assertEqual(len(admitted), 1)
        with self.factory() as db:
            view = status(db)
            self.assertEqual(view['remaining'],20)
            self.assertEqual(view['used'],0)
            self.assertEqual(view['in_flight_send_count'],1)
            self.assertEqual(view['dispatch_remaining'],0)
        schedule(self.factory)
        with self.factory() as db:
            self.assertIsNotNone(db.scalar(select(Work).where(Work.kind=='observe', Work.status=='ready')))

    def test_twelve_confirmed_eight_uncertain_can_reach_twenty_without_retries(self):
        unknown = []
        for n in range(20):
            item = self.reserve(n)
            with self.factory() as db:
                if n < 8:
                    unknown.append(item['reservation_id'])
                    complete(db,item['reservation_id'],outcome='uncertain')
                else:
                    complete(db,item['reservation_id'],receipt='receipt:'+str(n))
                db.commit()
        with self.factory() as db:
            view=status(db)
            self.assertEqual((view['used'],view['sent'],view['remaining'],view['uncertain_contact_count']),(12,12,8,8))
        for n in range(8):
            with self.assertRaises(GrowthError): self.reserve(n)
        for n in range(20,28):
            item=self.reserve(n)
            with self.factory() as db:
                authorize_submission(db,item['reservation_id'])
                complete(db,item['reservation_id'],receipt='receipt:'+str(n)); db.commit()
        with self.assertRaises(GrowthError): self.reserve(28)
        with self.factory() as db:
            self.assertEqual(status(db)['sent'],20)
            self.assertEqual(status(db)['uncertain_contact_count'],8)
            complete(db,unknown[0],receipt='late verified receipt'); db.commit()
            self.assertEqual(status(db)['sent'],21)
            self.assertEqual(status(db)['late_confirmation_overage'],1)
            self.assertEqual(status(db)['dispatch_remaining'],0)
            self.assertEqual(status(db)['next_slot_at'], review_day(time.time()).end)
        with self.assertRaises(GrowthError): self.reserve(29)

    def test_late_confirmation_fences_an_existing_permit(self):
        unknown=self.reserve(0)['reservation_id']
        with self.factory() as db:
            complete(db,unknown,outcome='uncertain'); db.commit()
        for n in range(1,20):
            item=self.reserve(n)
            with self.factory() as db:
                complete(db,item['reservation_id'],receipt='receipt:'+str(n)); db.commit()
        pending=self.reserve(20)['reservation_id']
        with self.factory() as db:
            complete(db,unknown,receipt='late receipt'); db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError): authorize_submission(db,pending)
            self.assertEqual(status(db)['sent'],20)

    def test_expired_and_consumed_permits_never_authorize_a_repeat(self):
        now=time.time()
        item=self.reserve(0,now=now)
        with self.factory() as db:
            authorize_submission(db,item['reservation_id'],now=now); db.commit()
        with self.factory() as db:
            with self.assertRaises(GrowthError): authorize_submission(db,item['reservation_id'],now=now+1)
            with self.assertRaises(GrowthError): authorize_submission(db,item['reservation_id'],now=now+601)
            view=status(db,now+601)
            self.assertEqual((view['sent'],view['remaining'],view['in_flight_send_count'],view['uncertain_contact_count']),(0,20,0,1))
        with self.assertRaises(GrowthError): self.reserve(0,now=now+601)
        self.reserve(1,now=now+601)

    def test_ambiguous_outcomes_cannot_accumulate_without_bound(self):
        for n in range(MAX_UNCERTAIN):
            item=self.reserve(n)
            with self.factory() as db:
                complete(db,item['reservation_id'],outcome='uncertain'); db.commit()
        with self.factory() as db:
            view=status(db)
            self.assertEqual((view['sent'],view['remaining']),(0,20))
            self.assertEqual(view['blocker'],'OUTREACH_UNCERTAINTY_SAFETY_HOLD')
        with self.assertRaises(GrowthError): self.reserve(MAX_UNCERTAIN)

    def test_uncapped_owner_policy_continues_after_twenty_and_late_confirmation(self):
        with self.factory() as db:
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': None})
            db.commit()
        unknown = self.reserve(0)['reservation_id']
        with self.factory() as db:
            complete(db, unknown, outcome='uncertain'); db.commit()
        for n in range(1, 23):
            item = self.reserve(n)
            with self.factory() as db:
                authorize_submission(db, item['reservation_id'])
                complete(db, item['reservation_id'], receipt='receipt:' + str(n)); db.commit()
        self.engine.dispose()  # The owner policy and duplicate fence survive restart.
        with self.factory() as db:
            view = status(db)
            self.assertEqual((view['sent'], view['uncertain_contact_count']), (22, 1))
            for field in ('limit', 'remaining', 'remaining_confirmed_capacity', 'next_slot_at', 'blocker'):
                self.assertIsNone(view[field], field)
            self.assertEqual(view['dispatch_remaining'], 1)
        with self.assertRaises(GrowthError): self.reserve(0)
        pending = self.reserve(23)['reservation_id']
        with self.factory() as db:
            complete(db, unknown, receipt='late verified receipt'); db.commit()
            authorize_submission(db, pending)
            complete(db, pending, receipt='receipt:23'); db.commit()
            self.assertEqual(status(db)['confirmed_sent_count'], 24)
            self.assertEqual(status(db)['late_confirmation_overage'], 0)
        from app.growth import browser_executor
        # No task is manually seeded: an empty queue still invokes autonomous planning.
        next_task = browser_executor.take(self.factory, 'uncapped-restarted-executor')
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task['stage'], 'plan')

    def test_uncapped_still_serializes_dispatch_and_bounds_ambiguous_outcomes(self):
        with self.factory() as db:
            remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': None}); db.commit()
        def attempt(n):
            try: return self.reserve(n)
            except GrowthError: return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            admitted = [r for r in pool.map(attempt, range(8)) if r]
        self.assertEqual(len(admitted), 1)
        with self.factory() as db:
            complete(db, admitted[0]['reservation_id'], outcome='uncertain'); db.commit()
        for n in range(8, 8 + MAX_UNCERTAIN - 1):
            item = self.reserve(n)
            with self.factory() as db:
                complete(db, item['reservation_id'], outcome='uncertain'); db.commit()
        with self.factory() as db:
            view = status(db)
            self.assertEqual(view['confirmed_sent_count'], 0)
            self.assertIsNone(view['remaining'])
            self.assertEqual(view['uncertain_contacts_protected'], MAX_UNCERTAIN)
            self.assertEqual(view['blocker'], 'OUTREACH_UNCERTAINTY_SAFETY_HOLD')
        with self.assertRaises(GrowthError): self.reserve(39)

    def test_invalid_owner_ceiling_fails_closed(self):
        with self.factory() as db:
            for value in (-1, True, 'unlimited', 2.5):
                remember(db, 'strategic', 'outreach_policy', {'daily_new_contact_limit': value})
                with self.subTest(value=value), self.assertRaises(GrowthError): status(db)

    def test_linked_merchant_history_blocks_cross_channel_duplicate_and_suppression(self):
        from app.growth.identity import link_merchant, merchant_view
        with self.factory() as db:
            link_merchant(db, {'merchant_key': 'fixture-store', 'routes': [
                {'identity': 'merchant:0', 'channel': 'contact_form', 'source': 'https://fixture.test/contact',
                 'relationship': 'Store contact page links the community profile.'},
                {'identity': 'merchant:1', 'channel': 'shopify_community', 'source': 'https://fixture.test/contact',
                 'relationship': 'Same store links this community profile.'}]})
            db.commit()
        item = self.reserve(0)
        with self.factory() as db:
            complete(db, item['reservation_id'], receipt='verified form receipt'); db.commit()
            history = merchant_view(db, 'merchant:1')
            self.assertEqual(set(history['contact_ids']), {'0', '1'})
            self.assertEqual(history['first_contacts'][0]['receipt'], 'verified form receipt')
        with self.assertRaisesRegex(GrowthError, 'already contacted'): self.reserve(1)
        with self.factory() as db:
            db.get(Contact, '0').suppressed = True; db.commit()
            self.assertTrue(merchant_view(db, 'merchant:1')['suppressed'])
        with self.assertRaisesRegex(GrowthError, 'suppressed'): self.reserve(1)

    def test_owner_pause_fences_admission_and_final_submission(self):
        pending=self.reserve(0)['reservation_id']
        with self.factory() as db:
            remember(db,'working','control',{'paused':True}); db.commit()
            with self.assertRaises(GrowthError): authorize_submission(db,pending)
        with self.assertRaises(GrowthError): self.reserve(1)
        with self.factory() as db:
            remember(db,'working','control',{'paused':True,'deployment_drain':'fixture-release'}); db.commit()
            authorize_submission(db,pending); db.commit()

    def test_midnight_reset_restart_and_permanent_dedupe(self):
        now = time.time()
        midnight = review_day(now).end
        for n in range(20):
            item = self.reserve(n, now=now)
            with self.factory() as db:
                complete(db,item['reservation_id'],receipt='receipt:'+str(n),now=now); db.commit()
        self.engine.dispose()
        with self.factory() as db:
            self.assertEqual(status(db,midnight-0.001)['remaining'],0)
            self.assertEqual(status(db,midnight)['remaining'],20)
            self.assertEqual(status(db,midnight)['day_timezone'],'America/Los_Angeles')
        with self.assertRaises(GrowthError): self.reserve(0,now=midnight)
        pending = self.reserve(20,now=midnight)['reservation_id']
        with self.factory() as db:
            complete(db,pending,receipt='today receipt',now=midnight); db.commit()
            self.assertEqual(status(db,midnight)['sent'],1)
            self.assertEqual(status(db,midnight)['remaining'],19)

    def test_pacific_day_handles_dst_and_retains_uncertainty_across_midnight(self):
        for day, hours in [('2026-03-08',23),('2026-11-01',25)]:
            now = datetime.fromisoformat(day+'T12:00:00').replace(tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()
            with self.factory() as db:
                view = status(db,now)
                self.assertEqual(view['day'],day)
                self.assertEqual(view['window_hours'],hours)
        now = time.time()
        item = self.reserve(0,now=now)
        with self.factory() as db:
            complete(db,item['reservation_id'],outcome='uncertain',now=now); db.commit()
        midnight = review_day(now).end
        with self.factory() as db:
            view = status(db,midnight)
            self.assertEqual((view['sent'],view['remaining'],view['uncertain_contact_count']),(0,20,1))
        with self.assertRaises(GrowthError): self.reserve(0,now=midnight)

    def test_suppression_and_missing_evidence_and_cohort_snapshot(self):
        with self.factory() as db:
            db.get(Contact,'0').suppressed=True
            db.get(Contact,'1').facts=[]
            db.commit()
        for n in (0,1):
            with self.assertRaises(GrowthError): self.reserve(n)
        result=self.reserve(2)
        with self.factory() as db:
            db.get(Contact,'2').qualification={'qualified':False}
            db.commit()
            row=db.get(FirstContact,result['reservation_id'])
            self.assertTrue(row.cohort['qualification']['qualified'])
            complete(db,row.id,receipt='verified-public-url'); db.commit()
            self.assertTrue(complete(db,row.id,receipt='verified-public-url')['already_recorded'])

    def test_reconciliation_needs_no_effect_evidence_and_invalidates_old_permit(self):
        reservation=self.reserve(0)['reservation_id']
        with self.factory() as db:
            with self.assertRaises(GrowthError): reconcile_not_sent(db,reservation,9999)
            proof=record(db,'fixture-no-send','OUTREACH_NOT_SENT_VERIFIED',reservation,
                         {'no_external_effect':True,'reason':'Fixture composer never submitted'},source='owner_operator')
            db.flush()
            reconcile_not_sent(db,reservation,proof.id); db.commit()
            self.assertEqual(status(db)['remaining'],20)
        fresh=self.reserve(0)['reservation_id']
        self.assertNotEqual(reservation,fresh)
        with self.factory() as db:
            with self.assertRaises(GrowthError): complete(db,reservation,receipt='stale')
