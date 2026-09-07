"use client";

import { API_BASE_URL } from "@/lib/api-base";
import { authenticatedFetch, isDemoActive } from "@/lib/shopify-embedded";

type AnalyticsProperties = Record<string, string | number | boolean | null | undefined>;

type AnalyticsWindow = Window & {
  va?: (eventName: string, properties?: AnalyticsProperties) => void;
  gtag?: (...args: unknown[]) => void;
};

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
    if (typeof window === "undefined" || isDemoActive() || navigator.doNotTrack === "1") return;
    const key = "skubase-growth-attribution-v1";
    const previous = JSON.parse(localStorage.getItem(key) || "null") as {
      visitor_id: string; at: number; landing_page: string; attribution: Record<string, string>;
    } | null;
    const query = new URLSearchParams(window.location.search);
    const attribution: Record<string, string> = {};
    for (const field of ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]) {
      const value = query.get(field);
      if (value) attribution[field] = value.slice(0, 120);
    }
    // Store only referrer origin: queries may contain tokens or personal information.
    if (document.referrer) attribution.referrer = new URL(document.referrer).origin;
    const state = previous && Date.now() - previous.at < 30 * 86400000 ? previous : {
      visitor_id: crypto.randomUUID(), at: Date.now(), landing_page: location.pathname, attribution,
    };
    // Explicit campaign links update attribution while preserving the visitor identity.
    if (attribution.utm_campaign) state.attribution = attribution;
    localStorage.setItem(key, JSON.stringify(state));
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
