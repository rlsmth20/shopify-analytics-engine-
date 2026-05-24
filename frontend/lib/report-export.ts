"use client";

import type { InventoryAction } from "@/lib/api";
import { currency, type LiquidationSuggestion, type PurchaseOrderDraft } from "@/lib/api-v2";
import { getActionImpactValue, statusLabel } from "@/lib/app-helpers";

// ExcelJS is loaded dynamically only when an export is triggered, so the
// ~800kB library is never bundled into the initial page payload.
type AnyExcel = typeof import("exceljs");
let excelModulePromise: Promise<AnyExcel> | null = null;
async function loadExcel(): Promise<AnyExcel> {
  if (!excelModulePromise) {
    excelModulePromise = import("exceljs");
  }
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

type Tone = "neutral" | "good" | "warning" | "danger";

type ReportTableColumn<T> = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: number;
  format: (row: T) => string;
  numericValue?: (row: T) => number | null;
  tone?: (row: T) => Tone | null;
  numFmt?: string;
};

type ReportKpi = {
  label: string;
  value: string;
  note?: string;
  tone?: Tone;
};

type BarPoint = {
  label: string;
  value: number;
  display: string;
  tone?: Tone;
};

const LIQUIDATION_TACTIC_LABELS: Record<LiquidationSuggestion["tactic"], string> = {
  markdown: "Markdown",
  bundle: "Bundle",
  wholesale: "Wholesale",
  donate_write_off: "Write-off",
};

