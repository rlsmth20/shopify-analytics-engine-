"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ReportEmptyState,
  ReportFilters,
  ReportMetricCards,
  ReportSearchInput,
  ReportStatusBadge,
  ReportTable,
  ReportToolbar,
  type ReportColumn,
  type ReportFilterConfig,
  type ReportMetric,
} from "@/components/reports/report-components";
import { fetchInventoryActions, type InventoryAction } from "@/lib/api";
import { getActionImpactValue, statusLabel } from "@/lib/app-helpers";
import {
  currency,
  fetchForecasts,
  fetchReorderSuggestions,
  fetchScorecards,
  type ForecastResult,
  type ReorderSuggestion,
  type SkuScorecard,
} from "@/lib/api-v2";
import { exportReportRowsCsv, type CsvColumn } from "@/lib/report-export";

type ReportKind = "actions" | "stockout" | "dead-stock" | "reorder";
type SortDirection = "asc" | "desc";

type ReportRow = {
  id: string;
  product: string;
  sku: string;
  vendor: string;
  category: string;
  priority: number;
  actionType: string;
  currentStock: number | null;
  daysLeft: number | null;
  daysInventory: number | null;
  leadTime: number | null;
  recommendedQty: number | null;
  cashImpact: number | null;
  reason: string;
  recommendedAction: string;
  riskLevel: "Critical" | "High" | "Medium" | "Low";
  salesLast30: number | null;
  dailyVelocity: number | null;
  estimatedStockoutDate: string;
  inventoryValue: number | null;
  daysSinceLastSale: number | null;
  status: "Dead stock" | "Slow mover" | "Overstock" | "Reorder" | "Review";
  targetCoverage: number | null;
  estimatedCost: number | null;
  orderDeadline: string;
};

type LoadedData = {
  actions: InventoryAction[];
  forecasts: ForecastResult[];
  reorder: ReorderSuggestion[];
  scorecards: SkuScorecard[];
};

const reportCards = [
  {
    key: "actions" as const,
    title: "Inventory Action Report",
    category: "Action queue",
    description: "Urgent, optimize, and dead-stock actions with rationale and impact.",
    status: "Available",
    href: "/actions",
    cta: "Open action queue",
  },
  {
    key: "stockout" as const,
    title: "Stockout Risk Report",
    category: "Forecasting",
    description: "SKUs ranked by risk level, days left, lead time, and forecast demand.",
    status: "Available",
    href: "/forecast",
    cta: "Review forecasts",
  },
  {
    key: "reorder" as const,
    title: "Reorder Plan Report",
    category: "Replenishment",
    description: "Recommended reorder quantities, estimated cost, and vendor exposure.",
    status: "Available",
    href: "/purchase-orders",
    cta: "Open PO drafts",
  },
  {
    key: "dead-stock" as const,
    title: "Dead Stock / Overstock Report",
    category: "Cash recovery",
    description: "Stale, slow-moving, and over-covered SKUs tying up working capital.",
    status: "Available",
    href: "/liquidation",
    cta: "Open liquidation",
  },
  {
    title: "Inventory Health Snapshot",
    category: "Analytics",
    description: "Stockout revenue risk, cash trapped, forecast confidence, and health buckets.",
    status: "Available",
    href: "/analytics",
    cta: "Open analytics",
  },
  {
    title: "Supplier Scorecard",
    category: "Suppliers",
    description: "Requires PO receipt history with expected and received dates.",
    status: "Requires data",
    href: "/suppliers",
    cta: "View suppliers",
  },
  {
    title: "Sample Inventory Risk Snapshot",
    category: "Outbound sample",
    description: "Demo-only sample deliverable for cold-email prospects.",
    status: "Demo/sample",
    href: "/sample-inventory-risk-snapshot",
    cta: "View sample",
  },
  {
    title: "Scheduled Weekly Reports",
    category: "Automation",
    description: "Planned recurring email delivery. Not active yet.",
    status: "Coming soon",
    href: "/alerts",
    cta: "Configure alerts",
  },
] as const;

const reportMeta: Record<ReportKind, { title: string; description: string }> = {
  actions: {
    title: "Inventory Action Report",
    description:
      "A working table of the current action queue, enriched with vendor and category when scorecard data is available.",
  },
  stockout: {
    title: "Stockout Risk Report",
    description:
      "A forecast-first view of SKUs that may run out before lead time can recover them.",
  },
  "dead-stock": {
    title: "Dead Stock / Overstock Report",
    description:
      "Slow movers and stale inventory that may be tying up cash or needing a clearance plan.",
  },
  reorder: {
    title: "Reorder Plan Report",
    description:
      "Suggested replenishment quantities with vendor, lead-time, and estimated cost context.",
  },
};

