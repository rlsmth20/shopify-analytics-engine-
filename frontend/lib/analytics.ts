"use client";

import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch, isDemoActive } from "@/lib/shopify-embedded";

type AnalyticsProperties = Record<string, string | number | boolean | null | undefined>;

type AnalyticsWindow = Window & {
  va?: (eventName: string, properties?: AnalyticsProperties) => void;
  gtag?: (...args: unknown[]) => void;
};

const ATTRIBUTION_KEY = "skubase-growth-attribution-v1";
const UTM_FIELDS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;
type GrowthState = {
  visitor_id: string; at: number; landing_page: string; attribution: Record<string, string>;
};

function storedGrowthState(): GrowthState | null {
  try {
    const value = JSON.parse(localStorage.getItem(ATTRIBUTION_KEY) || "null") as Partial<GrowthState> | null;
    if (!value || typeof value.visitor_id !== "string" || !/^[a-f0-9-]{32,36}$/.test(value.visitor_id) ||
        typeof value.at !== "number" || !Number.isFinite(value.at) || value.at > Date.now() ||
        Date.now() - value.at >= 30 * 86400000 || typeof value.landing_page !== "string" ||
        !value.landing_page.startsWith("/") || !value.attribution || typeof value.attribution !== "object") return null;
    const attribution: Record<string, string> = {};
    for (const field of UTM_FIELDS) {
      const entry = value.attribution[field];
      if (typeof entry === "string" && entry) attribution[field] = entry.slice(0, 120);
    }
    if (typeof value.attribution.referrer === "string") {
      try { attribution.referrer = new URL(value.attribution.referrer).origin; } catch { /* Ignore malformed referrers. */ }
    }
    return { visitor_id: value.visitor_id, at: value.at,
      landing_page: value.landing_page.split(/[?#]/, 1)[0].slice(0, 200), attribution };
  } catch {
    return null;
  }
}

function currentGrowthAttribution(): Record<string, string> {
  const attribution: Record<string, string> = {};
  const query = new URLSearchParams(window.location.search);
  for (const field of UTM_FIELDS) {
    const value = query.get(field);
    if (value) attribution[field] = value.slice(0, 120);
  }
  // Store only referrer origin: queries may contain tokens or personal information.
  if (document.referrer) {
    try { attribution.referrer = new URL(document.referrer).origin; } catch { /* Ignore malformed referrers. */ }
  }
  return attribution;
}

function growthTrackingAllowed(): boolean {
  return typeof window !== "undefined" && !isDemoActive() && navigator.doNotTrack !== "1";
}

/** Campaign fields for an explicit form submission, without visitor IDs or referrer data. */
export function getGrowthAttribution(): Record<string, string> {
  if (!growthTrackingAllowed()) return {};
  const current = currentGrowthAttribution();
  // A new explicit campaign replaces the old cohort instead of mixing its fields.
  const attribution = UTM_FIELDS.some((field) => current[field]) ? current : storedGrowthState()?.attribution ?? {};
  return Object.fromEntries(UTM_FIELDS.flatMap((field) => attribution[field] ? [[field, attribution[field]]] : []));
}

export function trackEvent(eventName: string, properties: AnalyticsProperties = {}): void {
  if (typeof window === "undefined") return;
  const analyticsWindow = window as AnalyticsWindow;

  try {
    analyticsWindow.va?.(eventName, properties);
    analyticsWindow.gtag?.("event", eventName, properties);
  } catch {
    // Analytics must never break conversion paths.
  }
  void trackGrowthEvent(eventName);
}

export async function trackGrowthEvent(name: string): Promise<void> {
  try {
    if (!growthTrackingAllowed()) return;
    const previous = storedGrowthState();
    const attribution = currentGrowthAttribution();
    const state = previous ?? {
      visitor_id: crypto.randomUUID(), at: Date.now(), landing_page: location.pathname, attribution,
    };
    // Explicit campaign links update attribution while preserving the visitor identity.
    if (UTM_FIELDS.some((field) => attribution[field])) state.attribution = attribution;
    localStorage.setItem(ATTRIBUTION_KEY, JSON.stringify(state));
    await authenticatedFetch(`${API_BASE_URL}/growth/events`, {
      method: "POST", credentials: "include", keepalive: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: crypto.randomUUID(), visitor_id: state.visitor_id, name,
        landing_page: name === "CALCULATOR_USED" ? location.pathname : state.landing_page, attribution: state.attribution }),
    });
  } catch {
    // Storage blocking, private browsing or telemetry failure must never block the app.
  }
}
