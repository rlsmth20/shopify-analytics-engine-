"use client";

import type { InventoryAction } from "@/lib/api";
import { currency, type LiquidationSuggestion, type PurchaseOrderDraft } from "@/lib/api-v2";
import { getActionImpactValue, statusLabel } from "@/lib/app-helpers";

// ExcelJS is loaded dynamically only when an export is triggered so the
// ~800kB library is never bundled into the initial page payload.
type AnyExcel = typeof import("exceljs");
let excelModulePromise: Promise<AnyExcel> | null = null;
async function loadExcel(): Promise<AnyExcel> {
  if (!excelModulePromise) excelModulePromise = import("exceljs");
  return excelModulePromise;
}

// ---------------------------------------------------------------------------
// Design system
// ---------------------------------------------------------------------------
const COLOR_BRAND = "FF0F172A";
const COLOR_BRAND_INK = "FFFFFFFF";
const COLOR_BRAND_MUTED = "FFCBD5E1";
const COLOR_PAGE_BG = "FFF4F7FB";
const COLOR_PANEL_BG = "FFFFFFFF";
const COLOR_BORDER = "FFDBE3EF";
const COLOR_SECTION_BG = "FFEEF4FF";
const COLOR_HEADER_BG = "FFDBEAFE";
const COLOR_HEADER_INK = "FF334155";
const COLOR_ALT_ROW = "FFF8FBFF";

const TONE_FILL: Record<string, string> = {
  good: "FFDFF7EF",
  warning: "FFFFF3CF",
  danger: "FFFEE2E2",
  neutral: "FFFFFFFF",
};
const TONE_INK: Record<string, string> = {
  good: "FF065F46",
  warning: "FF92400E",
  danger: "FF991B1B",
  neutral: "FF0F172A",
};
const TONE_ACCENT: Record<string, string> = {
  good: "FF0F766E",
  warning: "FFB45309",
  danger: "FFB91C1C",
  neutral: "FF2563EB",
};

const FONT_BASE = "Calibri";
const FONT_DISPLAY = "Calibri";

export type Tone = "neutral" | "good" | "warning" | "danger";

export type ReportTableColumn<T> = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: number;
  format: (row: T) => string;
  numericValue?: (row: T) => number | null;
  tone?: (row: T) => Tone | null;
  numFmt?: string;
  // "sum" renders a styled totals row at the bottom of the detail sheet.
  summarize?: "sum";
};

// Extra data tabs beyond the main detail sheet. Types are erased so one
// workbook can carry differently-shaped tables; build them with sheetOf().
export type AnyReportSheet = {
  sheetName: string;
  tableTitle: string;
  rows: unknown[];
  columns: ReportTableColumn<unknown>[];
};

export function sheetOf<T>(spec: {
  sheetName: string;
  tableTitle: string;
  rows: T[];
  columns: ReportTableColumn<T>[];
}): AnyReportSheet {
  return spec as unknown as AnyReportSheet;
}

export type ReportKpi = {
  label: string;
  value: string;
  note?: string;
  tone?: Tone;
};

export type BarPoint = {
  label: string;
  value: number;
  display: string;
  tone?: Tone;
};

export type ReportTodo = {
  label: string;
  detail?: string;
  tone?: Tone;
};

const LIQUIDATION_TACTIC_LABELS: Record<LiquidationSuggestion["tactic"], string> = {
  markdown: "Markdown",
  bundle: "Bundle",
  wholesale: "Wholesale",
  donate_write_off: "Write-off",
};