export default function ReportsPage() {
  const [selectedReport, setSelectedReport] = useState<ReportKind>("actions");
  const [data, setData] = useState<LoadedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState("priority");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetchInventoryActions(controller.signal),
      fetchForecasts(controller.signal),
      fetchReorderSuggestions(0.95, controller.signal),
      fetchScorecards(controller.signal),
    ])
      .then(([actions, forecasts, reorder, scorecards]) => {
        setData({
          actions: actions.actions,
          forecasts: forecasts.forecasts,
          reorder: reorder.suggestions,
          scorecards: scorecards.scorecards,
        });
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    setSearch("");
    setFilters({});
    setSortKey("priority");
    setSortDirection("desc");
  }, [selectedReport]);

  const isDemo = isDemoMode();
  const rowsByReport = useMemo(() => buildReportRows(data), [data]);
  const rows = rowsByReport[selectedReport];
  const filterConfig = useMemo(
    () => buildFilterConfig(selectedReport, rows),
    [selectedReport, rows],
  );
  const columns = useMemo(() => buildColumns(selectedReport), [selectedReport]);
  const metrics = useMemo(
    () => buildMetrics(selectedReport, rows),
    [selectedReport, rows],
  );
  const visibleRows = useMemo(
    () => sortRows(filterRows(rows, selectedReport, search, filters), columns, sortKey, sortDirection),
    [rows, selectedReport, search, filters, columns, sortKey, sortDirection],
  );

  function updateSort(key: string) {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "product" ? "asc" : "desc");
  }

  function exportCsv() {
    exportReportRowsCsv({
      filename: `skubase-${selectedReport}-report-${new Date().toISOString().slice(0, 10)}.csv`,
      columns: buildCsvColumns(selectedReport),
      rows: visibleRows,
    });
  }

  return (
    <div className="reports-page page-stack">
      <section className="section-card">
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Report workspace</p>
            <h2 className="section-title section-title-small">
              Inventory reports, filters, and exports in one place
            </h2>
            <p className="muted section-copy">
              Skubase keeps reporting close to the workflow: use the preview below for
              filtering, then export the filtered rows.
            </p>
          </div>
          {isDemo ? <ReportStatusBadge tone="demo">Demo data</ReportStatusBadge> : null}
        </div>
      </section>

      <section className="reports-grid">
        {reportCards.map((report) => (
          <article
            key={report.title}
            className={`report-card${"key" in report && report.key === selectedReport ? " report-card-selected" : ""}`}
          >
            <div className="report-card-head">
              <div>
                <p className="section-eyebrow">{report.category}</p>
                <h3>{report.title}</h3>
              </div>
              <span className={`report-status report-status-${statusClass(report.status)}`}>
                {report.status}
              </span>
            </div>
            <p className="report-copy">{report.description}</p>
            {"key" in report ? (
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setSelectedReport(report.key)}
              >
                Preview report
              </button>
            ) : (
              <a
                className={`button ${report.status === "Coming soon" ? "button-ghost" : "button-secondary"}`}
                href={report.href}
              >
                {report.cta}
              </a>
            )}
          </article>
        ))}
      </section>

      <section className="report-workspace section-card">
        <ReportToolbar
          title={reportMeta[selectedReport].title}
          description={reportMeta[selectedReport].description}
          badge={isDemo ? <ReportStatusBadge tone="demo">Demo data</ReportStatusBadge> : undefined}
          actions={
            <button
              type="button"
              className="button button-primary"
              onClick={exportCsv}
              disabled={visibleRows.length === 0}
            >
              Export filtered CSV
            </button>
          }
        />

        {error ? (
          <ReportEmptyState
            title="Report data unavailable"
            description={error}
            actions={<a className="button button-secondary" href="/store-sync">Check store sync</a>}
          />
        ) : (
          <>
            <ReportMetricCards metrics={metrics} />
            <div className="report-control-panel">
              <ReportSearchInput value={search} onChange={setSearch} />
              <ReportFilters
                filters={filterConfig}
                values={filters}
                onChange={(key, value) =>
                  setFilters((current) => ({ ...current, [key]: value }))
                }
                onReset={() => {
                  setFilters({});
                  setSearch("");
                }}
              />
            </div>
            <ReportTable
              columns={columns}
              rows={visibleRows}
              rowKey={(row) => `${selectedReport}-${row.id}`}
              sortKey={sortKey}
              sortDirection={sortDirection}
              onSort={updateSort}
              loading={loading}
              emptyState={
                <ReportEmptyState
                  title={data ? "No rows match the current filters" : "Requires connected store data"}
                  description={
                    data
                      ? "Try clearing filters or searching a different SKU, product, vendor, or category."
                      : "Connect Shopify or enter demo mode to populate report previews."
                  }
                />
              }
            />
          </>
        )}
      </section>
    </div>
  );
}

