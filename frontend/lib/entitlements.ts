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
};

export async function fetchEntitlements(): Promise<Entitlements> {
  const response = await authenticatedFetch(`${API_BASE}/billing/entitlements`, {
    credentials: "include",
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) {
    throw new Error(body?.detail || `Entitlements failed with status ${response.status}.`);
  }
  return body as Entitlements;
}

export function entitlementHas(
  entitlements: Entitlements | null,
  capability: CapabilityKey,
): boolean {
  return Boolean(entitlements?.capabilities.includes(capability));
}
