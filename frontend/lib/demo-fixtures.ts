import {
  DEMO_ALERT_CHANNELS,
  DEMO_ALERT_EVENTS,
  DEMO_ALERT_RULES,
  DEMO_BUYING_CALENDAR,
  DEMO_BUNDLES,
  DEMO_DASHBOARD,
  DEMO_FORECASTS,
  DEMO_INVENTORY_HEALTH,
  DEMO_LIQUIDATION,
  DEMO_PURCHASE_ORDERS,
  DEMO_REORDER,
  DEMO_SCORECARDS,
  DEMO_SUPPLIERS,
  DEMO_TRANSFERS,
} from "@/lib/demo-data";

// Map API paths to their demo fixtures.
// Keys are path prefixes (longest match wins).
const DEMO_FIXTURES: Record<string, unknown> = {
  "/dashboard": DEMO_DASHBOARD,
  "/analytics/inventory-health": DEMO_INVENTORY_HEALTH,
  "/forecast": DEMO_FORECASTS,
  "/analytics/scorecards": DEMO_SCORECARDS,
  "/reorder/purchase-orders": DEMO_PURCHASE_ORDERS,
  "/reorder/buying-calendar": DEMO_BUYING_CALENDAR,
  "/reorder": DEMO_REORDER,
  "/suppliers": DEMO_SUPPLIERS,
  "/bundles": DEMO_BUNDLES,
  "/transfers": DEMO_TRANSFERS,
  "/liquidation": DEMO_LIQUIDATION,
  "/reports/schedules": { schedules: [] },
  "/audit/events": { events: [] },
  "/alerts/rules": DEMO_ALERT_RULES,
  "/alerts/events": DEMO_ALERT_EVENTS,
  "/alerts/channels": DEMO_ALERT_CHANNELS,
};

export function getDemoFixture<T>(path: string): T {
  // Strip query string for matching
  const bare = path.split("?")[0];
  // Longest matching prefix wins
  const key = Object.keys(DEMO_FIXTURES)
    .filter((k) => bare === k || bare.startsWith(k + "/") || bare.startsWith(k + "?"))
    .sort((a, b) => b.length - a.length)[0];
  if (key) return DEMO_FIXTURES[key] as T;
  // Fallback: return an empty shell so pages don't crash
  return {} as T;
}
