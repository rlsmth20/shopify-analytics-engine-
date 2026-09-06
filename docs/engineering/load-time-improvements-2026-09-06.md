# SKUbase load-time improvements — September 6, 2026

The dashboard repeatedly scanned the entire SKU list twice for every cash-risk
action. A lookup built once now resolves each action's vendor. This preserves
the original first-match behavior for duplicate SKU IDs and the unknown-vendor
fallback while making that aggregation linear in catalog size.

On a synthetic 5,000-SKU fixture, dashboard computation changed from 1.266 seconds
to 0.316 seconds (about 75% less time). The complete response content matched
after excluding its generated timestamp. This measures local computation only;
it is not an end-to-end production page-load claim.

Settings and supplier/category lead-time queries now filter to the authenticated
store instead of loading every store's records and selecting one afterward.
Dashboard, action queue, reorder planning, chat, reports, and notifications use
the scoped queries. Batch jobs retain the explicit all-store behavior.

The frontend pass replaces internal full-document links on dashboard, suppliers,
bundles, reports, and transfers with Next.js navigation. Moving between those
pages keeps the shared app shell and its authentication/bootstrap state mounted.
External navigation, downloads, and billing approval retain their own behavior.

Four backend regressions verify unchanged vendor totals, bounded catalog work,
three scoped settings queries, and unchanged batch results. All 61 backend tests
pass. Frontend type checking and the production build also pass.

An isolated browser against the local production build verified Dashboard's
"Open action queue" and Reports' dynamic "View suppliers" links. Across both
navigations, `performance.timeOrigin` stayed unchanged, the document navigation
entry count stayed at one, and the browser error log was empty. The demo route
did not repeat `/auth/me` during navigation. This demonstrates retained browser
and app state; an authenticated Shopify production timing remains to be measured.

Remaining measurement targets include Shopify token delivery, database latency
during authentication, and concurrent subscription-status lookups. This release
does not cache merchant analytics or alter authentication or billing rules.
