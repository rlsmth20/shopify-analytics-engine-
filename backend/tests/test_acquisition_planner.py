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
        self.assertIsNone(executor.take(self.factory,'executor'))
        with self.factory() as db:
            e=record(db,'terminal-outcome','ACQUISITION_STAGE_RESULT','terminal',{'outcome':'blocked'})
            remember(db,'operator_task','terminal',{'stage':'send','status':'blocked','attempts':3,'result_evidence_id':e.id})
            db.commit()
        self.assertEqual(executor.take(self.factory,'executor')['stage'],'plan')

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

    def test_budget_wait_is_durable_not_true_idle(self):
        with self.factory() as db:
            for n in range(planner.MAX_PLANS):record(db,f'plan:{n}','ACQUISITION_PLANNER_QUEUED','acquisition',{})
            self.assertIsNone(planner.replenish(db,{'remaining':15}))
            state=get_memory(db,'working','acquisition_planner')
            self.assertEqual(state['status'],'exploration_budget_wait')
            self.assertGreater(state['retry_at'],time.time())
            db.commit()
        self.assertIsNone(executor.take(self.factory,'new-process'))

    def test_unsupported_idle_cannot_end_mission_or_restart_immediately(self):
        task=executor.take(self.factory,'one')
        executor.accept(self.factory,'one',task,{**self.result([]),'stop_reason':'TRUE_IDLE',
            'idle':{'external_condition':'Owner should assign a task','attempted_evidence_ids':[]}})
        with self.factory() as db:
            self.assertEqual(get_memory(db,'working','acquisition_planner')['status'],'planning_retry')
        self.assertIsNone(executor.take(self.factory,'one'))

if __name__=='__main__':unittest.main()
