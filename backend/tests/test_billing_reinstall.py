"""Exercise the real billing/auth routes with a stateful Shopify boundary."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.billing import router
from app.db.models import Base, ShopifyConnection
from app.db.session import get_db_session
from app.services import shopify_billing as billing
from app.services.shopify_oauth import ShopifyTokenExchangeError
from test_shopify_installation import signed_token, SECRET, DOMAIN, GRANT


class BillingReinstallTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SHOPIFY_CLIENT_ID': 'fixture-client', 'SHOPIFY_CLIENT_SECRET': SECRET})
        self.env.start()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.active = None
        self.grant = 'original-grant'
        self.creations = []
        self.queries = 0
        self.exchange = patch('app.services.shopify_oauth.exchange_session_token', side_effect=self.exchange_grant).start()
        patch.object(billing, '_gql', side_effect=self.graphql).start()
        billing._summary_cache.clear()
        app = FastAPI()
        app.include_router(router)
        def session():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db_session] = session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        billing._summary_cache.clear()
        patch.stopall()

    def exchange_grant(self, **kwargs):
        return {**GRANT, 'access_token': self.grant}

    def graphql(self, conn, query, variables):
        if conn.access_token != self.grant:
            raise billing.ShopifyBillingAuthError('Shopify rejected revoked grant')
        if query == billing.CURRENT_APP_INSTALLATION_QUERY:
            self.queries += 1
            return {'data': {'currentAppInstallation': {'activeSubscriptions': [self.active] if self.active else []}}}
        if query == billing.APP_SUBSCRIPTION_CREATE:
            self.creations.append(variables)
            return {'data': {'appSubscriptionCreate': {'userErrors': [], 'confirmationUrl': 'https://fixture.myshopify.com/approve/' + str(len(self.creations))}}}
        return {'data': {'shop': {'plan': {'partnerDevelopment': True}}}}

    def get(self, fresh=True):
        return self.client.get('/billing/entitlements' + ('?fresh=1' if fresh else ''), headers={'Authorization': 'Bearer ' + signed_token()})

    def choose(self):
        return self.client.post('/billing/shopify/subscribe', json={'plan': 'scale_monthly'}, headers={'Authorization': 'Bearer ' + signed_token()})

    def approve(self):
        self.active = {'id': 'gid://shopify/AppSubscription/1', 'name': 'Skubase Scale', 'status': 'ACTIVE', 'currentPeriodEnd': '2026-11-14T00:00:00Z'}

    def test_reinstall_before_uninstall_webhook_can_decline_and_request_approval_again(self):
        self.assertEqual(self.get().json()['subscription_status'], 'inactive')
        self.assertEqual(self.choose().status_code, 200)
        self.approve()
        self.assertEqual(self.get().json()['plan_id'], 'scale')
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            original_shop = conn.shop_id
            conn.installed_at = datetime.now(timezone.utc) - timedelta(days=2)
            self.assertIsNone(conn.uninstalled_at)
            db.commit()
        # Shopify revoked the old grant on uninstall, but our webhook is delayed.
        # The saved token still has time remaining, reproducing the reviewer path.
        self.grant, self.active = 'reinstalled-grant', None
        result = self.get()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIsNone(result.json()['billing_status_error'], result.text)
        self.assertEqual(result.json()['subscription_status'], 'inactive')
        self.assertNotIn('forecast', result.json()['capabilities'])
        self.assertEqual(self.exchange.call_count, 2)
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            self.assertEqual(conn.shop_id, original_shop)
            self.assertEqual(conn.access_token, self.grant)
            from app.services.shopify_privacy import mark_shop_uninstalled
            mark_shop_uninstalled(db, shop_domain=DOMAIN, triggered_at=datetime.now(timezone.utc)-timedelta(minutes=1))
            self.assertEqual(conn.access_token, self.grant)
        self.assertEqual(self.choose().status_code, 200)
        # Merchant declines: no active subscription, and choosing again is valid.
        self.assertEqual(self.get().json()['subscription_status'], 'inactive')
        self.assertEqual(self.choose().status_code, 200)
        self.approve()
        self.assertEqual(self.get().json()['plan_id'], 'scale')
        self.assertEqual(len(self.creations), 3)
        self.assertTrue(all(v['test'] for v in self.creations))

    def test_failed_recovery_is_actionable_and_not_cached(self):
        self.get()
        self.grant = 'reinstalled-grant'
        self.exchange.side_effect = ShopifyTokenExchangeError('temporary outage')
        result = self.get()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['billing_status_error'], 'shopify_unavailable')
        self.exchange.side_effect = self.exchange_grant
        self.assertIsNone(self.get(fresh=False).json()['billing_status_error'])

    def test_second_rejected_grant_does_not_loop(self):
        self.get()
        self.grant = 'new-grant'
        self.exchange.side_effect = None
        self.exchange.return_value = {**GRANT, 'access_token': 'also-rejected'}
        result = self.get()
        self.assertEqual(result.json()['billing_status_error'], 'shopify_unauthorized')
        self.assertEqual(self.exchange.call_count, 2)
        self.assertEqual(self.creations, [])

    def test_wrong_shop_session_cannot_recover_a_connection(self):
        self.get()
        from app.services.shopify_session_tokens import recover_rejected_shopify_connection, ShopifySessionTokenError
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            other = 'other-fixture.myshopify.com'
            with self.assertRaises(ShopifySessionTokenError):
                recover_rejected_shopify_connection(db, conn=conn, rejected_access_token=conn.access_token,
                    session_token=signed_token(iss=f'https://{other}/admin', dest=f'https://{other}'))
        self.assertEqual(self.exchange.call_count, 1)

    def test_recovery_reuses_a_grant_replaced_by_another_request(self):
        self.get()
        from app.services.shopify_session_tokens import recover_rejected_shopify_connection
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            rejected = conn.access_token
            with self.sessions() as other:
                fresh = other.get(ShopifyConnection, conn.id)
                fresh.access_token = 'recovered-by-other-request'
                other.commit()
            recover_rejected_shopify_connection(db, conn=conn, session_token=signed_token(),
                                                rejected_access_token=rejected)
            self.assertEqual(conn.access_token, 'recovered-by-other-request')
        self.assertEqual(self.exchange.call_count, 1)

    def test_delayed_uninstall_during_recovery_does_not_leave_empty_grant(self):
        self.get()
        from app.services.shopify_session_tokens import recover_rejected_shopify_connection
        from app.services.shopify_privacy import mark_shop_uninstalled
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            conn.installed_at = datetime.now(timezone.utc) - timedelta(days=2)
            rejected = conn.access_token
            db.commit()
            with self.sessions() as webhook:
                mark_shop_uninstalled(webhook, shop_domain=DOMAIN,
                                      triggered_at=datetime.now(timezone.utc)-timedelta(minutes=1))
            self.grant = 'reinstalled-grant'
            recover_rejected_shopify_connection(db, conn=conn, session_token=signed_token(),
                                                rejected_access_token=rejected)
            self.assertEqual(conn.access_token, self.grant)
            self.assertIsNone(conn.uninstalled_at)
        self.assertEqual(self.exchange.call_count, 2)

    def test_unknown_charge_result_is_not_replayed(self):
        self.get()
        def outage(conn, query, variables):
            if query == billing.APP_SUBSCRIPTION_CREATE:
                self.creations.append(variables)
                raise billing.ShopifyBillingError('Connection closed after request')
            return self.graphql(conn, query, variables)
        with patch.object(billing, '_gql', side_effect=outage):
            self.assertEqual(self.choose().status_code, 400)
        self.assertEqual(len(self.creations), 1)


if __name__ == '__main__':
    unittest.main()