// ---------------------------------------------------------------------------
// Public exports — dedicated report exporters
// ---------------------------------------------------------------------------
export async function exportActionsReport(actions: InventoryAction[]): Promise<void> {
  const totals = actions.reduce(
    (summary, action) => {
      summary.impact += getActionImpactValue(action);
      summary[action.status] += 1;
      return summary;
    },
    { urgent: 0, optimize: 0, dead: 0, impact: 0 }
  );

  await buildWorkbook({
    title: "Inventory Action Report",
    subtitle:
      "Prioritized SKUs grouped by urgency, working-capital impact, and recommended next move.",
    filename: `skubase-inventory-actions-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "Actions",
    kpis: [
      { label: "Actions", value: String(actions.length), note: "Visible queue" },
      { label: "Urgent", value: String(totals.urgent), tone: "danger" },
      { label: "Optimize", value: String(totals.optimize), tone: "warning" },
      { label: "Profit / cash impact", value: currency(totals.impact), tone: "good" },
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
          .sort((l, r) => getActionImpactValue(r) - getActionImpactValue(l))
          .slice(0, 8)
          .map((action) => ({
            label: action.name,
            value: getActionImpactValue(action),
            display: currency(getActionImpactValue(action)),
            tone: (action.status === "urgent"
              ? "danger"
              : action.status === "optimize"
                ? "warning"
                : "neutral") as Tone,
          })),
      },
    ],
    todos: [
      { label: "Start with urgent SKUs", detail: "Review every critical stockout action before optimization work.", tone: "danger" },
      { label: "Turn reorder actions into POs", detail: "Use the purchase order workflow for high-priority replenishment.", tone: "warning" },
      { label: "Clear dead-stock cash", detail: "Move stale SKUs into liquidation or bundle review.", tone: "good" },
    ],
    tableTitle: "Action Details",
    tableRows: actions,
    columns: [
      {
        key: "status",
        label: "Status",
        width: 14,
        format: (action) => statusLabel[action.status],
        tone: (action) =>
          action.status === "urgent" ? "danger" : action.status === "optimize" ? "warning" : null,
      },
      { key: "sku", label: "SKU", width: 34, format: (action) => action.name },
      {
        key: "on_hand",
        label: "On hand",
        align: "right",
        width: 12,
        format: (action) => String(action.current_on_hand),
        numericValue: (action) => action.current_on_hand,
        numFmt: "#,##0",
      },
      {
        key: "priority",
        label: "Priority",
        align: "right",
        width: 12,
        format: (action) => action.priority_score.toFixed(2),
        numericValue: (action) => action.priority_score,
        numFmt: "0.00",
        tone: (action) =>
          action.priority_score >= 80 ? "danger" : action.priority_score >= 60 ? "warning" : null,
      },
      {
        key: "impact",
        label: "Impact",
        align: "right",
        width: 16,
        format: (action) => currency(getActionImpactValue(action)),
        numericValue: (action) => getActionImpactValue(action),
        numFmt: '"$"#,##0',
        tone: (action) => (getActionImpactValue(action) >= 1000 ? "good" : null),
        summarize: "sum",
      },
      {
        key: "coverage",
        label: "Target days",
        align: "right",
        width: 14,
        format: (action) => String(action.target_coverage_days),
        numericValue: (action) => action.target_coverage_days,
        numFmt: "#,##0",
      },
      {
        key: "recommendation",
        label: "Recommendation",
        width: 60,
        format: (action) => action.recommended_action,
      },
    ],
  });
}

export async function exportLiquidationReport(
  suggestions: LiquidationSuggestion[]
): Promise<void> {
  const capitalTiedUp = suggestions.reduce((sum, item) => sum + item.capital_tied_up, 0);
  const projectedRecovery = suggestions.reduce(
    (sum, item) => sum + item.projected_recovered_capital,
    0
  );
  const tacticCounts = suggestions.reduce<Record<string, number>>((counts, item) => {
    const label = LIQUIDATION_TACTIC_LABELS[item.tactic];
    counts[label] = (counts[label] ?? 0) + 1;
    return counts;
  }, {});

  await buildWorkbook({
    title: "Liquidation Plan",
    subtitle: "Dead-stock recommendations with recovery estimates, markdown guidance, and tactic mix.",
    filename: `skubase-liquidation-plan-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "Plan",
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
          tone: (label === "Write-off"
            ? "danger"
            : label === "Markdown"
              ? "warning"
              : "neutral") as Tone,
        })),
      },
      {
        title: "Largest recovery opportunities",
        points: [...suggestions]
          .sort((l, r) => r.projected_recovered_capital - l.projected_recovered_capital)
          .slice(0, 8)
          .map((item) => ({
            label: item.name,
            value: item.projected_recovered_capital,
            display: currency(item.projected_recovered_capital),
            tone: (item.tactic === "donate_write_off" ? "danger" : "good") as Tone,
          })),
      },
    ],
    todos: [
      { label: "Tackle largest recovery opportunities", detail: "Start with SKUs tying up the most capital.", tone: "danger" },
      { label: "Choose the right clearance tactic", detail: "Markdown, bundle, wholesale, or write-off based on margin and age.", tone: "warning" },
      { label: "Recheck after the promotion window", detail: "Compare recovered capital against the plan before cutting deeper.", tone: "good" },
    ],
    tableTitle: "Markdown Plan",
    tableRows: suggestions,
    columns: [
      { key: "sku", label: "SKU", width: 34, format: (item) => item.name },
      {
        key: "tactic",
        label: "Tactic",
        width: 14,
        format: (item) => LIQUIDATION_TACTIC_LABELS[item.tactic],
        tone: (item) =>
          item.tactic === "donate_write_off"
            ? "danger"
            : item.tactic === "markdown"
              ? "warning"
              : "good",
      },
      {
        key: "on_hand",
        label: "On hand",
        align: "right",
        width: 12,
        format: (item) => String(item.on_hand),
        numericValue: (item) => item.on_hand,
        numFmt: "#,##0",
      },
      {
        key: "days",
        label: "Days stale",
        align: "right",
        width: 13,
        format: (item) =>
          item.days_since_last_sale >= 999 ? "No sales" : String(item.days_since_last_sale),
        numericValue: (item) =>
          item.days_since_last_sale >= 999 ? null : item.days_since_last_sale,
        numFmt: "#,##0",
        tone: (item) =>
          item.days_since_last_sale >= 365
            ? "danger"
            : item.days_since_last_sale >= 180
              ? "warning"
              : null,
      },
      {
        key: "markdown",
        label: "Markdown",
        align: "right",
        width: 12,
        format: (item) => `${item.suggested_markdown_pct.toFixed(0)}%`,
        numericValue: (item) => item.suggested_markdown_pct / 100,
        numFmt: "0%",
        tone: (item) =>
          item.suggested_markdown_pct >= 50
            ? "danger"
            : item.suggested_markdown_pct >= 25
              ? "warning"
              : null,
      },
      {
        key: "price",
        label: "Suggested price",
        align: "right",
        width: 16,
        format: (item) => currency(item.suggested_price),
        numericValue: (item) => item.suggested_price,
        numFmt: '"$"#,##0.00',
      },
      {
        key: "stuck",
        label: "Capital stuck",
        align: "right",
        width: 16,
        format: (item) => currency(item.capital_tied_up),
        numericValue: (item) => item.capital_tied_up,
        numFmt: '"$"#,##0',
        tone: () => "danger",
        summarize: "sum",
      },
      {
        key: "recovery",
        label: "Recovery",
        align: "right",
        width: 16,
        format: (item) => currency(item.projected_recovered_capital),
        numericValue: (item) => item.projected_recovered_capital,
        numFmt: '"$"#,##0',
        tone: () => "good",
        summarize: "sum",
      },
    ],
  });
}

