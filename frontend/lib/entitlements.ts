"use client";

import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
import type { CapabilityKey, PlanId } from "@/lib/plans";
import { authenticatedFetch } from "@/lib/shopify-embedded";

const API_BASE = APP_API_BASE_URL;

export type Entitlements = {
  billing_provider: "shopify_managed_pricing" | "stripe" | "none";
  is_shopify_installed: boolean;
  plan_id: PlanId;
  plan_name: string;
  raw_plan: string;
  subscription_status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
  billing_status_loaded: boolean;
  capabilities: CapabilityKey[];
  shopify_domain?: string | null;
  shopify_manage_url?: string | null;
  stripe_configured?: boolean;
  // "shopify_unauthorized" => stored token is stale; prompt re-authorization.
  billing_status_error?: string | null;
};

// Entitlements are fetched by the app shell, gated-feature cards, and several
// pages on every navigation. Share one request and reuse the result briefly so
// a single page view doesn't fan out into 2-3 identical API calls.
const ENTITLEMENTS_TTL_MS = 60_000;
let cachedEntitlements: { at: number; value: Entitlements } | null = null;
let inflight: Promise<Entitlements> | null = null;

export function invalidateEntitlementsCache(): void {
  cachedEntitlements = null;
  inflight = null;
}

async function requestEntitlements(fresh: boolean): Promise<Entitlements> {
  const url = `${API_BASE}/billing/entitlements${fresh ? "?fresh=1" : ""}`;
  const response = await authenticatedFetch(url, { credentials: "include" });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) {
    throw new Error(body?.detail || `Entitlements failed with status ${response.status}.`);
  }
  return body as Entitlements;
}

export async function fetchEntitlements(options?: { fresh?: boolean }): Promise<Entitlements> {
  const fresh = Boolean(options?.fresh);
  if (!fresh) {
    if (cachedEntitlements && Date.now() - cachedEntitlements.at < ENTITLEMENTS_TTL_MS) {
      return cachedEntitlements.value;
    }
    if (inflight) return inflight;
  }
  inflight = requestEntitlements(fresh)
    .then((value) => {
      cachedEntitlements = { at: Date.now(), value };
      return value;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function entitlementHas(
  entitlements: Entitlements | null,
  capability: CapabilityKey,
): boolean {
  return Boolean(entitlements?.capabilities.includes(capability));
}
