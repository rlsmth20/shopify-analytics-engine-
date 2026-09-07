# Inventory cost provenance

Stocky CSV cost parsing also preserves an explicit zero on insert or update. Blank, invalid, nonfinite and negative entries remain missing rather than silently becoming zero; blank updates preserve an existing recorded cost.

Previously, a missing product cost became 40% of retail price. An established-history SKU priced at $100 with 500 units and 30 monthly sales therefore reported $17,000 of excess capital and high confidence despite having no recorded cost. A recorded cost of zero also fell through to this estimate in the live shop loader.

The numeric compatibility fields remain in the HTTP contract. Consumers must use the additive canonical projections for display, exports and decisions:

- `cost_source`: `recorded`, `estimated_from_price` or `missing`. A recorded zero is valid. Neither of the latter states is a verified cost.
- `financial_values_known` plus `financial_values`: keys match each resource's legacy numeric fields; cost-dependent fields become `null` when the required cost is absent. This covers actions, scorecards, reorder and vendor totals, purchase-order and calendar projections, cash plans, liquidation and bundle suggestions. `ReorderFeedResponse.known_vendor_totals` preserves missing vendor totals as null.
- KPI/chart rows use `value_known` plus `known_value`; normal constructors populate the canonical value, including true zero. False flags always serialize canonical null.

“Known” means the required cost inputs are recorded, not that a modeled profit, sell-through, margin or recovery is guaranteed. Sales-history confidence remains independent. Demand quantities, coverage and stockout warnings remain available with missing costs. Cost-based rankings and EOQ/freight-share optimization do not use fabricated cost inputs. Unknown-cost liquidation rows remain visible for review but do not recommend a discount, sale price or write-off. Backend explanatory text, copilot context, scheduled reports, weekly buy lists and financial alerts respect the same boundary.

New PO drafts with unknown prices cannot be saved until explicit line costs are supplied. The save endpoint returns 422 and the service rejects before writing. Existing saved merchant-entered line prices remain unchanged and are treated as recorded amounts. No provenance column or migration is introduced. The test also fixed the existing first-save flush before required vendor assignment. Configured shipping remains present for genuine zero-cost goods.

Historical inventory-value snapshots never stored cost completeness; they cannot be retroactively certified. Their existing amount is a **recorded-cost subtotal**, not a complete inventory valuation. No historical records are rewritten. Older clients can still read numeric compatibility estimates, so the frontend masking change must ship with the backend projection change.

Verification: `python -m unittest tests.test_cost_provenance tests.test_inventory_trust tests.test_dashboard_performance tests.test_dashboard_forecast_variance tests.test_buying_calendar`. Tests exercise an in-memory database, canonical JSON, mixed/zero/missing costs, stock and cash recommendations, saved-price rejection and genuine recorded-price persistence. Email provider interactions are mocked; no live merchant data, provider calls or production writes are involved.
