import { API_BASE_URL as APP_API_BASE_URL } from "@/lib/api-base";
// V2 API client for forecast, analytics, reorder, suppliers, bundles, transfers,
// liquidation, alerts, and dashboard endpoints.

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
import { authenticatedFetch, isDemoActive } from "@/lib/shopify-embedded";

const API_BASE_URL = APP_API_BASE_URL;

// ---------------------------------------------------------------------------
// Demo-mode detection
// ---------------------------------------------------------------------------

function isDemo(): boolean {
  return isDemoActive();
}

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
  history_days: number;
  adjusted_stockout_days: number;
  data_quality_warnings: string[];
  backtest_mae_14d: number | null;
  backtest_mape_14d: number | null;
  forecast_bias_14d: "over_forecast" | "under_forecast" | "balanced" | null;
  trust_reasons: string[];
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

export type InventoryHealthKpi = {
  label: string;
  value: number;
  unit: "currency" | "count" | "percent" | "days";
  tone: "positive" | "negative" | "neutral";
  note: string;
};

export type InventoryHealthBucket = {
  label: string;
  value: number;
  tone: "positive" | "negative" | "neutral";
};

export type InventoryHealthSku = {
  sku_id: string;
  name: string;
  vendor: string;
  value: number;
  note: string;
  severity: "critical" | "warning" | "info";
};

export type InventoryHealthInsight = {
  title: string;
  severity: "critical" | "warning" | "info";
  description: string;
  metric_label: string;
  metric_value: string;
};

export type InventoryHealthResponse = {
  kpis: InventoryHealthKpi[];
  health_buckets: InventoryHealthBucket[];
  forecast_confidence: InventoryHealthBucket[];
  top_cash_trapped: InventoryHealthSku[];
  top_stockout_risk: InventoryHealthSku[];
  insights: InventoryHealthInsight[];
  generated_at: string;
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
  order_cost: number;
  landed_extended_cost: number;
  landed_unit_cost: number;
  freight_share_pct: number;
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

export type BundleOpportunity = {
  id: string;
  product_a_id: number;
  product_a_name: string;
  product_a_sku: string | null;
  product_a_category: string | null;
  product_b_id: number;
  product_b_name: string;
  product_b_sku: string | null;
  product_b_category: string | null;
  co_purchase_count: number;
  support: number;
  confidence_a_to_b: number;
  confidence_b_to_a: number;
  lift: number | null;
  combined_revenue: number;
  average_order_value_impact: number | null;
  opportunity_type: "Bundle" | "Cross-sell" | "Promo test" | "Watch" | string;
  suggested_action: "Create bundle" | "Add cross-sell" | "Test promo" | "Watch" | string;
  explanation: string;
};

export type TransferRecommendation = {
  sku_id: string;
  name: string;
  from_location: string;
  to_location: string;
  qty: number;
  source_stock?: number;
  destination_stock?: number;
  destination_days_left?: number;
  lead_time_days?: number;
  priority?: "Critical" | "High" | "Medium" | "Low";
  status?: "Recommended" | "Reviewed" | "Exported";
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
  received_qty: number;
};

export type PurchaseOrderReceipt = {
  id: number | string;
  sku_id: string;
  ordered_qty: number;
  received_qty: number;
  ordered_unit_cost: number;
  received_unit_cost: number;
  expected_arrival_date: string;
  received_at: string;
  created_at: string;
};

export type PurchaseOrderDraft = {
  po_id: string;
  vendor: string;
  created_at: string;
  status: "draft" | "ready" | "approved" | "sent" | "partially_received" | "received" | "cancelled";
  source?: "recommended" | "saved";
  lines: PurchaseOrderLine[];
  subtotal_cost: number;
  shipping_cost: number;
  total_cost: number;
  expected_arrival_date: string;
  rationale: string;
  approved_at: string | null;
  approved_by_user_id: number | null;
  sent_at: string | null;
  received_at: string | null;
  receipts?: PurchaseOrderReceipt[];
};

export type BuyingCalendarLine = {
  sku_id: string;
  name: string;
  qty: number;
  unit_cost: number;
  extended_cost: number;
  current_on_hand: number | null;
  reorder_point: number | null;
  daily_velocity: number | null;
  lead_time_days: number | null;
};

export type BuyingCalendarEvent = {
  event_id: string;
  vendor: string;
  source: "recommended" | "saved";
  status: string;
  order_by_date: string;
  expected_arrival_date: string;
  days_until_order: number;
  lead_time_days: number;
  line_count: number;
  total_units: number;
  estimated_cost: number;
  urgency: "due_now" | "this_week" | "future" | "open";
  rationale: string;
  lines: BuyingCalendarLine[];
};

export type BuyingCalendarResponse = {
  generated_at: string;
  horizon_days: number;
  events: BuyingCalendarEvent[];
  total_estimated_cost: number;
  due_now_count: number;
  future_count: number;
  saved_open_count: number;
};

export type AuditLogEvent = {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ReportSchedule = {
  id: number;
  report_type: "actions" | "stockout" | "dead-stock" | "reorder";
  cadence: "weekly" | "monthly";
  channel: "email";
  recipient_email: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type AlertRule = {
  id: string;
  name: string;
  trigger: AlertTrigger;
  severity: AlertSeverity;
  channels: NotificationChannel[];
  threshold: number;
  scope: "storewide" | "custom";
  match_mode: "all" | "any";
  target_skus: string[];
  product_title_contains: string;
  categories: string[];
  suppliers: string[];
  tags: string[];
  collections: string[];
  locations: string[];
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
  const url = `${API_BASE_URL}${path}`;
  const response = await fetchWithNetworkContext(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "include",
      signal,
    },
    path
  );
  await handlePlanGate(response, path);
  if (!response.ok) {
    throw new Error(
      `${path} failed with ${response.status}: ${await response
        .text()
        .catch(() => "")}`
    );
  }
  return (await response.json()) as T;
}

// 402 = no active trial/subscription -> billing page. 403 = the plan does
// not include this feature; surface the message in place instead of falsely
// claiming the trial ended (GatedFeature renders the upgrade card).
async function handlePlanGate(response: Response, path: string): Promise<void> {
  if (response.status === 402) {
    if (typeof window !== "undefined") {
      window.location.href = "/billing?trial_expired=1";
    }
    throw new Error("Your trial has ended. Redirecting to billing.");
  }
  if (response.status === 403) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail || `Your current plan does not include this feature (${path}).`
    );
  }
}