export async function exportPurchaseOrderReport(po: PurchaseOrderDraft): Promise<void> {
  await buildWorkbook({
    title: `${po.po_id} - Purchase Order`,
    subtitle: `${po.vendor} - expected arrival ${po.expected_arrival_date}. ${po.rationale}`,
    filename: `skubase-${po.po_id.toLowerCase()}-${slugify(po.vendor)}-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "Lines",
    kpis: [
      { label: "Supplier", value: po.vendor },
      { label: "Lines", value: String(po.lines.length) },
      { label: "Subtotal", value: currency(po.subtotal_cost), tone: "neutral" },
      { label: "Shipping", value: currency(po.shipping_cost), tone: "warning" },
      { label: "Total landed cost", value: currency(po.total_cost), tone: "warning" },
    ],
    charts: [
      {
        title: "Cost by line",
        points: [...po.lines]
          .sort((l, r) => r.extended_cost - l.extended_cost)
          .slice(0, 12)
          .map((line) => ({
            label: line.name,
            value: line.extended_cost,
            display: currency(line.extended_cost),
            tone: (line.extended_cost >= 1000 ? "warning" : "neutral") as Tone,
          })),
      },
    ],
    todos: [
      { label: "Approve the PO", detail: "Confirm quantities, costs, and expected arrival before sending.", tone: "warning" },
      { label: "Open vendor email draft", detail: "Use the exported line detail or the PO page email draft to contact the supplier.", tone: "good" },
      { label: "Record receipts", detail: "Receiving history powers supplier scorecards and lead-time confidence.", tone: "neutral" },
    ],
    tableTitle: "PO Lines",
    tableRows: po.lines,
    columns: [
      { key: "sku", label: "SKU", width: 36, format: (line) => line.name },
      {
        key: "qty",
        label: "Qty",
        align: "right",
        width: 10,
        format: (line) => String(line.qty),
        numericValue: (line) => line.qty,
        numFmt: "#,##0",
        summarize: "sum",
      },
      {
        key: "unit",
        label: "Unit cost",
        align: "right",
        width: 14,
        format: (line) => currency(line.unit_cost),
        numericValue: (line) => line.unit_cost,
        numFmt: '"$"#,##0.00',
      },
      {
        key: "extended",
        label: "Extended",
        align: "right",
        width: 16,
        format: (line) => currency(line.extended_cost),
        numericValue: (line) => line.extended_cost,
        numFmt: '"$"#,##0.00',
        tone: (line) => (line.extended_cost >= 1000 ? "warning" : null),
        summarize: "sum",
      },
    ],
  });
}

export async function exportBuyPlanReport(drafts: PurchaseOrderDraft[]): Promise<void> {
  const totalCapital = drafts.reduce((sum, po) => sum + po.total_cost, 0);
  const totalLines = drafts.reduce((sum, po) => sum + po.lines.length, 0);
  const totalUnits = drafts.reduce(
    (sum, po) => sum + po.lines.reduce((lineSum, line) => lineSum + line.qty, 0),
    0,
  );
  const allLines = drafts.flatMap((po) =>
    po.lines.map((line) => ({ po_id: po.po_id, vendor: po.vendor, ...line })),
  );

  await buildWorkbook({
    title: "Reorder Buy Plan",
    subtitle:
      "Every supplier purchase order draft in one workbook - share with your team or your suppliers.",
    filename: `skubase-buy-plan-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "POs by supplier",
    kpis: [
      { label: "Purchase orders", value: String(drafts.length) },
      { label: "Lines", value: String(totalLines) },
      { label: "Units", value: totalUnits.toLocaleString() },
      { label: "Total capital required", value: currency(totalCapital), tone: "warning" },
    ],
    charts: [
      {
        title: "Capital by supplier",
        points: [...drafts]
          .sort((l, r) => r.total_cost - l.total_cost)
          .slice(0, 8)
          .map((po) => ({
            label: po.vendor,
            value: po.total_cost,
            display: currency(po.total_cost),
            tone: (po.total_cost >= totalCapital / Math.max(drafts.length, 1)
              ? "warning"
              : "neutral") as Tone,
          })),
      },
    ],
    todos: [
      { label: "Approve urgent POs first", detail: "Start with suppliers covering SKUs at or below their reorder point.", tone: "danger" },
      { label: "Send each PO to its supplier", detail: "Use the per-PO export or email draft from the Purchase Orders page.", tone: "warning" },
      { label: "Record receipts when stock arrives", detail: "Receipt history powers supplier scorecards and lead-time confidence.", tone: "good" },
    ],
    tableTitle: "Purchase Orders",
    tableRows: drafts,
    columns: [
      { key: "po", label: "PO", width: 20, format: (po) => po.po_id },
      { key: "vendor", label: "Supplier", width: 26, format: (po) => po.vendor },
      {
        key: "lines",
        label: "Lines",
        align: "right",
        width: 10,
        format: (po) => String(po.lines.length),
        numericValue: (po) => po.lines.length,
        numFmt: "#,##0",
        summarize: "sum",
      },
      { key: "arrival", label: "Expected arrival", width: 18, format: (po) => po.expected_arrival_date },
      { key: "status", label: "Status", width: 14, format: (po) => po.status ?? "draft" },
      {
        key: "subtotal",
        label: "Items",
        align: "right",
        width: 14,
        format: (po) => currency(po.subtotal_cost),
        numericValue: (po) => po.subtotal_cost,
        numFmt: '"$"#,##0',
        summarize: "sum",
      },
      {
        key: "shipping",
        label: "Shipping",
        align: "right",
        width: 12,
        format: (po) => currency(po.shipping_cost),
        numericValue: (po) => po.shipping_cost,
        numFmt: '"$"#,##0',
        summarize: "sum",
      },
      {
        key: "total",
        label: "Total",
        align: "right",
        width: 14,
        format: (po) => currency(po.total_cost),
        numericValue: (po) => po.total_cost,
        numFmt: '"$"#,##0',
        tone: (po) => (po.total_cost >= 2500 ? "warning" : null),
        summarize: "sum",
      },
      { key: "rationale", label: "Rationale", width: 60, format: (po) => po.rationale },
    ],
    extraSheets: [
      sheetOf({
        sheetName: "All lines",
        tableTitle: "Every Line, Every Supplier",
        rows: allLines,
        columns: [
          { key: "po", label: "PO", width: 20, format: (line) => line.po_id },
          { key: "vendor", label: "Supplier", width: 24, format: (line) => line.vendor },
          { key: "sku", label: "SKU", width: 36, format: (line) => line.name },
          {
            key: "qty",
            label: "Qty",
            align: "right",
            width: 10,
            format: (line) => String(line.qty),
            numericValue: (line) => line.qty,
            numFmt: "#,##0",
            summarize: "sum",
          },
          {
            key: "unit",
            label: "Unit cost",
            align: "right",
            width: 14,
            format: (line) => currency(line.unit_cost),
            numericValue: (line) => line.unit_cost,
            numFmt: '"$"#,##0.00',
          },
          {
            key: "extended",
            label: "Extended",
            align: "right",
            width: 16,
            format: (line) => currency(line.extended_cost),
            numericValue: (line) => line.extended_cost,
            numFmt: '"$"#,##0.00',
            summarize: "sum",
          },
        ],
      }),
    ],
  });
}

