"""CSV/Shopify inventory ownership regression tests with isolated, mocked data."""
from contextlib import contextmanager
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Inventory, OrderLineItem, Product, Shop, ShopifyConnection
from app.services import shopify_sync, stocky_import
from tests.test_shopify_sync import page, product_node


class StockyInventorySourceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        with self.sessions() as db:
            shop = Shop(shopify_domain="stocky-source.myshopify.com")
            db.add(shop)
            db.commit()
            self.shop_id = shop.id
        @contextmanager
        def local_scope():
            with self.sessions() as db:
                try:
                    yield db
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        self.scope = patch.object(stocky_import, "session_scope", local_scope)
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def tearDown(self):
        self.engine.dispose()

    def import_csv(self, rows="SKU-1,CSV title,10,99,9,21\n"):
        return stocky_import.import_stocky_products_csv(shopify_domain="stocky-source.myshopify.com",
            csv_bytes=("SKU,Product,Inventory,Price,Cost,LeadTimeDays\n" + rows).encode())

    def sync_catalog(self, nodes=None):
        with self.sessions() as db, patch.object(shopify_sync, "_gql", return_value={
            "data": {"products": page(nodes if nodes is not None else [product_node(quantity=10)])}}):
            return shopify_sync._ingest_products(db, shop_id=self.shop_id, domain="stocky-source.myshopify.com", token="fixture")

    def test_csv_only_workspace_keeps_inventory_import_and_repeat_update(self):
        first = self.import_csv()
        repeat = self.import_csv("SKU-1,CSV title,8,99,0,21\n")
        self.assertEqual((first.inventory_source, first.products_inserted, first.inventory_rows_inserted), ("csv", 1, 1))
        self.assertEqual((repeat.products_updated, repeat.inventory_rows_inserted), (1, 0))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Inventory.quantity)), 8)
            self.assertEqual(db.scalar(select(Product.cost)), 0)

    def test_shopify_inventory_stays_authoritative_while_known_cost_and_lead_time_update(self):
        self.sync_catalog()
        result = self.import_csv()
        self.assertEqual((result.inventory_source, result.inventory_rows_skipped, result.inventory_rows_inserted), ("shopify", 1, 0))
        self.assertEqual((result.products_processed, result.products_updated, result.rows_skipped), (1, 1, 0))
        self.assertTrue(result.warnings)
        with self.sessions() as db:
            product = db.scalar(select(Product))
            self.assertEqual((product.name, product.price, product.cost, product.sku_lead_time_days), ("Fixture 1", 20, 9, 21))
            self.assertEqual([(row.shopify_location_id, row.quantity) for row in db.scalars(select(Inventory)).all()], [("aggregate", 10)])
        repeated = self.import_csv()
        self.assertEqual((repeated.products_updated, repeated.inventory_rows_skipped), (0, 1))

    def test_csv_then_shopify_does_not_merge_history_or_readd_csv_stock(self):
        self.import_csv()
        with self.sessions() as db:
            original = db.scalar(select(Product))
            original_id = original.id
            db.add(OrderLineItem(shop_id=self.shop_id, product_id=original_id, shopify_order_id="external-fixture",
                                 sku="SKU-1", quantity=10, price=20, created_at=datetime.now(timezone.utc)))
            db.commit()
        self.sync_catalog()
        result = self.import_csv()
        self.assertEqual((result.products_updated, result.rows_skipped, result.inventory_rows_skipped), (0, 1, 1))
        self.assertIn("multiple catalog products", result.skip_reasons[0])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 2)
            self.assertEqual(db.scalar(select(func.sum(Inventory.quantity))), 10)
            self.assertEqual(db.scalar(select(OrderLineItem.product_id)), original_id)
            self.assertEqual(db.get(Product, original_id).sku_lead_time_days, 21)

    def test_real_shopify_variants_with_same_sku_are_not_arbitrarily_updated(self):
        second = product_node(2, quantity=20)
        second["variants"]["edges"][0]["node"]["sku"] = "SKU-1"
        self.sync_catalog([product_node(quantity=10), second])
        result = self.import_csv()
        self.assertEqual((result.products_updated, result.rows_skipped), (0, 1))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.sum(Inventory.quantity))), 30)
            self.assertTrue(all(product.cost == 10 and product.sku_lead_time_days is None
                                for product in db.scalars(select(Product)).all()))

    def test_connected_store_before_first_sync_holds_unmapped_csv_products(self):
        with self.sessions() as db:
            db.add(ShopifyConnection(shop_id=self.shop_id, shopify_domain="stocky-source.myshopify.com",
                                    access_token="fixture-only", scope="read_products"))
            db.commit()
        result = self.import_csv()
        self.assertEqual((result.inventory_source, result.products_inserted, result.rows_skipped, result.inventory_rows_skipped),
                         ("shopify", 0, 1, 1))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(Inventory)), 0)

    def test_new_or_missing_sku_after_native_sync_cannot_create_inventory_placeholders(self):
        self.sync_catalog()
        result = self.import_csv("NEW,New title,10,20,9,21\n,No SKU,12,20,9,21\n")
        self.assertEqual((result.products_processed, result.products_inserted, result.rows_skipped, result.inventory_rows_skipped), (2, 0, 2, 2))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Product)), 1)
            self.assertEqual(db.scalar(select(func.sum(Inventory.quantity))), 10)

    def test_inventory_source_and_sku_match_are_shop_scoped(self):
        with self.sessions() as db:
            other = Shop(shopify_domain="other-stocky-source.myshopify.com")
            db.add(other)
            db.flush()
            product = Product(shop_id=other.id, shopify_product_id="1", shopify_variant_id="1", sku="SKU-1", name="Other", price=20, cost=15)
            db.add(product)
            db.commit()
            other_id = product.id
        result = self.import_csv()
        self.assertEqual((result.inventory_source, result.products_inserted), ("csv", 1))
        with self.sessions() as db:
            self.assertEqual(db.get(Product, other_id).cost, 15)
            self.assertEqual(db.scalar(select(Inventory.shop_id)), self.shop_id)

    def test_blank_or_absent_inventory_preserves_stock_and_does_not_create_a_zero_count(self):
        self.import_csv()
        blank = self.import_csv("SKU-1,Existing,,99,0,21\nNEW,No stock provided,,20,,\n")
        self.assertEqual(blank.inventory_rows_inserted, 0)
        self.assertTrue(any("without an inventory quantity" in warning for warning in blank.warnings))
        missing = stocky_import.import_stocky_products_csv(shopify_domain="stocky-source.myshopify.com",
            csv_bytes=b"SKU,Product,Cost\nSKU-1,Existing,7\n")
        self.assertEqual(missing.inventory_rows_inserted, 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Inventory.quantity)), 10)
            existing = db.scalar(select(Product).where(Product.sku == "SKU-1"))
            self.assertEqual((existing.price, existing.cost), (99, 7))
            new = db.scalar(select(Product).where(Product.sku == "NEW"))
            self.assertIsNone(new.cost)
            self.assertIsNone(db.scalar(select(Inventory).where(Inventory.product_id == new.id)))

    def test_invalid_inventory_skips_entire_row_without_truncation_or_stock_loss(self):
        self.import_csv()
        for quantity in ["Infinity", "-Infinity", "NaN", "not a quantity", "1.5", "2147483648", "-2147483649"]:
            with self.subTest(quantity=quantity):
                result = self.import_csv(f"SKU-1,Changed,{quantity},20,0,30\n")
                self.assertEqual((result.rows_skipped, result.products_updated, result.inventory_rows_inserted), (1, 0, 0))
                self.assertIn("inventory must be", result.skip_reasons[0])
                with self.sessions() as db:
                    self.assertEqual(db.scalar(select(Inventory.quantity)), 10)
                    product = db.scalar(select(Product))
                    self.assertEqual((product.name, product.price, product.cost, product.sku_lead_time_days), ("CSV title", 99, 9, 21))

    def test_finite_whole_quantities_include_zero_and_oversold_stock(self):
        self.import_csv()
        for quantity in [0, -3, 2_147_483_647, -2_147_483_648]:
            with self.subTest(quantity=quantity):
                result = self.import_csv(f"SKU-1,CSV title,{quantity},99,9,21\n")
                self.assertEqual((result.rows_skipped, result.inventory_rows_inserted), (0, 0))
                with self.sessions() as db:
                    self.assertEqual(db.scalar(select(Inventory.quantity)), quantity)

    def test_malformed_provided_price_skips_row_instead_of_erasing_price_or_crashing(self):
        self.import_csv()
        for price in ["NaN", "Infinity", "-Infinity", "bad", "-1", "0.001", "100000000", "1e999999999"]:
            with self.subTest(price=price):
                result = self.import_csv(f"SKU-1,Changed,999,{price},0,30\n")
                self.assertEqual((result.rows_skipped, result.products_updated), (1, 0))
                self.assertIn("price must be", result.skip_reasons[0])
                with self.sessions() as db:
                    self.assertEqual(db.scalar(select(Inventory.quantity)), 10)
                    self.assertEqual(db.scalar(select(Product.price)), 99)

    def test_optional_price_preserves_existing_value_and_explicit_zero_is_valid(self):
        self.import_csv()
        self.import_csv("SKU-1,CSV title,8,,9,21\n")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Product.price)), 99)
        zero = self.import_csv("SKU-1,CSV title,8,0,9,Infinity\n")
        self.assertEqual(zero.rows_skipped, 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Product.price)), 0)
            self.assertEqual(db.scalar(select(Product.sku_lead_time_days)), 21)

    def test_invalid_new_row_does_not_prevent_valid_rows_or_create_placeholder_stock(self):
        result = self.import_csv("BAD,Bad price,10,NaN,9,21\nGOOD,Valid,7,20,0,21\n")
        self.assertEqual((result.products_processed, result.rows_skipped, result.products_inserted, result.inventory_rows_inserted), (2, 1, 1, 1))
        with self.sessions() as db:
            self.assertEqual(db.scalars(select(Product.sku)).all(), ["GOOD"])
            self.assertEqual(db.scalar(select(Inventory.quantity)), 7)
            self.assertEqual(db.scalar(select(Product.cost)), 0)


if __name__ == "__main__":
    unittest.main()
