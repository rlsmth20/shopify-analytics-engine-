# Forecast evidence and honest empty states

A fresh CSV workspace could import inventory with no sales and then receive a forecast labeled high confidence, 90 days of history and low backtest error. The history loader's zero-filled window was mistaken for measured zero demand. This release carries observation information into forecasts and prevents missing data from appearing as a known zero-risk result.

## Source and forecast behavior

Forecasts expose additive `forecast_available` and `demand_signal` fields. Missing usable history produces an unavailable forecast, no chart points and unknown backtest values. Legacy numeric demand/risk fields remain compatibility placeholders; consumers must honor availability. An established recorded history followed by a window with no recent recorded sales is distinct: its zero-demand estimate remains available with low confidence and no inferred finite stock coverage.

The existing daily arrays stay unchanged for purchasing and reorder calculations. Observation information is collected from the existing aggregate history query, without per-SKU queries. Backtesting excludes unobserved padding, and short or sparse histories cannot establish high confidence. Percentage accuracy and directional bias remain unknown when the comparison window has no recorded sales. The relative error measure uses mean daily absolute error divided by the larger of that day's recorded sales and one; the UI describes that calculation rather than treating it as a calibrated guarantee.

Observation duration follows the same completed UTC dates as daily history. Yesterday's sale is usable even if fewer than 24 hours have elapsed, while today's sales can appear in recent-sales metrics before a completed forecast day exists. Padding is removed once; known leading zero-sales days remain in observed windows. Existing failed/stale-sync and incomplete-history warnings flow through all forecast callers, constrain confidence and qualify backtest trust.

Forecast list and detail API horizons are bounded to 1–90 days, with a 30-day default. Missing-history forecasts cannot trigger a forecast stockout alert, including a rule with a zero-percent threshold.

## Merchant presentation

Missing forecasts show Unknown values and visible import/sync steps instead of zero-demand charts, green risk badges or accuracy claims. The high-risk filter explicitly says 30 days. Risk remains an estimate; values that would round to 100% display as greater than 99%. Relative backtest errors can exceed 100% and are not probability-capped. Explicit sample forecasts remain available in the demo, with unspecified history and backtest values left unknown.

Inventory health reports forecast coverage. Missing SKU forecasts leave total revenue risk unknown, while any available subtotal is labeled as partial. Short-history and low-confidence estimates retain adjacent caveats. Known zero estimates remain distinguishable from unavailable ones. An empty purchasing list explains that no recommendations were produced and prompts review of data and lead times; it does not claim every item is safely stocked.

## Verification

Before the fix, a real authenticated non-admin trial flow was exercised entirely in isolated temporary SQLite through local ASGI HTTP, with external sockets blocked. Stocky supplied three CSV-only products and 214 stock units. Explicit non-Shopify shipment history bound 57 rows, 102 sold units and $2,160 historical revenue to those same products. Actions identified the fast item's two days of stock cover and the slow item's overstock. Replaying both files left product, inventory and sales totals unchanged. This verified usable CSV onboarding and exposed the misleading missing-history forecast; these are synthetic results, not customer acquisition evidence.

The complete suite passed 303 backend tests and 196 frontend tests, plus typecheck. The durable non-admin CSV workflow is in `tests/test_forecast_provenance.py`; it now covers missing, established zero-sales, first-sale-today and yesterday-evening data. Independent review also verified all forecast callers and downstream health handling.

Browser verification used seven synthetic SKUs against the actual local API. Missing history displayed Unknown demand/risk/accuracy and no charts; the established zero-sales SKU displayed a cautious zero estimate, 90 recorded days and unknown relative accuracy. A no-result search cleared the previous detail and chart. At 390px, both forecast and analytics stayed within the viewport. Analytics reported six of seven assessable SKUs with a labeled partial subtotal and unknown total exposure. Forecast list buttons now use the existing card styling and retain visible keyboard focus, without native gray button borders or default list indentation.

Deployment identifiers and the production build result are recorded after rollout. Live merchant notification destinations and outreach cohorts are not changed by this release.

Production rollout: commit `56ac2b8`, Vercel `dpl_4uZ8WdPquMMbX4ufpU4ZJasXEhGf` READY and Railway `9672f33c-0d7d-41dd-ab1d-43efc04e4b4d` SUCCESS, both from the same immutable snapshot. Production build, health, additive forecast/coverage schemas and bounded horizon contracts passed verification; retained release evidence is `5487`. The live sample forecast kept its charts, sample disclosure and 390px layout. Business inbox monitoring remained verified with a successful zero-new-reply check; the worker was running and unpaused with 13/20 rolling first contacts and no unresolved sends.