// ---------------------------------------------------------------------------
// Generic formatted workbook exporter — drives the /reports page output.
// Callers supply KPIs, charts, and column structure; the same buildWorkbook
// used by the dedicated exporters above produces the polished xlsx.
// ---------------------------------------------------------------------------
export async function exportFormattedReport<T>(spec: {
  title: string;
  subtitle: string;
  filename: string;
  summarySheetName?: string;
  detailSheetName?: string;
  kpis: ReportKpi[];
  charts: Array<{ title: string; points: BarPoint[] }>;
  todos?: ReportTodo[];
  tableTitle: string;
  rows: T[];
  columns: ReportTableColumn<T>[];
  extraSheets?: AnyReportSheet[];
}): Promise<void> {
  await buildWorkbook({
    title: spec.title,
    subtitle: spec.subtitle,
    filename: spec.filename,
    summarySheetName: spec.summarySheetName ?? "Summary",
    detailSheetName: spec.detailSheetName ?? "Detail",
    kpis: spec.kpis,
    charts: spec.charts,
    todos: spec.todos ?? defaultTodos(spec.title),
    tableTitle: spec.tableTitle,
    tableRows: spec.rows,
    columns: spec.columns,
    extraSheets: spec.extraSheets,
  });
}

// ---------------------------------------------------------------------------
// Legacy CSV exporter — kept for back-compat with any caller still wired up.
// ---------------------------------------------------------------------------
export type CsvColumn<T> = {
  label: string;
  value: (row: T) => string | number | null | undefined;
};

export function exportReportRowsCsv<T>({
  filename,
  columns,
  rows,
}: {
  filename: string;
  columns: CsvColumn<T>[];
  rows: T[];
}): void {
  const csv = [
    columns.map((c) => escapeCsv(c.label)).join(","),
    ...rows.map((row) => columns.map((c) => escapeCsv(c.value(row) ?? "")).join(",")),
  ].join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => window.URL.revokeObjectURL(url), 2000);
}

// ---------------------------------------------------------------------------
// Workbook builder
// ---------------------------------------------------------------------------
type WorkbookSpec<T> = {
  title: string;
  subtitle: string;
  filename: string;
  summarySheetName: string;
  detailSheetName: string;
  kpis: ReportKpi[];
  charts: Array<{ title: string; points: BarPoint[] }>;
  todos: ReportTodo[];
  tableTitle: string;
  tableRows: T[];
  columns: ReportTableColumn<T>[];
  extraSheets?: AnyReportSheet[];
};

async function buildWorkbook<T>(spec: WorkbookSpec<T>): Promise<void> {
  const ExcelJS = await loadExcel();
  const wb = new ExcelJS.Workbook();
  wb.creator = "skubase";
  wb.created = new Date();
  wb.modified = new Date();
  await buildSummarySheet(wb, spec);
  buildDetailSheet(wb, {
    sheetName: spec.detailSheetName,
    tableTitle: spec.tableTitle,
    rows: spec.tableRows,
    columns: spec.columns,
  });
  for (const sheet of spec.extraSheets ?? []) {
    buildDetailSheet(wb, sheet);
  }
  const buffer = await wb.xlsx.writeBuffer();
  triggerDownload(buffer as ArrayBuffer, spec.filename);
}

