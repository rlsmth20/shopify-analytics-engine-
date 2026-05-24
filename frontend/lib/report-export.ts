"use client";

import type { InventoryAction } from "@/lib/api";
import type { LiquidationSuggestion, PurchaseOrderDraft } from "@/lib/api-v2";
import { currency } from "@/lib/api-v2";
import { getActionImpactValue, statusLabel } from "@/lib/app-helpers";

type ReportTableColumn<T> = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  format: (row: T) => string;
  tone?: (row: T) => string | null;
};

type ReportKpi = {
  label: string;
  value: string;
  note?: string;
  tone?: "neutral" | "good" | "warning" | "danger";
};

type BarPoint = {
  label: string;
  value: number;
  display: string;
  tone?: "neutral" | "good" | "warning" | "danger";
};

const LIQUIDATION_TACTIC_LABELS: Record<LiquidationSuggestion["tactic"], string> = {
  markdown: "Markdown",
  bundle: "Bundle",
  wholesale: "Wholesale",
  donate_write_off: "Write-off",
};

export function exportActionsReport(actions: InventoryAction[]): void {
  const totals = actions.reduce(
    (summary, action) => {
      summary.impact += getActionImpactValue(action);
      summary[action.status] += 1;
      return summary;
    },
    { urgent: 0, optimize: 0, dead: 0, impact: 0 }
  );

  downloadReport({
    title: "Inventory Action Report",
    subtitle: "Prioritized SKUs grouped by urgency, working-capital impact, and recommended next move.",
    filename: `inventory-actions-${todayStamp()}.xls`,
    kpis: [
      { label: "Actions", value: String(actions.length), note: "Visible queue" },
      { label: "Urgent", value: String(totals.urgent), tone: "danger" },
      { label: "Optimize", value: String(totals.optimize), tone: "warning" },
      { label: "Profit/cash impact", value: currency(totals.impact), tone: "good" },
    ],
    charts: [
      {
        title: "Action mix",
        points: [
          { label: "Urgent", value: totals.urgent, display: String(totals.urgent), tone: "danger" },
          { label: "Optimize", value: totals.optimize, display: String(totals.optimize), tone: "warning" },
          { label: "Dead", value: totals.dead, display: String(totals.dead), tone: "neutral" },
        ],
      },
      {
        title: "Top impact SKUs",
        points: [...actions]
          .sort((left, right) => getActionImpactValue(right) - getActionImpactValue(left))
          .slice(0, 8)
          .map((action) => ({
            label: action.name,
            value: getActionImpactValue(action),
            display: currency(getActionImpactValue(action)),
            tone:
              action.status === "urgent"
                ? "danger"
                : action.status === "optimize"
                  ? "warning"
                  : "neutral",
          })),
      },
    ],
    tableTitle: "Action Details",
    tableRows: actions,
    columns: [
      {
        key: "status",
        label: "Status",
        format: (action) => statusLabel[action.status],
        tone: (action) =>
          action.status === "urgent" ? "danger" : action.status === "optimize" ? "warning" : null,
      },
      { key: "sku", label: "SKU", format: (action) => action.name },
      {
        key: "on_hand",
        label: "On hand",
        align: "right",
        format: (action) => String(action.current_on_hand),
      },
      {
        key: "priority",
        label: "Priority",
        align: "right",
        format: (action) => action.priority_score.toFixed(2),
        tone: (action) =>
          action.priority_score >= 80 ? "danger" : action.priority_score >= 60 ? "warning" : null,
      },
      {
        key: "impact",
        label: "Impact",
        align: "right",
        format: (action) => currency(getActionImpactValue(action)),
        tone: (action) => (getActionImpactValue(action) >= 1000 ? "good" : null),
      },
      {
        key: "coverage",
        label: "Target days",
        align: "right",
        format: (action) => String(action.target_coverage_days),
      },
      { key: "recommendation", label: "Recommendation", format: (action) => action.recommended_action },
    ],
  });
}

