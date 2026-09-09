"""Real cookie authentication through CSV routes, using an isolated database."""
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.routes import auth as auth_routes, stocky_import as stocky_routes, shipstation_import as shipment_routes
from app.db.base import Base
from app.db.models import Inventory, Product, Shop, User
from app.db.session import get_db_session
from app.services import auth, stocky_import, shipstation_import


class LoginImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.folder.name) / 'fixture.db'), connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        @contextmanager
        def scope():
            with self.factory() as db:
                try:
                    yield db
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        def dependency():
            with scope() as db:
                yield db
        app = FastAPI()
        for router in (auth_routes.router, stocky_routes.router, shipment_routes.router):
            app.include_router(router)
        app.dependency_overrides[get_db_session] = dependency
        self.client = TestClient(app, base_url='https://testserver')
        for target, name, value in [(stocky_import, 'session_scope', scope), (shipstation_import, 'session_scope', scope), (auth, 'COOKIE_DOMAIN', None)]:
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.mail = patch.object(auth_routes, 'send_magic_link_email', return_value=True).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.folder.cleanup()

    def login(self, **extra):
        response = self.client.post('/auth/magic-link/request', json={'email': 'inventory_buyer@example.com', **extra})
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(self.mail.call_args.kwargs['link']).query)
        response = self.client.post('/auth/magic-link/verify', json={'token': query['token'][0], **extra})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/auth/me').status_code, 200)
        return response.json(), query

    def test_new_login_stocky_shipments_replay_and_logout(self):
        user, query = self.login(return_to='/import-stocky')
        self.assertEqual(query.get('return_to'), ['/import-stocky'])
        stock = b'SKU,Product,Inventory,Price\nSKU-A,Test item,12,10\n'
        for _ in range(2):
            response = self.client.post('/integrations/stocky/import', files={'csv_file': ('stock.csv', stock, 'text/csv')})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['shop_id'], user['shop_id'])
        shipment = b'OrderId,ShipDate,SKU,Quantity,UnitPrice,Source\nQA-1,2026-09-08,SKU-A,3,10,Wholesale\n'
        for expected in (1, 0):
            response = self.client.post('/integrations/shipstation/import', data={'source_scope': 'non_shopify'}, files={'csv_file': ('sales.csv', shipment, 'text/csv')})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['line_items_inserted'], expected)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 1)
            self.assertEqual(db.scalar(select(Inventory.quantity)), 12)
        # Email scanners/duplicate clicks cannot consume an otherwise valid link.
        self.assertEqual(self.client.post('/auth/magic-link/verify', json={'token': query['token'][0]}).status_code, 200)
        self.client.post('/auth/logout')
        self.assertEqual(self.client.get('/auth/me').status_code, 401)
        self.assertEqual(self.client.post('/integrations/stocky/import', files={'csv_file': ('stock.csv', stock)}).status_code, 401)

    def test_mail_failure_is_reported_instead_of_check_your_inbox(self):
        self.mail.return_value = False
        response = self.client.post('/auth/magic-link/request', json={'email': 'inventory_buyer@example.com'})
        self.assertEqual(response.status_code, 503)

    def test_entering_a_shop_domain_does_not_grant_its_workspace(self):
        with self.factory() as db:
            shop = Shop(shopify_domain='existing-merchant.myshopify.com')
            db.add(shop)
            db.commit()
            other_shop_id = shop.id
        user, _ = self.login(shopify_domain='existing-merchant.myshopify.com')
        self.assertNotEqual(user['shop_id'], other_shop_id)

    def test_name_only_stocky_file_can_be_reimported(self):
        self.login()
        content = b'Product,Inventory,Price\nPlain item,8,10\n'
        for _ in range(2):
            response = self.client.post('/integrations/stocky/import', files={'csv_file': ('stock.csv', content)})
            self.assertEqual(response.status_code, 200, response.text)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Inventory)), 1)

    def test_external_return_destination_is_not_in_login_email(self):
        _, query = self.login(return_to='//example.com')
        self.assertNotIn('return_to', query)