async function buildSummarySheet<T>(
  wb: import("exceljs").Workbook,
  spec: WorkbookSpec<T>,
): Promise<void> {
  const ws = wb.addWorksheet(spec.summarySheetName, {
    views: [{ showGridLines: false, state: "normal" }],
    properties: { defaultRowHeight: 18 },
  });
  const COLS = 12;
  for (let i = 1; i <= COLS; i += 1) ws.getColumn(i).width = i === 1 ? 28 : 12;

  let row = 1;
  ws.mergeCells(row, 1, row, COLS - 2);
  const brandCell = ws.getCell(row, 1);
  brandCell.value = "SKUBASE EXPORT";
  brandCell.font = { name: FONT_DISPLAY, bold: true, size: 11, color: { argb: COLOR_BRAND_INK } };
  brandCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  fillCells(ws, row, 1, row, COLS, COLOR_BRAND);

  ws.mergeCells(row, COLS - 1, row, COLS);
  const genCell = ws.getCell(row, COLS - 1);
  genCell.value = `Generated ${new Date().toLocaleString()}`;
  genCell.font = { name: FONT_BASE, size: 10, color: { argb: COLOR_BRAND_MUTED } };
  genCell.alignment = { vertical: "middle", horizontal: "right", indent: 1 };
  ws.getRow(row).height = 22;

  row += 1;
  ws.mergeCells(row, 1, row, COLS);
  const titleCell = ws.getCell(row, 1);
  titleCell.value = spec.title;
  titleCell.font = { name: FONT_DISPLAY, bold: true, size: 26, color: { argb: COLOR_BRAND_INK } };
  titleCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  fillCells(ws, row, 1, row, COLS, COLOR_BRAND);
  ws.getRow(row).height = 42;

  row += 1;
  ws.mergeCells(row, 1, row, COLS);
  const subtitleCell = ws.getCell(row, 1);
  subtitleCell.value = spec.subtitle;
  subtitleCell.font = { name: FONT_BASE, size: 11, color: { argb: COLOR_BRAND_MUTED } };
  subtitleCell.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
  fillCells(ws, row, 1, row, COLS, COLOR_BRAND);
  ws.getRow(row).height = 32;

  row += 1;
  ws.getRow(row).height = 14;
  fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);

  row += 1;
  const kpiHeaderRow = row;
  const kpiValueRow = row + 1;
  const kpiNoteRow = row + 2;
  const cardWidth = Math.floor(COLS / spec.kpis.length);

  spec.kpis.forEach((kpi, idx) => {
    const startCol = idx * cardWidth + 1;
    const endCol = idx === spec.kpis.length - 1 ? COLS : startCol + cardWidth - 1;
    const tone = kpi.tone ?? "neutral";
    const fill = TONE_FILL[tone];
    const ink = TONE_INK[tone];

    ws.mergeCells(kpiHeaderRow, startCol, kpiHeaderRow, endCol);
    const labelCell = ws.getCell(kpiHeaderRow, startCol);
    labelCell.value = kpi.label.toUpperCase();
    labelCell.font = { name: FONT_BASE, bold: true, size: 9, color: { argb: "FF64748B" } };
    labelCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
    fillCells(ws, kpiHeaderRow, startCol, kpiHeaderRow, endCol, fill);

    ws.mergeCells(kpiValueRow, startCol, kpiValueRow, endCol);
    const valueCell = ws.getCell(kpiValueRow, startCol);
    valueCell.value = kpi.value;
    valueCell.font = { name: FONT_DISPLAY, bold: true, size: 22, color: { argb: ink } };
    valueCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
    fillCells(ws, kpiValueRow, startCol, kpiValueRow, endCol, fill);

    ws.mergeCells(kpiNoteRow, startCol, kpiNoteRow, endCol);
    const noteCell = ws.getCell(kpiNoteRow, startCol);
    noteCell.value = kpi.note ?? "";
    noteCell.font = { name: FONT_BASE, size: 10, color: { argb: "FF64748B" } };
    noteCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
    fillCells(ws, kpiNoteRow, startCol, kpiNoteRow, endCol, fill);

    drawCardBorder(ws, kpiHeaderRow, startCol, kpiNoteRow, endCol);
  });
  ws.getRow(kpiHeaderRow).height = 20;
  ws.getRow(kpiValueRow).height = 32;
  ws.getRow(kpiNoteRow).height = 18;

  row = kpiNoteRow + 1;
  ws.getRow(row).height = 14;
  fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);

  row += 1;
  ws.mergeCells(row, 1, row, COLS);
  const todoTitle = ws.getCell(row, 1);
  todoTitle.value = "Recommended next actions";
  todoTitle.font = { name: FONT_DISPLAY, bold: true, size: 14, color: { argb: COLOR_BRAND } };
  todoTitle.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  fillCells(ws, row, 1, row, COLS, COLOR_SECTION_BG);
  drawBoxBorder(ws, row, 1, row, COLS, COLOR_BORDER);
  ws.getRow(row).height = 28;

  spec.todos.slice(0, 6).forEach((todo, idx) => {
    const r = row + idx + 1;
    const tone = todo.tone ?? "neutral";
    ws.getCell(r, 1).value = idx + 1;
    ws.getCell(r, 1).font = { name: FONT_BASE, bold: true, size: 12, color: { argb: TONE_INK[tone] } };
    ws.getCell(r, 1).alignment = { vertical: "middle", horizontal: "center" };
    ws.getCell(r, 1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: TONE_FILL[tone] } };

    ws.mergeCells(r, 2, r, 5);
    const label = ws.getCell(r, 2);
    label.value = todo.label;
    label.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: COLOR_BRAND } };
    label.alignment = { vertical: "middle", horizontal: "left", indent: 1 };

    ws.mergeCells(r, 6, r, COLS);
    const detail = ws.getCell(r, 6);
    detail.value = todo.detail ?? "";
    detail.font = { name: FONT_BASE, size: 10, color: { argb: "FF475569" } };
    detail.alignment = { vertical: "middle", horizontal: "left", wrapText: true, indent: 1 };
    fillCells(ws, r, 2, r, COLS, idx % 2 === 0 ? COLOR_PANEL_BG : COLOR_ALT_ROW);
    drawBoxBorder(ws, r, 1, r, COLS, COLOR_BORDER);
    ws.getRow(r).height = 30;
  });

  row += Math.max(spec.todos.slice(0, 6).length, 1) + 1;
  ws.getRow(row).height = 12;
  fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);

  for (const chart of spec.charts) {
    row += 1;
    ws.mergeCells(row, 1, row, COLS);
    const sectionCell = ws.getCell(row, 1);
    sectionCell.value = chart.title;
    sectionCell.font = { name: FONT_DISPLAY, bold: true, size: 14, color: { argb: COLOR_BRAND } };
    sectionCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
    fillCells(ws, row, 1, row, COLS, COLOR_SECTION_BG);
    drawBoxBorder(ws, row, 1, row, COLS, COLOR_BORDER);
    ws.getRow(row).height = 28;

    const chartStartRow = row + 1;
    const chartHeightRows = 15;
    for (let r = chartStartRow; r < chartStartRow + chartHeightRows; r += 1) {
      ws.getRow(r).height = 18;
      fillCells(ws, r, 1, r, COLS, COLOR_PANEL_BG);
    }
    drawBoxBorder(ws, chartStartRow, 1, chartStartRow + chartHeightRows - 1, COLS, COLOR_BORDER);

    const chartImage = renderBarChartDataUrl(chart.title, chart.points);
    if (chartImage) {
      const imageId = wb.addImage({ base64: chartImage, extension: "png" });
      ws.addImage(imageId, {
        tl: { col: 0.25, row: chartStartRow - 0.85 },
        ext: { width: 900, height: 260 },
      });
    } else {
      buildFallbackChartRows(ws, chart, chartStartRow, COLS);
    }

    row = chartStartRow + chartHeightRows;
    row += 1;
    ws.getRow(row).height = 10;
    fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);
  }

  row += 1;
  ws.mergeCells(row, 1, row, COLS);
  const ptr = ws.getCell(row, 1);
  const dataTabs = [spec.detailSheetName, ...(spec.extraSheets ?? []).map((s) => s.sheetName)];
  ptr.value =
    dataTabs.length === 1
      ? `Full data on the "${dataTabs[0]}" tab.`
      : `Full data on the ${dataTabs.map((name) => `"${name}"`).join(", ")} tabs.`;
  ptr.font = { name: FONT_BASE, italic: true, size: 11, color: { argb: "FF64748B" } };
  ptr.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  ws.getRow(row).height = 22;

  ws.views = [{ state: "frozen", xSplit: 0, ySplit: 3, showGridLines: false }];
}

