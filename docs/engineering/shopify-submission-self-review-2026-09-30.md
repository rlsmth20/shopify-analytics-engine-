# Shopify submission self-review, September 30, 2026

Live requirements fetched today using Shopify CLI `shopify doc fetch`; each base requirement evaluated separately. This is a subset check, not official approval. No backend/frontend source or deployment changed.

## Result

31 requirements checked: 28 likely passing, 0 likely failing, 3 needs review. Ten conditional groups skipped. The reported 1.2.1 pricing-mode mismatch is repaired and independently confirmed live. Listing/common-error checks show passed in Partner Dashboard.

## Remaining uncertainty

- 1.1.4: non-USD analytics formatting remains unverified; listing inaccuracies encountered today were corrected.
- 1.2.2: complete live accept/decline/reinstall charge cycle remains unverified; do not count the historical test approval screen as a completed charge.
- 1.2.3: completed live plan changes and charge-history entries remain unverified.

These are verification limits, not demonstrated new failures. The repaired 1.2.1 incident can be returned to Shopify review without claiming full certification.

## Independent requirement results

| Requirement | Assessment | Evidence |
| --- | --- | --- |
| 1.1.1 Use session tokens for authentication | Likely passing | App Bridge bearer session tokens; embedded fetch omits cookies. Auth and reinstall tests pass. |
| 1.1.2 Use Shopify checkout | Likely passing | No buyer checkout replacement or offsite order-payment flow found. |
| 1.1.3 Direct merchants to the Shopify Theme Store | Likely passing | No theme installation/download feature found. |
| 1.1.4 Use only factual information | Needs review | Listing claims corrected and saved: removed automatic restocking, expiry tracking, back-in-stock tags, real-time/instant guarantees and obsolete magic-link instructions. Existing non-USD reporting remains unverified. |
| 1.1.6 Build single-merchant storefronts. Marketplaces should be sales channels | Likely passing | Single-merchant shop/workspace model; no multi-seller marketplace found. |
| 1.1.7 Always build Payment Gateway apps using the Payments API and after obtaining authorization | Likely passing | App subscription billing only; no buyer payment gateway found. |
| 1.1.8 Build apps for Shopify POS only, not third-party systems | Likely passing | No third-party POS sync integration found; ShipStation source-channel labels are not a POS integration. |
| 1.1.9 Obtain explicit buyer consent before adding charges | Likely passing | No buyer cart charges or checkout extension found. |
| 1.1.10 Maintain the cheapest shipping option as default | Likely passing | No checkout shipping-option reordering found. |
| 1.1.13 Duplicate only authorized product information | Likely passing | Imports authorized connected-shop data; no arbitrary-store product copying feature found. |
| 1.1.14 Don't connect merchants to external agencies and developers | Likely passing | Own product support only; no freelancer/agency marketplace found. |
| 1.1.15 Process refunds only through the original payment processor | Likely passing | No buyer refund execution path found. Refunds must remain with original processor or permitted Shopify store-credit APIs. |
| 1.1.16 Don't provide capital lending | Likely passing | No capital lending feature found. |
| 1.2.1 Use Shopify App Pricing or the Shopify Billing API | Likely passing | Live Partner pricing says Manual pricing (legacy); App Pricing enabled is not started. Three plans match Billing API amounts and 14-day trials. Shopify checkout route uses appSubscriptionCreate; retired Stripe creation has no callers, and Shopify accounts cannot use legacy Stripe portal. |
| 1.2.2 Implement Shopify App Pricing or the Shopify Billing API correctly | Needs review | Billing API confirmation URL, fresh active-subscription reconciliation and reinstall paths present. Sept 16 evidence 127124 reached a test-charge approval page. Complete live approval/decline/reinstall billing cycle was not repeated or approved. |
| 1.2.3 Allow pricing plan changes | Needs review | In-app plan selection uses appSubscriptionCreate with APPLY_IMMEDIATELY. Completed live upgrade/downgrade and merchant charge-history verification remain unverified. |
| 2.2.1 Use Shopify APIs | Likely passing | OAuth, session-token exchange, inventory/product/order queries and billing use Shopify APIs. |
| 2.2.3 Use the latest version of Shopify App Bridge | Likely passing | Native synchronous app-bridge.js CDN script appears first in embedded document head; loader tests pass. |
| 2.2.4 Use the GraphQL Admin API | Likely passing | General Admin API calls found only at versioned graphql.json endpoints in shopify_sync.py and shopify_billing.py. |
| 2.2.6 Don't display promotions or advertisements in admin extensions | Likely passing | No admin UI block/action/link extensions found. |
| 2.2.7 Only launch Max modal with merchant interaction | Likely passing | No automatic Max modal/fullscreen launch found. |
| 2.3.1 Initiate installation from a Shopify-owned surface | Likely passing | Embedded context provides shop identity; installation routes consume Shopify context. Public health-check URL intake is lead intake and does not install or grant store access. |
| 2.3.2 Authenticate immediately after install | Likely passing | Managed installation exchanges signed session token; fallback install immediately redirects to OAuth with configured app credentials. |
| 2.3.3 Redirect to the app UI after installation | Likely passing | Validated callback exchanges code and redirects to embedded_admin_redirect_url. |
| 2.3.4 Require OAuth authentication immediately after reinstall | Likely passing | Existing connection is reused and grants rotate on reinstall; dedicated tests pass. |
| 3.1.1 Use a valid TLS/SSL certificate | Likely passing | Configured app, callback and API endpoints use HTTPS; existing production/browser evidence shows valid secure access. No HTTP production fallback found. |
| 3.2.1 Request read_all_orders access scope only if it provides necessary app functionality | Likely passing | read_all_orders absent from requested and optional scopes. |
| 3.2.2 Request write_payment_mandate scope only if it provides necessary app functionality | Likely passing | write_payment_mandate absent. |
| 3.2.3 Request write_checkout_extensions_apis scope only if it provides necessary app functionality | Likely passing | write_checkout_extensions_apis absent. |
| 3.2.4 Request read_advanced_dom_pixel_events scope only if it provides necessary app functionality | Likely passing | read_advanced_dom_pixel_events absent. |
| 3.2.5 Request read_checkout_extensions_chat scope only when required | Likely passing | read_checkout_extensions_chat absent. |

## Conditional groups

5.1 theme, 5.2 payment, 5.4 purchase options, 5.6 checkout, 5.7 sales channel and 5.8 post-purchase skipped because their extension/configuration/scope triggers are absent. 5.3 payment facilitator, 5.5 product sourcing, 5.9 mobile builder and 5.10 donation opt-in groups were not requested.

## Validation

24 backend installation/privacy tests and 15 frontend embedded-authentication/billing-view tests passed. No payment or subscription was approved. Preserve historical test evidence 127124 and incident evidence 127136.

Sources: [Live AI self-review requirements](https://shopify.dev/docs/apps/launch/app-store-review/app-store-ai-self-review-requirements), [full requirements](https://shopify.dev/docs/apps/launch/shopify-app-store/app-store-requirements), [manual pricing migration guidance](https://shopify.dev/docs/apps/launch/billing/shopify-app-pricing/migrating-to-shopify-app-pricing).