async function postJson<T>(
  path: string,
  payload: unknown,
  signal?: AbortSignal
): Promise<T> {
  if (isDemo()) return getDemoFixture<T>(path);
  const url = `${API_BASE_URL}${path}`;
  const response = await fetchWithNetworkContext(
    url,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
      credentials: "include",
      signal,
    },
    path
  );
  await handlePlanGate(response, path);
  if (!response.ok) {
    throw new Error(
      `${path} failed with ${response.status}: ${await response
        .text()
        .catch(() => "")}`
    );
  }
  return (await response.json()) as T;
}

async function fetchWithNetworkContext(
  url: string,
  init: RequestInit,
  path: string
): Promise<Response> {
  try {
    return await authenticatedFetch(url, init);
  } catch (error) {
    if (
      error instanceof DOMException && error.name === "AbortError" ||
      error instanceof Error && error.name === "AbortError"
    ) {
      throw error;
    }
    const origin = typeof window !== "undefined" ? window.location.origin : "unknown origin";
    throw new Error(
      `Could not reach the Skubase API for ${path}. Browser origin: ${origin}. API URL: ${url}. ${
        error instanceof Error ? error.message : String(error)
      }`
    );
  }
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

export const fetchInventoryHealth = (signal?: AbortSignal) =>
  get<InventoryHealthResponse>("/analytics/inventory-health", signal);

export const fetchReorderSuggestions = (
  serviceLevel: number,
  shippingCostOrSignal: number | AbortSignal = 35,
  maybeSignal?: AbortSignal
) => {
  const shippingCost =
    typeof shippingCostOrSignal === "number" ? shippingCostOrSignal : 35;
  const signal =
    typeof shippingCostOrSignal === "number" ? maybeSignal : shippingCostOrSignal;
  return get<ReorderFeed>(
    `/reorder?service_level=${serviceLevel}&shipping_cost=${shippingCost}`,
    signal
  );
};

export const fetchPurchaseOrders = (
  serviceLevel: number,
  shippingCostOrSignal: number | AbortSignal = 35,
  maybeSignal?: AbortSignal
) => {
  const shippingCost =
    typeof shippingCostOrSignal === "number" ? shippingCostOrSignal : 35;
  const signal =
    typeof shippingCostOrSignal === "number" ? maybeSignal : shippingCostOrSignal;
  return get<{ drafts: PurchaseOrderDraft[]; total_capital_required: number }>(
    `/reorder/purchase-orders?service_level=${serviceLevel}&shipping_cost=${shippingCost}`,
    signal
  );
};

export const fetchBuyingCalendar = (
  serviceLevel: number,
  shippingCostOrSignal: number | AbortSignal = 35,
  horizonDaysOrSignal: number | AbortSignal = 180,
  maybeSignal?: AbortSignal
) => {
  const shippingCost =
    typeof shippingCostOrSignal === "number" ? shippingCostOrSignal : 35;
  const horizonDays =
    typeof horizonDaysOrSignal === "number" ? horizonDaysOrSignal : 180;
  const signal =
    typeof shippingCostOrSignal !== "number"
      ? shippingCostOrSignal
      : typeof horizonDaysOrSignal !== "number"
        ? horizonDaysOrSignal
        : maybeSignal;
  return get<BuyingCalendarResponse>(
    `/reorder/buying-calendar?service_level=${serviceLevel}&shipping_cost=${shippingCost}&horizon_days=${horizonDays}`,
    signal
  );
};

export const savePurchaseOrder = (draft: PurchaseOrderDraft, signal?: AbortSignal) =>
  postJson<{ po: PurchaseOrderDraft }>("/reorder/purchase-orders", { draft }, signal);

export const updatePurchaseOrderStatus = (
  poId: string,
  status: PurchaseOrderDraft["status"],
  signal?: AbortSignal,
) =>
  postJson<{ po: PurchaseOrderDraft }>(
    `/reorder/purchase-orders/${encodeURIComponent(poId)}/status?status=${status}`,
    {},
    signal,
  );

export const receivePurchaseOrder = (
  poId: string,
  payload: {
    lines: { sku_id: string; received_qty: number; received_unit_cost?: number | null }[];
    received_at?: string | null;
  },
  signal?: AbortSignal,
) =>
  postJson<{ po: PurchaseOrderDraft }>(
    `/reorder/purchase-orders/${encodeURIComponent(poId)}/receive`,
    payload,
    signal,
  );

export const fetchAuditEvents = (limit = 20, signal?: AbortSignal) =>
  get<{ events: AuditLogEvent[] }>(`/audit/events?limit=${limit}`, signal);

export const fetchReportSchedules = (signal?: AbortSignal) =>
  get<{ schedules: ReportSchedule[] }>("/reports/schedules", signal);

export const saveReportSchedule = (
  payload: Omit<ReportSchedule, "id" | "created_at" | "updated_at">,
  signal?: AbortSignal,
) => {
  if (isDemo()) {
    const now = new Date().toISOString();
    return Promise.resolve({
      id: 0,
      created_at: now,
      updated_at: now,
      ...payload,
    } satisfies ReportSchedule);
  }
  return postJson<ReportSchedule>("/reports/schedules", payload, signal);
};

export const fetchSuppliers = (signal?: AbortSignal) =>
  get<{ vendors: SupplierScorecard[] }>("/suppliers", signal);

export const fetchBundles = (signal?: AbortSignal) =>
  get<{ bundles: BundleHealth[]; opportunities?: BundleOpportunity[]; orders_analyzed?: number }>("/bundles", signal);

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
) => postJson<{ delivered: boolean; error: string }>("/alerts/test", payload, signal);

