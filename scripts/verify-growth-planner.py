"""Read-only production proof; never seeds or completes planner/executor tasks."""
import json
import time
from sqlalchemy import select, text
from app.db.session import SessionLocal
from app.growth.models import Evidence, Memory
from app.growth.execution import state

with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    kinds = ['ACQUISITION_QUEUE_EMPTY', 'ACQUISITION_PLANNER_QUEUED',
             'ACQUISITION_HYPOTHESES', 'ACQUISITION_HYPOTHESIS_SELECTED',
             'ACQUISITION_DISCOVERY_STARTED']
    events = list(db.scalars(select(Evidence).where(Evidence.kind.in_(kinds))
                            .order_by(Evidence.id.desc()).limit(25)))
    tasks = [m.value for m in db.scalars(select(Memory).where(Memory.namespace == 'operator_task')
             .order_by(Memory.id.desc()).limit(20))]
    results = []
    for t in tasks:
        if not (t.get('hypothesis_id') or t.get('stage') == 'plan'):
            continue
        e = db.get(Evidence, t.get('result_evidence_id')) if t.get('result_evidence_id') else None
        results.append({'task': t, 'result': {'id':e.id, 'at':e.occurred_at, 'data':e.data} if e else None})
    print(json.dumps({'at':time.time(), 'execution':state(db),
        'events':[{'id':e.id,'at':e.occurred_at,'kind':e.kind,'subject':e.subject,
                   'data':{k:v for k,v in e.data.items() if k!='context'}} for e in reversed(events)],
        'results':results}, indent=2))
