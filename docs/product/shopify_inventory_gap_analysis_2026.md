# Shopify Inventory Gap Analysis - May 2026

## Method

This analysis is based on public Shopify App Store reviews, Reddit threads, and 2026 Shopify inventory comparison guides gathered on May 22, 2026. I clustered the excerpts with a lightweight keyword-vector pass, then mapped each cluster against current skubase product surfaces and backend wiring.

Sources reviewed:

- Shopify App Store review pages for Stocky, Inventory Planner by Sage, Katana, Prediko, Monocle, Sensible Forecasting, and PML Stock Take.
- Reddit threads about Stocky shutdown, Shopify inventory replacements, Cin7/Katana/Stocky alternatives, and multi-location retail workflows.
- 2026 comparison guides from Canopy and Charle covering Shopify inventory feature gaps and competitor positioning.

## Cluster Summary

| Cluster | Market signal | skubase opportunity | Current wiring | Priority |
| --- | --- | --- | --- | --- |
| Pricing and contract risk | Merchants complain about surprise renewal hikes, annual lock-ins, add-ons, and being moved up tiers by order count or GMV. | Lead with published price, price-lock pledge, no quote-only plan, no hidden add-ons for core inventory intelligence. | Strong. Pricing page, terms copy, Stripe plan keys, and plan gates exist. | Keep |
| Stocky replacement middle ground | Stocky users need POs, receiving, transfers, stocktakes, and basic inventory control without jumping to ERP pricing. | Position as the focused middle ground: Shopify-first decisions, POs, receiving/transfers, forecasting, supplier metrics, not ERP sprawl. | Partial. Purchase order drafts exist. Transfers route/page exist but backend currently returns empty until multi-location ingestion is complete. Stocktake/receiving flow is not built. | P0/P1 |
| Forecast trust and seasonality | Complaints mention manual overrides, weak handling of stockouts, seasonality, new fast sellers, and needing long history before forecasts become useful. | Make forecast confidence visible, account for stockout days, separate seasonal vs new-product strategy, explain every recommendation. | Good foundation. Forecasting, ABC/XYZ, reorder optimizer, and visible rationale exist. Missing true stockout-day exclusion and richer new-product handling. | P0 |
| Workflow and sync safety | Merchants fear integrations that alter inventory unexpectedly, sync too aggressively, miss Shopify tags, or jumble SKU quantities. | Safe-by-default sync: preview changes, dry-run, explain inventory writes, never mutate Shopify stock without explicit approval. | Partial. Shopify ingestion and sync status exist. Current app reads/ingests, but explicit write-safety UX and sync preview are not fully established. | P0 |
| Usability, performance, and support | Stocky reviews complain about slow pages, missing filters, no select-all, and poor support after onboarding. Positive reviews reward responsive, tailored support. | Fast action queue, dense filters, bulk actions, high-touch migration support, and clear first-run setup. | Partial. Dashboard/action queue exists. Need stronger filtering, bulk operations, migration checklist, and performance budgets for larger catalogs. | P1 |
| Supplier and vendor intelligence | Guides and reviews highlight supplier lead times, minimum order quantities, and vendor-specific reorder decisions. | Own "vendors as performers": on-time rate, fill rate, lead-time variance, cost stability, and PO-aware safety stock. | Partial. Supplier scorecards exist, but route currently uses empty PO/receipt observations until receipt history is ingested. | P1 |
| Bundles, kits, and multi-channel complexity | Bundle handling and multi-channel sync come up repeatedly as reasons merchants outgrow native Shopify. | Handle Shopify bundles/components and import multi-channel history through ShipStation without becoming a full ERP. | Partial. Bundle analyzer service/page exists, but current route returns empty until component mappings land. ShipStation import exists. | P1 |
| Alerting and escalation | Merchants want alerts that reach the right channel, not just reports they must remember to check. | Alert rules with channel gates: Starter email/Slack, Growth SMS/webhook. | Improved. Plan-gated alert channels now enforced. Fixed alert rules/channels/events to be shop-scoped. | Keep |

## Competitive Gaps We Can Fill

### 1. The "middle ground" after Stocky

Merchants describe a gap between native Shopify/Stocky and expensive ERPs like Cin7, Katana, Unleashed, and Fishbowl. The repeated shape is: "I need POs, receiving, transfers, and forecasting, but I do not want a manufacturing ERP or a sales call."

What to build or sharpen:

- Stocky migration checklist as a first-run workflow.
- PO receiving flow that updates local inventory and optionally pushes to Shopify after confirmation.
- Transfer recommendations tied to actual per-location inventory, not just placeholder endpoints.
- Stocktake/count workflow or an integration stance if we decide not to build it.

### 2. Trustworthy forecasting for messy Shopify data