function buildReportRows(data: LoadedData | null): Record<ReportKind, ReportRow[]> {
  if (!data) {
    return { actions: [], stockout: [], "dead-stock": [], reorder: [] };
  }

  const scoreBySku = new Map(data.scorecards.map((score) => [score.sku_id, score]));
  const actionBySku = new Map(data.actions.map((action) => [action.sku_id, action]));
  const forecastBySku = new Map(data.forecasts.map((forecast) => [forecast.sku_id, forecast]));

  const actionRows = data.actions.map((action) =>
    actionToRow(action, scoreBySku.get(action.sku_id), forecastBySku.get(action.sku_id)),
  );

  const stockoutRows = data.forecasts.map((forecast) =>
    forecastToRow(
      forecast,
      actionBySku.get(forecast.sku_id),
      scoreBySku.get(forecast.sku_id),
    ),
  );

  const deadStockRows = data.actions
    .filter((action) => action.status === "dead" || action.status === "optimize")
    .map((action) =>
      actionToRow(action, scoreBySku.get(action.sku_id), forecastBySku.get(action.sku_id)),
    );

  const reorderRows = data.reorder.map((suggestion) =>
    reorderToRow(
      suggestion,
      scoreBySku.get(suggestion.sku_id),
      forecastBySku.get(suggestion.sku_id),
    ),
  );

  return {
    actions: actionRows,
    stockout: stockoutRows,
    "dead-stock": deadStockRows,
    reorder: reorderRows,
  };
}

function actionToRow(
  action: InventoryAction,
  score: SkuScorecard | undefined,
  forecast: ForecastResult | undefined,
): ReportRow {
  const isUrgent = action.status === "urgent";
  const daysLeft = isUrgent ? action.days_until_stockout : action.days_of_inventory;
  const dailyVelocity = action.daily_velocity || score?.avg_daily_units || null;
  const recommendedQty = isUrgent
    ? Math.max(Math.round(action.target_inventory_units - action.current_on_hand), 0)
    : null;
  const riskLevel = calculateRiskLevel(daysLeft, action.lead_time_days_used);
  const status =
    action.status === "dead"
      ? "Dead stock"
      : action.status === "optimize"
        ? action.days_of_inventory >= 75
          ? "Overstock"
          : "Slow mover"
        : "Reorder";

  return {
    id: action.sku_id,
    product: action.name,
    sku: action.sku_id,
    vendor: score?.vendor ?? "Unknown",
    category: score?.category ?? "Unassigned",
    priority: action.priority_score,
    actionType: statusLabel[action.status],
    currentStock: action.current_on_hand,
    daysLeft,
    daysInventory: action.days_of_inventory,
    leadTime: action.lead_time_days_used,
    recommendedQty,
    cashImpact: getActionImpactValue(action),
    reason: action.explanation ?? action.recommended_action,
    recommendedAction: action.recommended_action,
    riskLevel,
    salesLast30: dailyVelocity === null ? null : Math.round(dailyVelocity * 30),
    dailyVelocity,
    estimatedStockoutDate: isUrgent ? dateFromNow(daysLeft) : "Not in stockout window",
    inventoryValue: action.current_on_hand && score?.profit_per_unit
      ? Math.round(action.current_on_hand * score.profit_per_unit)
      : action.status === "dead" || action.status === "optimize"
        ? action.cash_tied_up
        : null,
    daysSinceLastSale: inferDaysSinceLastSale(action),
    status,
    targetCoverage: action.target_coverage_days,
    estimatedCost: null,
    orderDeadline: isUrgent ? dateFromNow(Math.max(daysLeft - action.lead_time_days_used, 0)) : "Review",
  };
}

