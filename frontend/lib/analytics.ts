"use client";

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
}
