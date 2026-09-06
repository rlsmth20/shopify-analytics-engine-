"""Regression coverage for App Store review 116756. No real Shopify calls."""
import base64
import hashlib
import hmac
import json
import io
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import router as auth_router
from app.api.routes.shopify_ingestion import router as shopify_router
from app.db.models import Base, Shop, ShopifyConnection, User
from app.db.session import get_db_session
from app.services.shopify_oauth import (
    ShopifyTokenExchangeError, issue_oauth_state, persist_connection, exchange_session_token,
)
from app.services.shopify_session_tokens import (
    resolve_user_from_shopify_session_token, verify_shopify_session_token, ShopifySessionTokenError,
)

DOMAIN = "review-fixture.myshopify.com"
SECRET = "fixture-only-not-a-real-secret"
GRANT = {"access_token": "fixture-access", "refresh_token": "fixture-refresh",
         "expires_in": 3600, "refresh_token_expires_in": 7776000,
         "scope": "read_products,read_orders,read_inventory,read_locations"}


def signed_token(**overrides):
    now = datetime.now(timezone.utc).timestamp()
    payload = {"iss": f"https://{DOMAIN}/admin", "dest": f"https://{DOMAIN}",
               "aud": "fixture-client", "sub": "42", "exp": now + 60, "nbf": now - 1}
    payload.update(overrides)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    body = encode(json.dumps({"alg": "HS256"}).encode()) + "." + encode(json.dumps(payload).encode())
    return body + "." + encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SHOPIFY_CLIENT_ID": "fixture-client", "SHOPIFY_CLIENT_SECRET": SECRET,
                                          "SHOPIFY_APP_HANDLE": "", "ADMIN_EMAILS": ""})
        self.env.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(shopify_router)
        def session():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db_session] = session
        self.client = TestClient(app)
        self.exchange = patch("app.services.shopify_oauth.exchange_session_token", return_value=GRANT.copy()).start()

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        patch.stopall()

    def me(self, token=None):
        return self.client.get("/auth/me", headers={"Authorization": "Bearer " + (token or signed_token())})

    def test_fresh_managed_install_connects_without_oauth_redirect(self):
        result = self.me()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["is_admin"])
        connection = self.client.get("/integrations/shopify/connection", headers={"Authorization": "Bearer " + signed_token()})
        self.assertEqual(connection.status_code, 200)
        self.assertEqual(connection.json()["shopify_domain"], DOMAIN)
        self.assertTrue(connection.json()["connected"])
        self.assertEqual(self.exchange.call_count, 1)

    def test_reinstall_reuses_workspace_and_rotates_token(self):
        original = self.me().json()
        with self.sessions() as db:
            conn = db.scalar(select(ShopifyConnection))
            conn.access_token = ""
            conn.uninstalled_at = datetime.now(timezone.utc)
            db.commit()
        result = self.me()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["shop_id"], original["shop_id"])
        self.assertEqual(self.exchange.call_count, 2)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Shop)), 1)
            self.assertIsNone(db.scalar(select(ShopifyConnection)).uninstalled_at)

    def test_expired_api_token_renews_from_current_shopify_session(self):
        self.me()
        with self.sessions() as db:
            db.scalar(select(ShopifyConnection)).access_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        self.assertEqual(self.me().status_code, 200)
        self.assertEqual(self.exchange.call_count, 2)

    def test_parallel_first_requests_create_only_one_connection(self):
        token = signed_token()
        def authenticate(_):
            with self.sessions() as db:
                return resolve_user_from_shopify_session_token(db, token).shop_id
        with ThreadPoolExecutor(max_workers=4) as executor:
            shops = list(executor.map(authenticate, range(4)))
        self.assertEqual(len(set(shops)), 1)
        self.assertEqual(self.exchange.call_count, 1)

    def test_failed_exchange_does_not_create_partial_workspace(self):
        self.exchange.side_effect = ShopifyTokenExchangeError("Shopify temporarily unavailable")
        self.assertEqual(self.me().status_code, 503)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Shop)), 0)

    def test_invalid_bearer_cannot_fall_back_to_website_cookie(self):
        with patch("app.api.deps.resolve_session") as cookie_auth:
            result = self.client.get("/auth/me", headers={"Authorization": "Bearer invalid", "Cookie": "skubase_session=fixture"})
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.headers["X-Shopify-Retry-Invalid-Session-Request"], "1")
        cookie_auth.assert_not_called()
        self.exchange.assert_not_called()

    def test_website_callback_reuses_installed_shop_without_moving_website_user(self):
        installed = self.me().json()
        with self.sessions() as db:
            website = Shop(shopify_domain="website-workspace.local")
            db.add(website)
            db.flush()
            user = User(email="reviewer@example.test", shop_id=website.id, is_admin=False)
            db.add(user)
            db.commit()
            website_id = website.id
            user_id = user.id
            state = issue_oauth_state(db, user=user, shop_domain=DOMAIN)
        params = {"shop": DOMAIN, "code": "fixture-code", "state": state}
        canonical = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        params["hmac"] = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        with patch("app.api.routes.shopify_ingestion.exchange_code_for_token", return_value=GRANT.copy()):
            response = self.client.get("/integrations/shopify/callback?" + urlencode(params), follow_redirects=False)
        self.assertEqual(response.status_code, 302, response.text)
        self.assertEqual(response.headers["location"], f"https://{DOMAIN}/admin/apps/fixture-client")
        with self.sessions() as db:
            self.assertEqual(db.get(User, user_id).shop_id, website_id)
            self.assertEqual(db.get(Shop, website_id).shopify_domain, "website-workspace.local")
            self.assertEqual(db.scalar(select(ShopifyConnection)).shop_id, installed["shop_id"])

    def test_persist_connection_handles_existing_domain(self):
        installed = self.me().json()
        with self.sessions() as db:
            other = Shop(shopify_domain="unrelated.local")
            db.add(other)
            db.commit()
            conn = persist_connection(db, shop_id=other.id, shop_domain=DOMAIN, token_payload=GRANT.copy())
            self.assertEqual(conn.shop_id, installed["shop_id"])
            self.assertEqual(other.shopify_domain, "unrelated.local")

    def test_staff_does_not_inherit_global_admin_or_a_new_trial(self):
        self.me()
        with self.sessions() as db:
            owner = db.scalar(select(User).where(User.email == f"shopify-owner@{DOMAIN}"))
            owner.is_admin = True
            owner.trial_ends_at = datetime(2020, 1, 1)
            db.commit()
        response = self.me(signed_token(sub="43"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_admin"])
        self.assertFalse(response.json()["in_trial"])

    def test_invalid_claims_rejected_before_grant(self):
        for overrides in ({"exp": float("nan")}, {"nbf": float("inf")}, {"exp": 1},
                          {"aud": "wrong"}, {"dest": "http://review-fixture.myshopify.com"},
                          {"iss": f"https://{DOMAIN}/wrong"}, {"sub": "bad@user"}):
            with self.subTest(overrides=overrides), self.assertRaises(ShopifySessionTokenError):
                verify_shopify_session_token(signed_token(**overrides))

    def test_install_json_format_works_without_cookie(self):
        with patch("app.services.shopify_oauth.BACKEND_URL", "https://api.example.test"):
            response = self.client.get(f"/integrations/shopify/install?shop={DOMAIN}&format=json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("authorize_url", response.json())

    def test_token_exchange_requests_renewable_offline_grant(self):
        from urllib.parse import parse_qs
        with patch("app.services.shopify_oauth.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(GRANT).encode())) as request:
            payload = exchange_session_token(shop_domain=DOMAIN, session_token="fixture-id-token")
        self.assertEqual(payload["access_token"], "fixture-access")
        http_request = request.call_args.args[0]
        self.assertEqual(http_request.full_url, f"https://{DOMAIN}/admin/oauth/access_token")
        body = parse_qs(http_request.data.decode())
        self.assertEqual(body["grant_type"], ["urn:ietf:params:oauth:grant-type:token-exchange"])
        self.assertEqual(body["expiring"], ["1"])
        self.assertEqual(body["subject_token"], ["fixture-id-token"])

    def test_malformed_signature_returns_401(self):
        response = self.me(signed_token().rsplit(".", 1)[0] + ".not+base64url")
        self.assertEqual(response.status_code, 401)
        with self.assertRaises(ShopifySessionTokenError):
            verify_shopify_session_token(signed_token().rsplit(".", 1)[0] + ".not-ascii-ü")


if __name__ == "__main__":
    unittest.main()
