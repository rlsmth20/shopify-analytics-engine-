"""Admission tests use isolated storage and never contact real merchants."""
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap, schedule
from app.growth.models import Contact, Experiment, FirstContact, Work
from app.growth.outbound import LIMIT, complete, reconcile_not_sent, reserve_contact, status
from app.growth.store import record
from app.growth.policy import GrowthError


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
            for n in range(25):
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

    def test_concurrent_channels_cannot_admit_a_twenty_first_contact(self):
        def attempt(n):
            try: self.reserve(n); return True
            except GrowthError: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(25))), LIMIT)
        with self.factory() as db:
            self.assertEqual(status(db)['remaining'],0)
        # Full outbound capacity must not pause research/observation scheduling.
        schedule(self.factory)
        with self.factory() as db:
            self.assertIsNotNone(db.scalar(select(Work).where(Work.kind=='observe', Work.status=='ready')))

    def test_rolling_boundary_restart_uncertainty_and_permanent_dedupe(self):
        now = time.time()
        for n in range(20):
            item = self.reserve(n, now=now)
            with self.factory() as db:
                complete(db,item['reservation_id'],receipt='receipt:'+str(n),now=now); db.commit()
        self.engine.dispose()
        with self.factory() as db:
            self.assertEqual(status(db,now+86399)['remaining'],0)
            self.assertEqual(status(db,now+86400)['remaining'],20)
        with self.assertRaises(GrowthError): self.reserve(0,now=now+86401)
        self.reserve(20,now=now+86400)
        with self.factory() as db:
            self.assertEqual(status(db,now+172800)['remaining'],19)

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