export function exportLiquidationReport(suggestions: LiquidationSuggestion[]): void {
  const capitalTiedUp = suggestions.reduce((sum, item) => sum + item.capital_tied_up, 0);
  const projectedRecovery = suggestions.reduce(
    (sum, item) => sum + item.projected_recovered_capital,
    0
  );
  const tacticCounts = suggestions.reduce<Record<string, number>>((counts, item) => {
    counts[LIQUIDATION_TACTIC_LABELS[item.tactic]] =
      (counts[LIQUIDATION_TACTIC_LABELS[item.tactic]] ?? 0) + 1;
    return counts;
  }, {});

  downloadReport({
    title: "Liquidation Plan",
    subtitle: "Dead-stock recommendations with recovery estimates, markdown guidance, and tactic mix.",
    filename: `skubase-liquidation-plan-${todayStamp()}.xls`,
    kpis: [
      { label: "Dead SKUs", value: String(suggestions.length), tone: "danger" },
      { label: "Capital stuck", value: currency(capitalTiedUp), tone: "danger" },
      { label: "Projected recovery", value: currency(projectedRecovery), tone: "good" },
      {
        label: "Recovery rate",
        value: capitalTiedUp > 0 ? `${((projectedRecovery / capitalTiedUp) * 100).toFixed(0)}%` : "0%",
      },
    ],
    charts: [
      {
        title: "Tactic mix",
        points: Object.entries(tacticCounts).map(([label, value]) => ({
          label,
          value,
          display: String(value),
          tone: label === "Write-off" ? "danger" : label === "Markdown" ? "warning" : "neutral",
        })),
      },
      {
        title: "Largest recovery opportunities",
        points: [...suggestions]
          .sort((left, right) => right.projected_recovered_capital - left.projected_recovered_capital)
          .slice(0, 8)
          .map((item) => ({
            label: item.name,
            value: item.projected_recovered_capital,
            display: currency(item.projected_recovered_capital),
            tone: item.tactic === "donate_write_off" ? "danger" : "good",
          })),
      },
    ],
    tableTitle: "Markdown Plan",
    tableRows: suggestions,
    columns: [
      { key: "sku", label: "SKU", format: (item) => item.name },
      {
        key: "tactic",
        label: "Tactic",
        format: (item) => LIQUIDATION_TACTIC_LABELS[item.tactic],
        tone: (item) =>
          item.tactic === "donate_write_off"
            ? "danger"
            : item.tactic === "markdown"
              ? "warning"
              : "good",
      },
      { key: "on_hand", label: "On hand", align: "right", format: (item) => String(item.on_hand) },
      {
        key: "days",
        label: "Days stale",
        align: "right",
        format: (item) => (item.days_since_last_sale >= 999 ? "No sales" : String(item.days_since_last_sale)),
        tone: (item) => (item.days_since_last_sale >= 365 ? "danger" : item.days_since_last_sale >= 180 ? "warning" : null),
      },
      {
        key: "markdown",
        label: "Markdown",
        align: "right",
        format: (item) => `${item.suggested_markdown_pct.toFixed(0)}%`,
        tone: (item) => (item.suggested_markdown_pct >= 50 ? "danger" : item.suggested_markdown_pct >= 25 ? "warning" : null),
      },
      { key: "price", label: "Suggested price", align: "right", format: (item) => currency(item.suggested_price) },
      { key: "stuck", label: "Capital stuck", align: "right", format: (item) => currency(item.capital_tied_up), tone: () => "danger" },
      { key: "recovery", label: "Recovery", align: "right", format: (item) => currency(item.projected_recovered_capital), tone: () => "good" },
    ],
  });
}

