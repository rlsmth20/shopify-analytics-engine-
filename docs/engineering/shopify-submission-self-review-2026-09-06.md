# Shopify submission self-review — September 6, 2026

App: SKUbase. Paused review reference: 116756.

Evaluated the live [Shopify code-review requirements](https://shopify.dev/docs/apps/launch/app-store-review/app-store-ai-self-review-requirements), fetched on September 6, 2026. Each applicable requirement was evaluated separately against current configuration, frontend, backend, and available production evidence.

## Summary

- Likely passing: **27**
- Likely failing: **0** after the repairs in this release
- Needs review: **4**
- Groups skipped: **10**

This is the subset Shopify identifies as checkable from source code. It is not Shopify approval; additional listing, browser, billing, and operational requirements are evaluated during submission.

## Needs review

**1.1.4 — Factual information.** Catalog and sales data are tenant-scoped; missing history now produces explicit monitoring instead of invented liquidation figures. Unsupported popularity and setup claims were removed, and annual price equivalents corrected. The hosted App Store listing still needs comparison with the final product. Existing valuation uses a cost fallback when cost is unavailable and money displays assume USD; do not present estimated valuations as audited profit or promise fully supported multi-currency analytics.

**1.2.1 — Shopify billing.** New subscriptions use `appSubscriptionCreate`; the retired Stripe checkout routes through Shopify for connected stores, and Stripe portal access is blocked for connected stores. Legacy Stripe servicing remains in the code. Confirm that no listed Shopify merchant is actually being billed externally and that listing prices match Shopify's plans.

**1.2.2 — Charge approval, decline, and reinstall.** Code delegates approval to Shopify and queries active subscriptions; uninstall now revokes the local billing mirror. The live reinstall reached the dashboard, but a complete new charge approval/decline/reapproval cycle has not yet been recorded. A Shopify development-store charge must remain a test charge.

**1.2.3 — Plan changes.** In-app upgrade/downgrade controls and Shopify subscription replacement are implemented. Confirm the completed switch in Shopify's charge history before representing the full billing lifecycle as verified.

## Skipped groups

| Group | Reason |
| --- | --- |
| 5.1 Online store | No theme extension configuration. |
| 5.2 Payment | No payment extension or `write_payment_gateway` scope. |
| 5.3 Payment facilitator | Opt-in review not requested. |
| 5.4 Purchase option | No customer payment-method, subscription-contract, or payment-mandate scopes. App subscription billing is distinct from buyer purchase options. |
| 5.5 Product sourcing | Opt-in review not requested. |
| 5.6 Checkout customization | No checkout UI extension targets. |
| 5.7 Sales channel | No `channel_config` extension. |
| 5.8 Post purchase | No `checkout_post_purchase` extension. |
| 5.9 Mobile app builders | Opt-in review not requested. |
| 5.10 Donation | Opt-in review not requested. |

## Submission evidence and remaining browser work

The original 2.1.1 blocker is covered separately in [review 116756 verification](shopify-review-116756.md): the repaired embedded app passed live uninstall/reinstall and repeat catalog sync. The test store returned 17 products, 26 variants, 19 eligible planning variants, and seven exclusions. Its old orders were outside the 60-day window. A fresh paid development order still needs completion and first/repeat sync verification.

Privacy endpoints are registered in the app TOML using `compliance_topics`; current deployed configuration must also be checked in Shopify. Invalid signatures are rejected and customer/shop requests now perform actual scoped work. See [privacy webhook behavior](../shopify-privacy-webhooks.md).

Validation: 61 backend tests and 25 frontend tests pass; type checking and production build pass. Five billing tests prove that absent Stripe configuration cannot bypass webhook signatures or activate a subscription. Four performance tests protect equivalent dashboard results and scoped settings queries. The production privacy list and individual export endpoints both reject anonymous access with HTTP 401. Both frontend and backend deployment statuses for the billing security commit `ebc892a` succeeded. The user's signed-in Chrome submission tab was reached and automated checks restarted; completion and final submission remain unverified after Computer Use stopped because the current browser URL could not be determined confidently.

## Resources

- [Submitting an app for review](https://shopify.dev/docs/apps/launch/app-store-review/submit-app-for-review)
- [Shopify privacy compliance](https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance)
- [Shopify app billing](https://shopify.dev/docs/apps/launch/billing)