export const evaluateAlertsNow = (dryRun: boolean, signal?: AbortSignal) =>
  postJson<{ events: AlertEvent[] }>(
    `/alerts/evaluate?dry_run=${dryRun ? "true" : "false"}`,
    {},
    signal
  );

export const createAlertRule = (
  payload: {
    name: string;
    trigger: AlertTrigger;
    severity: AlertSeverity;
    channels: NotificationChannel[];
    threshold: number;
    scope?: "storewide" | "custom";
    match_mode?: "all" | "any";
    target_skus?: string[];
    product_title_contains?: string;
    categories?: string[];
    suppliers?: string[];
    tags?: string[];
    collections?: string[];
    locations?: string[];
    enabled: boolean;
  },
  signal?: AbortSignal
) => postJson<AlertRule>("/alerts/rules", payload, signal);

export const deleteAlertRule = async (
  ruleId: string,
  signal?: AbortSignal
): Promise<boolean> => {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/alerts/rules/${encodeURIComponent(ruleId)}`,
    { method: "DELETE", cache: "no-store", credentials: "include", signal }
  );
  return response.ok;
};

export const toggleAlertRule = async (
  ruleId: string,
  enabled: boolean,
  signal?: AbortSignal
): Promise<AlertRule> => {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/alerts/rules/${encodeURIComponent(
      ruleId
    )}/toggle?enabled=${enabled ? "true" : "false"}`,
    {
      method: "PATCH",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "include",
      signal,
    }
  );
  if (!response.ok) {
    throw new Error(`toggle failed with ${response.status}`);
  }
  return (await response.json()) as AlertRule;
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

export const currency = (n: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);

export const percent = (n: number, fractionDigits = 0) =>
  `${(n * 100).toFixed(fractionDigits)}%`;