export function exportPurchaseOrderReport(po: PurchaseOrderDraft): void {
  downloadReport({
    title: `${po.po_id} Purchase Order`,
    subtitle: `${po.vendor} - expected arrival ${po.expected_arrival_date}. ${po.rationale}`,
    filename: `${po.po_id.toLowerCase()}-${slugify(po.vendor)}-${todayStamp()}.xls`,
    kpis: [
      { label: "Vendor", value: po.vendor },
      { label: "Lines", value: String(po.lines.length) },
      { label: "Total cost", value: currency(po.total_cost), tone: "warning" },
      { label: "Status", value: po.status },
    ],
    charts: [
      {
        title: "Cost by line",
        points: [...po.lines]
          .sort((left, right) => right.extended_cost - left.extended_cost)
          .map((line) => ({
            label: line.name,
            value: line.extended_cost,
            display: currency(line.extended_cost),
            tone: line.extended_cost >= 1000 ? "warning" : "neutral",
          })),
      },
    ],
    tableTitle: "PO Lines",
    tableRows: po.lines,
    columns: [
      { key: "sku", label: "SKU", format: (line) => line.name },
      { key: "qty", label: "Qty", align: "right", format: (line) => String(line.qty) },
      { key: "unit", label: "Unit cost", align: "right", format: (line) => currency(line.unit_cost) },
      {
        key: "extended",
        label: "Extended",
        align: "right",
        format: (line) => currency(line.extended_cost),
        tone: (line) => (line.extended_cost >= 1000 ? "warning" : null),
      },
    ],
  });
}

function downloadReport<T>({
  title,
  subtitle,
  filename,
  kpis,
  charts,
  tableTitle,
  tableRows,
  columns,
}: {
  title: string;
  subtitle: string;
  filename: string;
  kpis: ReportKpi[];
  charts: Array<{ title: string; points: BarPoint[] }>;
  tableTitle: string;
  tableRows: T[];
  columns: ReportTableColumn<T>[];
}): void {
  const html = buildReportHtml({
    title,
    subtitle,
    generatedAt: new Date().toLocaleString(),
    kpis,
    charts,
    tableTitle,
    tableRows,
    columns,
  });
  const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

function buildReportHtml<T>({
  title,
  subtitle,
  generatedAt,
  kpis,
  charts,
  tableTitle,
  tableRows,
  columns,
}: {
  title: string;
  subtitle: string;
  generatedAt: string;
  kpis: ReportKpi[];
  charts: Array<{ title: string; points: BarPoint[] }>;
  tableTitle: string;
  tableRows: T[];
  columns: ReportTableColumn<T>[];
}): string {
  const kpiCells = kpis.map(renderKpiCell).join("");
  const chartSections = charts.map(renderChartRows).join("");
  const headerCells = columns
    .map((column) => `<th class="${column.align ?? "left"}">${escapeHtml(column.label)}</th>`)
    .join("");
  const bodyRows = tableRows
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => {
            const tone = column.tone?.(row);
            return `<td class="${column.align ?? "left"} ${tone ? `cell-${tone}` : ""}">${escapeHtml(column.format(row))}</td>`;
          })
          .join("")}</tr>`
    )
    .join("");

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>${reportCss()}</style>
</head>
<body>
  <table class="sheet">
    <colgroup>
      <col class="w-label"><col class="w-value"><col class="w-label"><col class="w-value">
      <col class="w-label"><col class="w-value"><col class="w-label"><col class="w-value">
    </colgroup>
    <tr><td class="brand" colspan="6">skubase export</td><td class="generated" colspan="2">Generated<br><strong>${escapeHtml(generatedAt)}</strong></td></tr>
    <tr><td class="title" colspan="8">${escapeHtml(title)}</td></tr>
    <tr><td class="subtitle" colspan="8">${escapeHtml(subtitle)}</td></tr>
    <tr class="spacer"><td colspan="8"></td></tr>
    <tr>${kpiCells}</tr>
    <tr class="spacer"><td colspan="8"></td></tr>
    ${chartSections}
    <tr class="spacer"><td colspan="8"></td></tr>
    <tr><td class="section-title" colspan="8">${escapeHtml(tableTitle)}</td></tr>
    <tr>${headerCells}</tr>
    ${bodyRows}
  </table>
</body>
</html>`;
}

