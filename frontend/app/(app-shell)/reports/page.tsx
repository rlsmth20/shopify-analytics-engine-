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
import { ProjectedStockHealth } from "@/components/projected-stock-health";
import { fetchInventoryActions, type InventoryAction } from "@/lib/api";
import { getActionImpactValue, statusLabel } from "@/lib/app-helpers";
import {
  currency,
  fetchAuditEvents,
  fetchForecasts,
  fetchReportSchedules,
  fetchReorderSuggestions,
  fetchScorecards,
  saveReportSchedule,
  type AuditLogEvent,
  type ForecastResult,
  type ReportSchedule,
  type ReorderSuggestion,
  type SkuScorecard,
} from "@/lib/api-v2";
import { useAuth } from "@/components/auth-guard";
import { entitlementHas, fetchEntitlements, type Entitlements } from "@/lib/entitlements";
import {
  exportFormattedReport,
  type BarPoint,
  type ReportKpi as XlsxKpi,
  type ReportTableColumn as XlsxColumn,
  type Tone as XlsxTone,
} from "@/lib/report-export";

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
  rawReason?: string | null;
  calculationDetails?: string | null;
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
    description: "Recommended reorder quantities, estimated cost, and supplier exposure.",
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
    title: "Transfer Plan Report",
    category: "Operations",
    description: "Recommended inventory moves between locations when location-level stock is available.",
    status: "Sample data",
    href: "/transfers",
    cta: "Open transfers",
  },
  {
    title: "Bundle Opportunity Report",
    category: "Revenue",
    description: "Products frequently bought together, ranked by co-purchase strength and revenue opportunity.",
    status: "Available",
    href: "/bundles",
    cta: "Open bundles",
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
    status: "Sample report",
    href: "/sample-inventory-risk-snapshot",
    cta: "View sample",
  },
  {
    title: "Schedule Preferences",
    category: "Automation",
    description: "Save report delivery preferences; automated email delivery is planned.",
    status: "Delivery planned",
    href: "/reports",
    cta: "Configure schedule",
  },
] as const;

const reportMeta: Record<ReportKind, { title: string; description: string }> = {
  actions: {
    title: "Inventory Action Report",
    description:
      "A working table of the current Action Queue, enriched with supplier and category when scorecard data is available.",
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
      "Suggested replenishment quantities with supplier, lead-time, and estimated cost context.",
  },
};

