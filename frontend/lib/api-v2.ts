// V2 API client for forecast, analytics, reorder, suppliers, bundles, transfers,
// liquidation, alerts, and dashboard endpoints.

import {
  DEMO_ALERT_CHANNELS,
  DEMO_ALERT_EVENTS,
  DEMO_ALERT_RULES,
  DEMO_BUNDLES,
  DEMO_DASHBOARD,
  DEMO_FORECASTS,
  DEMO_LIQUIDATION,
  DEMO_PURCHASE_ORDERS,
  DEMO_REORDER,
  DEMO_SCORECARDS,
  DEMO_SUPPLIERS,
  DEMO_TRANSFERS,
} from "@/lib/demo-data";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Demo-mode detection
// ---------------------------------------------------------------------------

function isDemo(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      sessionStorage.getItem("skubase_demo") === "1" ||
      new URLSearchParams(window.location.search).get("demo") === "1"
    );
  } catch {
    return false;
  }
}

// Map API paths to their demo fixtures.
// Keys are path prefixes (longest match wins).
const DEMO_FIXTURES: Record<string, unknown> = {
  "/dashboard": DEMO_DASHBOARD,
  "/forecast": DEMO_FORECASTS,
  "/analytics/scorecards": DEMO_SCORECARDS,
  "/reorder/purchase-orders": DEMO_PURCHASE_ORDERS,
  "/reorder": DEMO_REORDER,
  "/suppliers": DEMO_SUPPLIERS,
  "/bundles": DEMO_BUNDLES,
  "/transfers": DEMO_TRANSFERS,
  "/liquidation": DEMO_LIQUIDATION,
  "/alerts/rules": DEMO_ALERT_RULES,
  "/alerts/events": DEMO_ALERT_EVENTS,
  "/alerts/channels": DEMO_ALERT_CHANNELS,
};

function getDemoFixture<T>(path: string): T {
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TrendDirection = "rising" | "steady" | "declining" | "volatile";
export type SeasonalityPattern =
  | "weekend_heavy"
  | "weekday_heavy"
  | "flat"
  | "unknown";
export type AbcClass = "A" | "B" | "C";
export type XyzClass = "X" | "Y" | "Z";
export type NotificationChannel = "email" | "sms" | "slack" | "webhook";
export type AlertSeverity = "info" | "warning" | "critical";
export type AlertTrigger =
  | "stockout_risk"
  | "dead_stock"
  | "overstock"
  | "forecast_miss"
  | "supplier_slip"
  | "bundle_break"
  | "price_drop";
export type SupplierTier = "preferred" | "acceptable" | "at_risk";

export type ForecastPoint = {
  day_offset: number;
  expected_units: number;
  lower_bound: number;
  upper_bound: number;
};

export type ForecastResult = {
  sku_id: string;
  horizon_days: number;
  method: string;
  trend: TrendDirection;
  seasonality: SeasonalityPattern;
  weekly_index: number[];
  confidence: "high" | "medium" | "low";
  projected_30_day_demand: number;
  projected_60_day_demand: number;
  projected_90_day_demand: number;
  stockout_probability_30d: number;
  points: ForecastPoint[];
  explain: string;
};

export type SkuScorecard = {
  sku_id: string;
  name: string;
  vendor: string;
  category: string;
  abc_class: AbcClass;
  xyz_class: XyzClass;
  contribution_pct: number;
  variability_cv: number;
  avg_daily_units: number;
  avg_daily_revenue: number;
  profit_per_unit: number;
  sell_through_30d: number;
  inventory_on_hand: number;
  classification_note: string;
};

export type ReorderSuggestion = {
  sku_id: string;
  name: string;
  vendor: string;
  current_on_hand: number;
  reorder_point: number;
  safety_stock: number;
  order_up_to: number;
  recommended_order_qty: number;
  economic_order_qty: number;
  service_level_target: number;
  expected_stockout_prob: number;
  unit_cost: number;
  extended_cost: number;
  lead_time_days: number;
  rationale: string;
};

export type ReorderFeed = {
  service_level: number;
  suggestions: ReorderSuggestion[];
  total_extended_cost: number;
  vendor_totals: Record<string, number>;
};

export type SupplierScorecard = {
  vendor: string;
  sku_count: number;
  on_time_pct: number;
  fill_rate_pct: number;
  avg_lead_time_days: number;
  lead_time_variance_days: number;
  cost_stability_score: number;
  overall_score: number;
  tier: SupplierTier;
  notes: string[];
};

export type BundleHealth = {
  bundle_sku_id: string;
  bundle_name: string;
  max_bundles_sellable: number;
  limiting_component_sku_id: string;
  limiting_component_name: string;
  component_status: string[];
  total_component_value_at_risk: number;
  recommended_action: string;
};

export type TransferRecommendation = {
  sku_id: string;
  name: string;
  from_location: string;
  to_location: string;
  qty: number;
  from_days_of_cover_before: number;
  to_days_of_cover_before: number;
  from_days_of_cover_after: number;
  to_days_of_cover_after: number;
  rationale: string;
};

export type LiquidationSuggestion = {
  sku_id: string;
  name: string;
  on_hand: number;
  days_since_last_sale: number;
  capital_tied_up: number;
  suggested_markdown_pct: number;
  suggested_price: number;
  projected_recovered_capital: number;
  tactic: "markdown" | "bundle" | "wholesale" | "donate_write_off";
  rationale: string;
};

export type PurchaseOrderLine = {
  sku_id: string;
  name: string;
  qty: number;
  unit_cost: number;
  extended_cost: number;
};

export type PurchaseOrderDraft = {
  po_id: string;
  vendor: string;
  created_at: string;
  status: "draft" | "ready" | "sent" | "received" | "cancelled";
  lines: PurchaseOrderLine[];
  total_cost: number;
  expected_arrival_date: string;
  rationale: string;
};

export type AlertRule = {
  id: string;
  name: string;
  trigger: AlertTrigger;
  severity: AlertSeverity;
  channels: NotificationChannel[];
  threshold: number;
  enabled: boolean;
  created_at: string;
  last_fired_at: string | null;
};

export type AlertEvent = {
  id: string;
  rule_id: string;
  rule_name: string;
  severity: AlertSeverity;
  trigger: AlertTrigger;
  sku_id: string | null;
  sku_name: string | null;
  message: string;
  fired_at: string;
  channels_sent: NotificationChannel[];
  delivered: boolean;
};

export type NotificationChannelConfig = {
  channel: NotificationChannel;
  enabled: boolean;
  target: string;
  verified: boolean;
};

export type DashboardKpi = {
  label: string;
  value: number;
  unit: "currency" | "count" | "percent" | "days";
  delta_pct: number | null;
  tone: "positive" | "negative" | "neutral";
};

export type DashboardSeriesPoint = {
  label: string;
  value: number;
};

export type DashboardResponse = {
  kpis: DashboardKpi[];
  revenue_trend_30d: DashboardSeriesPoint[];
  stock_health_breakdown: DashboardSeriesPoint[];
  top_movers: DashboardSeriesPoint[];
  abc_distribution: DashboardSeriesPoint[];
  cash_at_risk_by_vendor: DashboardSeriesPoint[];
  forecast_vs_actual_7d: DashboardSeriesPoint[];
  alert_counts_by_severity: DashboardSeriesPoint[];
  generated_at: string;
};

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  if (isDemo()) return getDemoFixture<T>(path);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "include",
    signal,
  });
  if (response.status === 402) {
    // Trial expired or no active subscription — send to pricing.
    if (typeof window !== "undefined") {
      window.location.href = "/pricing?trial_expired=1";
    }
    throw new Error("Trial expired. Redirecting to pricing.");
  }
  if (!response.ok) {
    throw new Error(
      `${path} failed with ${response.status}: ${await response
        .text()
        .catch(() => "")}`
    );
  }
  return (await response.json()) as T;
}

