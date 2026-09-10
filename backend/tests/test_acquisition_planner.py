import tempfile
import time
import unittest
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.growth.engine import bootstrap
from app.growth import browser_executor as executor, acquisition_planner as planner
from app.growth.models import Evidence, Memory, FirstContact
from app.growth.store import record, remember, get_memory
from app.growth.operator import offer


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'planner.db'))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        bootstrap(self.factory)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def result(self, proposals=None):
        return {'outcome':'done','observation':'fixture evidence synthesis','sources':['retained evidence'],
            'next_step':'Execute admitted hypothesis','stop_reason':None,'successors':[],
            'hypotheses': proposals if proposals is not None else [self.proposal()], 'search_result':None,'idle':None}

    def proposal(self, query='supplier lead times inventory spreadsheet'):
        return {'hypothesis':'Merchants struggling with supplier lead times need reorder priorities',
            'channel':'community.shopify.com','problem':'supplier lead times','segment':'physical goods operators',
            'query':query,'decision':'Find exact recent merchant requests; four source reads maximum.',
            'source':'https://community.shopify.com/search','rationale':'Adjacent supported planning need',
            'expected_value':6,'confidence':.4}

    def test_empty_queue_plans_then_discovers_without_seed_or_continuation(self):
        seen=[]
        def adapter(task):
            seen.append(task['stage'])
            if task['stage']=='plan':return self.result()
            return {**self.result([]),'observation':'One real source in isolated fixture',
                'search_result':{'result_count':1,'qualified_count':0,'rejection_reasons':[]},
                'successors':[{'key':'fixture:merchant:qualify','source':'https://example.com/request',
                    'decision':'Qualify merchant-owned inventory need','stage':'qualify'}]}
        self.assertTrue(executor.cycle(self.factory,'first-process',adapter))
        self.assertTrue(executor.cycle(self.factory,'restarted-process',adapter))
        self.assertEqual(seen,['plan','discover'])
        task=executor.take(self.factory,'restarted-process')
        self.assertEqual(task['stage'],'qualify')
        self.assertTrue(task['hypothesis_id'])
        with self.factory() as db:
            self.assertIsNone(db.scalar(select(FirstContact)))
            events=list(db.scalars(select(Evidence).where(Evidence.kind=='ACQUISITION_QUEUE_EMPTY')))
            self.assertEqual(events[0].data['depth'],0)

    def test_terminal_channel_outcome_does_not_globally_stop_discovery(self):
        with self.factory() as db:
            remember(db,'operator_task','terminal',{'stage':'send','status':'blocked','attempts':3})
            db.commit()
        task = executor.take(self.factory,'executor')
        self.assertEqual(task['stage'], 'plan')
        executor.accept(self.factory,'executor',task,self.result())
        with self.factory() as db:
            e=record(db,'terminal-outcome','ACQUISITION_STAGE_RESULT','terminal',{'outcome':'blocked'})
            remember(db,'operator_task','terminal',{'stage':'send','status':'blocked','attempts':3,'result_evidence_id':e.id})
            db.commit()
        self.assertEqual(executor.take(self.factory,'executor')['stage'],'discover')

    def test_exhausted_prepare_is_isolated_and_next_hypothesis_executes(self):
        with self.factory() as db:
            remember(db,'operator_task','failed-form',{'id':'failed-form','stage':'prepare',
                'status':'blocked','attempts':3,'error':'No executable successor',
                'source':'https://example.com/contact'})
            db.commit()
        plan=executor.take(self.factory,'autonomous')
        self.assertEqual(plan['stage'],'plan')
        executor.accept(self.factory,'autonomous',plan,self.result())
        discovery=executor.take(self.factory,'autonomous')
        self.assertEqual(discovery['stage'],'discover')
        with self.factory() as db:
            failed=get_memory(db,'operator_task','failed-form')
            self.assertEqual((failed['status'],failed['attempts']),('blocked',3))
            self.assertTrue(failed['branch_failure_evidence_id'])
            self.assertEqual(len(list(db.scalars(select(Evidence).where(
                Evidence.kind=='ACQUISITION_BRANCH_EXHAUSTED')))),1)
            self.assertIsNone(db.scalar(select(FirstContact)))

    def test_explicitly_excluded_route_needs_no_manufactured_successor(self):
        with self.factory() as db:
            e=record(db,'route','OBSERVATION','merchant',{})
            offer(db,key='prepare-no-form',source='https://example.com/contact',
                decision='Check form route',stage='prepare',evidence_id=e.id)
            db.commit()
        task=executor.take(self.factory,'autonomous')
        executor.accept(self.factory,'autonomous',task,{**self.result([]),'outcome':'excluded',
            'observation':'Published contact page offers email only, no business form.',
            'search_result':{'rejection_reasons':['NO_USABLE_CONTACT_FORM_ROUTE']}})
        self.assertEqual(executor.take(self.factory,'autonomous')['stage'],'plan')

    def test_uncertain_contacts_and_receipt_backlog_do_not_block_new_discovery(self):
        from app.growth.models import Contact
        from app.growth.outbound import status
        with self.factory() as db:
            for n in range(20):
                contact=Contact(identity=f'fixture:{n}',source='https://example.com/contact')
                db.add(contact); db.flush()
                db.add(FirstContact(contact_id=contact.id,action_key=f'fixture:{n}',channel='contact_form',
                    experiment_id='fixture',cohort={},body_hash='fixture',reserved_at=time.time()-1200,
                    status='uncertain' if n<8 else 'sent',sent_at=None if n<8 else time.time()-1000))
            source=record(db,'receipt-source','OBSERVATION','receipt',{'fixture':True})
            offer(db,key='receipt-backlog',source='https://example.com/contact',decision='Check retained receipt',
                  stage='reconcile',evidence_id=source.id)
            remember(db,'operator_task','old-uncertain-send',{'stage':'send','status':'blocked','attempts':3})
            db.commit()
            self.assertEqual((status(db)['sent'],status(db)['remaining']),(12,8))
        task=executor.take(self.factory,'autonomous-worker')
        self.assertEqual(task['stage'],'plan')
        executor.accept(self.factory,'autonomous-worker',task,self.result())
        task=executor.take(self.factory,'autonomous-worker')
        self.assertEqual(task['stage'],'discover')
        with self.factory() as db:
            self.assertEqual(status(db)['uncertain_contact_count'],8)

    def test_pending_retry_hold_capacity_mission_and_competing_executor(self):
        with self.factory() as db:
            self.assertIsNone(planner.replenish(db,{'remaining':0}))
            remember(db,'working','acquisition_hold',{'reason':'incident'})
            self.assertIsNone(planner.replenish(db,{'remaining':15}))
            remember(db,'working','acquisition_hold',{})
            remember(db,'working','browser_safety_check',{'requires_attention':True})
            self.assertIsNone(planner.replenish(db,{'remaining':15}))
            remember(db,'working','browser_safety_check',{})
            for n in range(10):record(db,f'connection:{n}','SHOPIFY_CONNECTION',f'shop:{n}',{'verified':True})
            self.assertIsNone(planner.replenish(db,{'remaining':15}))
            db.rollback()
        task=executor.take(self.factory,'one')
        self.assertEqual(task['stage'],'plan')
        self.assertIsNone(executor.take(self.factory,'two'))
        executor.failed(self.factory,'one',task,'temporary provider outage')
        self.assertIsNone(executor.take(self.factory,'one'))

    def test_semantic_date_and_synonym_duplicates_are_rejected(self):
        task=executor.take(self.factory,'one')
        executor.accept(self.factory,'one',task,self.result([self.proposal('overstock after:2026-09-01 order:latest'),
                                                              self.proposal('excess inventory after:2026-09-08 order:latest')]))
        with self.factory() as db:
            hypotheses=list(db.scalars(select(Memory).where(Memory.namespace==planner.HYPOTHESES)))
            self.assertEqual(len(hypotheses),1)
            admission=db.scalar(select(Evidence).where(Evidence.kind=='ACQUISITION_HYPOTHESES'))
            self.assertEqual(admission.data['rejected'][0]['reason'],'semantically_duplicate_search')

    def test_history_downweights_vendor_heavy_source_and_preserves_unknown(self):
        p=self.proposal()
        vendor=[{'source':p['channel'],'qualified_count':0,'value':'no_successor','rejection_reasons':['vendors only']}]*3
        self.assertLess(planner.score(p,vendor),planner.score(p,[]))
        task=executor.take(self.factory,'one')
        executor.accept(self.factory,'one',task,self.result())
        task=executor.take(self.factory,'one')
        result={**self.result([]),'stop_reason':'DISCOVERY_EXHAUSTED_FOR_CURRENT_SEARCH_SPACE',
            'search_result':{'result_count':3,'qualified_count':0,'rejection_reasons':['vendors only']}}
        executor.accept(self.factory,'one',task,result)
        with self.factory() as db:
            history=get_memory(db,planner.SEARCHES,task['id'])
            self.assertEqual(history['result_count'],3)
            self.assertIsNone(history['cost']['estimated_usd'])
            self.assertEqual(get_memory(db,planner.HYPOTHESES,task['hypothesis_id'])['status'],'retired')

    def test_former_daily_limits_and_persisted_wait_do_not_stop_autonomous_work(self):
        with self.factory() as db:
            remember(db,'strategic','qualification_policy',{'version':'market_discovery_v1'})
            for n in range(30):
                record(db,f'plan:{n}','ACQUISITION_PLANNER_QUEUED','acquisition',{})
                record(db,f'start:{n}','ACQUISITION_DISCOVERY_STARTED',str(n),{})
                remember(db,'operator_task',f'old:{n}',{'stage':'discover','status':'done','created_at':time.time()})
            remember(db,'working','acquisition_planner',{'status':'exploration_budget_wait','retry_at':time.time()+86400})
            db.commit()
        task=executor.take(self.factory,'new-process')
        self.assertEqual(task['stage'],'plan')
        executor.accept(self.factory,'new-process',task,self.result())
        task=executor.take(self.factory,'new-process')
        self.assertEqual(task['stage'],'discover')
        with self.factory() as db:
            self.assertEqual(len(list(db.scalars(select(Evidence).where(Evidence.kind=='ACQUISITION_PLANNER_QUEUED')))),31)
            self.assertIsNotNone(db.scalar(select(Evidence).where(Evidence.kind=='ACQUISITION_RESEARCH_WAIT_RETIRED')))

    def test_removing_research_wait_cannot_bypass_contact_capacity_or_safety_hold(self):
        with self.factory() as db:
            remember(db,'working','acquisition_planner',{'status':'exploration_budget_wait','retry_at':time.time()+86400})
            self.assertIsNone(planner.replenish(db,{'remaining':0}))
            remember(db,'working','acquisition_hold',{'reason':'unresolved safety incident'})
            self.assertIsNone(planner.replenish(db,{'remaining':8}))
            self.assertEqual(get_memory(db,'working','acquisition_planner')['status'],'exploration_budget_wait')

    def test_unsupported_idle_cannot_end_mission_or_restart_immediately(self):
        task=executor.take(self.factory,'one')
        executor.accept(self.factory,'one',task,{**self.result([]),'stop_reason':'TRUE_IDLE',
            'idle':{'external_condition':'Owner should assign a task','attempted_evidence_ids':[]}})
        with self.factory() as db:
            self.assertEqual(get_memory(db,'working','acquisition_planner')['status'],'planning_retry')
        self.assertIsNone(executor.take(self.factory,'one'))

if __name__=='__main__':unittest.main()