function renderKpiCell(kpi: ReportKpi): string {
  return `<td class="kpi kpi-${kpi.tone ?? "neutral"}" colspan="2">
    <div class="kpi-label">${escapeHtml(kpi.label)}</div>
    <div class="kpi-value">${escapeHtml(kpi.value)}</div>
    ${kpi.note ? `<div class="kpi-note">${escapeHtml(kpi.note)}</div>` : ""}
  </td>`;
}

function renderChartRows(chart: { title: string; points: BarPoint[] }): string {
  const max = Math.max(...chart.points.map((point) => point.value), 1);
  return `<tr><td class="section-title" colspan="8">${escapeHtml(chart.title)}</td></tr>
    ${chart.points
      .map((point) => {
        const filled = Math.max(1, Math.round((point.value / max) * 4));
        const empty = 4 - filled;
        return `<tr>
          <td class="bar-label" colspan="2">${escapeHtml(point.label)}</td>
          ${Array.from({ length: filled })
            .map(() => `<td class="bar-fill bar-${point.tone ?? "neutral"}"></td>`)
            .join("")}
          ${Array.from({ length: empty })
            .map(() => `<td class="bar-empty"></td>`)
            .join("")}
          <td class="bar-value" colspan="2">${escapeHtml(point.display)}</td>
        </tr>`;
      })
      .join("")}
    <tr class="mini-spacer"><td colspan="8"></td></tr>`;
}

function reportCss(): string {
  return `
    body{margin:0;background:#f4f7fb;color:#0f172a;font-family:Segoe UI,Arial,sans-serif;font-size:12px}
    .sheet{width:1180px;margin:24px;border-collapse:collapse;background:#ffffff}
    .w-label{width:170px}.w-value{width:125px}
    td,th{border:1px solid #dbe3ef;padding:10px 12px;vertical-align:middle}
    .brand{background:#0f172a;color:#ffffff;font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
    .generated{background:#0f172a;color:#cbd5e1;text-align:right;font-size:11px}.generated strong{color:#ffffff}
    .title{background:#0f172a;color:#ffffff;font-size:28px;font-weight:800;line-height:1.15;padding-top:18px;border-top:0}
    .subtitle{background:#0f172a;color:#cbd5e1;font-size:13px;padding-bottom:18px;border-top:0}
    .spacer td{height:14px;background:#f4f7fb;border-color:#f4f7fb}.mini-spacer td{height:8px;background:#ffffff;border-left-color:#ffffff;border-right-color:#ffffff}
    .kpi{background:#ffffff}.kpi-label{color:#64748b;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.kpi-value{margin-top:6px;font-size:22px;font-weight:800}.kpi-note{margin-top:4px;color:#64748b}
    .kpi-good{background:#dff7ef!important}.kpi-warning{background:#fff3cf!important}.kpi-danger{background:#fee2e2!important}
    .section-title{background:#eef4ff!important;color:#0f172a;font-size:16px;font-weight:800}
    .bar-label{font-weight:700}.bar-empty{background:#edf2f7!important}.bar-fill{background:#2563eb!important}.bar-good{background:#0f766e!important}.bar-warning{background:#b45309!important}.bar-danger{background:#b91c1c!important}.bar-value{text-align:right;color:#0f172a;font-weight:800}
    th{background:#dbeafe;color:#334155;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}
    tr:nth-child(even) td{background:#f8fbff}.right{text-align:right}.center{text-align:center}.left{text-align:left}
    .cell-good{background:#dff7ef!important;color:#065f46;font-weight:800}.cell-warning{background:#fff3cf!important;color:#92400e;font-weight:800}.cell-danger{background:#fee2e2!important;color:#991b1b;font-weight:800}
  `;
}

function todayStamp(): string {
  return new Date().toISOString().slice(0, 10);
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
