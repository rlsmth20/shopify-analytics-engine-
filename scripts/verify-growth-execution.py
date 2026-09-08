"""Read-only production acceptance snapshot. Never seeds prospects or sends mail.

Run with backend on PYTHONPATH and the existing authorized DATABASE_URL.
"""
import json
import time
from sqlalchemy import func, select
from app.db.session import SessionLocal
from app.growth.execution import state
from app.growth.models import Evidence, FirstContact, Memory, Work
from app.growth.store import get_memory

with SessionLocal() as db:
    progress = list(db.scalars(select(Evidence).where(Evidence.kind == 'ACQUISITION_PROGRESS')
                              .order_by(Evidence.id.desc()).limit(20)))
    contacts = list(db.scalars(select(FirstContact).order_by(FirstContact.sent_at)))
    sends = [r.sent_at for r in contacts if r.sent_at is not None]
    maximum = max((sum(at - 86400 < prior <= at for prior in sends) for at in sends), default=0)
    duplicates = list(db.execute(select(FirstContact.contact_id, func.count()).group_by(FirstContact.contact_id)
                                .having(func.count() > 1)))
    works = list(db.scalars(select(Work).where(Work.status.in_(['ready', 'running', 'failed', 'blocked']))
                           .order_by(Work.updated_at.desc()).limit(20)))
    result = {'checked_at': time.time(), 'execution': state(db),
        'server_activity': get_memory(db, 'working', 'activity'),
        'essential_checks': get_memory(db, 'working', 'browser_safety_check'),
        'browser_tasks': [{k: r.value.get(k) for k in ('id', 'key', 'stage', 'status', 'attempts',
            'executor', 'lease_until', 'last_progress_at', 'result_evidence_id', 'next_step')}
            for r in db.scalars(select(Memory).where(Memory.namespace == 'operator_task')
                                .order_by(Memory.updated_at.desc()).limit(10))],
        'sequential_actions': [{'id': e.id, 'at': e.occurred_at, 'task_id': e.subject, **e.data} for e in reversed(progress)],
        'duplicate_first_contacts': len(duplicates), 'largest_recorded_rolling_send_count': maximum,
        'work': [{'kind': w.kind, 'status': w.status, 'attempts': w.attempts, 'error': w.error,
                  'due_at': w.due_at, 'updated_at': w.updated_at} for w in works]}
    print(json.dumps(result, indent=2))
    assert not duplicates and maximum <= 20 and result['execution']['remaining_capacity'] >= 0
