import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from app.db.models import Base, Shop, ShopifyConnection, Product, OrderLineItem, InventoryValueSnapshot
from app.services import shopify_sync as sync
from app.services.inventory_value import inventory_value_history


def page(nodes, cursor=None):
    return {"edges": [{"node": node} for node in nodes], "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}


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

    def test_full_sync_imports_nested_pages_and_repeat_does_not_duplicate_orders(self):
        variants = [{"id": f"gid://shopify/ProductVariant/{i}", "sku": f"SKU-{i}", "title": "Default Title",
                     "price": "20", "inventoryQuantity": 5, "inventoryItem": {"unitCost": {"amount": "10"}}} for i in (1, 2)]
        lines = [{"id": f"gid://shopify/LineItem/{i}", "sku": f"SKU-{i}", "quantity": 2,
                  "variant": {"id": variants[i-1]["id"]}, "originalUnitPriceSet": {"shopMoney": {"amount": "20"}}} for i in (1, 2)]
        def gql(domain, token, query, variables=None):
            if query == sync.PRODUCTS_QUERY:
                return {"data": {"products": page([{"id": "gid://shopify/Product/1", "title": "Fixture", "variants": page(variants[:1], "v-next")}])}}
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
        self.assertEqual(first["order_line_items_count"], 2)
        self.assertEqual(second["order_line_items_count"], 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Product)), 2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderLineItem)), 2)

    def test_nested_cursor_loop_is_reported_instead_of_hanging(self):
        connection = page([], "repeated")
        with patch.object(sync, "_gql", return_value={"data": {"product": {"variants": connection}}}):
            with self.assertRaisesRegex(RuntimeError, "pagination cursor"):
                sync._all_child_edges("fixture.myshopify.com", "fixture", "gid://shopify/Product/1", connection, sync.PRODUCT_VARIANTS_QUERY, "product", "variants")

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
