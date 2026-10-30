"""Background sync runs: one per shop, polled by id, recovered after restarts."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_active_access
from app.api.routes import shopify_ingestion as routes
from app.db.models import Base, Shop, ShopifyConnection, ShopifySyncRun, User
from app.db.session import get_db_session
from app.services import shopify_sync as sync, shopify_sync_jobs as jobs


def page(nodes, cursor=None):
    return {"edges": [{"node": node} for node in nodes],
            "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}


def product_node(number=1, quantity=10):
    return {"id": f"gid://shopify/Product/{number}", "title": f"Fixture {number}", "status": "ACTIVE",
            "isGiftCard": False,
            "variants": page([{"id": f"gid://shopify/ProductVariant/{number}", "sku": f"SKU-{number}",
                               "price": "20", "inventoryQuantity": quantity,
                               "inventoryItem": {"tracked": True, "unitCost": {"amount": "10"}}}])}


def order_node(number=1):
    return {"id": f"gid://shopify/Order/{number}", "createdAt": datetime.now(timezone.utc).isoformat(),
            "lineItems": page([{"id": f"gid://shopify/LineItem/{number}", "quantity": 2,
                                "variant": {"id": "gid://shopify/ProductVariant/1"},
                                "originalUnitPriceSet": {"shopMoney": {"amount": "20"}}}])}


def shopify(products=1, orders=1):
    def gql(domain, token, query, variables=None):
        if query == sync.PRODUCTS_QUERY:
            return {"data": {"products": page([product_node(i) for i in range(1, products + 1)])}}
        if query == sync.ORDERS_QUERY:
            return {"data": {"orders": page([order_node(i) for i in range(1, orders + 1)])}}
        raise AssertionError(f"Unexpected GraphQL query: {query[:40]}")
    return gql


class SyncJobTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        with self.factory() as db:
            shop = Shop(shopify_domain="fixture.myshopify.com")
            other = Shop(shopify_domain="other.myshopify.com")
            db.add_all([shop, other])
            db.flush()
            db.add(ShopifyConnection(shop_id=shop.id, shopify_domain=shop.shopify_domain,
                                     access_token="fixture", scope="read_orders,read_products"))
            user = User(email="owner@example.com", shop_id=shop.id)
            db.add(user)
            db.commit()
            self.shop_id, self.other_shop_id, self.user_id = shop.id, other.id, user.id

        app = FastAPI()
        app.include_router(routes.router)

        def session():
            with self.factory() as db:
                yield db

        def current_user():
            with self.factory() as db:
                return db.get(User, self.user_id)

        app.dependency_overrides[get_db_session] = session
        app.dependency_overrides[require_active_access] = current_user
        app.dependency_overrides[get_current_user] = current_user
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.spawn = patch.object(routes, "run_in_background").start()
        self.addCleanup(patch.stopall)

    def status(self, run_id=None):
        query = f"?run_id={run_id}" if run_id else ""
        return self.client.get(f"/integrations/shopify/sync/status{query}")

    def test_sync_request_is_queued_then_completed_in_the_background(self):
        response = self.client.post("/integrations/shopify/sync")
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual((body["status"], body["triggered_by"], body["result"]), ("queued", "manual", None))
        run_id = body["run_id"]
        self.spawn.assert_called_once_with(run_id)
        # A second click while the run is live is refused instead of racing it.
        self.assertEqual(self.client.post("/integrations/shopify/sync").status_code, 409)
        self.assertEqual(self.status().json()["status"], "queued")

        with patch.object(sync, "_gql", side_effect=shopify()):
            result = jobs.execute_run(run_id, factory=self.factory)
        self.assertEqual(result["status"], "succeeded")
        status = self.status(run_id).json()
        self.assertEqual(status["status"], "succeeded")
        self.assertEqual(status["result"]["variants_imported"], 1)
        self.assertEqual(status["result"]["order_line_items_count"], 1)
        self.assertIsNotNone(status["finished_at"])
        with self.factory() as db:
            conn = db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == self.shop_id))
            self.assertIsNotNone(conn.last_sync_at)
        # The shop is free again, and finished runs are not executed twice.
        self.assertEqual(self.client.post("/integrations/shopify/sync").status_code, 202)
        self.assertIsNone(jobs.execute_run(run_id, factory=self.factory))

    def test_status_is_scoped_to_the_callers_shop(self):
        self.assertEqual(self.status().status_code, 404)
        with self.factory() as db:
            foreign = ShopifySyncRun(shop_id=self.other_shop_id, status="succeeded")
            db.add(foreign)
            db.commit()
            foreign_id = foreign.id
        self.assertEqual(self.status(foreign_id).status_code, 404)
        self.assertEqual(self.status().status_code, 404)

    def test_failed_run_records_the_error_instead_of_raising(self):
        with self.factory() as db:
            run_id = jobs.start_run(db, shop_id=self.shop_id).id
        with patch.object(sync, "_gql", return_value={"errors": [{"message": "fixture failure"}]}):
            self.assertIsNone(jobs.execute_run(run_id, factory=self.factory))
        status = self.status(run_id).json()
        self.assertEqual(status["status"], "failed")
        self.assertIn("products query failed", status["error_message"])
        self.assertIsNotNone(status["finished_at"])
        with self.factory() as db:
            self.assertIsNotNone(jobs.start_run(db, shop_id=self.shop_id))

    def test_errors_outside_the_traversal_still_close_the_run(self):
        with self.factory() as db:
            run_id = jobs.start_run(db, shop_id=self.shop_id).id
        with patch("app.services.shopify_oauth.ensure_fresh_access_token", side_effect=RuntimeError("token refresh down")):
            self.assertIsNone(jobs.execute_run(run_id, factory=self.factory))
        status = self.status(run_id).json()
        self.assertEqual(status["status"], "failed")
        self.assertIn("token refresh down", status["error_message"])

    def test_abandoned_and_interrupted_runs_stop_blocking_new_ones(self):
        with self.factory() as db:
            stale = ShopifySyncRun(shop_id=self.shop_id, status="running",
                                   started_at=datetime.now(timezone.utc) - timedelta(hours=3))
            db.add(stale)
            db.commit()
            stale_id = stale.id
        with self.factory() as db:
            run_id = jobs.start_run(db, shop_id=self.shop_id).id
            self.assertEqual(db.get(ShopifySyncRun, stale_id).status, "failed")
            with self.assertRaises(jobs.SyncInProgress):
                jobs.start_run(db, shop_id=self.shop_id)
        # A restart closes whatever the previous process left active.
        self.assertEqual(jobs.recover_interrupted_sync_runs(factory=self.factory), 1)
        with self.factory() as db:
            self.assertEqual(db.get(ShopifySyncRun, run_id).error_message, jobs.INTERRUPTED_MESSAGE)
            self.assertIsNotNone(jobs.start_run(db, shop_id=self.shop_id))

    def test_missing_connection_is_a_client_error(self):
        with self.factory() as db:
            conn = db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == self.shop_id))
            conn.uninstalled_at = datetime.now(timezone.utc)
            db.commit()
        response = self.client.post("/integrations/shopify/sync")
        self.assertEqual(response.status_code, 400)
        self.spawn.assert_not_called()

    def test_repeat_sync_queries_do_not_scale_with_catalog_size(self):
        statements = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        with self.factory() as db, patch.object(sync, "_gql", side_effect=shopify(products=40, orders=40)):
            sync.sync_shop_now(db, shop_id=self.shop_id)
            event.listen(self.engine, "before_cursor_execute", record)
            try:
                second = sync.sync_shop_now(db, shop_id=self.shop_id)
            finally:
                event.remove(self.engine, "before_cursor_execute", record)
        self.assertEqual(second["variants_imported"], 40)
        self.assertEqual(second["line_item_skip_reasons"], {"already_imported": 40})
        selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
        # One lookup per variant and per line item would be 80+ here.
        self.assertLess(len(selects), 20, selects)

    def test_due_stores_are_installed_ones_without_a_recent_run(self):
        now = datetime.now(timezone.utc)
        interval = timedelta(hours=6)
        with self.factory() as db:
            self.assertEqual(jobs.due_shop_ids(db, now=now, interval=interval), [self.shop_id])
            db.add(ShopifySyncRun(shop_id=self.shop_id, status="failed", started_at=now - timedelta(hours=1)))
            db.commit()
            self.assertEqual(jobs.due_shop_ids(db, now=now, interval=interval), [])
            self.assertEqual(jobs.due_shop_ids(db, now=now + timedelta(hours=6), interval=interval), [self.shop_id])
            conn = db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == self.shop_id))
            conn.uninstalled_at = now
            db.commit()
            self.assertEqual(jobs.due_shop_ids(db, now=now + timedelta(days=1), interval=interval), [])

    def test_scheduled_tick_syncs_due_stores_and_respects_live_runs(self):
        with patch.object(sync, "_gql", side_effect=shopify()):
            self.assertEqual(jobs.run_due_syncs(factory=self.factory), 1)
            # Not due again until the interval passes, whatever the outcome.
            self.assertEqual(jobs.run_due_syncs(factory=self.factory), 0)
        status = self.status().json()
        self.assertEqual((status["status"], status["triggered_by"]), ("succeeded", "scheduled"))
        self.assertEqual(status["result"]["variants_imported"], 1)
        # A live manual run is left alone rather than raced.
        later = datetime.now(timezone.utc) + timedelta(days=1)
        with self.factory() as db:
            queued = ShopifySyncRun(shop_id=self.shop_id, status="queued", started_at=later - timedelta(minutes=5))
            db.add(queued)
            db.commit()
        self.assertEqual(jobs.run_due_syncs(factory=self.factory, now=later), 0)

    def test_scheduled_order_window_covers_the_gap_since_the_last_success(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(jobs.order_window_days(None, now), 60)
        self.assertEqual(jobs.order_window_days(now - timedelta(hours=6), now), 3)
        self.assertEqual(jobs.order_window_days(now - timedelta(days=10), now), 12)
        self.assertEqual(jobs.order_window_days(now - timedelta(days=200), now), 60)
        # Naive timestamps from SQLite are treated as UTC.
        self.assertEqual(jobs.order_window_days((now - timedelta(days=4)).replace(tzinfo=None), now), 6)
        with self.factory() as db:
            run_id = jobs.start_run(db, shop_id=self.shop_id).id
        with patch.object(sync, "_ingest_orders", wraps=sync._ingest_orders) as orders, \
                patch.object(sync, "_gql", side_effect=shopify()):
            jobs.execute_run(run_id, factory=self.factory, order_days_back=5)
        self.assertEqual(orders.call_args.kwargs["days_back"], 5)


if __name__ == "__main__":
    unittest.main()