function forecastToRow(
  forecast: ForecastResult,
  action: InventoryAction | undefined,
  score: SkuScorecard | undefined,
): ReportRow {
  const dailyVelocity =
    action?.daily_velocity || forecast.projected_30_day_demand / 30 || score?.avg_daily_units || null;
  const currentStock = action?.current_on_hand ?? score?.inventory_on_hand ?? null;
  const leadTime = action?.lead_time_days_used ?? 14;
  const daysLeft =
    action?.status === "urgent"
      ? action.days_until_stockout
      : currentStock !== null && dailyVelocity
        ? currentStock / dailyVelocity
        : null;
  const riskLevel = calculateRiskLevel(daysLeft, leadTime);

  return {
    id: forecast.sku_id,
    product: score?.name ?? action?.name ?? forecast.sku_id,
    sku: forecast.sku_id,
    vendor: score?.vendor ?? "Unknown",
    category: score?.category ?? "Unassigned",
    priority: Math.round(forecast.stockout_probability_30d * 100),
    actionType: action ? statusLabel[action.status] : "Review",
    currentStock,
    daysLeft,
    daysInventory: daysLeft,
    leadTime,
    recommendedQty:
      action?.status === "urgent"
        ? Math.max(Math.round(action.target_inventory_units - action.current_on_hand), 0)
        : null,
    cashImpact: action ? getActionImpactValue(action) : null,
    reason: forecast.explain,
    recommendedAction: action?.recommended_action ?? buildStockoutRecommendation(riskLevel),
    riskLevel,
    salesLast30: forecast.projected_30_day_demand,
    dailyVelocity,
    estimatedStockoutDate: daysLeft === null ? "Unavailable" : dateFromNow(daysLeft),
    inventoryValue: currentStock && score?.profit_per_unit
      ? Math.round(currentStock * score.profit_per_unit)
      : null,
    daysSinceLastSale: null,
    status: riskLevel === "Low" ? "Review" : "Reorder",
    targetCoverage: action?.target_coverage_days ?? null,
    estimatedCost: null,
    orderDeadline: daysLeft === null ? "Unavailable" : dateFromNow(Math.max(daysLeft - leadTime, 0)),
  };
}

function reorderToRow(
  suggestion: ReorderSuggestion,
  score: SkuScorecard | undefined,
  forecast: ForecastResult | undefined,
): ReportRow {
  const dailyVelocity =
    score?.avg_daily_units ?? (forecast ? forecast.projected_30_day_demand / 30 : null);
  const daysLeft = dailyVelocity ? suggestion.current_on_hand / dailyVelocity : null;
  const riskLevel = calculateRiskLevel(daysLeft, suggestion.lead_time_days);

  return {
    id: suggestion.sku_id,
    product: suggestion.name,
    sku: suggestion.sku_id,
    vendor: suggestion.vendor,
    category: score?.category ?? "Unassigned",
    priority: Math.round(suggestion.expected_stockout_prob * 100),
    actionType: "Reorder",
    currentStock: suggestion.current_on_hand,
    daysLeft,
    daysInventory: daysLeft,
    leadTime: suggestion.lead_time_days,
    recommendedQty: suggestion.recommended_order_qty,
    cashImpact: suggestion.extended_cost,
    reason: suggestion.rationale,
    recommendedAction: suggestion.rationale,
    riskLevel,
    salesLast30: dailyVelocity === null ? null : Math.round(dailyVelocity * 30),
    dailyVelocity,
    estimatedStockoutDate: daysLeft === null ? "Unavailable" : dateFromNow(daysLeft),
    inventoryValue: suggestion.current_on_hand * suggestion.unit_cost,
    daysSinceLastSale: null,
    status: "Reorder",
    targetCoverage: dailyVelocity ? suggestion.order_up_to / dailyVelocity : null,
    estimatedCost: suggestion.extended_cost,
    orderDeadline: daysLeft === null ? "Unavailable" : dateFromNow(Math.max(daysLeft - suggestion.lead_time_days, 0)),
  };
}

