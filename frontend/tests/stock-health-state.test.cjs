const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const root = path.join(__dirname, "..");
const cache = new Map();
function load(relative) {
  if (cache.has(relative)) return cache.get(relative);
  const exports = {};
  cache.set(relative, exports);
  let compiled = ts.transpileModule(fs.readFileSync(path.join(root, relative), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  if (relative === "app/(app-shell)/reports/page.tsx") {
    // Keep Next's page exports unchanged while exercising real report mappings.
    compiled += "\nexports.reportMappings = { actionToRow, forecastToRow, reorderToRow, buildMetrics, riskDistribution, vendorExposure };";
  }
  vm.runInNewContext(compiled, {
    exports, process, Intl, URLSearchParams, URL, console,
    require: (name) => {
      if (name.endsWith(".module.css")) return { default: {} };
      if (name.startsWith("@/")) return load(name.slice(2) + (name.startsWith("@/components/") ? ".tsx" : ".ts"));
      return require(name);
    },
  });
  return exports;
}
const { stockoutRiskLevel, stockCoverageGeometry } = load("lib/stock-health-state.ts");
const { ProjectedStockHealth } = load("components/projected-stock-health.tsx");
const { ActionCard } = load("components/action-card.tsx");
const { reportMappings } = load("app/(app-shell)/reports/page.tsx");
const renderHealth = (props) => renderToStaticMarkup(React.createElement(ProjectedStockHealth, props));
const known = { currentStock: 50, dailyVelocity: 1, daysLeft: 50, leadTimeDays: 14, targetCoverageDays: 60 };
const action = {
  sku_id: "SKU-1", name: "Shirt", status: "urgent", urgency_level: "critical", priority_score: 90,
  current_on_hand: 10, daily_velocity: 2, days_until_stockout: 5, days_of_inventory: 5,
  lead_time_days_used: 14, target_coverage_days: 60, target_inventory_units: 120,
  estimated_profit_impact: 220, data_quality_confidence: "high", data_quality_warnings: [],
  recommended_action: "Review replenishment", explanation: null,
};

test("missing, invalid or negative risk measurements are unknown, not low risk", () => {
  for (const value of [null, undefined, NaN, Infinity, -1]) {
    assert.equal(stockoutRiskLevel(value, 14), "Unknown");
    assert.equal(stockoutRiskLevel(50, value), "Unknown");
  }
  assert.equal(stockoutRiskLevel(50, 0), "Unknown");
  assert.equal(stockoutRiskLevel(0, 14), "Critical");
  assert.equal(stockoutRiskLevel(50, 14), "Low");
});

test("history-review report state cannot render Healthy despite a positive velocity and Low label", () => {
  const html = renderHealth({ ...known, daysLeft: null, status: "Review", riskLevel: "Low" });
  assert.match(html, />Review</);
  assert.match(html, /Stock cover unavailable/);
  assert.doesNotMatch(html, />Healthy<|has enough projected cover|stock-health-fill/);
});

test("incomplete history overrides stale healthy badges and stale cover estimates", () => {
  const html = renderHealth({ ...known, status: "Healthy", salesHistoryComplete: false, recommendedQty: 99, stockoutDate: "Tomorrow" });
  assert.match(html, />Review</);
  assert.match(html, /Sales history is incomplete/);
  assert.match(html, /Needs sales history/);
  assert.doesNotMatch(html, />Healthy<|Tomorrow|stock-health-fill/);
});

test("invalid healthy inputs never generate a sufficient-coverage claim or invalid CSS geometry", () => {
  for (const props of [{ daysLeft: null }, { dailyVelocity: 0 }, { currentStock: null }, { targetCoverageDays: NaN }, { leadTimeDays: Infinity }]) {
    const html = renderHealth({ ...known, status: "Healthy", ...props });
    assert.match(html, />Review</);
    assert.doesNotMatch(html, />Healthy<|has enough projected cover|width:NaN|left:NaN|Infinity%/);
  }
});

test("zero sales alone cannot turn existing stock into proven dead stock", () => {
  const html = renderHealth({ currentStock: 50, dailyVelocity: 0, leadTimeDays: 14, targetCoverageDays: 60 });
  assert.match(html, />Review</);
  assert.doesNotMatch(html, />Dead stock<|>Healthy</);
});

test("valid coverage below target is described numerically without claiming the target is exceeded", () => {
  const html = renderHealth(known);
  assert.match(html, /50 days against a 14-day lead time and a 60-day target/);
  assert.match(html, /Cover is below the target/);
  assert.doesNotMatch(html, /enough projected cover beyond/);
});

test("bar and lead/target markers share one scale, and true zero cover stays zero", () => {
  const scale = stockCoverageGeometry(20, 100, 14);
  assert.equal(scale.fill, 20);
  assert.equal(scale.lead, 98);
  assert.ok(Math.abs(scale.target - 14) < 1e-10);
  assert.equal(stockCoverageGeometry(0, 14, 60).fill, 0);
  assert.equal(stockCoverageGeometry(null, 14, 60).fill, null);
  assert.equal(stockCoverageGeometry(20, NaN, 60).lead, null);
});

test("ActionCard retains real urgent stockout behavior and bypasses projections for history review", () => {
  const html = renderToStaticMarkup(React.createElement(ActionCard, { action }));
  assert.match(html, />Stockout risk</);
  assert.match(html, /replenishment may not arrive before stock runs out/);
  const review = renderToStaticMarkup(React.createElement(ActionCard, { action: { ...action, status: "optimize", sales_history_complete: false, cash_tied_up: 0 } }));
  assert.match(review, /More sales history needed/);
  assert.doesNotMatch(review, /stock-health-badge-healthy/);
});

test("report history rows retain Unknown risk and do not infer inventory value from profit margin", () => {
  const row = reportMappings.actionToRow({ ...action, status: "optimize", sales_history_complete: false, cash_tied_up: 0 }, { profit_per_unit: 12 }, undefined);
  assert.equal(row.status, "Review");
  assert.equal(row.riskLevel, "Unknown");
  assert.equal(row.daysLeft, null);
  assert.equal(row.dailyVelocity, null);
  assert.equal(row.salesHistoryComplete, false);
  assert.equal(row.inventoryValue, null);
  const distribution = reportMappings.riskDistribution([row]);
  assert.equal(distribution.find(bucket => bucket.label === "Unknown").value, 1);
  assert.equal(distribution.find(bucket => bucket.label === "Low").value, 0);
});

test("missing action cost blocks legacy profit estimates without hiding valid stockout math", () => {
  const row = reportMappings.actionToRow({ ...action, financial_values_known: false, cost_source: "estimated_from_price", financial_values: { estimated_profit_impact: null } }, undefined, undefined);
  assert.equal(row.cashImpact, null);
  assert.equal(row.inventoryValue, null);
  assert.equal(row.daysLeft, 5);
  assert.equal(row.recommendedQty, 110);
  assert.equal(row.riskLevel, "Critical");
  const metric = reportMappings.buildMetrics("actions", [row]).find(metric => metric.label === "Estimated cash impact");
  assert.equal(metric.value, "Unknown");
});

test("reorder reports preserve canonical missing and known-zero costs instead of falling back", () => {
  const base = { sku_id: "SKU", name: "Shirt", vendor: "Supplier", current_on_hand: 10, unit_cost: 10, extended_cost: 200, landed_extended_cost: 220, recommended_order_qty: 20, expected_stockout_prob: 0.5, lead_time_days: 14, order_up_to: 60, rationale: "Review reorder" };
  const missing = reportMappings.reorderToRow({ ...base, financial_values_known: false, financial_values: { landed_extended_cost: null, unit_cost: null } }, { avg_daily_units: 2 }, undefined);
  assert.equal(missing.estimatedCost, null);
  assert.equal(missing.inventoryValue, null);
  assert.equal(missing.recommendedQty, 20);
  assert.equal(missing.daysLeft, 5);
  const zero = reportMappings.reorderToRow({ ...base, financial_values_known: true, financial_values: { landed_extended_cost: 0, unit_cost: 0 } }, undefined, undefined);
  assert.equal(zero.estimatedCost, 0);
  assert.equal(zero.inventoryValue, 0);
  assert.equal(reportMappings.vendorExposure([missing, zero]).length, 0);
});

test("forecast report does not present predicted demand as observed last-month sales", () => {
  const row = reportMappings.forecastToRow({ sku_id: "SKU", projected_30_day_demand: 150, stockout_probability_30d: 0.3, explain: "Forecast" }, undefined, { inventory_on_hand: 30, profit_per_unit: 12 });
  assert.equal(row.salesLast30, null);
  assert.equal(row.inventoryValue, null);
});
