import type { Entitlements } from "./entitlements";

export type AccountConnection = { connected: boolean; shopify_domain: string | null; last_sync_at: string | null };

export function readAccountConnection(body: unknown): AccountConnection {
  if (!body || typeof body !== "object" || !("connected" in body) || typeof body.connected !== "boolean") {
    throw new Error("Shopify connection status could not be confirmed.");
  }
  const record = body as Record<string, unknown>;
  if (record.connected && (typeof record.shopify_domain !== "string" || !record.shopify_domain)) {
    throw new Error("Shopify connection details could not be confirmed.");
  }
  return { connected: body.connected, shopify_domain: typeof record.shopify_domain === "string" ? record.shopify_domain : null,
    last_sync_at: typeof record.last_sync_at === "string" ? record.last_sync_at : null };
}

export function accountPlanConfirmed(plan: Entitlements | null): boolean {
  return Boolean(plan?.billing_status_loaded && !plan.billing_status_error && typeof plan.plan_name === "string" && typeof plan.subscription_status === "string");
}
