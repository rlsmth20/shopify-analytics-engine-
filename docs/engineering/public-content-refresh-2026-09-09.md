# Public content refresh, September 9, 2026

Updated all five blog articles, the blog index, Stocky and Genie migration pages,
and the spreadsheet comparison. Existing URLs are retained. Article metadata,
previews, visible review dates, and sitemap article dates use `frontend/lib/blog-posts.ts`.
Original publication dates remain intact.

## Corrections

- Stocky retirement and available exports reflect Shopify's current migration guide.
- Purchasing copy includes verified supplier-grouped drafts, Excel PO exports,
  vendor email drafts, and receipt recording. Shopify inventory updates remain
  in the merchant's operational workflow.
- Genie no longer invites visitors to a future early-access opening or promises
  an unimplemented Genie-specific import.
- Current CSV access, free browser tools, and Shopify review status are explicit.
- Removed incorrect Inventory Planner acquisition/pricing claims from blog cards.
- Corrected safety-stock arithmetic, inventory-position terminology, and the
  distinction between an illustrative variable-lead-time formula and Skubase's
  configured-lead-time implementation. Removed unsupported cash-saving guarantees.
- Refreshed the two Stocky community drafts; marked other old launch drafts archived
  rather than allowing stale prices and competitor claims to enter new outreach.
  No public posts or historical sent messages were edited by this release.

## Sources checked

- https://help.shopify.com/en/manual/products/inventory/transitioning-from-stocky
- https://genie.io/blog-articles/we-are-joining-doss
- https://www.prediko.io/pricing
- https://www.inventory-planner.com/pricing/
- https://www.sumtracker.com/pricing
- https://www.cin7.com/pricing/
- https://www.linnworks.com/pricing?region=GB
- https://www.brightpearl.com/pricing
- https://otexts.com/fpp3/holt.html
- https://otexts.com/fpp3/holt-winters.html

Product claims checked against purchase-orders UI and report exports, inventory
engine, reorder optimizer, forecasting, and Stocky import behavior. No backend
logic or contracts changed.

## Verification

Production build and TypeScript checks pass. Browser review at 390px confirms
readable blog previews and Stocky migration content with no page-width overflow.
No browser errors were reported during the checks.