function buildDetailSheet<T>(
  wb: import("exceljs").Workbook,
  sheet: {
    sheetName: string;
    tableTitle: string;
    rows: T[];
    columns: ReportTableColumn<T>[];
  },
): void {
  const ws = wb.addWorksheet(sheet.sheetName, {
    views: [{ showGridLines: false }],
    properties: { defaultRowHeight: 18 },
  });

  sheet.columns.forEach((col, idx) => { ws.getColumn(idx + 1).width = col.width ?? 16; });
  const colCount = sheet.columns.length;

  ws.mergeCells(1, 1, 1, colCount);
  const titleCell = ws.getCell(1, 1);
  titleCell.value = sheet.tableTitle;
  titleCell.font = { name: FONT_DISPLAY, bold: true, size: 18, color: { argb: COLOR_BRAND_INK } };
  titleCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  fillCells(ws, 1, 1, 1, colCount, COLOR_BRAND);
  ws.getRow(1).height = 32;

  const headerRow = 2;
  sheet.columns.forEach((col, idx) => {
    const cell = ws.getCell(headerRow, idx + 1);
    cell.value = col.label;
    cell.font = { name: FONT_BASE, bold: true, size: 10, color: { argb: COLOR_HEADER_INK } };
    cell.alignment = { vertical: "middle", horizontal: col.align ?? "left", indent: 1 };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: COLOR_HEADER_BG } };
    cell.border = {
      top: { style: "thin", color: { argb: COLOR_BORDER } },
      bottom: { style: "medium", color: { argb: COLOR_BRAND } },
      left: { style: "thin", color: { argb: COLOR_BORDER } },
      right: { style: "thin", color: { argb: COLOR_BORDER } },
    };
  });
  ws.getRow(headerRow).height = 26;

  const wrapKeys = new Set(["recommendation", "recommendedAction", "reason", "explanation", "notes", "rationale"]);
  sheet.rows.forEach((row, idx) => {
    const r = headerRow + 1 + idx;
    const isAlt = idx % 2 === 1;
    sheet.columns.forEach((col, cIdx) => {
      const cell = ws.getCell(r, cIdx + 1);
      const numeric = col.numericValue?.(row);
      if (numeric !== undefined && numeric !== null && Number.isFinite(numeric)) {
        cell.value = numeric;
        if (col.numFmt) cell.numFmt = col.numFmt;
      } else {
        cell.value = col.format(row);
      }
      const tone = col.tone?.(row);
      const baseFill = tone ? TONE_FILL[tone] : isAlt ? COLOR_ALT_ROW : COLOR_PANEL_BG;
      const ink = tone ? TONE_INK[tone] : "FF0F172A";
      cell.font = { name: FONT_BASE, size: 10, bold: Boolean(tone), color: { argb: ink } };
      cell.alignment = {
        vertical: "middle",
        horizontal: col.align ?? "left",
        indent: 1,
        wrapText: wrapKeys.has(col.key),
      };
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: baseFill } };
      cell.border = {
        top: { style: "hair", color: { argb: COLOR_BORDER } },
        bottom: { style: "hair", color: { argb: COLOR_BORDER } },
        left: { style: "hair", color: { argb: COLOR_BORDER } },
        right: { style: "hair", color: { argb: COLOR_BORDER } },
      };
    });
    const wraps = sheet.columns.some((c) => wrapKeys.has(c.key));
    ws.getRow(r).height = wraps ? 36 : 22;
  });

  // Totals row for any column marked summarize: "sum".
  const summarized = sheet.columns
    .map((col, idx) => ({ col, idx }))
    .filter(({ col }) => col.summarize === "sum" && col.numericValue !== undefined);
  if (summarized.length > 0 && sheet.rows.length > 0) {
    const totalRow = headerRow + sheet.rows.length + 1;
    sheet.columns.forEach((col, cIdx) => {
      const cell = ws.getCell(totalRow, cIdx + 1);
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: COLOR_SECTION_BG } };
      cell.border = {
        top: { style: "medium", color: { argb: COLOR_BRAND } },
        bottom: { style: "thin", color: { argb: COLOR_BORDER } },
      };
      const summary = summarized.find((entry) => entry.idx === cIdx);
      if (cIdx === 0 && !summary) {
        cell.value = "Total";
        cell.font = { name: FONT_BASE, bold: true, size: 10, color: { argb: COLOR_BRAND } };
        cell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
        return;
      }
      if (!summary) return;
      const total = sheet.rows.reduce((sum, row) => {
        const value = summary.col.numericValue?.(row);
        return sum + (value !== null && value !== undefined && Number.isFinite(value) ? value : 0);
      }, 0);
      cell.value = total;
      if (summary.col.numFmt) cell.numFmt = summary.col.numFmt;
      cell.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: COLOR_BRAND } };
      cell.alignment = { vertical: "middle", horizontal: summary.col.align ?? "right", indent: 1 };
    });
    ws.getRow(totalRow).height = 24;
  }

  const numericCols = sheet.columns
    .map((col, idx) => ({ col, idx }))
    .filter(({ col }) => col.numericValue !== undefined);
  if (numericCols.length > 0 && sheet.rows.length > 0) {
    const target = numericCols[numericCols.length - 1];
    const colLetter = columnLetter(target.idx + 1);
    const firstDataRow = headerRow + 1;
    const lastDataRow = headerRow + sheet.rows.length;
    ws.addConditionalFormatting({
      ref: `${colLetter}${firstDataRow}:${colLetter}${lastDataRow}`,
      rules: [
        {
          type: "dataBar",
          cfvo: [{ type: "min" }, { type: "max" }],
          color: { argb: TONE_ACCENT.neutral },
          gradient: true,
          showValue: true,
          priority: 1,
        } as never,
      ],
    });
  }

  ws.autoFilter = {
    from: { row: headerRow, column: 1 },
    to: { row: headerRow, column: colCount },
  };
  ws.views = [{ state: "frozen", xSplit: 0, ySplit: headerRow, showGridLines: false }];
}

