# Shopify review 116756: billing after reinstall

Status: source repair verified locally; deployment and actual Shopify lifecycle verification pending. Do not mark requirement 1.2.2 resolved or submit fixes yet.

## Reviewer evidence and cause

The owner's October 14 screenshots show requirement 1.2.2, "Implement Shopify App Pricing or the Shopify Billing API correctly." After reinstall, Plan and billing displayed "Could not load billing" and "Your plan could not be checked. Please try again," without a usable way to request approval again.

Production Railway logs for October 14, 14:00–16:00 UTC contain repeated Shopify 401 invalid-access-token responses while `/billing/entitlements?fresh=1` returned HTTP 200 with a billing error. A successful subscription-creation request appears earlier in the same window. These logs support the revoked-token failure, but do not independently establish the reviewer's exact uninstall timing.

Two defects reproduced in tests:

1. A stored offline grant with future expiry can already be revoked after uninstall. When reinstall precedes the uninstall webhook, authentication reused that grant and the billing lookup failed.
2. The frontend entitlement helper threw away structured billing recovery metadata. The generic error screen returned before the existing reconnect control could render.

## Repair

- A rejected billing lookup can exchange the current, verified Shopify session token for a new offline grant, restricted to the same shop. Recovery uses the existing connection lock and reuses another request's replacement grant. It also handles an uninstall webhook clearing the grant during recovery.
- A recovered grant advances the installation timestamp so an older delayed uninstall cannot revoke the new installation. Normal refresh retains the original timestamp.
- Only the billing read is retried, once. Subscription creation is never automatically replayed after an uncertain response.
- Failed billing lookups are not cached. The billing page separately reads recovery metadata; shared feature entitlements continue to reject unverified billing state.
- Billing errors show Retry billing check and, when a Shopify store context exists, Reconnect Shopify. Stale paid-plan state is not displayed as verified. After a successful check, an inactive or declined plan can request approval normally.

No schema migration, price, trial, offer, acquisition policy, or pricing-mode change.

## Completed verification

54 focused automated tests passed:

- Backend billing reinstall: 7; installation/authentication: 14; privacy/uninstall ordering: 10.
- Frontend billing recovery, entitlement cache, embedded Shopify, billing view: 23.
- Frontend typecheck and production build passed.
- Existing subscription lookup and creation GraphQL operations validated against Admin API 2026-04.
- Public production `/billing` and API `/health` returned HTTP 200. These are availability checks of the existing deployment, not proof that this repair is deployed.

The new route-level tests use real FastAPI authentication, database services, signed test session tokens, and a stateful simulated Shopify boundary. They reproduce a previously approved plan, reinstall before the uninstall webhook, inactive billing after recovery, declined approval, a second approval request, and an approved plan. Separate tests cover wrong-shop rejection, failed recovery without cached errors, no infinite recovery loop, overlapping recovery, delayed uninstall during recovery, and no automatic charge replay.

These tests do not prove actual Shopify acceptance, browser redirects, or a completed live charge lifecycle.

## Required live evidence before resolution

Use the owner's development store only, independently verify `partnerDevelopment` and that Shopify explicitly identifies the approval as a test charge. Keep this separate from customers, revenue, and growth activation.

1. Deploy the exact tested current-source release to the verified Skubase frontend and backend targets.
2. Open the embedded app from Shopify Admin. Verify Plan and billing loads and all published plan prices/trials match the approval page.
3. Request a test plan, decline it, return to billing, and request approval again. Verify no paid entitlement is granted after decline.
4. Approve the test subscription. Verify the return flow, fresh Shopify `activeSubscriptions`, matching plan, and allowed features.
5. Uninstall and reinstall the development-store app. Verify workspace continuity, billing loads, the cancelled subscription is not treated as active, and a fresh approval can be requested and completed.
6. Verify a test plan change and reload. Retain the final subscription state and check for unauthorized billing responses.
7. Record a continuous walkthrough showing the reinstall, billing page, decline/retry and approval outcome. Supply this as proof only after all steps pass.

No real paid charge was approved, app uninstalled, or review resolution submitted during this repair.

## Access blockers at handoff

Shopify Partners in the Work Chrome window is at `accounts.shopify.com`, "Continue to Partners." The owner must sign in before the live store test.

The saved Vercel link is project `prj_vUAxpfJd3IiQ84ygFnrwZzUeDqgq` (`project-jkmic`), team `team_eeUaZfAaesP3pRNofCkAxcvt`. The connector returns project-not-found, and its team listing contains only Leadforge and IntelliCart. The CLI has no credentials and opened a Vercel sign-in flow; that waiting command was cancelled. Do not relink to either unrelated project or deploy to an unverified target. The owner must restore access to the account/team that owns Skubase.

Railway's existing production service is identifiable and healthy. No partial backend-only deployment was made while frontend target verification is blocked. No deployment settings or secrets were changed.

## References

- https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens
- https://shopify.dev/docs/apps/build/authentication-authorization/implement-token-exchange
- https://shopify.dev/docs/api/admin-graphql/2026-04/queries/currentAppInstallation
