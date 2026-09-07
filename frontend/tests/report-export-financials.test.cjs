const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const ExcelJS = require("exceljs");
const root = path.join(__dirname, "..");
const cache = new Map();

function load(relative) {
  if (cache.has(relative)) return cache.get(relative);
  const exports = {};
  cache.set(relative, exports);
  let compiled = ts.transpileModule(fs.readFileSync(path.join(root, relative), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  if (relative === "lib/report-export.ts") {
    // Capture the real exporter spec without triggering a browser download, then
    // exercise its cell construction with the actual ExcelJS workbook below.
    compiled += `
      exports.captureReport = async (name, rows) => {
        let spec;
        const original = buildWorkbook;
        buildWorkbook = async (value) => { spec = value; };
        try { await exports[name](rows); } finally { buildWorkbook = original; }
        return spec;
      };
      exports.buildDetailSheet = buildDetailSheet;
    `;
  }
  vm.runInNewContext(compiled, {
    exports, process, Intl, URL, URLSearchParams, console,
    require: (name) => name.startsWith("@/") ? load(name.slice(2) + ".ts") : require(name),
  });
  return exports;
}

const { captureReport, buildDetailSheet } = load("lib/report-export.ts");
const missing = { cost_source: "estimated_from_price", financial_values_known: false };
const action = {
  sku_id: "shirt", name: "Shirt", status: "urgent", current_on_hand: 2,
  priority_score: 80, target_coverage_days: 60, estimated_profit_impact: 500,
  recommended_action: "Check reorder quantities",
};
const liquidation = {
  sku_id: "shirt", name: "Shirt", on_hand: 10, days_since_last_sale: 120,
  capital_tied_up: 100, suggested_markdown_pct: 25, suggested_price: 4,
  projected_recovered_capital: 40, tactic: "markdown",
};
const line = { sku_id: "shirt", name: "Shirt", qty: 2, unit_cost: 5, extended_cost: 10, received_qty: 0 };
const po = {
  po_id: "PO-1", vendor: "Supplier A", source: "saved", status: "draft", lines: [line],
  subtotal_cost: 10, shipping_cost: 5, total_cost: 15,
  expected_arrival_date: "2026-10-01", rationale: "Merchant-entered order",
};
const kpi = (spec, label) => spec.kpis.find((item) => item.label === label).value;
const column = (spec, key) => spec.columns.find((item) => item.key === key);
function detail(spec) {
  const workbook = new ExcelJS.Workbook();
  buildDetailSheet(workbook, {
    sheetName: spec.detailSheetName, tableTitle: spec.tableTitle,
    rows: spec.tableRows, columns: spec.columns,
  });
  return workbook;
}
function cellFor(sheet, spec, key, row) {
  return sheet.getCell(row, spec.columns.findIndex((item) => item.key === key) + 1);
}

test("action exports keep unknown impact separate from zero and omit missing-cost chart points", async () => {
  const unknown = { ...action, ...missing, financial_values: { estimated_profit_impact: null } };
  const free = { ...action, name: "Recorded zero", financial_values: { estimated_profit_impact: 0 } };
  const spec = await captureReport("exportActionsReport", [unknown, free]);
  assert.equal(kpi(spec, "Profit / cash impact"), "Unknown");
  assert.equal(kpi(spec, "Actions"), "2");
  assert.equal(column(spec, "impact").numericValue(unknown), null);
  assert.equal(column(spec, "impact").tone(unknown), null);
  assert.equal(spec.charts[1].points.length, 1);
  assert.equal(spec.charts[1].points[0].label, "Recorded zero");
  assert.equal(spec.charts[1].points[0].value, 0);
  assert.match(spec.charts[1].title, /known amounts only/);
  const sheet = detail(spec).worksheets[0];
  assert.equal(cellFor(sheet, spec, "impact", 3).value, "Unknown");
  assert.equal(cellFor(sheet, spec, "impact", 4).value, 0);
  assert.equal(cellFor(sheet, spec, "impact", 5).value, "Unknown");
});

test("action rankings and totals use canonical recorded amounts instead of legacy estimates", async () => {
  const canonical = { ...action, estimated_profit_impact: 9000, financial_values: { estimated_profit_impact: 10 } };
  const legacy = { ...action, name: "Legacy recorded", estimated_profit_impact: 20 };
  const spec = await captureReport("exportActionsReport", [canonical, legacy]);
  assert.equal(kpi(spec, "Profit / cash impact"), "$30");
  assert.equal(spec.charts[1].points[0].label, "Legacy recorded");
  assert.equal(spec.charts[1].points[1].value, 10);
});

test("liquidation exports suppress unsupported markdown, prices and recovery without hiding stock", async () => {
  const unknown = { ...liquidation, ...missing, financial_values: {
    suggested_markdown_pct: null, suggested_price: null,
    capital_tied_up: null, projected_recovered_capital: null,
  } };
  const spec = await captureReport("exportLiquidationReport", [liquidation, unknown]);
  for (const label of ["Capital stuck", "Projected recovery", "Recovery rate"]) assert.equal(kpi(spec, label), "Unknown");
  for (const key of ["markdown", "price", "stuck", "recovery"]) {
    assert.equal(column(spec, key).numericValue(unknown), null);
    assert.equal(column(spec, key).format(unknown), "Unknown");
  }
  assert.equal(column(spec, "on_hand").numericValue(unknown), 10);
  assert.equal(spec.charts[1].points.length, 1);
  assert.equal(spec.charts[1].points[0].value, 40);
  assert.equal(spec.charts[0].points[0].value, 2);
  const known = await captureReport("exportLiquidationReport", [liquidation]);
  assert.equal(kpi(known, "Recovery rate"), "40%");
  const zero = await captureReport("exportLiquidationReport", [{ ...liquidation, capital_tied_up: 0 }]);
  assert.equal(kpi(zero, "Recovery rate"), "Unknown");
});

test("generated PO exports retain unknown costs while preserving valid quantities and known lines", async () => {
  const unknown = { ...line, name: "Needs unit cost", qty: 3, ...missing,
    financial_values: { unit_cost: null, extended_cost: null } };
  const generated = { ...po, source: "recommended", financial_values_known: false,
    financial_values: { subtotal_cost: null, total_cost: null }, lines: [line, unknown] };
  const spec = await captureReport("exportPurchaseOrderReport", generated);
  for (const label of ["Subtotal", "Shipping", "Total landed cost"]) assert.equal(kpi(spec, label), "Unknown");
  assert.equal(spec.charts[0].points.length, 1);
  assert.equal(spec.charts[0].points[0].value, 10);
  const sheet = detail(spec).worksheets[0];
  assert.equal(cellFor(sheet, spec, "unit", 4).value, "Unknown");
  assert.equal(cellFor(sheet, spec, "extended", 4).value, "Unknown");
  assert.equal(cellFor(sheet, spec, "extended", 5).value, "Unknown");
  assert.equal(cellFor(sheet, spec, "qty", 5).value, 5);
});

test("saved explicit PO amounts and real zero costs remain numeric in the serialized workbook", async () => {
  const free = { ...line, name: "Free sample", unit_cost: 900, extended_cost: 1800,
    cost_source: "recorded", financial_values_known: true, financial_values: { unit_cost: 0, extended_cost: 0 } };
  const spec = await captureReport("exportPurchaseOrderReport", { ...po, lines: [line, free] });
  assert.equal(kpi(spec, "Subtotal"), "$10");
  assert.equal(kpi(spec, "Shipping"), "$5");
  assert.equal(kpi(spec, "Total landed cost"), "$15");
  const workbook = detail(spec);
  const reloaded = new ExcelJS.Workbook();
  await reloaded.xlsx.load(await workbook.xlsx.writeBuffer());
  const sheet = reloaded.worksheets[0];
  assert.equal(cellFor(sheet, spec, "unit", 4).value, 0);
  assert.equal(cellFor(sheet, spec, "extended", 4).value, 0);
  assert.equal(cellFor(sheet, spec, "extended", 5).value, 10);
  assert.equal(cellFor(sheet, spec, "qty", 5).value, 4);
});

test("buy-plan totals and every extra-sheet line preserve missing-cost provenance", async () => {
  const unknown = { ...line, ...missing };
  const generated = { ...po, po_id: "PO-2", vendor: "Supplier B", source: "recommended",
    financial_values_known: false, lines: [unknown] };
  const spec = await captureReport("exportBuyPlanReport", [po, generated]);
  assert.equal(kpi(spec, "Total capital required"), "Unknown");
  assert.equal(kpi(spec, "Units"), "4");
  assert.equal(spec.charts[0].points.length, 1);
  assert.equal(spec.charts[0].points[0].label, "Supplier A");
  for (const key of ["subtotal", "shipping", "total"]) {
    assert.equal(column(spec, key).format(generated), "Unknown");
    assert.equal(column(spec, key).numericValue(generated), null);
  }
  const workbook = detail(spec);
  buildDetailSheet(workbook, spec.extraSheets[0]);
  const extra = workbook.getWorksheet("All lines");
  assert.equal(extra.getCell("E4").value, "Unknown");
  assert.equal(extra.getCell("F4").value, "Unknown");
  assert.equal(extra.getCell("F5").value, "Unknown");
  assert.equal(extra.getCell("D5").value, 4);
});

test("generic sum does not quietly drop unavailable or invalid currency values", async () => {
  for (const unavailable of [null, undefined, NaN, Infinity]) {
    const workbook = new ExcelJS.Workbook();
    buildDetailSheet(workbook, {
      sheetName: "Details", tableTitle: "Generic report", rows: [{ cost: 20, qty: 2 }, { cost: unavailable, qty: 3 }],
      columns: [
        { key: "name", label: "SKU", format: () => "Product" },
        { key: "cost", label: "Cost", format: () => "Unknown", numericValue: (row) => row.cost, summarize: "sum", numFmt: '"$"#,##0' },
        { key: "qty", label: "Qty", format: (row) => String(row.qty), numericValue: (row) => row.qty, summarize: "sum" },
      ],
    });
    const reloaded = new ExcelJS.Workbook();
    await reloaded.xlsx.load(await workbook.xlsx.writeBuffer());
    assert.equal(reloaded.worksheets[0].getCell("B4").value, "Unknown");
    assert.equal(reloaded.worksheets[0].getCell("B5").value, "Unknown");
    assert.equal(reloaded.worksheets[0].getCell("C5").value, 5);
  }
});