function buildColumns(report: ReportKind): ReportColumn<ReportRow>[] {
  const baseProduct: ReportColumn<ReportRow>[] = [
    textColumn("product", "Product", (row) => row.product),
    textColumn("sku", "SKU", (row) => row.sku),
    textColumn("vendor", "Vendor", (row) => row.vendor),
  ];

  if (report === "actions") {
    return [
      numberColumn("priority", "Priority", (row) => row.priority),
      badgeColumn("actionType", "Action", (row) => row.actionType),
      ...baseProduct,
      numberColumn("currentStock", "Current stock", (row) => row.currentStock),
      numberColumn("daysLeft", "Days left / DOI", (row) => row.daysLeft),
      numberColumn("leadTime", "Lead time", (row) => row.leadTime),
      numberColumn("recommendedQty", "Recommended qty", (row) => row.recommendedQty),
      currencyColumn("cashImpact", "Cash impact", (row) => row.cashImpact),
      textColumn("reason", "Reason", (row) => row.reason),
    ];
  }

  if (report === "stockout") {
    return [
      ...baseProduct,
      numberColumn("currentStock", "Current stock", (row) => row.currentStock),
      numberColumn("salesLast30", "30-day sales", (row) => row.salesLast30),
      numberColumn("dailyVelocity", "Daily velocity", (row) => row.dailyVelocity),
      numberColumn("daysLeft", "Days left", (row) => row.daysLeft),
      numberColumn("leadTime", "Lead time", (row) => row.leadTime),
      textColumn("estimatedStockoutDate", "Est. stockout", (row) => row.estimatedStockoutDate),
      badgeColumn("riskLevel", "Risk", (row) => row.riskLevel),
      textColumn("recommendedAction", "Recommended action", (row) => row.recommendedAction),
    ];
  }

  if (report === "dead-stock") {
    return [
      ...baseProduct,
      numberColumn("currentStock", "Current stock", (row) => row.currentStock),
      currencyColumn("inventoryValue", "Inventory value", (row) => row.inventoryValue),
      numberColumn("daysSinceLastSale", "Days since sale", (row) => row.daysSinceLastSale),
      numberColumn("salesLast30", "Sales last 30", (row) => row.salesLast30),
      numberColumn("daysInventory", "Days inventory", (row) => row.daysInventory),
      currencyColumn("cashImpact", "Cash tied up", (row) => row.cashImpact),
      textColumn("recommendedAction", "Recommended action", (row) => row.recommendedAction),
    ];
  }

  return [
    ...baseProduct,
    numberColumn("currentStock", "Current stock", (row) => row.currentStock),
    numberColumn("dailyVelocity", "Daily velocity", (row) => row.dailyVelocity),
    numberColumn("leadTime", "Lead time", (row) => row.leadTime),
    numberColumn("targetCoverage", "Target coverage", (row) => row.targetCoverage),
    numberColumn("recommendedQty", "Recommended qty", (row) => row.recommendedQty),
    currencyColumn("estimatedCost", "Estimated cost", (row) => row.estimatedCost),
    textColumn("orderDeadline", "Order deadline", (row) => row.orderDeadline),
    textColumn("recommendedAction", "Status / action", (row) => row.recommendedAction),
  ];
}

function buildCsvColumns(report: ReportKind): CsvColumn<ReportRow>[] {
  return buildColumns(report).map((column) => ({
    label: column.label,
    value: (row) => csvValue(column.key, row),
  }));
}

function buildMetrics(report: ReportKind, rows: ReportRow[]): ReportMetric[] {
  if (report === "actions") {
    return [
      metric("Critical actions", rows.filter((row) => row.priority >= 80).length, "danger"),
      metric("Reorder actions", rows.filter((row) => row.actionType === "Urgent").length, "warning"),
      metric("Dead-stock actions", rows.filter((row) => row.actionType === "Dead").length, "danger"),
      metric("Estimated cash impact", currency(sum(rows, "cashImpact")), "positive"),
    ];
  }
  if (report === "stockout") {
    return [
      metric("Critical risk", rows.filter((row) => row.riskLevel === "Critical").length, "danger"),
      metric("High risk", rows.filter((row) => row.riskLevel === "High").length, "warning"),
      metric("Lead-time misses", rows.filter((row) => (row.daysLeft ?? 999) <= (row.leadTime ?? 0)).length, "danger"),
      metric("SKUs reviewed", rows.length, "neutral"),
    ];
  }
  if (report === "dead-stock") {
    return [
      metric("Dead stock SKUs", rows.filter((row) => row.status === "Dead stock").length, "danger"),
      metric("Slow movers", rows.filter((row) => row.status === "Slow mover" || row.status === "Overstock").length, "warning"),
      metric("Cash tied up", currency(sum(rows, "cashImpact")), "danger"),
      metric("Suggested recovery", currency(Math.round(sum(rows, "cashImpact") * 0.68)), "positive"),
    ];
  }
  return [
    metric("SKUs to reorder", rows.length, "warning"),
    metric("Estimated reorder value", currency(sum(rows, "estimatedCost")), "warning"),
    metric("Critical reorder items", rows.filter((row) => row.riskLevel === "Critical").length, "danger"),
    metric("Vendors involved", new Set(rows.map((row) => row.vendor)).size, "neutral"),
  ];
}