Inventory Planner complaints specifically mention manual work, stockout blind spots, seasonal products, and new fast-selling products. This is a direct opening because skubase already emphasizes visible math.

What to build or sharpen:

- Exclude out-of-stock days from velocity where Shopify inventory history makes it detectable.
- Add "new fast seller" handling separate from seasonal historical forecasts.
- Add forecast confidence reasons, not just confidence labels.
- Show when a recommendation is using fallback/mock/limited history.

### 3. Safe sync as a differentiator

Katana complaints include inventory being jumbled on install and sync behavior being too automatic. This is not just a feature gap; it is a trust gap.

What to build or sharpen:

- Read-only default after Shopify OAuth.
- Sync preview before any inventory write.
- Explicit "Shopify is source of truth" vs "skubase writes quantity updates" mode.
- Audit log for every outbound stock change.

### 4. Supplier performance, not supplier contacts

The market talks about supplier lead times and reorder timing, but few tools make supplier reliability central. skubase already has the right positioning, but it needs live receipt/PO data.

What to build or sharpen:

- Persist PO lifecycle events: drafted, approved, sent, received, partial, canceled.
- Record expected vs actual receipt dates and ordered vs received quantities.
- Feed supplier scorecards from those observations.
- Let unreliable suppliers change safety stock and reorder timing automatically.

### 5. Actionable dead-stock recovery

Many tools identify slow movers; fewer recommend a concrete recovery plan. skubase has this surface already, so the gap is to make it operational.

What to build or sharpen:

- Markdown plan export or Shopify price-change draft.
- Bundle candidates using component and co-purchase data.
- Wholesale/liquidation list export.
- Recovery forecast: expected cash recovered and margin impact.

## Wiring Audit

### Confirmed working

- Frontend typecheck passes with `npm run typecheck`.
- Frontend production build passes with `npm run build`.
- Backend Python compile passes with `python -m compileall app`.
- Plan gates are wired backend-side for suppliers, bundles, transfers, liquidation, and Growth-only SMS/webhook alert channels.
- Pricing tiers are centralized in `frontend/lib/plans.ts` and reused by pricing, billing, account, and navigation surfaces.
- Trial/no-subscription access is gated through `require_active_access()`.

### Fixed during this audit

- Alert rules, notification channel settings, and in-memory alert events were globally shared. They are now scoped per shop:
  - `alert_rules.shop_id` migration added.
  - Alert rule CRUD filters by `user.shop_id`.
  - Channel config stores per-shop channel keys internally while preserving the public API shape.
  - Dashboard alert counts now read only the current shop's alert events.
- Forecast responses now include data-quality warnings, history days, and stockout-limited demand adjustment counts.
- The forecast page now surfaces warning notes for limited history, sparse demand, new fast-seller signals, and likely stockout-suppressed demand.
- The Shopify Store Sync page now explicitly communicates read-only sync safety.
- Multi-location transfers now use real per-location inventory rows when present instead of always returning an empty result.

### Still not fully wired

- `/bundles` route currently returns an empty list despite bundle analyzer service existing.
- Transfer recommendations use shop-wide velocity allocated across locations until location-specific demand exists; this is useful but should be labeled conservative.
- Supplier scorecards currently use empty PO/receipt observations, so vendor performance is not yet grounded in live receipt history.
- Purchase order drafts exist, but approval/send/receive lifecycle is not yet complete.
- Alert rule/channel persistence now scopes by shop, but the legacy global records remain ignored rather than migrated into a specific shop.

## Recommended Build Order

1. **P0: Forecast trust**
   - Stockout-day exclusion.
   - New fast-seller detection.
   - Forecast confidence reasons and warnings.

2. **P0: Safe Shopify sync**
   - Read-only default.
   - Sync preview and write audit log.
   - Clear outbound write mode.

3. **P1: Stocky replacement core**
   - PO receive flow.
   - Multi-location transfer engine wired to Shopify locations.
   - Stocktake/count workflow decision.

4. **P1: Supplier intelligence loop**
   - PO/receipt persistence.
   - Supplier scorecards from actual receipt performance.
   - Safety stock adjustment by supplier reliability.

5. **P1: Bundle and dead-stock operations**
   - Component mapping ingestion.
   - Bundle bottleneck route wired to real data.
   - Markdown/export flows for liquidation plans.

6. **P2: Support and migration experience**
   - Stocky migration wizard.
   - Catalog scale filters and bulk actions.
   - Visible support SLA inside onboarding.

## Positioning Takeaway

The strongest wedge is not "another inventory dashboard." It is:

> skubase is the Shopify-first Stocky replacement for merchants who need forecasting, POs, transfers, supplier reliability, and dead-stock recovery without ERP pricing or unsafe sync.

That positioning is credible now, but the product should prioritize forecast trust, safe sync, PO receiving, and real multi-location transfer data before leaning too hard into the full Stocky replacement claim.
