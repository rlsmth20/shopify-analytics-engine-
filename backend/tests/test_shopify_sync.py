import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.db.models import Base, Shop, ShopifyConnection, Product, Inventory, OrderLineItem, InventoryValueSnapshot
from app.services import shopify_sync as sync
from app.services.inventory_value import inventory_value_history, capture_inventory_value_snapshot
from app.services.shop_skus import load_skus_for_shop
from app.services.inventory_engine import build_inventory_actions


def page(nodes, cursor=None):
    return {"edges": [{"node": node} for node in nodes], "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}


def product_node(number=1, *, quantity=10, status="ACTIVE", gift_card=False, tracked=True):
    return {"id": f"gid://shopify/Product/{number}", "title": f"Fixture {number}",
            "status": status, "isGiftCard": gift_card,
            "variants": page([{"id": f"gid://shopify/ProductVariant/{number}", "sku": f"SKU-{number}",
                               "price": "20", "inventoryQuantity": quantity,
                               "inventoryItem": {"tracked": tracked, "unitCost": {"amount": "10"}}}])}


def order_node(number=1):
    return {"id": f"gid://shopify/Order/{number}", "createdAt": datetime.now(timezone.utc).isoformat(),
            "lineItems": page([{"id": f"gid://shopify/LineItem/{number}", "quantity": 2,
                                "variant": {"id": "gid://shopify/ProductVariant/1"},
                                "originalUnitPriceSet": {"shopMoney": {"amount": "20"}}}])}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        shop = Shop(shopify_domain="fixture.myshopify.com")
        self.db.add(shop)
        self.db.flush()
        self.shop_id = shop.id
        self.db.add(ShopifyConnection(shop_id=shop.id, shopify_domain=shop.shopify_domain,
                    access_token="fixture", scope="read_orders,read_products"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def ingest_products(self, nodes):
        with patch.object(sync, "_gql", return_value={"data": {"products": page(nodes)}}):
            return sync._ingest_products(self.db, shop_id=self.shop_id,
                                         domain="fixture.myshopify.com", token="fixture")

    def test_full_sync_imports_nested_pages_and_repeat_does_not_duplicate_orders(self):
        variants = [{"id": f"gid://shopify/ProductVariant/{i}", "sku": f"SKU-{i}", "title": "Default Title",
                     "price": "20", "inventoryQuantity": 5, "inventoryItem": {"tracked": True, "unitCost": {"amount": "10"}}} for i in (1, 2)]
        lines = [{"id": f"gid://shopify/LineItem/{i}", "sku": f"SKU-{i}", "quantity": 2,
                  "variant": {"id": variants[i-1]["id"]}, "originalUnitPriceSet": {"shopMoney": {"amount": "20"}}} for i in (1, 2)]
        def gql(domain, token, query, variables=None):
            if query == sync.PRODUCTS_QUERY:
                return {"data": {"products": page([{"id": "gid://shopify/Product/1", "title": "Fixture", "status": "ACTIVE", "isGiftCard": False, "variants": page(variants[:1], "v-next")}])}}
            if query == sync.PRODUCT_VARIANTS_QUERY:
                self.assertEqual(variables["cursor"], "v-next")
                return {"data": {"product": {"variants": page(variants[1:])}}}
            if query == sync.ORDERS_QUERY:
                return {"data": {"orders": page([{"id": "gid://shopify/Order/1", "createdAt": datetime.now(timezone.utc).isoformat(), "lineItems": page(lines[:1], "l-next")}])}}
            if query == sync.ORDER_LINE_ITEMS_QUERY:
                self.assertEqual(variables["cursor"], "l-next")
                return {"data": {"order": {"lineItems": page(lines[1:])}}}
            self.fail("Unexpected GraphQL query")
        with patch.object(sync, "_gql", side_effect=gql):
            first = sync.sync_shop_now(self.db, shop_id=self.shop_id)
            second = sync.sync_shop_now(self.db, shop_id=self.shop_id)
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(first["variants_imported"], 2)
        self.assertEqual(first["inventory_variants_active"], 2)
        self.assertEqual(first["inventory_variants_excluded"], 0)
        self.assertEqual(first["inventory_rows_retired"], 0)
        self.assertEqual(first["order_line_items_count"], 2)
        self.assertEqual(second["order_line_items_count"], 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Product)), 2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderLineItem)), 2)

    def test_inventory_reconciliation_retires_ineligible_deleted_and_prior_location_rows(self):
        self.ingest_products([product_node(i) for i in range(1, 7)])
        products = {p.shopify_variant_id: p for p in self.db.scalars(select(Product)).all()}
        self.db.add(Inventory(shop_id=self.shop_id, product_id=products["1"].id,
                              shopify_location_id="prior-csv-location", quantity=200))
        self.db.add(OrderLineItem(shop_id=self.shop_id, product_id=products["6"].id,
                                  shopify_order_id="historical:1", quantity=3, price=20,
                                  created_at=datetime.now(timezone.utc)))
        other_shop = Shop(shopify_domain="other.myshopify.com")
        self.db.add(other_shop)
        self.db.flush()
        other_product = Product(shop_id=other_shop.id, shopify_product_id="1", shopify_variant_id="1",
                                name="Other shop", price=20)
        self.db.add(other_product)
        self.db.flush()
        self.db.add(Inventory(shop_id=other_shop.id, product_id=other_product.id,
                              shopify_location_id="aggregate", quantity=99))
        self.db.commit()

        stats = self.ingest_products([
            product_node(1, quantity=0), product_node(2, status="ARCHIVED"),
            product_node(3, status="DRAFT"), product_node(4, gift_card=True),
            product_node(5, tracked=False, quantity=None),
        ])

        self.assertEqual(stats, {"products_scanned": 5, "variants_imported": 5,
                                "inventory_variants_active": 1, "inventory_variants_excluded": 4,
                                "inventory_rows_retired": 6})
        skus = load_skus_for_shop(self.db, self.shop_id)
        self.assertEqual([(sku.sku_id, sku.inventory) for sku in skus], [("SKU-1", 0)])
        snapshot = capture_inventory_value_snapshot(self.db, shop_id=self.shop_id)
        self.assertEqual((snapshot.sku_count, snapshot.total_units, snapshot.total_cost_value), (1, 0, 0))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Product).where(Product.shop_id == self.shop_id)), 6)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderLineItem)), 1)
        self.assertEqual(self.db.scalar(select(Inventory.quantity).where(Inventory.shop_id == other_shop.id)), 99)

    def test_empty_catalog_retires_inventory_without_deleting_history_or_showing_sample_actions(self):
        self.ingest_products([product_node()])
        stats = self.ingest_products([])
        self.assertEqual(stats["inventory_variants_active"], 0)
        self.assertEqual(stats["inventory_rows_retired"], 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Product)), 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Inventory)), 0)
        self.assertEqual(build_inventory_actions(load_skus_for_shop(self.db, self.shop_id)), [])

    def test_failed_later_product_page_preserves_previous_inventory(self):
        self.ingest_products([product_node(quantity=10)])
        with patch.object(sync, "_gql", side_effect=[
            {"data": {"products": page([product_node(quantity=2), product_node(2)], "next")}},
            {"errors": [{"message": "fixture page failure"}]},
        ]):
            with self.assertRaisesRegex(RuntimeError, "products query failed"):
                sync._ingest_products(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(Inventory.quantity)), 10)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Product)), 1)

    def test_repeated_product_cursor_preserves_previous_inventory(self):
        self.ingest_products([product_node(quantity=10)])
        with patch.object(sync, "_gql", return_value={"data": {"products": page([product_node(quantity=2)], "repeated")}}):
            with self.assertRaisesRegex(RuntimeError, "pagination cursor"):
                sync._ingest_products(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(Inventory.quantity)), 10)

    def test_incomplete_catalog_responses_cannot_retire_existing_inventory(self):
        self.ingest_products([product_node(quantity=10)])
        missing_status = product_node()
        del missing_status["status"]
        missing_tracking = product_node()
        del missing_tracking["variants"]["edges"][0]["node"]["inventoryItem"]["tracked"]
        responses = [
            {"data": {"products": None}},
            {"data": {"products": {"edges": []}}},
            {"data": {"products": page([missing_status])}},
            {"data": {"products": page([missing_tracking])}},
            {"data": {"products": page([product_node(quantity=None)])}},
            {"data": {"products": page([{"id": "gid://shopify/Product/1", "status": "ACTIVE", "isGiftCard": False}])}},
            {"data": {"products": page([{}])}},
            {"data": {"products": {"edges": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}}},
        ]
        for response in responses:
            with self.subTest(response=response), patch.object(sync, "_gql", return_value=response):
                with self.assertRaises(RuntimeError):
                    sync._ingest_products(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
            self.db.rollback()
            self.assertEqual(self.db.scalar(select(Inventory.quantity)), 10)

    def test_nested_cursor_loop_is_reported_instead_of_hanging(self):
        connection = page([], "repeated")
        with patch.object(sync, "_gql", return_value={"data": {"product": {"variants": connection}}}):
            with self.assertRaisesRegex(RuntimeError, "pagination cursor"):
                sync._all_child_edges("fixture.myshopify.com", "fixture", "gid://shopify/Product/1", connection, sync.PRODUCT_VARIANTS_QUERY, "product", "variants")

    def test_incomplete_order_roots_fail_instead_of_reporting_successful_empty_history(self):
        for connection in [None, {"edges": []}, page([{}]),
                           {"edges": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}]:
            with self.subTest(connection=connection), patch.object(sync, "_gql", return_value={"data": {"orders": connection}}):
                with self.assertRaises(RuntimeError):
                    sync._ingest_orders(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
            self.db.rollback()

    def test_failed_later_order_page_preserves_previously_committed_history_only(self):
        self.ingest_products([product_node()])
        product = self.db.scalar(select(Product))
        self.db.add(OrderLineItem(shop_id=self.shop_id, product_id=product.id,
                                  shopify_order_id="existing:1", quantity=9, price=20,
                                  created_at=datetime.now(timezone.utc)))
        self.db.commit()
        with patch.object(sync, "_gql", side_effect=[
            {"data": {"orders": page([order_node()], "next")}},
            {"errors": [{"message": "fixture later order page failed"}]},
        ]):
            with self.assertRaisesRegex(RuntimeError, "orders query failed"):
                sync._ingest_orders(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
        self.db.rollback()
        self.assertEqual(self.db.scalars(select(OrderLineItem.quantity)).all(), [9])

    def test_repeated_order_cursor_fails_instead_of_hanging(self):
        with patch.object(sync, "_gql", return_value={"data": {"orders": page([], "repeated")}}):
            with self.assertRaisesRegex(RuntimeError, "pagination cursor"):
                sync._ingest_orders(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
        self.db.rollback()

    def test_complete_order_pages_keep_import_counts_and_repeat_idempotency(self):
        self.ingest_products([product_node()])
        responses = [{"data": {"orders": page([order_node(1)], "next")}},
                     {"data": {"orders": page([order_node(2)])}}]
        for expected_imports in [2, 0]:
            with patch.object(sync, "_gql", side_effect=responses):
                stats = sync._ingest_orders(self.db, shop_id=self.shop_id, domain="fixture.myshopify.com", token="fixture")
            self.assertEqual(stats["orders_scanned"], 2)
            self.assertEqual(stats["line_items_scanned"], 2)
            self.assertEqual(stats["line_items_imported"], expected_imports)
        self.assertEqual(stats["line_item_skip_reasons"], {"already_imported": 2})
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderLineItem)), 2)

    def test_graphql_throttling_retries_then_succeeds(self):
        throttled = {"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]}
        responses = [io.BytesIO(json.dumps(result).encode()) for result in [throttled, {"data": {"products": page([])}}]]
        with patch.object(sync.urllib.request, "urlopen", side_effect=responses) as request, patch.object(sync.time, "sleep") as sleep:
            result = sync._gql("fixture.myshopify.com", "fixture", sync.PRODUCTS_QUERY)
        self.assertIn("data", result)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once()

    def test_history_window_uses_dates_not_row_count(self):
        today = datetime.now(timezone.utc).date()
        for offset in (0, 6, 7, 90):
            self.db.add(InventoryValueSnapshot(shop_id=self.shop_id, snapshot_date=(today-timedelta(days=offset)).isoformat(),
                        total_units=10, sku_count=1, total_cost_value=100, total_retail_value=200))
        other = Shop(shopify_domain="other.myshopify.com")
        self.db.add(other)
        self.db.flush()
        self.db.add(InventoryValueSnapshot(shop_id=other.id, snapshot_date=today.isoformat(), total_units=99, sku_count=1, total_cost_value=999, total_retail_value=999))
        self.db.commit()
        history = inventory_value_history(self.db, shop_id=self.shop_id, days=7)
        self.assertEqual([point["date"] for point in history], [(today-timedelta(days=6)).isoformat(), today.isoformat()])
        self.assertTrue(all(point["cost_value"] == 100 for point in history))


if __name__ == "__main__":
    unittest.main()
