import unittest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.deps import get_current_user
from app.api.routes.growth import router
from app.db.base import Base
from app.db.session import get_db_session
from app.growth.models import Contact, FirstContact, Message
from app.growth.store import record, digest
from app.growth.outreach_history import history, public_url


class OutreachHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, identity, status='sent', channel='contact_form', stamp=100):
        c = Contact(identity=identity, organization=identity, source='https://merchant.test/original-post')
        self.db.add(c); self.db.flush()
        body = 'Original message\nWith a concrete offer.'
        r = FirstContact(contact_id=c.id, action_key=identity, channel=channel, experiment_id='experiment',
            cohort={'message_version': 4}, body_hash=digest(body), status=status, reserved_at=stamp,
            sent_at=stamp + 1 if status == 'sent' else None,
            receipt='Verified submission: https://merchant.test/contact?contact_posted=true' if status == 'sent' else None)
        self.db.add(r); self.db.flush()
        record(self.db, 'first-contact-intent:' + r.id, 'FIRST_CONTACT_RESERVED', c.id, {'body': body})
        self.db.commit()
        return c, r

    def test_exact_text_source_receipt_and_unknown_status_are_separate(self):
        self.add('Sent merchant'); self.add('Uncertain merchant', status='uncertain')
        result = history(self.db)
        self.assertEqual(len(result['items']), 1)
        item = result['items'][0]
        self.assertEqual(item['message'], 'Original message\nWith a concrete offer.')
        self.assertEqual(item['source_url'], 'https://merchant.test/original-post')
        self.assertEqual(item['receipt_urls'], ['https://merchant.test/contact?contact_posted=true'])
        self.assertEqual(history(self.db, status='uncertain')['items'][0]['sent_at'], None)

    def test_hash_mismatch_never_displays_a_new_draft_as_sent(self):
        c, r = self.add('merchant')
        r.body_hash = digest('Another text')
        self.db.add(Message(key='draft', contact_id=c.id, direction='outbound', body='Another text', status='draft'))
        self.db.commit()
        self.assertIsNone(history(self.db)['items'][0]['message'])

    def test_historical_message_uses_retained_source_evidence(self):
        c, r = self.add('historical')
        old = record(self.db, 'old', 'HISTORICAL_OUTREACH', c.id, {'body_normalized_whitespace': 'Old exact message'})
        r.cohort = {'source_evidence_id': old.id, 'timestamp_basis': 'Imported time'}
        r.body_hash = digest('Old exact message')
        # Historical imports never had an intent row.
        from app.growth.models import Evidence
        from sqlalchemy import delete
        self.db.execute(delete(Evidence).where(Evidence.key == 'first-contact-intent:' + r.id))
        self.db.commit()
        self.assertEqual(history(self.db)['items'][0]['message'], 'Old exact message')
        self.assertIn('spacing', history(self.db)['items'][0]['message_basis'])

    def test_pagination_is_stable_with_tied_timestamps_and_filters(self):
        for name in ['A', 'B', 'C']: self.add(name, channel='reddit')
        self.add('Other', channel='email', stamp=200)
        first = history(self.db, limit=2, method='reddit')
        second = history(self.db, limit=2, method='reddit', before=first['next_cursor'])
        ids = [i['id'] for i in first['items'] + second['items']]
        self.assertEqual(len(set(ids)), 3)
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(history(self.db, search='oth')['items'][0]['contact'], 'Other')
        self.assertEqual(history(self.db, search='%')['items'], [])

    def test_dangerous_and_credential_urls_are_not_links(self):
        for url in ['javascript:alert(1)', 'https://user:secret@host.test/', '//host.test', 'https://[']:
            self.assertIsNone(public_url(url))

    def test_api_requires_owner_and_disables_response_caching(self):
        self.add('Private merchant')
        app = FastAPI(); app.include_router(router)
        def session():
            with self.factory() as db: yield db
        app.dependency_overrides[get_db_session] = session
        with TestClient(app) as client:
            self.assertEqual(client.get('/growth/outreach-history').status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)
            self.assertEqual(client.get('/growth/outreach-history').status_code, 403)
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=True)
            response = client.get('/growth/outreach-history')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['cache-control'])
            self.assertEqual(client.get('/growth/outreach-history?limit=10000').status_code, 422)