function buildFilterConfig(report: ReportKind, rows: ReportRow[]): ReportFilterConfig[] {
  const vendor = selectFilter("vendor", "Vendor", uniqueValues(rows, "vendor"));
  const category = selectFilter("category", "Category", uniqueValues(rows, "category"));

  if (report === "actions") {
    return [
      selectFilter("priorityBucket", "Priority", ["Critical", "High", "Medium", "Low"]),
      selectFilter("actionType", "Action type", uniqueValues(rows, "actionType")),
      vendor,
      category,
    ];
  }
  if (report === "stockout") {
    return [
      selectFilter("riskLevel", "Risk level", ["Critical", "High", "Medium", "Low"]),
      vendor,
      category,
      selectFilter("daysLeftBucket", "Days left", ["0-7 days", "8-14 days", "15-30 days", "31+ days"]),
      selectFilter("leadTimeBucket", "Lead time", ["0-14 days", "15-21 days", "22+ days"]),
    ];
  }
  if (report === "dead-stock") {
    return [
      selectFilter("status", "Status", ["Dead stock", "Slow mover", "Overstock"]),
      vendor,
      category,
      selectFilter("inventoryValueBucket", "Inventory value", ["<$1k", "$1k-$5k", "$5k+"]),
      selectFilter("daysSinceLastSaleBucket", "Days since sale", ["0-30 days", "31-60 days", "61+ days", "Unavailable"]),
    ];
  }
  return [
    vendor,
    selectFilter("priorityBucket", "Priority", ["Critical", "High", "Medium", "Low"]),
    selectFilter("estimatedCostBucket", "Estimated cost", ["<$1k", "$1k-$5k", "$5k+"]),
    selectFilter("daysLeftBucket", "Days left", ["0-7 days", "8-14 days", "15-30 days", "31+ days"]),
  ];
}

function filterRows(
  rows: ReportRow[],
  report: ReportKind,
  search: string,
  filters: Record<string, string>,
): ReportRow[] {
  const needle = search.trim().toLowerCase();
  return rows.filter((row) => {
    if (
      needle &&
      ![row.product, row.sku, row.vendor, row.category, row.reason, row.recommendedAction]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    ) {
      return false;
    }
    return Object.entries(filters).every(([key, value]) => {
      if (!value) return true;
      if (key === "priorityBucket") return priorityBucket(row.priority) === value;
      if (key === "daysLeftBucket") return daysBucket(row.daysLeft) === value;
      if (key === "leadTimeBucket") return leadTimeBucket(row.leadTime) === value;
      if (key === "inventoryValueBucket") return moneyBucket(row.inventoryValue) === value;
      if (key === "estimatedCostBucket") return moneyBucket(row.estimatedCost) === value;
      if (key === "daysSinceLastSaleBucket") return staleBucket(row.daysSinceLastSale) === value;
      if (key in row) return String(row[key as keyof ReportRow]) === value;
      return report === "stockout" ? row.riskLevel === value : true;
    });
  });
}

function sortRows(
  rows: ReportRow[],
  columns: ReportColumn<ReportRow>[],
  sortKey: string,
  direction: SortDirection,
): ReportRow[] {
  const column = columns.find((item) => item.key === sortKey);
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = column?.sortValue?.(left) ?? csvValue(sortKey, left);
    const b = column?.sortValue?.(right) ?? csvValue(sortKey, right);
    if (typeof a === "number" && typeof b === "number") return (a - b) * multiplier;
    return String(a).localeCompare(String(b)) * multiplier;
  });
}

function textColumn(
  key: string,
  label: string,
  value: (row: ReportRow) => string,
): ReportColumn<ReportRow> {
  return {
    key,
    label,
    render: value,
    sortValue: value,
  };
}

function numberColumn(
  key: string,
  label: string,
  value: (row: ReportRow) => number | null,
): ReportColumn<ReportRow> {
  return {
    key,
    label,
    align: "right",
    render: (row) => formatNumber(value(row)),
    sortValue: (row) => value(row) ?? -1,
  };
}

