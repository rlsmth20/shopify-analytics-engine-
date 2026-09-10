import tempfile
import time
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth.models import Contact, Evidence, FirstContact, Message
from app.growth import community_inbox as inbox, browser_executor as executor
from app.growth.policy import GrowthError
from app.growth.store import get_memory, remember


class CommunityInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'inbox.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)
        with self.factory() as db:
            c = Contact(identity='shopify-community:merchant', source='https://community.shopify.com/t/fixture/123/1')
            db.add(c); db.flush()
            self.contact_id = c.id
            db.add(FirstContact(contact_id=c.id, action_key='fixture', channel='shopify_community',
                experiment_id='fixture', cohort={}, body_hash='fixture', status='sent',
                sent_at=time.time()-1000, receipt='https://community.shopify.com/t/fixture/123/2'))
            db.commit()
        self.payload = {'url':'https://community.shopify.com/t/fixture/123/3',
            'parent_url':'https://community.shopify.com/t/fixture/123/2', 'author':'Merchant',
            'text':'The Excel export sounds useful. I will look at Skubase.', 'classification':'SUBSTANTIVE_POSITIVE'}

    def tearDown(self):
        self.engine.dispose(); self.temp.cleanup()

    def test_reply_is_attributed_deduped_prioritized_without_counting_send(self):
        with self.factory() as db:
            first = inbox.ingest_reply(db,self.payload)
            again = inbox.ingest_reply(db,{**self.payload,'url':self.payload['url']+'?u=skubase'})
            self.assertTrue(again['duplicate'])
            self.assertEqual(first['message_id'],again['message_id'])
            self.assertEqual(db.scalar(select(func.count()).select_from(Message)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(FirstContact)),1)
            event=db.get(Evidence,first['evidence_id'])
            self.assertEqual(event.data['experiment_id'],'fixture')
            self.assertEqual(event.subject,self.contact_id)
            db.commit()
        self.assertEqual(executor.take(self.factory,'worker')['stage'],'reply')

    def test_opt_out_overrides_model_and_never_queues_answer(self):
        with self.factory() as db:
            result=inbox.ingest_reply(db,{**self.payload,'text':'Please stop contacting me.'})
            self.assertNotIn('task_id',result)
            self.assertTrue(db.get(Contact,self.contact_id).suppressed)
            self.assertEqual(db.get(Message,result['message_id']).classification,'UNSUBSCRIBE')

    def test_uncertain_conversation_reply_never_reconciles_original_first_contact(self):
        from app.growth.operator import export_packet
        from app.growth.store import record
        with self.factory() as db:
            first=db.scalar(select(FirstContact))
            event=record(db,'uncertain-answer','ACQUISITION_STAGE_RESULT','answer',
                {'stage':'reply','stop_reason':'OUTREACH_OUTCOMES_UNRESOLVED'})
            base={'id':'receipt','key':'receipt','stage':'reply','status':'pending','attempts':0,
                'priority':100,'contact_id':self.contact_id,'evidence_id':event.id,'created_at':time.time()}
            remember(db,'operator_task','receipt',base)
            self.assertEqual(export_packet(db)['tasks'][0]['stage'],'reply')
            remember(db,'operator_task','receipt',{**base,'stage':'reconcile',
                'prior_reply_attempts':1,'receipt_completion':True,'reservation_id':first.id})
            task=export_packet(db)['tasks'][0]
            self.assertEqual((task['stage'],task['attempts']),('reply',1))
            self.assertNotIn('reservation_id',task)
            self.assertEqual(first.status,'sent')

    def test_suppressed_or_unmatched_author_cannot_create_engagement_work(self):
        with self.factory() as db:
            with self.assertRaises(GrowthError):
                inbox.ingest_reply(db,{**self.payload,'author':'another-vendor'})
            with self.assertRaises(GrowthError):
                inbox.ingest_reply(db,{**self.payload,'author':'Skubase'})
            db.get(Contact,self.contact_id).suppressed=True
            self.assertNotIn('task_id',inbox.ingest_reply(db,self.payload))

    def test_monitor_is_durable_bounded_and_does_not_refresh_send_safety(self):
        now=time.time()
        with self.factory() as db:
            remember(db,'working','community_inbox',{'enabled':True})
            remember(db,'working','browser_executor',{'last_progress_at':now-3600})
            one=inbox.schedule(db,now)
            self.assertIsNone(inbox.schedule(db,now+10))
            self.assertIsNone(inbox.schedule(db,now+inbox.INTERVAL+1))
            db.commit()
        task=executor.take(self.factory,'worker')
        self.assertEqual(task['id'],one['id'])
        executor.accept(self.factory,'worker',task,{'outcome':'done','observation':'No new actual replies in fixture.',
            'sources':['https://community.shopify.com/u/skubase/notifications'],
            'next_step':'Continue acquisition; next inbox check scheduled.', 'successors':[], 'stop_reason':None})
        with self.factory() as db:
            self.assertFalse(get_memory(db,'working','browser_safety_check'))
            self.assertEqual(get_memory(db,'working','browser_executor')['last_progress_at'],now-3600)
            state=get_memory(db,'working','community_inbox')
            self.assertGreater(state['next_check_at'],now)
            self.assertIsNone(inbox.schedule(db,now+60))
            self.assertIsNotNone(inbox.schedule(db,state['next_check_at']+1))


if __name__=='__main__':unittest.main()