function buildFallbackChartRows(
  ws: import("exceljs").Worksheet,
  chart: { title: string; points: BarPoint[] },
  dataStartRow: number,
  colCount: number,
): void {
  const max = Math.max(...chart.points.map((p) => p.value), 1);
  chart.points.slice(0, 10).forEach((point, idx) => {
    const r = dataStartRow + idx;
    ws.mergeCells(r, 1, r, 3);
    const lab = ws.getCell(r, 1);
    lab.value = point.label;
    lab.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: COLOR_HEADER_INK } };
    lab.alignment = { vertical: "middle", horizontal: "left", indent: 1 };

    ws.mergeCells(r, 4, r, Math.max(4, colCount - 2));
    const barCell = ws.getCell(r, 4);
    barCell.value = point.value;
    barCell.numFmt = Math.abs(point.value) >= 100 ? '"$"#,##0' : "#,##0";
    barCell.font = { name: FONT_BASE, size: 1, color: { argb: "00FFFFFF" } };
    const tone: Tone = point.tone ?? "neutral";
    ws.addConditionalFormatting({
      ref: barCell.address,
      rules: [
        {
          type: "dataBar",
          cfvo: [
            { type: "num", value: 0 },
            { type: "num", value: max },
          ],
          color: { argb: TONE_ACCENT[tone] },
          gradient: true,
          showValue: false,
          priority: 1,
        } as never,
      ],
    });

    ws.mergeCells(r, colCount - 1, r, colCount);
    const disp = ws.getCell(r, colCount - 1);
    disp.value = point.display;
    disp.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: TONE_INK[tone] } };
    disp.alignment = { vertical: "middle", horizontal: "right", indent: 1 };
  });
}

