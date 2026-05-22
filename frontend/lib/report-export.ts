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
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>${reportCss()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <p class="eyebrow">skubase export</p>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(subtitle)}</p>
      </div>
      <div class="generated">Generated<br><strong>${escapeHtml(generatedAt)}</strong></div>
    </section>
    <section class="kpis">${kpis.map(renderKpi).join("")}</section>
    <section class="charts">${charts.map(renderChart).join("")}</section>
    <section class="table-card">
      <h2>${escapeHtml(tableTitle)}</h2>
      <table>
        <thead><tr>${columns.map((column) => `<th class="${column.align ?? "left"}">${escapeHtml(column.label)}</th>`).join("")}</tr></thead>
        <tbody>
          ${tableRows
            .map(
              (row) =>
                `<tr>${columns
                  .map((column) => {
                    const tone = column.tone?.(row);
                    return `<td class="${column.align ?? "left"} ${tone ? `cell-${tone}` : ""}">${escapeHtml(column.format(row))}</td>`;
                  })
                  .join("")}</tr>`
            )
            .join("")}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>`;
}

function renderKpi(kpi: ReportKpi): string {
  return `<article class="kpi kpi-${kpi.tone ?? "neutral"}">
    <p>${escapeHtml(kpi.label)}</p>
    <strong>${escapeHtml(kpi.value)}</strong>
    ${kpi.note ? `<span>${escapeHtml(kpi.note)}</span>` : ""}
  </article>`;
}

function renderChart(chart: { title: string; points: BarPoint[] }): string {
  const max = Math.max(...chart.points.map((point) => point.value), 1);
  return `<article class="chart-card">
    <h2>${escapeHtml(chart.title)}</h2>
    <div class="bar-list">
      ${chart.points
        .map((point) => {
          const width = Math.max(4, Math.round((point.value / max) * 100));
          return `<div class="bar-row">
            <div class="bar-label">${escapeHtml(point.label)}</div>
            <div class="bar-track"><span class="bar-fill bar-${point.tone ?? "neutral"}" style="width:${width}%"></span></div>
            <div class="bar-value">${escapeHtml(point.display)}</div>
          </div>`;
        })
        .join("")}
    </div>
  </article>`;
}

function reportCss(): string {
  return `
    :root{--ink:#0f172a;--muted:#64748b;--line:#dbe3ef;--bg:#f4f7fb;--card:#fff;--good:#0f766e;--good-bg:#dff7ef;--warn:#b45309;--warn-bg:#fff3cf;--danger:#b91c1c;--danger-bg:#fee2e2;--blue:#1d4ed8;--blue-bg:#dbeafe}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif;font-size:14px;line-height:1.45} main{max-width:1180px;margin:0 auto;padding:36px 28px 48px}
    .hero,.kpi,.chart-card,.table-card{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 16px 40px rgba(15,23,42,.08)}
    .hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;padding:28px}.eyebrow{margin:0 0 10px;color:var(--blue);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase} h1{margin:0;font-size:34px;line-height:1.05} .hero p:not(.eyebrow){max-width:760px;color:var(--muted)}.generated{text-align:right;color:var(--muted);white-space:nowrap}.generated strong{color:var(--ink)}
    .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:18px}.kpi{padding:18px}.kpi p{margin:0;color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.kpi strong{display:block;margin-top:10px;font-size:28px}.kpi span{display:block;margin-top:8px;color:var(--muted)}.kpi-good{background:linear-gradient(180deg,#fff,var(--good-bg))}.kpi-warning{background:linear-gradient(180deg,#fff,var(--warn-bg))}.kpi-danger{background:linear-gradient(180deg,#fff,var(--danger-bg))}
    .charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:18px}.chart-card{padding:22px}.chart-card h2,.table-card h2{margin:0 0 16px;font-size:18px}.bar-list{display:grid;gap:12px}.bar-row{display:grid;grid-template-columns:minmax(160px,1fr) 3fr 90px;gap:12px;align-items:center}.bar-label{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bar-track{height:14px;border-radius:999px;background:#e8eef7;overflow:hidden}.bar-fill{display:block;height:100%;border-radius:inherit;background:var(--blue)}.bar-good{background:var(--good)}.bar-warning{background:var(--warn)}.bar-danger{background:var(--danger)}.bar-value{text-align:right;font-variant-numeric:tabular-nums;color:var(--muted)}
    .table-card{margin-top:18px;padding:22px;overflow:auto}table{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border:1px solid var(--line);border-radius:12px}th,td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:#eef4ff;color:#334155;font-size:12px;text-transform:uppercase;letter-spacing:.08em}tr:nth-child(even) td{background:#f8fbff}tr:last-child td{border-bottom:0}.right{text-align:right}.center{text-align:center}.cell-good{background:var(--good-bg)!important;color:#065f46;font-weight:800}.cell-warning{background:var(--warn-bg)!important;color:#92400e;font-weight:800}.cell-danger{background:var(--danger-bg)!important;color:#991b1b;font-weight:800}
    @media print{body{background:#fff}main{padding:0}.hero,.kpi,.chart-card,.table-card{box-shadow:none}.generated{display:none}}
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
