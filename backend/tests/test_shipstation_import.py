"""Shipment imports use temporary tenant databases; no live imports or API calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import csv
from datetime import datetime
import io
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import require_active_access
from app.api.routes.shipstation_import import router
from app.db.models import Base, OrderLineItem, Product, ShipmentImportBatchRecord, ShipmentImportRowRecord, Shop
from app.db.session import get_db_session
from app.services import shipstation_import as importer, shop_skus


def export(rows, headers=None, newline="\n"):
    columns = headers or ["OrderId", "OrderNumber", "ShipmentId", "LineItemId", "StoreId", "Source", "ShipDate", "SKU", "Quantity", "UnitPrice"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator=newline)
    writer.writeheader()
    for values in rows:
        defaults = {"OrderId": "1001", "OrderNumber": "#11", "ShipDate": "2026-09-06", "SKU": "SKU-A", "Quantity": "3", "UnitPrice": "10"}
        writer.writerow({key: {**defaults, **values}.get(key, "") for key in columns})
    return output.getvalue().encode()


class ShipmentImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="skubase-shipment-fixture-")
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "synthetic.sqlite"), connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        with self.sessions() as db:
            self.shop = Shop(shopify_domain="shipment-fixture.myshopify.com")
            self.other = Shop(shopify_domain="other-shipment-fixture.myshopify.com")
            db.add_all([self.shop, self.other])
            db.commit()
        @contextmanager
        def scope():
            with self.sessions() as db:
                try:
                    yield db
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
        self.scope = scope
        self.factory = patch.object(importer, "session_scope", scope)
        self.factory.start()

    def tearDown(self):
        self.factory.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def upload(self, data=None, scope="non_shopify", shop=None):
        shop = shop or self.shop
        result = importer.import_shipstation_csv(shopify_domain=shop.shopify_domain, shop_id=shop.id,
            csv_bytes=data or export([{}]), source_scope=scope)
        self.assertEqual(result.rows_processed, result.line_items_inserted + result.rows_skipped)
        self.assertEqual(result.rows_skipped, result.duplicate_rows + result.rows_held + result.shopify_rows_excluded + result.invalid_rows)
        return result

    def rows(self, model, shop=None):
        with self.sessions() as db:
            return db.scalars(select(model).where(model.shop_id == (shop or self.shop).id)).all()

    def metrics(self):
        with self.sessions() as db, patch.object(shop_skus, "_now_naive_utc", return_value=datetime(2026, 9, 7, 12)):
            return (sum(shop_skus.load_daily_history_for_shop_sku(db, self.shop.id, "SKU-A", 30)),
                    sum(value for _, value in shop_skus.load_recent_daily_revenue_for_shop(db, self.shop.id)))

    def test_exact_reupload_preserves_sales_and_returns_no_new_analysis(self):
        first = self.upload()
        self.assertEqual(self.metrics(), (3, 30))
        again = self.upload()
        self.assertTrue(again.replayed)
        self.assertEqual(again.batch_id, first.batch_id)
        self.assertEqual((again.line_items_inserted, again.duplicate_rows), (0, 1))
        self.assertEqual((again.distinct_skus, again.top_skus_by_velocity, again.latest_ship_date), (0, [], None))
        self.assertEqual(self.metrics(), (3, 30))
        self.assertEqual(len(self.rows(ShipmentImportBatchRecord)), 1)

    def test_canonical_replay_ignores_bom_order_aliases_dates_and_irrelevant_private_fields(self):
        first = self.upload(export([{}, {"OrderId": "1002", "OrderNumber": "#12"}]))
        reordered = export([{"OrderId": "1002", "OrderNumber": "#12", "Quantity": "3.0", "ShipDate": "09/06/2026"},
                            {"Quantity": "3.0", "ShipDate": "09/06/2026"}], newline="\r\n")
        reordered = b"\xef\xbb\xbf" + reordered.replace(b"SKU", b"Item SKU", 1).replace(b"UnitPrice", b"Unit Price", 1)
        again = self.upload(reordered)
        self.assertTrue(again.replayed)
        self.assertEqual(again.batch_id, first.batch_id)
        self.assertEqual(len(self.rows(OrderLineItem)), 2)
        with_private = export([{}, {"OrderId": "1002", "OrderNumber": "#12"}],
            headers=["OrderId", "OrderNumber", "ShipmentId", "LineItemId", "StoreId", "Source", "ShipDate", "SKU", "Quantity", "UnitPrice", "CustomerEmail"])
        self.assertTrue(self.upload(with_private.replace(b",\n", b",private@example.invalid\n")).replayed)
        self.assertNotIn("private@example", str(self.rows(ShipmentImportRowRecord)[0].facts))

    def test_weak_identical_rows_keep_multiplicity_but_later_partial_overlap_is_held(self):
        first = self.upload(export([{}, {}]))
        self.assertEqual(first.line_items_inserted, 2)
        self.assertEqual(self.metrics(), (6, 60))
        self.assertEqual(self.upload(export([{}, {}])).duplicate_rows, 2)
        partial = self.upload(export([{}]))
        self.assertEqual((partial.line_items_inserted, partial.rows_held), (0, 1))
        self.assertEqual(self.metrics(), (6, 60))

    def test_missing_order_reference_does_not_make_changed_quantity_a_new_shipment(self):
        row = {"OrderId": "", "OrderNumber": ""}
        self.upload(export([row]))
        corrected = self.upload(export([{**row, "Quantity": "4"}]))
        self.assertEqual((corrected.rows_held, corrected.line_items_inserted), (1, 0))
        self.assertEqual(self.metrics(), (3, 30))

    def test_distinct_split_shipments_and_split_items_survive_overlapping_exports(self):
        first = {"ShipmentId": "S1", "LineItemId": "L1", "Quantity": "2"}
        second = {"ShipmentId": "S2", "LineItemId": "L1", "Quantity": "1"}
        third = {"ShipmentId": "S2", "LineItemId": "L2", "Quantity": "1"}
        self.upload(export([first]))
        next_result = self.upload(export([first, second, third]))
        self.assertEqual((next_result.line_items_inserted, next_result.duplicate_rows), (2, 1))
        self.assertEqual(self.metrics(), (4, 40))
        self.assertEqual(len({row.shopify_order_id for row in self.rows(OrderLineItem)}), 1)

    def test_repeated_strong_identity_within_file_counts_once_and_corrections_hold(self):
        row = {"ShipmentId": "S1", "LineItemId": "L1"}
        first = self.upload(export([row, row]))
        self.assertEqual((first.line_items_inserted, first.duplicate_rows), (1, 1))
        for change in [{"Quantity": "4"}, {"SKU": "CORRECTED-SKU"}, {"UnitPrice": "11"}, {"ShipDate": "2026-09-05"}]:
            corrected = self.upload(export([{**row, **change}]))
            self.assertEqual((corrected.rows_held, corrected.line_items_inserted), (1, 0))
        self.assertEqual(self.metrics(), (3, 30))

    def test_store_namespaces_preserve_distinct_orders_and_shipments(self):
        row = {"ShipmentId": "S1", "LineItemId": "L1", "StoreId": "etsy-store-1"}
        self.upload(export([row]))
        other = self.upload(export([{**row, "StoreId": "amazon-store-2"}]))
        self.assertEqual(other.line_items_inserted, 1)
        self.assertEqual(len({line.shopify_order_id for line in self.rows(OrderLineItem)}), 2)
        self.upload(export([{"OrderId": "2002", "OrderNumber": "#22", "Source": "Etsy"}]))
        self.assertEqual(self.upload(export([{"OrderId": "2002", "OrderNumber": "#22", "Source": "Amazon"}])).line_items_inserted, 1)

    def test_order_item_and_shipment_item_columns_coexist_without_collapsing_splits(self):
        columns = ["OrderId", "ShipmentId", "LineItemId", "ShipmentItemId", "ShipDate", "SKU", "Quantity", "UnitPrice"]
        row = {"ShipmentId": "S1", "LineItemId": "L1", "ShipmentItemId": "SL1"}
        self.assertEqual(self.upload(export([row], headers=columns)).line_items_inserted, 1)
        both = self.upload(export([row, {**row, "ShipmentId": "S2", "ShipmentItemId": "SL2"}], headers=columns))
        self.assertEqual((both.line_items_inserted, both.duplicate_rows), (1, 1))
        changed_kind = self.upload(export([{**row, "LineItemId": ""}], headers=columns))
        self.assertEqual(changed_kind.rows_held, 1)

    def test_unknown_source_hold_can_be_rechecked_without_bypassing_inserted_rows(self):
        mixed = export([{"Source": "Etsy", "OrderId": "1001"}, {"OrderId": "1002", "OrderNumber": "#12"}])
        first = self.upload(mixed, scope="unknown")
        self.assertEqual((first.line_items_inserted, first.rows_held), (1, 1))
        confirmed = self.upload(mixed)
        self.assertEqual((confirmed.line_items_inserted, confirmed.duplicate_rows), (1, 1))
        self.assertEqual(len(self.rows(OrderLineItem)), 2)
        self.assertFalse(confirmed.replayed)
        self.assertTrue(self.upload(mixed).replayed)

    def test_explicit_shopify_sources_are_excluded_even_after_non_shopify_confirmation(self):
        with self.sessions() as db:
            product = Product(shop_id=self.shop.id, shopify_product_id="501", shopify_variant_id="601", sku="SKU-A", name="Synthetic", price=10)
            db.add(product); db.flush()
            db.add(OrderLineItem(shop_id=self.shop.id, shopify_order_id="9001:8001", product_id=product.id, sku="SKU-A", quantity=3, price=10, created_at=datetime(2026, 9, 6)))
            db.commit()
        result = self.upload(export([{"Source": "Shopify", "OrderId": "9001"}, {"Source": "Etsy", "OrderId": "9002"}]))
        self.assertEqual((result.shopify_rows_excluded, result.line_items_inserted), (1, 1))
        self.assertEqual(self.metrics(), (6, 60))
        data = export([{"ShopifyOrderId": "9001", "Source": "Etsy"}], headers=["ShopifyOrderId", "Source", "ShipDate", "SKU", "Quantity"])
        self.assertEqual(self.upload(data).shopify_rows_excluded, 1)

    def test_legacy_overlap_is_held_without_modifying_historical_data(self):
        with self.sessions() as db:
            product = Product(shop_id=self.shop.id, shopify_product_id="old", shopify_variant_id="old", sku="SKU-A", name="Synthetic", price=10)
            db.add(product); db.flush()
            old = OrderLineItem(shop_id=self.shop.id, shopify_order_id="shipstation:#11", product_id=product.id, sku="SKU-A", quantity=3, price=10, created_at=datetime(2026, 9, 6))
            db.add(old); db.commit()
            old_id = old.id
        result = self.upload(export([{"ShipmentId": "S1", "LineItemId": "L1"}]))
        self.assertEqual(result.rows_held, 1)
        self.assertEqual([line.id for line in self.rows(OrderLineItem)], [old_id])

    def test_same_sku_catalog_ambiguity_is_held_instead_of_arbitrarily_assigned(self):
        with self.sessions() as db:
            for variant in ("one", "two"):
                db.add(Product(shop_id=self.shop.id, shopify_product_id=variant, shopify_variant_id=variant, sku="SKU-A", name="Synthetic", price=10))
            db.commit()
        self.assertEqual(self.upload().rows_held, 1)
        self.assertEqual(self.rows(OrderLineItem), [])

    def test_rollback_removes_batch_receipts_lines_and_created_products_then_retry_works(self):
        with patch.object(importer, "_summarize_imported", side_effect=RuntimeError("synthetic crash before commit")):
            with self.assertRaises(RuntimeError):
                self.upload()
        for model in (OrderLineItem, Product, ShipmentImportBatchRecord, ShipmentImportRowRecord):
            self.assertEqual(self.rows(model), [])
        self.assertEqual(self.upload().line_items_inserted, 1)

    def test_coincident_uploads_are_atomic_and_one_replays(self):
        barrier = threading.Barrier(2)
        @contextmanager
        def concurrent_scope():
            barrier.wait(timeout=10)
            with self.scope() as db:
                yield db
        with patch.object(importer, "session_scope", concurrent_scope), ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.upload(), range(2)))
        self.assertEqual(sorted(result.line_items_inserted for result in results), [0, 1])
        self.assertEqual(sorted(result.replayed for result in results), [False, True])
        self.assertEqual(self.metrics(), (3, 30))
        self.assertEqual(len(self.rows(ShipmentImportBatchRecord)), 1)

    def test_batch_and_source_identity_are_tenant_scoped(self):
        data = export([{"ShipmentId": "S1", "LineItemId": "L1"}])
        self.assertEqual(self.upload(data).line_items_inserted, 1)
        self.assertEqual(self.upload(data, shop=self.other).line_items_inserted, 1)
        with self.assertRaises(importer.ShipStationImportError):
            importer.import_shipstation_csv(shopify_domain=self.other.shopify_domain, shop_id=self.shop.id, csv_bytes=data)
        self.assertEqual(len(self.rows(ShipmentImportBatchRecord, shop=self.other)), 1)

    def test_invalid_numeric_rows_never_crash_or_truncate_demand(self):
        cases = [{"Quantity": value} for value in ("1.5", "NaN", "Infinity", "-1", "0", "2147483648")]
        cases += [{"UnitPrice": value} for value in ("NaN", "Infinity", "-1", "1.234", "99999999999")]
        result = self.upload(export(cases))
        self.assertEqual((result.invalid_rows, result.line_items_inserted), (len(cases), 0))
        self.assertEqual(self.rows(OrderLineItem), [])

    def test_malformed_headers_csv_and_row_limit_fail_before_any_write(self):
        cases = [b"SKU,Quantity\nSKU-A,1\n", b"SKU,ItemSKU,Quantity,ShipDate\nA,A,1,2026-09-06\n", b'SKU,Quantity,ShipDate\n"unfinished,1,2026-09-06']
        for data in cases:
            with self.assertRaises(importer.ShipStationImportError):
                self.upload(data)
        with patch.object(importer, "MAX_ROWS", 1), self.assertRaises(importer.ShipStationImportError):
            self.upload(export([{}, {}]))
        self.assertEqual(self.rows(ShipmentImportBatchRecord), [])

    def test_corrected_column_count_does_not_replay_prior_invalid_batch(self):
        malformed = b"SKU,Quantity,ShipDate\nSKU-A,3,2026-09-06,unexpected\n"
        self.assertEqual(self.upload(malformed).invalid_rows, 1)
        corrected = self.upload(b"SKU,Quantity,ShipDate\nSKU-A,3,2026-09-06\n")
        self.assertFalse(corrected.replayed)
        self.assertEqual(corrected.line_items_inserted, 1)

    def test_route_scopes_shop_validates_source_and_returns_additive_counts(self):
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[require_active_access] = lambda: SimpleNamespace(shop_id=self.shop.id)
        def get_db():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db_session] = get_db
        with TestClient(app) as client:
            result = client.post("/integrations/shipstation/import", files={"csv_file": ("fixture.csv", export([{}]), "text/csv")})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["rows_held"], 1)
            accepted = client.post("/integrations/shipstation/import", data={"source_scope": "non_shopify", "shop_id": self.other.id}, files={"csv_file": ("fixture.csv", export([{}]), "text/csv")})
            self.assertEqual(accepted.status_code, 200, accepted.text)
            self.assertEqual(accepted.json()["shop_id"], self.shop.id)
            self.assertEqual(accepted.json()["line_items_inserted"], 1)
            invalid = client.post("/integrations/shipstation/import", data={"source_scope": "allow_all"}, files={"csv_file": ("fixture.csv", export([{}]), "text/csv")})
            self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.rows(OrderLineItem, shop=self.other), [])


if __name__ == "__main__":
    unittest.main()
