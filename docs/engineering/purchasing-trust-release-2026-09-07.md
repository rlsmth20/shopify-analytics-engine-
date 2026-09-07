# Purchasing trust and financial evidence release

Missing product costs previously appeared as confident financial amounts by substituting 40% of retail price. This release carries cost provenance from the database into actions, charts, reports, Excel exports, recovery plans and purchasing decisions. Unknown is distinct from a recorded zero; physical stock and demand signals remain usable. Historical inventory charts explicitly show a recorded-cost subtotal because old snapshots lack coverage metadata.

The buying calendar now nets timely, outstanding issued PO quantities before recommending another buy. Opening a supplier email draft no longer marks a PO sent. Explicit zero-cost imports and freight are preserved, first-time PO saving no longer flushes a missing vendor, and unknown generated prices require explicit cost entry before saving. Incomplete sales history no longer produces a Healthy badge. PO review headers support keyboard disclosure, and phone layouts stack filters and freight controls while tables scroll locally.

## Verification

- Backend full suite: **173 tests passed**.
- Frontend: **103 tests passed** across the full suite and the final additional PO disclosure regression; TypeScript check and production build passed.
- XLSX serialization/reload tests preserve unknown totals, recorded zero amounts and numeric quantities.
- Isolated temporary SQLite fixture exercised production loader, API and browser. Five synthetic products covered recorded, zero, missing and incomplete-history inputs. Dashboard/report financial values stayed unknown where necessary; real sales and quantities remained readable.
- Browser rejected saving a blank PO unit cost. An explicit zero saved through the production PO service and survived reload as a recorded $0 line with $35 freight. No supplier email was opened or sent; no production purchase order was created.
- Keyboard Enter expands the saved PO disclosure and exposes its review controls. Desktop and 390px layouts were inspected.

The cost-provenance fields are additive; older clients can still read legacy estimated numeric fields. Frontend and backend should deploy together. No database migration or historical merchant-data rewrite is required. Existing sent PO statuses cannot retrospectively establish whether prior mailto drafts were actually sent, and expected arrivals remain planning assumptions.

## Growth evidence

The bounded research pass is preserved as production growth evidence **5211**, including the three deferred/excluded Shopify Community sources and a previously retained Reddit merchant observation. It produced zero new qualified prospects or outbound messages. Reopening one merchant thread does not increase its sample size. Existing experiment cohorts, the rolling-20 ceiling and $0 advertising policy remain in force.

## Follow-up identified during verification

Reports currently load forecast/reorder data as mandatory dependencies even for Starter users whose plan does not include those endpoints. A separate fix is in progress to load permitted report datasets independently and keep optional failures from hiding accessible action reports. The local full-permission fixture verified the financial presentation in this release; it does not establish Starter report access until that follow-up ships.