export default function ReportsPage() {
  const { user } = useAuth();
  const [selectedReport, setSelectedReport] = useState<ReportKind>("actions");
  const [data, setData] = useState<LoadedData | null>(null);
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditLogEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState("priority");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [scheduleEmail, setScheduleEmail] = useState(user.email);
  const [scheduleCadence, setScheduleCadence] = useState<ReportSchedule["cadence"]>("weekly");
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [entitlementsLoaded, setEntitlementsLoaded] = useState(user.id === 0 || user.is_admin);

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
    let cancelled = false;
    if (user.id === 0 || user.is_admin) {
      setEntitlements(null);
      setEntitlementsLoaded(true);
      return;
    }
    setEntitlementsLoaded(false);
    void fetchEntitlements()
      .then((data) => {
        if (!cancelled) setEntitlements(data);
      })
      .catch(() => {
        if (!cancelled) setEntitlements(null);
      })
      .finally(() => {
        if (!cancelled) setEntitlementsLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [user.id, user.is_admin]);

  useEffect(() => {
    setSearch("");
    setFilters({});
    setSortKey("priority");
    setSortDirection("desc");
    setSelectedRowId(null);
    const existing = schedules.find((schedule) => schedule.report_type === selectedReport);
    setScheduleEmail(existing?.recipient_email || user.email);
    setScheduleCadence(existing?.cadence || "weekly");
    setScheduleEnabled(existing?.enabled ?? true);
    setScheduleNotice(null);
  }, [selectedReport]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchReportSchedules(controller.signal),
      fetchAuditEvents(8, controller.signal),
    ])
      .then(([scheduleResponse, auditResponse]) => {
        setSchedules(scheduleResponse.schedules);
        setAuditEvents(auditResponse.events);
        const existing = scheduleResponse.schedules.find(
          (schedule) => schedule.report_type === selectedReport,
        );
        if (existing) {
          setScheduleEmail(existing.recipient_email);
          setScheduleCadence(existing.cadence);
          setScheduleEnabled(existing.enabled);
        }
      })
      .catch(() => {
        setSchedules([]);
        setAuditEvents([]);
      });
    return () => controller.abort();
  }, []);

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
  const insight = useMemo(
    () => buildInsight(selectedReport, rows),
    [selectedReport, rows],
  );
  const cta = reportCta(selectedReport);
  const canExport =
    user.id === 0 ||
    user.is_admin ||
    entitlementHas(entitlements, "reports_export");

  function updateSort(key: string) {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "product" ? "asc" : "desc");
  }

  async function exportWorkbook() {
    await exportFormattedReport({
      title: reportMeta[selectedReport].title,
      subtitle: reportMeta[selectedReport].description,
      filename: `skubase-${selectedReport}-report-${new Date().toISOString().slice(0, 10)}.xlsx`,
      summarySheetName: "Summary",
      detailSheetName: detailSheetName(selectedReport),
      kpis: metricsToKpis(metrics),
      charts: buildReportCharts(selectedReport, visibleRows),
      todos: buildReportTodos(selectedReport, visibleRows),
      tableTitle: reportMeta[selectedReport].title,
      rows: visibleRows,
      columns: buildXlsxColumns(selectedReport),
    });
  }

  async function saveSchedule() {
    const email = scheduleEmail.trim();
    if (!email || !email.includes("@")) {
      setScheduleNotice("Enter a valid email before saving the schedule.");
      return;
    }
    setScheduleSaving(true);
    setScheduleNotice(null);
    try {
      const saved = await saveReportSchedule({
        report_type: selectedReport,
        cadence: scheduleCadence,
        channel: "email",
        recipient_email: email,
        enabled: scheduleEnabled,
      });
      setSchedules((current) => [
        saved,
        ...current.filter((schedule) => schedule.report_type !== selectedReport),
      ]);
      setAuditEvents((current) => [
        {
          id: Date.now(),
          event_type: "report_schedule_saved",
          entity_type: "report_schedule",
          entity_id: selectedReport,
          summary: `${reportMeta[selectedReport].title} schedule saved for ${email}.`,
          metadata: {
            report_type: selectedReport,
            cadence: scheduleCadence,
            enabled: scheduleEnabled,
          },
          created_at: new Date().toISOString(),
        },
        ...current,
      ].slice(0, 8));
      setScheduleNotice("Report schedule preference saved.");
    } catch (err) {
      setScheduleNotice(err instanceof Error ? err.message : "Schedule could not be saved.");
    } finally {
      setScheduleSaving(false);
    }
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
          {isDemo ? <ReportStatusBadge tone="demo">Sample data</ReportStatusBadge> : null}
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
              <a className="button button-secondary" href={report.href}>
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
          badge={isDemo ? <ReportStatusBadge tone="demo">Sample data</ReportStatusBadge> : undefined}
          actions={
            <>
              <a className="button button-secondary" href={cta.href}>
                {cta.label}
              </a>
              {canExport ? (
                <button
                  type="button"
                  className="button button-primary"
                  onClick={exportWorkbook}
                  disabled={visibleRows.length === 0}
                >
                  Export filtered Excel
                </button>
              ) : (
                <a
                  className={`button button-primary${!entitlementsLoaded ? " button-disabled" : ""}`}
                  href={entitlementsLoaded ? "/billing" : undefined}
                  aria-disabled={!entitlementsLoaded}
                >
                  {entitlementsLoaded ? "Upgrade to Growth to export" : "Loading plan access..."}
                </a>
              )}
            </>
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
            <p className="report-insight">{insight}</p>
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
              selectedRowKey={selectedRowId}
              onRowClick={(row) => {
                const key = `${selectedReport}-${row.id}`;
                setSelectedRowId((current) => (current === key ? null : key));
              }}
              renderRowDetails={(row) => (
                <ReportRowDetails report={selectedReport} row={row} />
              )}
              sortKey={sortKey}
              sortDirection={sortDirection}
              onSort={updateSort}
              loading={loading}
              emptyState={
                <ReportEmptyState
                  title={data ? "No rows match the current filters" : "Requires connected store data"}
                  description={
                    data
                      ? "Try clearing filters or searching a different SKU, product, supplier, or category."
                      : "Connect Shopify or enter demo mode to populate report previews."
                  }
                />
              }
            />
          </>
        )}
      </section>

      <section className="report-admin-grid">
        <ReportSchedulePanel
          selectedReport={selectedReport}
          email={scheduleEmail}
          cadence={scheduleCadence}
          enabled={scheduleEnabled}
          saving={scheduleSaving}
          notice={scheduleNotice}
          onEmailChange={setScheduleEmail}
          onCadenceChange={setScheduleCadence}
          onEnabledChange={setScheduleEnabled}
          onSave={saveSchedule}
        />
        <AuditHistoryPanel events={auditEvents} />
      </section>
    </div>
  );
}

function ReportSchedulePanel({
  selectedReport,
  email,
  cadence,
  enabled,
  saving,
  notice,
  onEmailChange,
  onCadenceChange,
  onEnabledChange,
  onSave,
}: {
  selectedReport: ReportKind;
  email: string;
  cadence: ReportSchedule["cadence"];
  enabled: boolean;
  saving: boolean;
  notice: string | null;
  onEmailChange: (value: string) => void;
  onCadenceChange: (value: ReportSchedule["cadence"]) => void;
  onEnabledChange: (value: boolean) => void;
  onSave: () => void;
}) {
  return (
    <section className="section-card report-admin-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Schedule preferences</p>
          <h2 className="section-title section-title-small">
            Report delivery preferences
          </h2>
          <p className="section-copy">
            Save the selected report cadence and recipient. Automated email
            delivery is planned; exports are available now.
          </p>
        </div>
        <ReportStatusBadge tone="warning">Delivery planned</ReportStatusBadge>
      </div>
      <div className="report-schedule-form">
        <label className="report-filter-field">
          <span>Report</span>
          <input
            className="input-control"
            value={reportMeta[selectedReport].title}
            readOnly
          />
        </label>
        <label className="report-filter-field">
          <span>Cadence</span>
          <select
            value={cadence}
            onChange={(event) => onCadenceChange(event.target.value as ReportSchedule["cadence"])}
          >
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>
        <label className="report-filter-field">
          <span>Recipient</span>
          <input
            className="input-control"
            type="email"
            value={email}
            onChange={(event) => onEmailChange(event.target.value)}
            placeholder="ops@example.com"
          />
        </label>
        <label className="report-toggle-row">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => onEnabledChange(event.target.checked)}
          />
          Enabled
        </label>
      </div>
      <div className="button-row">
        <button
          type="button"
          className="button button-primary"
          onClick={() => void onSave()}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save schedule"}
        </button>
      </div>
      {notice ? <p className="report-schedule-notice">{notice}</p> : null}
    </section>
  );
}

