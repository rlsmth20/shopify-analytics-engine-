"""Privacy regression tests use only synthetic in-memory tenants."""
import base64
import hashlib
import hmac
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.routes import shopify_privacy_webhooks as routes
from app.db.models import (
    AlertDeliveryAttemptRecord, AlertEventRecord, ScheduledEmailDeliveryRecord,
    ShipmentImportBatchRecord, ShipmentImportRowRecord,
    AuditLogRecord, Base, InventoryRiskSnapshotLead, MagicLinkToken, NotificationChannelRecord,
    OrderLineItem, Session as LoginSession, Shop, ShopifyConnection, Subscription, User, WaitlistSignup,
)
from app.db.session import get_db_session
from app.growth import models as growth_models  # Register the same tenant tables as production init_db.
from app.services import shopify_privacy as privacy

SECRET = "fixture-privacy-secret-not-real"
NOW = datetime.now(timezone.utc)


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.one = self.seed_shop("one.myshopify.com")
        self.two = self.seed_shop("two.myshopify.com")
        self.env = patch.dict(os.environ, {"SHOPIFY_CLIENT_SECRET": SECRET})
        self.env.start()
        self.factory = patch.object(routes, "SessionLocal", self.sessions)
        self.factory.start()
        self.app = FastAPI()
        self.app.include_router(routes.router)
        def session():
            with self.sessions() as db:
                yield db
        self.app.dependency_overrides[get_db_session] = session
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()
        self.env.stop()
        self.factory.stop()

    def seed_shop(self, domain):
        shop = Shop(shopify_domain=domain)
        self.db.add(shop)
        self.db.flush()
        ids = {"shops": shop.id}
        # Seed one row in EVERY tenant table. This fails on schema additions
        # with unsupported required fields and keeps purge coverage complete.
        for table in Base.metadata.sorted_tables:
            if "shop_id" not in table.c:
                continue
            values = {"shop_id": shop.id}
            for column in table.c:
                if column.name == "shop_id" or (column.primary_key and isinstance(column.type, Integer)):
                    continue
                if column.foreign_keys:
                    target = next(iter(column.foreign_keys)).column.table.name
                    values[column.name] = ids[target]
                elif column.nullable or column.default is not None or column.server_default is not None:
                    continue
                elif isinstance(column.type, DateTime):
                    values[column.name] = NOW
                elif isinstance(column.type, Boolean):
                    values[column.name] = False
                elif isinstance(column.type, Integer):
                    values[column.name] = 1
                elif isinstance(column.type, Numeric):
                    values[column.name] = Decimal("10")
                elif isinstance(column.type, JSON):
                    values[column.name] = {}
                else:
                    values[column.name] = f"fixture-{shop.id}"
            if table.name == "users":
                values["email"] = f"owner-{shop.id}@example.test"
            if table.name == "shopify_connections":
                values.update(shopify_domain=domain, access_token="", uninstalled_at=NOW - timedelta(days=3),
                              installed_at=NOW - timedelta(days=10))
            if table.name in {"alert_events", "scheduled_email_deliveries"}:
                values["payload"] = {"subject": f"Private inventory report for shop {shop.id}",
                                     "to": [f"owner-{shop.id}@example.test"]}
            if table.name == "shipment_import_batches":
                values["result"] = {"batch_id": f"fixture-{shop.id}", "source_scope": "non_shopify", "line_items_inserted": 1}
            if table.name == "shipment_import_rows":
                values["facts"] = {"sku": f"private-sku-{shop.id}", "shipment_id": f"private-shipment-{shop.id}"}
            result = self.db.execute(table.insert().values(**values))
            ids[table.name] = result.inserted_primary_key[0]
        self.db.add_all([
            AlertDeliveryAttemptRecord(id=f"delivery-{shop.id}", event_id=ids["alert_events"],
                channel="email", target_fingerprint=f"hash-{shop.id}", status="accepted",
                provider_receipt=f"provider-{shop.id}",
                attempt_history=[{"status": "accepted", "provider_receipt": f"provider-{shop.id}"}]),
            LoginSession(user_id=ids["users"], token_hash=f"session-{shop.id}", expires_at=NOW + timedelta(days=1)),
            MagicLinkToken(email=f"owner-{shop.id}@example.test", token_hash=f"magic-{shop.id}", expires_at=NOW),
            NotificationChannelRecord(channel=f"{shop.id}:email", target=f"owner-{shop.id}@example.test"),
            WaitlistSignup(email=f"wait-{shop.id}@example.test", shopify_domain=domain),
            InventoryRiskSnapshotLead(first_name="Fixture", email=f"lead-{shop.id}@example.test",
                                      company_name="Fixture", store_url=f"https://{domain}/",
                                      approximate_sku_count="10", biggest_inventory_issue="stockouts"),
        ])
        self.db.commit()
        return shop.id

    def count(self, table):
        return self.db.scalar(select(func.count()).select_from(table))

    def conn(self, shop_id):
        return self.db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == shop_id))

    def sign_post(self, path, payload, *, extra_headers=None, valid=True):
        raw = json.dumps(payload).encode()
        signature = base64.b64encode(hmac.new(SECRET.encode(), raw, hashlib.sha256).digest()).decode()
        headers = {"Content-Type": "application/json", "X-Shopify-Hmac-Sha256": signature if valid else "bad"}
        headers.update(extra_headers or {})
        return self.client.post("/webhooks/" + path, content=raw, headers=headers)

    def test_shop_redaction_deletes_every_tenant_table_and_legacy_data_only_for_signed_shop(self):
        # Payload's external numeric ID intentionally equals the OTHER tenant.
        response = self.sign_post("shop/redact", {"shop_id": self.two, "shop_domain": "one.myshopify.com"})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        for table in Base.metadata.sorted_tables:
            with self.subTest(table=table.name):
                if table.name.startswith("growth_") and "shop_id" not in table.c:
                    # Growth operator-wide tables are not tenant fixtures.
                    self.assertEqual(self.count(table), 0)
                    continue
                self.assertEqual(self.count(table), 1)
                if "shop_id" in table.c:
                    self.assertEqual(self.db.scalar(select(table.c.shop_id)), self.two)
        self.assertIsNone(self.db.get(Shop, self.one))
        self.assertIsNotNone(self.db.get(Shop, self.two))
        again = self.sign_post("shop/redact", {"shop_domain": "one.myshopify.com"})
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.count(Shop), 1)

    def test_purge_rolls_back_if_a_dependent_table_delete_fails(self):
        original_execute = self.db.execute
        def fail_products(statement, *args, **kwargs):
            if str(statement).startswith("DELETE FROM products"):
                raise RuntimeError("Synthetic storage interruption")
            return original_execute(statement, *args, **kwargs)
        with patch.object(self.db, "execute", side_effect=fail_products):
            with self.assertRaisesRegex(RuntimeError, "Synthetic"):
                privacy.redact_shop(self.db, shop_domain="one.myshopify.com", triggered_at=None)
        for table in Base.metadata.sorted_tables:
            expected = 0 if table.name.startswith("growth_") and "shop_id" not in table.c else 2
            self.assertEqual(self.count(table), expected, table.name)
        self.assertEqual(self.db.get(AlertDeliveryAttemptRecord, f"delivery-{self.one}").provider_receipt,
                         f"provider-{self.one}")
        scheduled = self.db.scalar(select(ScheduledEmailDeliveryRecord).where(ScheduledEmailDeliveryRecord.shop_id == self.one))
        self.assertIn(f"shop {self.one}", scheduled.payload["subject"])
        shipment = self.db.scalar(select(ShipmentImportRowRecord).where(ShipmentImportRowRecord.shop_id == self.one))
        self.assertEqual(shipment.facts["shipment_id"], f"private-shipment-{self.one}")

    def test_alert_attempts_and_frozen_email_payloads_are_purged_without_sqlite_cascades(self):
        # Production uses FK cascades too, but our explicit tenant purge must
        # remain complete in SQLite configurations where they are disabled.
        self.db.commit()
        self.db.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")
        self.db.commit()
        self.assertEqual(self.db.connection().exec_driver_sql("PRAGMA foreign_keys").scalar(), 0)
        privacy.redact_shop(self.db, shop_domain="one.myshopify.com", triggered_at=None)
        self.db.expire_all()
        self.assertIsNone(self.db.get(AlertDeliveryAttemptRecord, f"delivery-{self.one}"))
        self.assertIsNotNone(self.db.get(AlertDeliveryAttemptRecord, f"delivery-{self.two}"))
        self.assertEqual([row.shop_id for row in self.db.scalars(select(AlertEventRecord)).all()], [self.two])
        payloads = self.db.scalars(select(ScheduledEmailDeliveryRecord)).all()
        self.assertEqual([row.shop_id for row in payloads], [self.two])
        self.assertIn(f"shop {self.two}", payloads[0].payload["subject"])
        for model in (ShipmentImportBatchRecord, ShipmentImportRowRecord):
            self.assertEqual([row.shop_id for row in self.db.scalars(select(model)).all()], [self.two])
        shipment = self.db.scalar(select(ShipmentImportRowRecord))
        self.assertEqual(shipment.facts["sku"], f"private-sku-{self.two}")

    def test_reinstalled_shop_survives_old_uninstall_and_redact_deliveries(self):
        conn = self.conn(self.one)
        conn.access_token, conn.uninstalled_at, conn.installed_at = "new-grant", None, NOW - timedelta(hours=1)
        self.db.commit()
        for when in (None, NOW - timedelta(hours=2), NOW):
            result = privacy.redact_shop(self.db, shop_domain="one.myshopify.com", triggered_at=when)
            self.assertEqual(result["shops_redacted"], 0)
        privacy.mark_shop_uninstalled(self.db, shop_domain="one.myshopify.com", triggered_at=NOW - timedelta(hours=2))
        self.assertEqual(conn.access_token, "new-grant")
        self.assertEqual(self.count(Shop), 2)

    def test_redact_with_event_time_handles_a_missed_uninstall_webhook(self):
        conn = self.conn(self.one)
        conn.access_token, conn.uninstalled_at = "stale-grant", None
        self.db.commit()
        result = privacy.redact_shop(self.db, shop_domain="one.myshopify.com", triggered_at=NOW)
        self.assertEqual(result["shops_redacted"], 1)

    def test_uninstall_revokes_grants_and_shopify_billing_but_preserves_data_until_redaction(self):
        conn = self.conn(self.one)
        conn.access_token, conn.refresh_token, conn.uninstalled_at = "old-grant", "old-refresh", None
        conn.access_token_expires_at, conn.refresh_token_expires_at = NOW, NOW
        subscription = self.db.scalar(select(Subscription).where(Subscription.shop_id == self.one))
        subscription.stripe_subscription_id, subscription.status, subscription.plan = "shopify:1", "active", "growth"
        self.db.commit()
        privacy.mark_shop_uninstalled(self.db, shop_domain="one.myshopify.com", triggered_at=NOW)
        self.assertEqual(conn.access_token, "")
        self.assertIsNone(conn.refresh_token)
        self.assertIsNone(conn.access_token_expires_at)
        self.assertEqual(subscription.status, "inactive")
        first_uninstall = conn.uninstalled_at
        privacy.mark_shop_uninstalled(self.db, shop_domain="one.myshopify.com", triggered_at=NOW + timedelta(minutes=1))
        self.assertEqual(conn.uninstalled_at, first_uninstall)
        self.assertEqual(self.count(Shop), 2)
        self.assertEqual(self.count(OrderLineItem), 2)

    def seed_customer_orders(self):
        existing = self.db.scalar(select(OrderLineItem).where(OrderLineItem.shop_id == self.one))
        product_id = existing.product_id
        existing.shopify_order_id = "12:1"
        for order_id in ("12", "12:2", "123:1", "13:1"):
            self.db.add(OrderLineItem(shop_id=self.one, product_id=product_id, shopify_order_id=order_id,
                                      quantity=2, price=10, sku="FIXTURE", created_at=NOW))
        other = self.db.scalar(select(OrderLineItem).where(OrderLineItem.shop_id == self.two))
        other.shopify_order_id = "12:1"
        self.db.commit()

    def test_customer_redaction_matches_order_boundaries_and_removes_prior_export_references(self):
        self.seed_customer_orders()
        privacy.record_customer_data_request(self.db, shop_domain="one.myshopify.com",
            payload={"orders_requested": [12, 13], "data_request": {"id": 7}}, webhook_id=None)
        payload = {"orders_to_redact": [12], "customer": {"email": "customer@example.test"}}
        result = privacy.redact_customer_orders(self.db, shop_domain="one.myshopify.com", payload=payload)
        self.assertEqual(result["order_line_items_redacted"], 3)
        self.assertEqual(privacy.redact_customer_orders(self.db, shop_domain="one.myshopify.com", payload=payload)["order_line_items_redacted"], 0)
        self.assertEqual(self.count(OrderLineItem), 3)
        item = privacy.list_customer_data_requests(self.db, shop_id=self.one)[0]
        export = privacy.export_customer_data_request(self.db, shop_id=self.one, request_id=item["id"])
        self.assertEqual([row["order_id"] for row in export["order_line_items"]], ["13"])

    def test_data_request_is_idempotent_durable_and_does_not_persist_customer_identity(self):
        self.seed_customer_orders()
        payload = {"shop_domain": "one.myshopify.com", "orders_requested": [12], "data_request": {"id": 77},
                   "customer": {"email": "private@example.test", "phone": "123456", "id": 999}}
        for _ in range(2):
            response = self.sign_post("customers/data_request", payload)
            self.assertEqual(response.status_code, 200, response.text)
        items = privacy.list_customer_data_requests(self.db, shop_id=self.one)
        self.assertEqual(len(items), 1)
        stored = self.db.get(AuditLogRecord, items[0]["id"])
        self.assertNotIn("private", json.dumps(stored.event_metadata))
        self.assertNotIn("customer", stored.event_metadata)
        export = privacy.export_customer_data_request(self.db, shop_id=self.one, request_id=items[0]["id"])
        self.assertEqual(len(export["order_line_items"]), 3)
        self.assertIsNone(privacy.export_customer_data_request(self.db, shop_id=self.two, request_id=items[0]["id"]))

    def test_hmac_and_signed_domain_required_before_any_mutation(self):
        for topic in ("customers/data_request", "customers/redact", "shop/redact", "app/uninstalled"):
            response = self.sign_post(topic, {"shop_domain": "one.myshopify.com"}, valid=False)
            self.assertEqual(response.status_code, 401)
        response = self.sign_post("shop/redact", {"shop_domain": "one.myshopify.com"},
                                  extra_headers={"X-Shopify-Shop-Domain": "two.myshopify.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.sign_post("shop/redact", {}).status_code, 400)
        self.assertEqual(self.sign_post("customers/redact", {"shop_domain": "one.myshopify.com", "orders_to_redact": ["12%"]}).status_code, 400)
        self.assertEqual(self.count(Shop), 2)
        self.assertFalse(routes.verify_shopify_webhook_hmac(b"{}", "non-ascii-ü"))

    def test_exports_require_authentication_and_are_not_plan_gated_or_cross_tenant(self):
        privacy.record_customer_data_request(self.db, shop_domain="one.myshopify.com",
            payload={"orders_requested": [], "data_request": {"id": 123}}, webhook_id=None)
        request_id = privacy.list_customer_data_requests(self.db, shop_id=self.one)[0]["id"]
        self.assertEqual(self.client.get("/webhooks/customer-data-requests").status_code, 401)
        user = self.db.scalar(select(User).where(User.shop_id == self.one))
        self.app.dependency_overrides[get_current_user] = lambda: user
        response = self.client.get("/webhooks/customer-data-requests")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json()["items"][0]["order_count"], 0)
        self.assertEqual(self.client.get(f"/webhooks/customer-data-requests/{request_id}").status_code, 200)
        other_user = self.db.scalar(select(User).where(User.shop_id == self.two))
        self.app.dependency_overrides[get_current_user] = lambda: other_user
        self.assertEqual(self.client.get(f"/webhooks/customer-data-requests/{request_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