function currencyColumn(
  key: string,
  label: string,
  value: (row: ReportRow) => number | null,
): ReportColumn<ReportRow> {
  return {
    key,
    label,
    align: "right",
    render: (row) => (value(row) === null ? "Unavailable" : currency(value(row) ?? 0)),
    sortValue: (row) => value(row) ?? -1,
  };
}

function badgeColumn(
  key: string,
  label: string,
  value: (row: ReportRow) => string,
): ReportColumn<ReportRow> {
  return {
    key,
    label,
    render: (row) => (
      <ReportStatusBadge tone={badgeTone(value(row))}>{value(row)}</ReportStatusBadge>
    ),
    sortValue: value,
  };
}

function csvValue(key: string, row: ReportRow): string | number {
  const value = row[key as keyof ReportRow];
  if (typeof value === "number") return Number.isFinite(value) ? value : "";
  return value ?? "";
}

function selectFilter(key: string, label: string, values: string[]): ReportFilterConfig {
  return {
    key,
    label,
    options: values.filter(Boolean).map((value) => ({ label: value, value })),
  };
}

function uniqueValues(rows: ReportRow[], key: keyof ReportRow): string[] {
  return [...new Set(rows.map((row) => String(row[key] ?? "")).filter(Boolean))].sort();
}

function metric(
  label: string,
  value: string | number,
  tone: ReportMetric["tone"],
): ReportMetric {
  return { label, value, tone };
}

function sum(rows: ReportRow[], key: keyof ReportRow): number {
  return rows.reduce((total, row) => {
    const value = row[key];
    return total + (typeof value === "number" && Number.isFinite(value) ? value : 0);
  }, 0);
}

function calculateRiskLevel(
  daysLeft: number | null,
  leadTimeDays: number | null,
): ReportRow["riskLevel"] {
  if (daysLeft === null || leadTimeDays === null) return "Low";
  if (daysLeft <= leadTimeDays) return "Critical";
  if (daysLeft <= leadTimeDays + 7) return "High";
  if (daysLeft <= leadTimeDays + 14) return "Medium";
  return "Low";
}

function buildStockoutRecommendation(risk: ReportRow["riskLevel"]): string {
  if (risk === "Critical") return "Review reorder quantity today.";
  if (risk === "High") return "Add to the next reorder review.";
  if (risk === "Medium") return "Monitor and confirm lead time.";
  return "No immediate reorder action.";
}

function inferDaysSinceLastSale(action: InventoryAction): number | null {
  const match = action.explanation?.match(/(\d+)\s+days since last sale/i);
  return match ? Number.parseInt(match[1], 10) : null;
}

function dateFromNow(days: number | null): string {
  if (days === null || !Number.isFinite(days)) return "Unavailable";
  const date = new Date();
  date.setDate(date.getDate() + Math.max(Math.round(days), 0));
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

function priorityBucket(priority: number): string {
  if (priority >= 80) return "Critical";
  if (priority >= 60) return "High";
  if (priority >= 35) return "Medium";
  return "Low";
}

function daysBucket(value: number | null): string {
  if (value === null) return "31+ days";
  if (value <= 7) return "0-7 days";
  if (value <= 14) return "8-14 days";
  if (value <= 30) return "15-30 days";
  return "31+ days";
}

function leadTimeBucket(value: number | null): string {
  if (value === null || value <= 14) return "0-14 days";
  if (value <= 21) return "15-21 days";
  return "22+ days";
}

function moneyBucket(value: number | null): string {
  if (value === null || value < 1000) return "<$1k";
  if (value < 5000) return "$1k-$5k";
  return "$5k+";
}

function staleBucket(value: number | null): string {
  if (value === null) return "Unavailable";
  if (value <= 30) return "0-30 days";
  if (value <= 60) return "31-60 days";
  return "61+ days";
}

function badgeTone(value: string): "neutral" | "positive" | "warning" | "danger" | "demo" {
  if (["Critical", "Dead", "Dead stock", "Urgent"].includes(value)) return "danger";
  if (["High", "Medium", "Optimize", "Overstock", "Slow mover", "Reorder"].includes(value)) return "warning";
  if (["Low"].includes(value)) return "positive";
  return "neutral";
}

function statusClass(status: string): string {
  return status.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-$/g, "");
}

function isDemoMode(): boolean {
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