function renderBarChartDataUrl(title: string, points: BarPoint[]): string | null {
  if (typeof document === "undefined" || points.length === 0) return null;
  const visible = points.slice(0, 8);
  const canvas = document.createElement("canvas");
  const width = 1200;
  const height = 360;
  const scale = 2;
  canvas.width = width * scale;
  canvas.height = height * scale;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(scale, scale);

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#0f172a";
  ctx.font = "700 28px Calibri, Arial, sans-serif";
  ctx.fillText(title, 28, 44);

  const chartTop = 78;
  const labelWidth = 310;
  const valueWidth = 160;
  const barLeft = labelWidth + 42;
  const barWidth = width - labelWidth - valueWidth - 78;
  const rowHeight = Math.min(34, Math.floor((height - chartTop - 26) / Math.max(visible.length, 1)));
  const max = Math.max(...visible.map((point) => Math.abs(point.value)), 1);

  ctx.font = "600 18px Calibri, Arial, sans-serif";
  visible.forEach((point, idx) => {
    const y = chartTop + idx * rowHeight;
    const tone = point.tone ?? "neutral";
    const label = truncate(point.label, 34);
    ctx.fillStyle = "#334155";
    ctx.fillText(label, 28, y + 22);

    ctx.fillStyle = "#eef2f7";
    roundRect(ctx, barLeft, y + 6, barWidth, 18, 9);
    ctx.fill();

    ctx.fillStyle = argbToHex(TONE_ACCENT[tone]);
    roundRect(ctx, barLeft, y + 6, Math.max((Math.abs(point.value) / max) * barWidth, 4), 18, 9);
    ctx.fill();

    ctx.fillStyle = argbToHex(TONE_INK[tone]);
    ctx.font = "700 18px Calibri, Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(point.display, width - 28, y + 22);
    ctx.textAlign = "left";
    ctx.font = "600 18px Calibri, Arial, sans-serif";
  });

  ctx.strokeStyle = "#dbe3ef";
  ctx.lineWidth = 2;
  roundRect(ctx, 1, 1, width - 2, height - 2, 18);
  ctx.stroke();

  return canvas.toDataURL("image/png");
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
): void {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}...`;
}

function argbToHex(argb: string): string {
  return `#${argb.slice(2)}`;
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------
function fillCells(
  ws: import("exceljs").Worksheet,
  r1: number, c1: number, r2: number, c2: number, argb: string,
): void {
  for (let r = r1; r <= r2; r += 1) {
    for (let c = c1; c <= c2; c += 1) {
      ws.getCell(r, c).fill = { type: "pattern", pattern: "solid", fgColor: { argb } };
    }
  }
}

function drawCardBorder(
  ws: import("exceljs").Worksheet,
  r1: number, c1: number, r2: number, c2: number,
): void {
  const color = { argb: COLOR_BORDER };
  for (let c = c1; c <= c2; c += 1) {
    const top = ws.getCell(r1, c);
    top.border = { ...(top.border ?? {}), top: { style: "thin", color } };
    const bot = ws.getCell(r2, c);
    bot.border = { ...(bot.border ?? {}), bottom: { style: "thin", color } };
  }
  for (let r = r1; r <= r2; r += 1) {
    const lf = ws.getCell(r, c1);
    lf.border = { ...(lf.border ?? {}), left: { style: "thin", color } };
    const rt = ws.getCell(r, c2);
    rt.border = { ...(rt.border ?? {}), right: { style: "thin", color } };
  }
}

function drawBoxBorder(
  ws: import("exceljs").Worksheet,
  r1: number, c1: number, r2: number, c2: number, argb: string,
): void {
  const color = { argb };
  for (let c = c1; c <= c2; c += 1) {
    const top = ws.getCell(r1, c);
    top.border = { ...(top.border ?? {}), top: { style: "thin", color } };
    const bot = ws.getCell(r2, c);
    bot.border = { ...(bot.border ?? {}), bottom: { style: "thin", color } };
  }
  for (let r = r1; r <= r2; r += 1) {
    const lf = ws.getCell(r, c1);
    lf.border = { ...(lf.border ?? {}), left: { style: "thin", color } };
    const rt = ws.getCell(r, c2);
    rt.border = { ...(rt.border ?? {}), right: { style: "thin", color } };
  }
}

function columnLetter(col: number): string {
  let n = col;
  let s = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

// ---------------------------------------------------------------------------
// Misc helpers
// ---------------------------------------------------------------------------
function triggerDownload(buffer: ArrayBuffer, filename: string): void {
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => window.URL.revokeObjectURL(url), 2000);
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

function defaultTodos(title: string): ReportTodo[] {
  const normalized = title.toLowerCase();
  if (normalized.includes("stockout")) {
    return [
      { label: "Review critical stockout risks", detail: "Start with SKUs where days left is inside supplier lead time.", tone: "danger" },
      { label: "Open the reorder plan", detail: "Convert high-risk SKUs into purchase order decisions.", tone: "warning" },
      { label: "Validate lead-time assumptions", detail: "Confirm supplier lead times before committing capital.", tone: "neutral" },
    ];
  }
  if (normalized.includes("dead") || normalized.includes("overstock")) {
    return [
      { label: "Prioritize largest cash recovery", detail: "Use the table to find the SKUs tying up the most money.", tone: "danger" },
      { label: "Pick liquidation tactic", detail: "Choose markdown, bundle, wholesale, or write-off per item.", tone: "warning" },
      { label: "Track recovered capital", detail: "Compare results with the projected recovery after the sale window.", tone: "good" },
    ];
  }
  if (normalized.includes("reorder") || normalized.includes("purchase")) {
    return [
      { label: "Approve urgent reorder lines", detail: "Confirm costs and quantities for SKUs inside the reorder window.", tone: "danger" },
      { label: "Group by supplier", detail: "Prepare fewer, cleaner purchase orders for suppliers.", tone: "warning" },
      { label: "Record receipts", detail: "Receipt history improves supplier scorecards and lead-time confidence.", tone: "good" },
    ];
  }
  return [
    { label: "Review the highest-priority rows", detail: "Start with the top of the detail table before lower-impact work.", tone: "danger" },
    { label: "Assign the next workflow", detail: "Move reorder, liquidation, and supplier issues into the right app workflow.", tone: "warning" },
    { label: "Export again after changes", detail: "Use a fresh export to confirm the action queue moved.", tone: "good" },
  ];
}

function escapeCsv(value: string | number): string {
  const str = String(value);
  if (/[",\r\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

// Reference unused constants so tsc doesn't complain
const _unusedPanelBg = COLOR_PANEL_BG;
void _unusedPanelBg;
