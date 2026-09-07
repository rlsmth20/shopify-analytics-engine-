import type { Entitlements } from "./entitlements";

type BillingState = Pick<Entitlements,
  "billing_provider" | "is_shopify_installed" | "stripe_configured" | "subscription_status"
>;

// This controls presentation only; the portal endpoint verifies the authenticated
// customer's stored Stripe identity and rejects Shopify-connected stores.
export function getStripePortalAction(sub: BillingState): "manage" | "update_payment" | null {
  if (sub.is_shopify_installed || sub.billing_provider !== "stripe" || sub.stripe_configured !== true) return null;
  if (sub.subscription_status === "past_due" || sub.subscription_status === "unpaid") return "update_payment";
  if (sub.subscription_status === "active" || sub.subscription_status === "trialing") return "manage";
  return null;
}