async function postJson<T>(
  path: string,
  payload: unknown,
  signal?: AbortSignal
): Promise<T> {
  if (isDemo()) return getDemoFixture<T>(path);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    credentials: "include",
    signal,
  });
  if (response.status === 402) {
    if (typeof window !== "undefined") {
      window.location.href = "/pricing?trial_expired=1";
    }
    throw new Error("Trial expired. Redirecting to pricing.");
  }
  if (!response.ok) {
    throw new Error(
      `${path} failed with ${response.status}: ${await response
        .text()
        .catch(() => "")}`
    );
  }
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const fetchDashboard = (signal?: AbortSignal) =>
  get<DashboardResponse>("/dashboard", signal);

export const fetchForecasts = (signal?: AbortSignal) =>
  get<{ forecasts: ForecastResult[] }>("/forecast", signal);

export const fetchForecastForSku = (skuId: string, signal?: AbortSignal) =>
  get<ForecastResult>(`/forecast/${encodeURIComponent(skuId)}`, signal);

export const fetchScorecards = (signal?: AbortSignal) =>
  get<{
    scorecards: SkuScorecard[];
    a_count: number;
    b_count: number;
    c_count: number;
    cutoff_a_pct: number;
    cutoff_b_pct: number;
  }>("/analytics/scorecards", signal);

export const fetchReorderSuggestions = (
  serviceLevel: number,
  signal?: AbortSignal
) => get<ReorderFeed>(`/reorder?service_level=${serviceLevel}`, signal);

export const fetchPurchaseOrders = (serviceLevel: number, signal?: AbortSignal) =>
  get<{ drafts: PurchaseOrderDraft[]; total_capital_required: number }>(
    `/reorder/purchase-orders?service_level=${serviceLevel}`,
    signal
  );

export const fetchSuppliers = (signal?: AbortSignal) =>
  get<{ vendors: SupplierScorecard[] }>("/suppliers", signal);

export const fetchBundles = (signal?: AbortSignal) =>
  get<{ bundles: BundleHealth[] }>("/bundles", signal);

export const fetchTransfers = (signal?: AbortSignal) =>
  get<{ transfers: TransferRecommendation[] }>("/transfers", signal);

export const fetchLiquidation = (signal?: AbortSignal) =>
  get<{
    total_capital_recoverable: number;
    suggestions: LiquidationSuggestion[];
  }>("/liquidation", signal);

export const fetchAlertRules = (signal?: AbortSignal) =>
  get<{ rules: AlertRule[] }>("/alerts/rules", signal);

export const fetchAlertEvents = (signal?: AbortSignal) =>
  get<{ events: AlertEvent[] }>("/alerts/events", signal);

export const fetchChannels = (signal?: AbortSignal) =>
  get<{ channels: NotificationChannelConfig[] }>("/alerts/channels", signal);

export const updateChannel = (
  payload: { channel: NotificationChannel; enabled: boolean; target: string },
  signal?: AbortSignal
) => postJson<NotificationChannelConfig>("/alerts/channels", payload, signal);

export const sendTestAlert = (
  payload: { channel: NotificationChannel; target: string },
  signal?: AbortSignal
) => postJson<{ delivered: boolean; error: string }>("/alerts/test