// ---------------------------------------------------------------------------
// Public exports
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
    filename: `inventory-actions-${todayStamp()}.xlsx`,
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
          .sort((left, right) => getActionImpactValue(right) - getActionImpactValue(left))
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
    subtitle:
      "Dead-stock recommendations with recovery estimates, markdown guidance, and tactic mix.",
    filename: `skubase-liquidation-plan-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "Plan",
    kpis: [
      { label: "Dead SKUs", value: String(suggestions.length), tone: "danger" },
      { label: "Capital stuck", value: currency(capitalTiedUp), tone: "danger" },
      { label: "Projected recovery", value: currency(projectedRecovery), tone: "good" },
      {
        label: "Recovery rate",
        value:
          capitalTiedUp > 0
            ? `${((projectedRecovery / capitalTiedUp) * 100).toFixed(0)}%`
            : "0%",
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
          .sort(
            (left, right) =>
              right.projected_recovered_capital - left.projected_recovered_capital
          )
          .slice(0, 8)
          .map((item) => ({
            label: item.name,
            value: item.projected_recovered_capital,
            display: currency(item.projected_recovered_capital),
            tone: (item.tactic === "donate_write_off" ? "danger" : "good") as Tone,
          })),
      },
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
      },
    ],
  });
}

export async function exportPurchaseOrderReport(po: PurchaseOrderDraft): Promise<void> {
  await buildWorkbook({
    title: `${po.po_id} - Purchase Order`,
    subtitle: `${po.vendor} - expected arrival ${po.expected_arrival_date}. ${po.rationale}`,
    filename: `${po.po_id.toLowerCase()}-${slugify(po.vendor)}-${todayStamp()}.xlsx`,
    summarySheetName: "Summary",
    detailSheetName: "Lines",
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
          .slice(0, 12)
          .map((line) => ({
            label: line.name,
            value: line.extended_cost,
            display: currency(line.extended_cost),
            tone: (line.extended_cost >= 1000 ? "warning" : "neutral") as Tone,
          })),
      },
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
      },
    ],
  });
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
  tableTitle: string;
  tableRows: T[];
  columns: ReportTableColumn<T>[];
};

async function buildWorkbook<T>(spec: WorkbookSpec<T>): Promise<void> {
  const ExcelJS = await loadExcel();

  const wb = new ExcelJS.Workbook();
  wb.creator = "skubase";
  wb.created = new Date();
  wb.modified = new Date();

  buildSummarySheet(wb, spec);
  buildDetailSheet(wb, spec);

  const buffer = await wb.xlsx.writeBuffer();
  triggerDownload(buffer as ArrayBuffer, spec.filename);
}

function buildSummarySheet<T>(
  wb: import("exceljs").Workbook,
  spec: WorkbookSpec<T>
): void {
  const ws = wb.addWorksheet(spec.summarySheetName, {
    views: [{ showGridLines: false, state: "normal" }],
    properties: { defaultRowHeight: 18 },
  });

  const COLS = 12;
  for (let i = 1; i <= COLS; i += 1) {
    ws.getColumn(i).width = i === 1 ? 28 : 12;
  }

  // ---- Brand bar ----
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

  // ---- Title ----
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

  // Spacer
  row += 1;
  ws.getRow(row).height = 14;
  fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);

  // ---- KPI row ----
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

  // ---- Chart sections ----
  spec.charts.forEach((chart) => {
    row += 1;
    ws.mergeCells(row, 1, row, COLS);
    const sectionCell = ws.getCell(row, 1);
    sectionCell.value = chart.title;
    sectionCell.font = { name: FONT_DISPLAY, bold: true, size: 14, color: { argb: COLOR_BRAND } };
    sectionCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
    fillCells(ws, row, 1, row, COLS, COLOR_SECTION_BG);
    drawBoxBorder(ws, row, 1, row, COLS, COLOR_BORDER);
    ws.getRow(row).height = 28;

    const dataStartRow = row + 1;
    const max = Math.max(...chart.points.map((p) => p.value), 1);

    chart.points.forEach((point, idx) => {
      const r = dataStartRow + idx;

      ws.mergeCells(r, 1, r, 3);
      const lab = ws.getCell(r, 1);
      lab.value = point.label;
      lab.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: COLOR_HEADER_INK } };
      lab.alignment = { vertical: "middle", horizontal: "left", indent: 1 };

      ws.mergeCells(r, 4, r, 10);
      const barCell = ws.getCell(r, 4);
      barCell.value = point.value;
      barCell.numFmt = Math.abs(point.value) >= 100 ? '"$"#,##0' : "#,##0";
      // Hide the cell value text — the bar speaks for itself
      barCell.font = { name: FONT_BASE, size: 1, color: { argb: "00FFFFFF" } };
      barCell.alignment = { vertical: "middle", horizontal: "left" };

      ws.mergeCells(r, 11, r, 12);
      const disp = ws.getCell(r, 11);
      disp.value = point.display;
      const tone: Tone = point.tone ?? "neutral";
      disp.font = { name: FONT_BASE, bold: true, size: 11, color: { argb: TONE_INK[tone] } };
      disp.alignment = { vertical: "middle", horizontal: "right", indent: 1 };

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

      ws.getRow(r).height = 22;
    });

    drawBoxBorder(
      ws,
      dataStartRow,
      1,
      dataStartRow + chart.points.length - 1,
      COLS,
      COLOR_BORDER
    );

    row = dataStartRow + chart.points.length;
    row += 1;
    ws.getRow(row).height = 10;
    fillCells(ws, row, 1, row, COLS, COLOR_PAGE_BG);
  });

  // Pointer to detail sheet
  row += 1;
  ws.mergeCells(row, 1, row, COLS);
  const ptr = ws.getCell(row, 1);
  ptr.value = `Full data on the "${spec.detailSheetName}" tab.`;
  ptr.font = { name: FONT_BASE, italic: true, size: 11, color: { argb: "FF64748B" } };
  ptr.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  ws.getRow(row).height = 22;

  ws.views = [{ state: "frozen", xSplit: 0, ySplit: 3, showGridLines: false }];
}

function buildDetailSheet<T>(
  wb: import("exceljs").Workbook,
  spec: WorkbookSpec<T>
): void {
  const ws = wb.addWorksheet(spec.detailSheetName, {
    views: [{ showGridLines: false }],
    properties: { defaultRowHeight: 18 },
  });

  spec.columns.forEach((col, idx) => {
    ws.getColumn(idx + 1).width = col.width ?? 16;
  });
  const colCount = spec.columns.length;

  ws.mergeCells(1, 1, 1, colCount);
  const titleCell = ws.getCell(1, 1);
  titleCell.value = spec.tableTitle;
  titleCell.font = { name: FONT_DISPLAY, bold: true, size: 18, color: { argb: COLOR_BRAND_INK } };
  titleCell.alignment = { vertical: "middle", horizontal: "left", indent: 1 };
  fillCells(ws, 1, 1, 1, colCount, COLOR_BRAND);
  ws.getRow(1).height = 32;

  const headerRow = 2;
  spec.columns.forEach((col, idx) => {
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

  spec.tableRows.forEach((row, idx) => {
    const r = headerRow + 1 + idx;
    const isAlt = idx % 2 === 1;
    spec.columns.forEach((col, cIdx) => {
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
      cell.font = {
        name: FONT_BASE,
        size: 10,
        bold: Boolean(tone),
        color: { argb: ink },
      };
      cell.alignment = {
        vertical: "middle",
        horizontal: col.align ?? "left",
        indent: 1,
        wrapText: col.key === "recommendation",
      };
      cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: baseFill } };
      cell.border = {
        top: { style: "hair", color: { argb: COLOR_BORDER } },
        bottom: { style: "hair", color: { argb: COLOR_BORDER } },
        left: { style: "hair", color: { argb: COLOR_BORDER } },
        right: { style: "hair", color: { argb: COLOR_BORDER } },
      };
    });
    if (spec.columns.some((c) => c.key === "recommendation")) {
      ws.getRow(r).height = 36;
    } else {
      ws.getRow(r).height = 22;
    }
  });

  // Data bars on the most-impactful numeric column
  const numericCols = spec.columns
    .map((col, idx) => ({ col, idx }))
    .filter(({ col }) => col.numericValue !== undefined);
  if (numericCols.length > 0 && spec.tableRows.length > 0) {
    const target = numericCols[numericCols.length - 1];
    const colLetter = columnLetter(target.idx + 1);
    const firstDataRow = headerRow + 1;
    const lastDataRow = headerRow + spec.tableRows.length;
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
  ws.views = [
    { state: "frozen", xSplit: 0, ySplit: headerRow, showGridLines: false },
  ];
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------
function fillCells(
  ws: import("exceljs").Worksheet,
  r1: number,
  c1: number,
  r2: number,
  c2: number,
  argb: string
): void {
  for (let r = r1; r <= r2; r += 1) {
    for (let c = c1; c <= c2; c += 1) {
      ws.getCell(r, c).fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb },
      };
    }
  }
}

function drawCardBorder(
  ws: import("exceljs").Worksheet,
  r1: number,
  c1: number,
  r2: number,
  c2: number
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
  r1: number,
  c1: number,
  r2: number,
  c2: number,
  argb: string
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

// Avoid unused-import warning when only the type side is consumed.
const _unusedPanelBg = COLOR_PANEL_BG;
void _unusedPanelBg;
