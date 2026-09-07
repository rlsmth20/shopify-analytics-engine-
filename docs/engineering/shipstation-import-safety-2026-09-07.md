# ShipStation shipment import safety

The authenticated ShipStation CSV endpoint now records atomic import receipts and excludes uncertain rows from sales history. It does not delete, merge or rewrite earlier imports or Shopify products.

## Source selection

The additive multipart `source_scope` field accepts `unknown` (the default) or `non_shopify`. The second value records the merchant's confirmation that the selected export excludes Shopify orders. Rows explicitly identifying Shopify through a source/store column or a Shopify Order ID are excluded in either mode. A recognized external channel such as Etsy or Amazon can be imported without the general confirmation. Other unidentified rows are held until the merchant can confirm their source.

This separation matters because Shopify imports sales orders, while ShipStation exports may describe fulfillment of those same sales. Matching SKU, quantity or nearby dates cannot establish cross-channel order identity. The importer does not claim that it can infer an undeclared Shopify origin. Merchants must accurately select an external-channel export. Existing Shopify data remains unchanged.

## Receipt and duplicate behavior

Two new tables, `shipment_import_batches` and `shipment_import_rows`, are created by the existing startup metadata initialization. A batch is unique per shop, canonical file contents and source selection. Canonical file identity ignores row order, BOM, header aliases, equivalent parsed numeric/date values and irrelevant customer/address columns. It preserves repeated-row multiplicity and row validity; correcting an invalid row does not replay its old invalid result.

The importer locks the shop before checking receipts or adding sales lines. PostgreSQL uses a row lock; local SQLite uses `BEGIN IMMEDIATE`. Batch receipts, row receipts, newly required products and order lines commit together. A crash before commit rolls everything back. A lost response after commit can be retried safely. Unique batch and source-line constraints provide additional protection.

When Shipment ID and an Order/Line Item ID or Shipment Item ID are available, their store/source-scoped combination identifies the imported line. Different shipments of the same order item, and separate line items containing the same SKU, remain distinct. A known line with changed SKU, quantity, price or date is held as a correction for review; it never silently overwrites history. Generic Item ID alone is not treated as a shipment-line ID because it may identify a catalog product.

Without strong IDs, rows have identities only within their exact canonical file, including occurrence count. An exact replay adds nothing. Changing the source selection can process newly confirmed rows while recognizing earlier accepted rows. A different file that may overlap prior history is held rather than guessed to be a duplicate or a new shipment. This includes legacy CSV rows without receipts. Exporting stable shipment and line IDs makes overlapping date-range imports more useful. A SKU matching multiple catalog products is also held; this release does not merge CSV placeholders into Shopify variants.

Each row receipt preserves selected shipment facts, its outcome and the exact inserted `OrderLineItem` ID when one exists. It does not retain the raw CSV or unrelated customer/address columns. These references support audited operator review or a future rollback workflow; no automatic cleanup or merchant rollback endpoint is introduced. Both tables carry `shop_id`, so the existing reverse-dependency tenant purge removes them, including when SQLite FK cascades are disabled.

## Response contract

Existing response fields remain. Additions are `batch_id`, `source_scope`, `replayed`, `duplicate_rows`, `rows_held`, `shopify_rows_excluded`, `invalid_rows` and `hold_reasons` (up to ten examples). `rows_skipped` includes all four non-inserted categories. Nonblank data rows satisfy:

`rows_processed = line_items_inserted + rows_skipped`

`rows_skipped = duplicate_rows + rows_held + shopify_rows_excluded + invalid_rows`

Replay returns zero newly inserted lines and no new SKU/date/velocity analysis. Newly inserted lines alone contribute to the response's velocity summary; its historical windows still end on the latest newly inserted shipment date, not today. Input limits are 50 MB and 100,000 nonblank rows. Malformed CSV/header errors fail before writes; invalid individual rows receive explicit outcomes. Quantities must be finite positive whole numbers.

## Verification

`python -m unittest tests.test_shipstation_import tests.test_shopify_privacy` uses temporary databases and no live imports. Cases cover demand/revenue remaining unchanged on replay, canonical files, row multiplicity, split shipments, overlapping exports, changed identities, source confirmation and Shopify exclusions, legacy preservation, ambiguous product mapping, concurrent workers, rollback, tenant isolation, corrected malformed rows, numeric validation and tenant purge with FK cascades disabled.