function AuditHistoryPanel({ events }: { events: AuditLogEvent[] }) {
  return (
    <section className="section-card report-admin-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">Decision history</p>
          <h2 className="section-title section-title-small">Recent workspace history</h2>
          <p className="section-copy">
            Saved report preferences and PO status changes appear here when they
            are recorded by the workspace.
          </p>
        </div>
      </div>
      {events.length === 0 ? (
        <ReportEmptyState
          title="No decisions logged yet"
          description="Save report preferences or update a purchase order status to start workspace history."
        />
      ) : (
        <div className="audit-timeline">
          {events.map((event) => (
            <article key={`${event.id}-${event.created_at}`} className="audit-event">
              <p className="audit-event-summary">{event.summary}</p>
              <p className="audit-event-meta">
                {formatDateTime(event.created_at)} - {event.entity_type}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
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

function reportCta(report: ReportKind): { label: string; href: string } {
  if (report === "stockout") return { label: "Review reorder plan", href: "/purchase-orders" };
  if (report === "reorder") return { label: "Open purchase orders", href: "/purchase-orders" };
  if (report === "dead-stock") return { label: "Open liquidation plan", href: "/liquidation" };
  return { label: "Open Action Queue", href: "/actions" };
}

function buildInsight(report: ReportKind, rows: ReportRow[]): string {
  if (report === "stockout") {
    const critical = rows.filter((row) => row.riskLevel === "Critical").length;
    const high = rows.filter((row) => row.riskLevel === "High").length;
    return `${critical + high} SKUs may run out before lead time can comfortably recover them. Start with the critical risk items below.`;
  }
  if (report === "actions") {
    const critical = rows.filter((row) => row.priority >= 80).length;
    return `${critical} high-priority actions are ranked by urgency, cash impact, and available inventory signals.`;
  }
  if (report === "dead-stock") {
    const cash = currency(sum(rows, "cashImpact"));
    return `${cash} is tied up across slow-moving or excess inventory. Start with the largest recovery opportunities.`;
  }
  const critical = rows.filter((row) => row.riskLevel === "Critical").length;
  return `${rows.length} SKUs need replenishment attention based on stock on hand, velocity, lead time, and target coverage. ${critical} are critical.`;
}

function buildReportTodos(report: ReportKind, rows: ReportRow[]) {
  if (report === "stockout") {
    const critical = rows.filter((row) => row.riskLevel === "Critical").length;
    return [
      {
        label: `Review ${critical} critical stockout ${critical === 1 ? "SKU" : "SKUs"}`,
        detail: "Start with rows where days left is inside the supplier lead time.",
        tone: "danger" as const,
      },
      {
        label: "Open reorder plan",
        detail: "Turn the urgent stockout rows into purchase order decisions.",
        tone: "warning" as const,
      },
      {
        label: "Confirm lead-time assumptions",
        detail: "Check supplier/category lead-time settings before committing capital.",
        tone: "neutral" as const,
      },
    ];
  }
  if (report === "reorder") {
    const vendors = new Set(rows.map((row) => row.vendor).filter(Boolean)).size;
    return [
      {
        label: "Approve urgent reorder items",
        detail: "Confirm quantities, costs, and target coverage for the shortest runway SKUs.",
        tone: "danger" as const,
      },
      {
        label: `Group orders across ${vendors} ${vendors === 1 ? "supplier" : "suppliers"}`,
        detail: "Use supplier grouping to keep purchase orders clean.",
        tone: "warning" as const,
      },
      {
        label: "Record receipts",
        detail: "Receiving history feeds supplier scorecards and lead-time confidence.",
        tone: "good" as const,
      },
    ];
  }
  if (report === "dead-stock") {
    const cash = currency(sum(rows, "cashImpact"));
    return [
      {
        label: `Recover the largest share of ${cash}`,
        detail: "Start with the rows tying up the most working capital.",
        tone: "danger" as const,
      },
      {
        label: "Pick liquidation tactic",
        detail: "Choose markdown, bundle, wholesale, or write-off based on age and cash tied up.",
        tone: "warning" as const,
      },
      {
        label: "Track recovery after the sale window",
        detail: "Export again after promotions to confirm the dead-stock list shrank.",
        tone: "good" as const,
      },
    ];
  }
  const highPriority = rows.filter((row) => row.priority >= 80).length;
  return [
    {
      label: `Work ${highPriority} highest-priority actions first`,
      detail: "These rows combine urgency, cash impact, and inventory signals.",
      tone: "danger" as const,
    },
    {
      label: "Route each action to the right workflow",
      detail: "Use purchase orders for reorders, liquidation for dead stock, and lead-time settings for supplier issues.",
      tone: "warning" as const,
    },
    {
      label: "Re-export after decisions",
      detail: "Use the next report to see whether the queue and cash exposure improved.",
      tone: "good" as const,
    },
  ];
}

function ReportRowDetails({
  report,
  row,
}: {
  report: ReportKind;
  row: ReportRow;
}) {
  const cta = reportCta(report);
  const keyMetrics = buildReportKeyMetrics(report, row);
  const advancedDetails = buildReportAdvancedDetails(report, row);
  const summaryReason = row.reason || buildWhyThisMatters(report, row);
  const statusText = report === "actions" ? row.actionType : report === "stockout" ? row.riskLevel : row.status;

  return (
    <div className="report-row-details">
      <div className="report-row-detail-main">
        <div>
          <p className="report-detail-eyebrow">Summary</p>
          <h3>{row.product}</h3>
          <p className="report-detail-meta">
            {row.sku}
            {row.vendor ? ` · Supplier: ${row.vendor}` : ""}
            {statusText ? ` · ${statusText}` : ""}
          </p>
          <p className="report-detail-copy">{summaryReason}</p>
        </div>
        <a className="button button-secondary button-sm" href={cta.href}>
          {cta.label}
        </a>
      </div>
      <ProjectedStockHealth
        productName={row.product}
        sku={row.sku}
        currentStock={row.currentStock}
        dailyVelocity={row.dailyVelocity}
        salesLast30Days={row.salesLast30}
        daysLeft={row.daysLeft}
        daysOfInventory={row.daysInventory}
        leadTimeDays={row.leadTime}
        targetCoverageDays={row.targetCoverage}
        stockoutDate={row.estimatedStockoutDate}
        recommendedQty={row.recommendedQty}
        recommendedAction={row.recommendedAction}
        riskLevel={row.riskLevel}
        status={row.status}
        inventoryValue={row.inventoryValue}
        cashImpact={row.cashImpact}
        daysSinceLastSale={row.daysSinceLastSale}
        compact
        hideMetricGrid
        hideIdentity
        hideActionText
        context="report"
      />
      <dl className="report-detail-grid">
        {keyMetrics.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="report-why-box">
        <p className="report-detail-eyebrow">Why this matters</p>
        <p>{buildWhyThisMatters(report, row)}</p>
        <strong>{row.recommendedAction || "Review this SKU before acting."}</strong>
      </div>
      {advancedDetails.length > 0 ? (
        <details className="report-advanced-details">
          <summary>Advanced details</summary>
          <dl className="report-detail-grid">
            {advancedDetails.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}
    </div>
  );
}

function buildReportKeyMetrics(report: ReportKind, row: ReportRow): Array<[string, string]> {
  if (report === "stockout") {
    return compactMetricPairs([
      ["Current stock", formatNumber(row.currentStock)],
      ["Days left", formatDaysValue(row.daysLeft)],
      ["Lead time", formatDaysValue(row.leadTime)],
      ["Estimated stockout", row.estimatedStockoutDate || "Unavailable"],
      row.recommendedQty !== null
        ? ["Recommended qty", formatNumber(row.recommendedQty)]
        : ["Recommended action", row.recommendedAction || "Review"],
    ]);
  }
  if (report === "reorder") {
    return compactMetricPairs([
      ["Current stock", formatNumber(row.currentStock)],
      ["Lead time", formatDaysValue(row.leadTime)],
      ["Recommended qty", formatNumber(row.recommendedQty)],
      ["Estimated cost", formatMoney(row.estimatedCost)],
      ["Order deadline", row.orderDeadline || "Unavailable"],
    ]);
  }
  if (report === "dead-stock") {
    return compactMetricPairs([
      ["Current stock", formatNumber(row.currentStock)],
      row.daysSinceLastSale !== null
        ? ["Days since sale", formatDaysValue(row.daysSinceLastSale)]
        : ["Days of cover", formatDaysValue(row.daysInventory)],
      ["Cash tied up", formatMoney(row.cashImpact ?? row.inventoryValue)],
      ["Sales last 30", formatNumber(row.salesLast30)],
      ["Recommended action", row.recommendedAction || "Review"],
    ]);
  }
  return compactMetricPairs([
    ["Current stock", formatNumber(row.currentStock)],
    ["Days left", formatDaysValue(row.daysLeft)],
    ["Lead time", formatDaysValue(row.leadTime)],
    ["Recommended qty", formatNumber(row.recommendedQty)],
    ["Cash impact", formatMoney(row.cashImpact)],
  ]);
}

function buildReportAdvancedDetails(report: ReportKind, row: ReportRow): Array<[string, string]> {
  const details: Array<[string, string]> = [
    ["Category", safeDetailText(row.category)],
    ["Daily velocity", row.dailyVelocity === null ? "Unavailable" : `${formatNumber(row.dailyVelocity)} / day`],
    ["Sales last 30", formatNumber(row.salesLast30)],
    ["Target coverage", formatDaysValue(row.targetCoverage)],
  ];

  if (report !== "stockout") {
    details.push(["Estimated stockout", row.estimatedStockoutDate || "Unavailable"]);
  }
  if (report !== "dead-stock") {
    details.push(["Inventory value", formatMoney(row.inventoryValue)]);
  }
  if (row.daysInventory !== null && report !== "actions") {
    details.push(["Days of cover", formatDaysValue(row.daysInventory)]);
  }
  if (row.calculationDetails) {
    details.push(["Calculation details", row.calculationDetails]);
  } else if (row.rawReason && row.rawReason !== row.reason) {
    details.push(["Raw reason", row.rawReason]);
  }

  return details.filter(([, value]) => value !== "Unavailable" && value !== "");
}

function compactMetricPairs(pairs: Array<[string, string]>): Array<[string, string]> {
  return pairs.filter(([, value]) => value !== "Unavailable" && value !== "");
}

function buildPlainReportReason({
  rawReason,
  currentStock,
  daysLeft,
  leadTime,
  status,
  cashImpact,
}: {
  rawReason?: string | null;
  currentStock?: number | null;
  daysLeft?: number | null;
  leadTime?: number | null;
  status?: string | null;
  cashImpact?: number | null;
}): string {
  if (!rawReason) return "Review this SKU before acting.";
  if (!containsTechnicalFormula(rawReason)) return rawReason;
  if (isFiniteNumber(daysLeft) && isFiniteNumber(leadTime)) {
    if (daysLeft <= leadTime) {
      return `Current stock covers ${formatNumber(daysLeft)} days, but supplier lead time is ${formatNumber(leadTime)} days. This SKU may run out before replenishment arrives.`;
    }
    return `Current stock covers ${formatNumber(daysLeft)} days against a ${formatNumber(leadTime)}-day lead time. Keep this SKU in reorder review.`;
  }
  if (status === "Dead stock" || status === "Overstock" || status === "Slow mover") {
    return `This SKU may have excess inventory${isFiniteNumber(cashImpact) ? ` with ${formatMoney(cashImpact)} tied up` : ""}. Review it before buying more.`;
  }
  if (isFiniteNumber(currentStock)) {
    return `Current stock is ${formatNumber(currentStock)} units. Review the inventory action and supporting metrics before acting.`;
  }
  return "Skubase found an actionable inventory signal, but the calculation details are available only in Advanced details.";
}

function containsTechnicalFormula(value?: string | null): boolean {
  if (!value) return false;
  return /normal_cdf|demand volatility|projected 30d|1\s*-\s*normal|z[-\s]?score|formula|cdf\(/i.test(value);
}

function formatDaysValue(value: number | null): string {
  return value === null || !Number.isFinite(value) ? "Unavailable" : `${formatNumber(value)} days`;
}

function safeDetailText(value?: string | null): string {
  if (!value || value === "Invalid Date" || value === "NaN" || value === "null" || value === "undefined") {
    return "Unavailable";
  }
  return value;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function buildWhyThisMatters(report: ReportKind, row: ReportRow): string {
  if (report === "stockout" || report === "reorder") {
    if (row.daysLeft !== null && row.leadTime !== null) {
      if (row.daysLeft <= row.leadTime) {
        return `This SKU has ${formatNumber(row.daysLeft)} days left and a ${formatNumber(row.leadTime)}-day lead time, so replenishment may not arrive before stock runs out.`;
      }
      return `This SKU has ${formatNumber(row.daysLeft)} days left against a ${formatNumber(row.leadTime)}-day lead time, so it belongs in the reorder review window.`;
    }
    return "Skubase has enough replenishment signal to keep this SKU in the report, but days-left context is limited.";
  }
  if (report === "dead-stock") {
    return `${formatMoney(row.cashImpact)} may be tied up in inventory that is slow-moving, stale, or above target coverage.`;
  }
  if (row.cashImpact !== null) {
    return `This action carries an estimated impact of ${formatMoney(row.cashImpact)}, so it is worth reviewing before lower-priority work.`;
  }
  return "This SKU is included because its inventory signals make it actionable in the current report.";
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
  const rawReason = action.explanation ?? action.recommended_action;
  const reason = buildPlainReportReason({
    rawReason,
    currentStock: action.current_on_hand,
    daysLeft,
    leadTime: action.lead_time_days_used,
    status,
    cashImpact: getActionImpactValue(action),
  });

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
    reason,
    recommendedAction: action.recommended_action,
    rawReason,
    calculationDetails: containsTechnicalFormula(rawReason) ? rawReason : null,
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
  const reason = buildPlainReportReason({
    rawReason: forecast.explain,
    currentStock,
    daysLeft,
    leadTime,
    status: riskLevel === "Low" ? "Review" : "Reorder",
    cashImpact: action ? getActionImpactValue(action) : null,
  });

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
    reason,
    recommendedAction: action?.recommended_action ?? buildStockoutRecommendation(riskLevel),
    rawReason: forecast.explain,
    calculationDetails: containsTechnicalFormula(forecast.explain) ? forecast.explain : null,
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
  const reason = buildPlainReportReason({
    rawReason: suggestion.rationale,
    currentStock: suggestion.current_on_hand,
    daysLeft,
    leadTime: suggestion.lead_time_days,
    status: "Reorder",
    cashImpact: suggestion.landed_extended_cost || suggestion.extended_cost,
  });

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
    cashImpact: suggestion.landed_extended_cost || suggestion.extended_cost,
    reason,
    recommendedAction: suggestion.rationale,
    rawReason: suggestion.rationale,
    calculationDetails: containsTechnicalFormula(suggestion.rationale) ? suggestion.rationale : null,
    riskLevel,
    salesLast30: dailyVelocity === null ? null : Math.round(dailyVelocity * 30),
    dailyVelocity,
    estimatedStockoutDate: daysLeft === null ? "Unavailable" : dateFromNow(daysLeft),
    inventoryValue: suggestion.current_on_hand * suggestion.unit_cost,
    daysSinceLastSale: null,
    status: "Reorder",
    targetCoverage: dailyVelocity ? suggestion.order_up_to / dailyVelocity : null,
    estimatedCost: suggestion.landed_extended_cost || suggestion.extended_cost,
    orderDeadline: daysLeft === null ? "Unavailable" : dateFromNow(Math.max(daysLeft - suggestion.lead_time_days, 0)),
  };
}

function buildColumns(report: ReportKind): ReportColumn<ReportRow>[] {
  const baseProduct: ReportColumn<ReportRow>[] = [
    textColumn("product", "Product", (row) => row.product),
    textColumn("sku", "SKU", (row) => row.sku),
    textColumn("vendor", "Supplier", (row) => row.vendor),
  ];

  if (report === "actions") {
    return [
      numberColumn("priority", "Priority", (row) => row.priority),
      badgeColumn("actionType", "Action", (row) => row.actionType),
      ...baseProduct,
      numberColumn("currentStock", "Current stock", (row) => row.currentStock),
      numberColumn("daysLeft", "Days left", (row) => row.daysLeft),
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
      numberColumn("daysInventory", "Days of cover", (row) => row.daysInventory),
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
      metric("SKUs Analyzed", rows.length, "neutral"),
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
    metric("Suppliers involved", new Set(rows.map((row) => row.vendor)).size, "neutral"),
  ];
}

function buildFilterConfig(report: ReportKind, rows: ReportRow[]): ReportFilterConfig[] {
  const vendor = selectFilter("vendor", "Supplier", uniqueValues(rows, "vendor"));
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

function formatMoney(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Unavailable";
  return currency(value);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
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

// ---------------------------------------------------------------------------
// Excel-export helpers — build report-specific KPIs, charts, and column
// definitions that drive the formatted xlsx output (summary tab + detail tab).
// ---------------------------------------------------------------------------
function detailSheetName(report: ReportKind): string {
  if (report === "actions") return "Actions";
  if (report === "stockout") return "Stockout";
  if (report === "dead-stock") return "Dead Stock";
  return "Reorder";
}

function metricsToKpis(metrics: ReportMetric[]): XlsxKpi[] {
  return metrics.map((metric) => ({
    label: metric.label,
    value: typeof metric.value === "number" ? formatNumber(metric.value) : String(metric.value ?? ""),
    tone: metricToneToXlsxTone(metric.tone),
  }));
}

function metricToneToXlsxTone(tone: ReportMetric["tone"]): XlsxTone {
  if (tone === "danger") return "danger";
  if (tone === "warning") return "warning";
  if (tone === "positive") return "good";
  return "neutral";
}

function riskToTone(risk: ReportRow["riskLevel"]): XlsxTone {
  if (risk === "Critical") return "danger";
  if (risk === "High") return "warning";
  if (risk === "Medium") return "warning";
  return "good";
}

function buildReportCharts(
  report: ReportKind,
  rows: ReportRow[],
): Array<{ title: string; points: BarPoint[] }> {
  if (rows.length === 0) return [];

  if (report === "actions") {
    return [
      {
        title: "Priority distribution",
        points: priorityDistribution(rows),
      },
      {
        title: "Top cash-impact SKUs",
        points: topByNumber(rows, (row) => row.cashImpact, 8, (n) => currency(n)),
      },
    ];
  }
  if (report === "stockout") {
    return [
      {
        title: "Risk distribution",
        points: riskDistribution(rows),
      },
      {
        title: "Shortest runway SKUs",
        points: bottomByNumber(rows, (row) => row.daysLeft, 8, (n) => `${formatNumber(n)} d`).map(
          (point, idx) => ({ ...point, tone: idx < 3 ? "danger" : idx < 6 ? "warning" : "neutral" }),
        ),
      },
    ];
  }
  if (report === "dead-stock") {
    return [
      {
        title: "Status mix",
        points: statusDistribution(rows),
      },
      {
        title: "Largest capital stuck",
        points: topByNumber(rows, (row) => row.cashImpact, 8, (n) => currency(n)).map((point) => ({
          ...point,
          tone: "danger",
        })),
      },
    ];
  }
  // reorder
  return [
    {
      title: "Supplier exposure",
      points: vendorExposure(rows),
    },
    {
      title: "Critical reorder SKUs",
      points: bottomByNumber(rows, (row) => row.daysLeft, 8, (n) => `${formatNumber(n)} d`).map(
        (point, idx) => ({ ...point, tone: idx < 3 ? "danger" : "warning" }),
      ),
    },
  ];
}

function priorityDistribution(rows: ReportRow[]): BarPoint[] {
  const buckets = { Critical: 0, High: 0, Medium: 0, Low: 0 };
  rows.forEach((row) => {
    buckets[priorityBucket(row.priority) as keyof typeof buckets] += 1;
  });
  return [
    { label: "Critical", value: buckets.Critical, display: String(buckets.Critical), tone: "danger" },
    { label: "High", value: buckets.High, display: String(buckets.High), tone: "warning" },
    { label: "Medium", value: buckets.Medium, display: String(buckets.Medium), tone: "warning" },
    { label: "Low", value: buckets.Low, display: String(buckets.Low), tone: "good" },
  ];
}

function riskDistribution(rows: ReportRow[]): BarPoint[] {
  const buckets = { Critical: 0, High: 0, Medium: 0, Low: 0 };
  rows.forEach((row) => {
    buckets[row.riskLevel] += 1;
  });
  return [
    { label: "Critical", value: buckets.Critical, display: String(buckets.Critical), tone: "danger" },
    { label: "High", value: buckets.High, display: String(buckets.High), tone: "warning" },
    { label: "Medium", value: buckets.Medium, display: String(buckets.Medium), tone: "warning" },
    { label: "Low", value: buckets.Low, display: String(buckets.Low), tone: "good" },
  ];
}

function statusDistribution(rows: ReportRow[]): BarPoint[] {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    counts.set(row.status, (counts.get(row.status) ?? 0) + 1);
  });
  return [...counts.entries()]
    .sort(([, a], [, b]) => b - a)
    .map(([label, value]) => ({
      label,
      value,
      display: String(value),
      tone: label === "Dead stock" ? "danger" : label === "Overstock" ? "warning" : "neutral",
    }));
}

function vendorExposure(rows: ReportRow[]): BarPoint[] {
  const totals = new Map<string, number>();
  rows.forEach((row) => {
    const cost = row.estimatedCost ?? row.cashImpact ?? 0;
    totals.set(row.vendor, (totals.get(row.vendor) ?? 0) + cost);
  });
  return [...totals.entries()]
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([label, value]) => ({
      label,
      value,
      display: currency(value),
      tone: value >= 5000 ? "warning" : "neutral",
    }));
}

function topByNumber(
  rows: ReportRow[],
  pick: (row: ReportRow) => number | null,
  limit: number,
  format: (n: number) => string,
): BarPoint[] {
  return [...rows]
    .filter((row) => pick(row) !== null && Number.isFinite(pick(row) as number))
    .sort((a, b) => (pick(b) as number) - (pick(a) as number))
    .slice(0, limit)
    .map((row) => {
      const value = pick(row) as number;
      return {
        label: row.product,
        value,
        display: format(value),
        tone: "neutral",
      };
    });
}

function bottomByNumber(
  rows: ReportRow[],
  pick: (row: ReportRow) => number | null,
  limit: number,
  format: (n: number) => string,
): BarPoint[] {
  return [...rows]
    .filter((row) => pick(row) !== null && Number.isFinite(pick(row) as number))
    .sort((a, b) => (pick(a) as number) - (pick(b) as number))
    .slice(0, limit)
    .map((row) => {
      const value = pick(row) as number;
      // For "shortest runway" type charts the bar should grow with severity
      // (smaller days left = bigger bar), so use 1/(value+1) as the bar value
      // but show the actual days left in the display column.
      return {
        label: row.product,
        value: Math.max(1, 100 - value),
        display: format(value),
        tone: "neutral",
      };
    });
}

function buildXlsxColumns(report: ReportKind): XlsxColumn<ReportRow>[] {
  const product: XlsxColumn<ReportRow> = {
    key: "product",
    label: "Product",
    width: 32,
    format: (row) => row.product,
  };
  const sku: XlsxColumn<ReportRow> = {
    key: "sku",
    label: "SKU",
    width: 18,
    format: (row) => row.sku,
  };
  const vendor: XlsxColumn<ReportRow> = {
    key: "vendor",
    label: "Supplier",
    width: 18,
    format: (row) => row.vendor,
  };

  if (report === "actions") {
    return [
      {
        key: "priority",
        label: "Priority",
        align: "right",
        width: 11,
        format: (row) => formatNumber(row.priority),
        numericValue: (row) => row.priority,
        numFmt: "0",
        tone: (row) => (row.priority >= 80 ? "danger" : row.priority >= 60 ? "warning" : null),
      },
      {
        key: "actionType",
        label: "Action",
        width: 12,
        format: (row) => row.actionType,
        tone: (row) =>
          row.actionType === "Urgent"
            ? "danger"
            : row.actionType === "Dead"
              ? "danger"
              : row.actionType === "Optimize"
                ? "warning"
                : null,
      },
      product,
      sku,
      vendor,
      numCol("currentStock", "Current stock", 13, (r) => r.currentStock, "#,##0"),
      numCol("daysLeft", "Days left", 14, (r) => r.daysLeft, "#,##0"),
      numCol("leadTime", "Lead time", 11, (r) => r.leadTime, "#,##0"),
      numCol("recommendedQty", "Rec. qty", 11, (r) => r.recommendedQty, "#,##0"),
      moneyCol("cashImpact", "Cash impact", 14, (r) => r.cashImpact, (r) =>
        (r.cashImpact ?? 0) >= 1000 ? "good" : null,
      ),
      {
        key: "reason",
        label: "Reason",
        width: 60,
        format: (row) => row.reason,
      },
    ];
  }

  if (report === "stockout") {
    return [
      product,
      sku,
      vendor,
      numCol("currentStock", "Current stock", 13, (r) => r.currentStock, "#,##0"),
      numCol("salesLast30", "30-day sales", 13, (r) => r.salesLast30, "#,##0"),
      numCol("dailyVelocity", "Daily velocity", 13, (r) => r.dailyVelocity, "0.0"),
      numCol("daysLeft", "Days left", 11, (r) => r.daysLeft, "0.0"),
      numCol("leadTime", "Lead time", 11, (r) => r.leadTime, "#,##0"),
      { key: "estimatedStockoutDate", label: "Est. stockout", width: 14, format: (r) => r.estimatedStockoutDate },
      {
        key: "riskLevel",
        label: "Risk",
        width: 11,
        format: (r) => r.riskLevel,
        tone: (r) => riskToTone(r.riskLevel),
      },
      { key: "recommendedAction", label: "Recommended action", width: 50, format: (r) => r.recommendedAction },
    ];
  }

  if (report === "dead-stock") {
    return [
      product,
      sku,
      vendor,
      {
        key: "status",
        label: "Status",
        width: 13,
        format: (r) => r.status,
        tone: (r) =>
          r.status === "Dead stock" ? "danger" : r.status === "Overstock" ? "warning" : "warning",
      },
      numCol("currentStock", "Current stock", 13, (r) => r.currentStock, "#,##0"),
      moneyCol("inventoryValue", "Inventory value", 15, (r) => r.inventoryValue, null),
      numCol("daysSinceLastSale", "Days since sale", 14, (r) => r.daysSinceLastSale, "#,##0"),
      numCol("salesLast30", "Sales last 30", 13, (r) => r.salesLast30, "#,##0"),
      numCol("daysInventory", "Days of cover", 14, (r) => r.daysInventory, "0.0"),
      moneyCol("cashImpact", "Cash tied up", 14, (r) => r.cashImpact, () => "danger"),
      { key: "recommendedAction", label: "Recommended action", width: 50, format: (r) => r.recommendedAction },
    ];
  }

  // reorder
  return [
    product,
    sku,
    vendor,
    numCol("currentStock", "Current stock", 13, (r) => r.currentStock, "#,##0"),
    numCol("dailyVelocity", "Daily velocity", 13, (r) => r.dailyVelocity, "0.0"),
    numCol("leadTime", "Lead time", 11, (r) => r.leadTime, "#,##0"),
    numCol("targetCoverage", "Target cov.", 12, (r) => r.targetCoverage, "0.0"),
    numCol("recommendedQty", "Rec. qty", 11, (r) => r.recommendedQty, "#,##0"),
    moneyCol("estimatedCost", "Est. cost", 13, (r) => r.estimatedCost, (r) =>
      (r.estimatedCost ?? 0) >= 5000 ? "warning" : null,
    ),
    { key: "orderDeadline", label: "Order deadline", width: 14, format: (r) => r.orderDeadline },
    { key: "recommendedAction", label: "Status / action", width: 50, format: (r) => r.recommendedAction },
  ];
}

function numCol(
  key: string,
  label: string,
  width: number,
  pick: (r: ReportRow) => number | null,
  numFmt: string,
): XlsxColumn<ReportRow> {
  return {
    key,
    label,
    align: "right",
    width,
    format: (r) => formatNumber(pick(r)),
    numericValue: (r) => {
      const v = pick(r);
      return v !== null && Number.isFinite(v) ? v : null;
    },
    numFmt,
  };
}

function moneyCol(
  key: string,
  label: string,
  width: number,
  pick: (r: ReportRow) => number | null,
  tone: ((r: ReportRow) => XlsxTone | null) | null,
): XlsxColumn<ReportRow> {
  return {
    key,
    label,
    align: "right",
    width,
    format: (r) => (pick(r) === null ? "Unavailable" : currency(pick(r) ?? 0)),
    numericValue: (r) => {
      const v = pick(r);
      return v !== null && Number.isFinite(v) ? v : null;
    },
    numFmt: '"$"#,##0',
    tone: tone ?? undefined,
  };
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
