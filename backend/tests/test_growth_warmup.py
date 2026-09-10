import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth import warmup
from app.growth.messaging import ingest_reply
from app.growth.models import Contact, Evidence, FirstContact, Message, Memory
from app.growth.policy import GrowthError
from app.growth.review_calendar import review_day
from app.growth.store import get_memory, record, remember


class WarmupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.engine=create_engine('sqlite:///'+str(Path(self.temp.name)/'test.db'))
        Base.metadata.create_all(self.engine)
        self.factory=sessionmaker(self.engine,expire_on_commit=False,autoflush=False)
        bootstrap(self.factory)
        # Keep the delayed reply within the same fixture day, including late-night runs.
        self.now=review_day(time.time()).start + 12*3600
        self.sender='info@skubase.io'; self.recipient='controlled@fixture.test'
        with self.factory() as db:
            accounts={}
            for n,address in enumerate([self.sender,self.recipient]):
                ev=record(db,'owned:'+address,'CONTROLLED_INBOX_VERIFIED',address,{'observed':True})
                accounts[address]={'enabled':True,'evidence_id':ev.id,'url':f'https://mail.google.com/mail/u/{n}/#inbox'}
            remember(db,'strategic','controlled_email_tests',{'enabled':True,'accounts':accounts,'daily_ceiling':4})
            db.commit()

    def tearDown(self):
        self.engine.dispose(); self.temp.cleanup()

    def item(self, db):
        task=warmup.schedule(db,self.now)
        self.assertEqual(task['stage'],'deliverability')
        db.flush()
        return warmup.messages(db)[0]

    def sent(self,db,item,now=None):
        now=now or self.now
        warmup.authorize(db,item['id'],item['sender'],now)
        return warmup.observe(db,{'message_id':item['id'],'event':'sent','account':item['sender'],
            'url':'https://mail.google.com/mail/u/0/#sent/'+item['id'],'observation':'Fixture sender, recipient and exact body matched'},now)

    def received(self,db,item,folder='inbox'):
        return warmup.observe(db,{'message_id':item['id'],'event':'received','account':item['recipient'],
            'url':'https://mail.google.com/mail/u/1/#inbox/'+item['id'],'observation':'Fixture received in original folder',
            'folder':folder,'authentication':{'spf':'pass','dkim':'pass','dmarc':'pass'}},max(self.now,item['due_at'])+60)

    def test_persistent_thread_cycle_is_not_acquisition(self):
        with self.factory() as db:
            before={m.__name__:db.scalar(select(func.count()).select_from(m)) for m in [Contact,Message,FirstContact]}
            item=self.item(db); self.sent(db,item); self.received(db,item); db.commit()
        with self.factory() as db:
            replies=[r for r in warmup.messages(db) if r.get('parent_id')]
            self.assertEqual(len(replies),1)
            reply=replies[0]
            self.assertEqual(reply['parent_id'],item['id'])
            self.assertEqual(reply['subject'],item['subject'])
            self.assertEqual(reply['recipient'],item['sender'])
            self.assertGreaterEqual(reply['due_at'],self.now+2700)
            self.assertIsNone(warmup.schedule(db,self.now+120))
            with self.assertRaises(GrowthError): warmup.authorize(db,reply['id'],reply['sender'],self.now+120)
            self.sent(db,reply,reply['due_at']); db.commit()
            self.assertEqual(warmup.status(db,reply['due_at'])['totals']['threaded_replies'],1)
            self.assertEqual(before,{m.__name__:db.scalar(select(func.count()).select_from(m)) for m in [Contact,Message,FirstContact]})

    def test_scheduler_and_authorization_are_idempotent(self):
        with self.factory() as db:
            item=self.item(db)
            task=warmup.schedule(db,self.now)
            self.assertEqual(warmup.schedule(db,self.now)['id'],task['id'])
            warmup.authorize(db,item['id'],item['sender'],self.now)
            with self.assertRaises(GrowthError): warmup.authorize(db,item['id'],item['sender'],self.now+1)
            warmup.schedule(db,self.now+31)
            self.assertEqual(get_memory(db,warmup.NS,item['id'])['state'],'uncertain')
            with self.assertRaises(GrowthError): warmup.authorize(db,item['id'],item['sender'],self.now+32)

    def test_controlled_replies_bypass_merchant_classification(self):
        with self.factory() as db:
            item=self.item(db)
            result=ingest_reply(db,provider_id='fixture-inbound',sender=self.recipient,recipients=[self.sender],
                subject=item['subject'],text='Interested in testing reply routing. '+item['body'])
            self.assertIsNone(result)
            self.assertEqual(db.scalar(select(func.count()).select_from(Contact)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)),0)
            self.assertTrue(db.scalar(select(Evidence.id).where(Evidence.kind=='WARMUP_INBOUND')))

    def test_spam_correction_never_erases_initial_placement(self):
        with self.factory() as db:
            item=self.item(db); self.sent(db,item); self.received(db,item,'spam')
            warmup.observe(db,{'message_id':item['id'],'event':'moved_from_spam','account':item['recipient'],
                'url':'https://mail.google.com/mail/u/1/#inbox/'+item['id'],'observation':'Fixture legitimate test moved from spam'},self.now+90)
            view=warmup.status(db,self.now+100)
            self.assertEqual(view['totals']['initial_spam'],1)
            self.assertEqual(view['totals']['moved_from_spam'],1)
            self.assertTrue(view['hold'])
            self.assertFalse(view['counts_toward_outreach'])

    def test_unknown_accounts_and_foreign_receipts_fail_closed(self):
        with self.factory() as db:
            with self.assertRaises(GrowthError): warmup._new(db,self.sender,'merchant@other.test',self.now)
            item=self.item(db)
            with self.assertRaises(GrowthError): warmup.authorize(db,item['id'],'personal@gmail.com',self.now)
            with self.assertRaises(GrowthError): warmup.observe(db,{'message_id':item['id'],'event':'sent',
                'account':item['sender'],'url':'https://mail.google.com/mail/u/0/#sent/fixture','observation':'Unattempted draft'},self.now)

    def test_daily_limit_and_phase_end_are_independent_of_merchant_ramp(self):
        with self.factory() as db:
            item=self.item(db); self.sent(db,item); self.received(db,item)
            reply=[r for r in warmup.messages(db) if r.get('parent_id')][0]
            self.sent(db,reply,reply['due_at'])
            self.received(db,reply)
            view=warmup.status(db,reply['due_at'])
            self.assertEqual(view['sent_today'],2)
            self.assertEqual(view['remaining'],0)
            self.assertIsNone(warmup.schedule(db,self.now+5*3600))
            self.assertIsNone(warmup.schedule(db,self.now+15*86400))
            self.assertEqual(warmup.status(db,self.now+15*86400)['phase'],'complete')

    def test_missing_receipt_replay_does_not_add_failures(self):
        with self.factory() as db:
            item=self.item(db); self.sent(db,item)
            payload={'message_id':item['id'],'event':'not_found','account':item['recipient'],
                'url':'https://mail.google.com/mail/u/1/#search/fixture',
                'observation':'Fixture inspection attempt 1 found no matching receipt'}
            first=warmup.observe(db,payload,self.now+300)
            again=warmup.observe(db,payload,self.now+301)
            self.assertEqual(first['evidence_id'],again['evidence_id'])
            self.assertEqual(get_memory(db,warmup.NS,item['id'])['checks'],1)

    def test_owned_test_mailbox_cannot_become_outreach_recipient(self):
        from app.growth.outbound import reserve_contact
        with self.factory() as db:
            contact=Contact(identity='email:'+self.recipient,email=self.recipient,source='https://fixture.test')
            db.add(contact); db.flush()
            with self.assertRaisesRegex(GrowthError,'Owned business account'):
                reserve_contact(db,contact,action_key='test',channel='email',experiment_id=None,body='test',cohort={})


if __name__ == '__main__': unittest.main()
