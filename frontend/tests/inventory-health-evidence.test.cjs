const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const compile = file => ts.transpileModule(readFileSync(path.join(__dirname, file), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const finance = {};
vm.runInNewContext(compile("../lib/financial-values.ts"), { exports: finance });
const jsx = (type, props) => ({ type, props });
const currency = value => value === null ? "Unknown" : `$${value.toLocaleString("en-US")}`;
const identity = {}, identityNotice = {};
vm.runInNewContext(compile("../lib/product-identity.ts"), { exports: identity });
vm.runInNewContext(compile("../components/identity-review-notice.tsx"), {
  exports: identityNotice,
  require: name => ({
    "react/jsx-runtime": { jsx, jsxs: jsx },
    "next/link": { __esModule: true, default: "a" },
    "@/lib/product-identity": identity,
  })[name],
});

function renderHealth(health) {
  let stateIndex = 0;
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: { useEffect() {}, useMemo: calculate => calculate(), useState: initial => [[health, null, false][stateIndex++] ?? initial, () => {}] },
    "next/link": { __esModule: true, default: "a" },
    "@/components/chart-card": { ChartCard: "ChartCard" },
    "@/components/inventory-value-chart": { InventoryValueChart: "InventoryValueChart" },
    "@/components/empty-state": { EmptyState: "EmptyState" },
    "@/components/kpi-card": { KpiCard: "KpiCard" },
    "@/components/identity-review-notice": identityNotice,
    "@/lib/use-action-feed": { useActionFeed: () => ({ actions: [], dataSource: "db", isLoading: false, errorMessage: null }) },
    "@/lib/financial-values": finance,
    "@/lib/api-v2": { currency },
    "@/lib/app-helpers": {
      confidenceLabel: { high: "High", medium: "Medium", low: "Low" },
      currencyFormatter: new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }),
      numberFormatter: new Intl.NumberFormat("en-US"), leadTimeSourceLabel: {}, urgencyLabel: {},
      summarizeDataSource: () => "Live store", getActionImpactValue: () => null,
    },
  };
  const exports = {};
  vm.runInNewContext(compile("../app/(app-shell)/analytics/page.tsx"), { exports, require: name => {
    if (!dependencies[name]) throw new Error(`Unexpected dependency: ${name}`);
    return dependencies[name];
  } });
  const nodes = [], text = [];
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (typeof node === "string" || typeof node === "number") { text.push(node); return; }
    if (!node || typeof node !== "object") return;
    if (typeof node.type === "function") return walk(node.type(node.props));
    nodes.push(node);
    walk(node.props?.children);
  }
  walk(exports.default());
  return { nodes, text: text.join(" ").replace(/\s+/g, " "), riskKpi: nodes.find(node => node.type === "KpiCard" && node.props.label === "Stockout revenue risk"),
    emptyRisk: nodes.find(node => node.type === "EmptyState" && /exposure/i.test(node.props.title)) };
}

function health(changes = {}) {
  return { kpis: [{ label: "Stockout revenue risk", value: 0, value_known: false, known_value: null, unit: "currency", note: "Sales history unavailable." }],
    insights: [], health_buckets: [], forecast_confidence: [], top_stockout_risk: [], top_cash_trapped: [],
    forecast_coverage: { total_skus: 2, available_skus: 0, unavailable_skus: 2, low_confidence_skus: 0, no_recent_sales_skus: 0 }, ...changes };
}

test("missing forecast evidence renders Unknown and an unassessed empty state", () => {
  const ui = renderHealth(health());
  assert.equal(ui.riskKpi.props.value, "Unknown");
  assert.match(ui.text, /0 of 2 SKUs can be assessed/);
  assert.match(ui.text, /Total stockout exposure is unknown/);
  assert.match(ui.emptyRisk.props.title, /not fully assessed/);
  assert.match(ui.emptyRisk.props.description, /does not mean there is no stockout risk/);
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/store-sync"));
});

test("partial coverage does not replace Unknown with its positive legacy subtotal", () => {
  const ui = renderHealth(health({
    kpis: [{ label: "Stockout revenue risk", value: 2500, value_known: false, known_value: null, unit: "currency", note: "Estimated subtotal: $2,500 from 1 of 2 SKUs." }],
    forecast_coverage: { total_skus: 2, available_skus: 1, unavailable_skus: 1, low_confidence_skus: 1, no_recent_sales_skus: 0 },
    top_stockout_risk: [{ sku_id: "A", name: "Fixture SKU", vendor: "Fixture vendor", value: 2500,
      note: "Low-confidence stockout estimate. Verify recent sales before ordering.", severity: "warning" }],
  }));
  assert.equal(ui.riskKpi.props.value, "Unknown");
  assert.match(ui.riskKpi.props.note, /subtotal/);
  assert.match(ui.text, /ranked estimates cover the available forecasts only/);
  assert.match(ui.text, /Low-confidence stockout estimate/);
  assert.match(ui.text, /\$2,500/);
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/forecast"));
});

test("observed zero sales show a real zero estimate with no claim of guaranteed demand", () => {
  const ui = renderHealth(health({
    kpis: [{ label: "Stockout revenue risk", value: 0, value_known: true, known_value: 0, unit: "currency", note: "Observed zero sales do not guarantee zero future demand." }],
    forecast_coverage: { total_skus: 1, available_skus: 1, unavailable_skus: 0, low_confidence_skus: 1, no_recent_sales_skus: 1 },
  }));
  assert.equal(ui.riskKpi.props.value, "$0");
  assert.match(ui.text, /1 of 1 SKUs can be assessed/);
  assert.match(ui.text, /do not guarantee zero future demand/);
  assert.doesNotMatch(ui.text, /Total stockout exposure is unknown/);
  assert.equal(ui.emptyRisk.props.title, "No exposure estimated in available forecasts");
});

test("legacy health responses use a qualified empty state without fabricating coverage", () => {
  const fixture = health(); delete fixture.forecast_coverage;
  const ui = renderHealth(fixture);
  assert.doesNotMatch(ui.text, /SKUs can be assessed/);
  assert.match(ui.emptyRisk.props.title, /available forecasts/);
  assert.doesNotMatch(ui.emptyRisk.props.description, /no stockout risk|no meaningful revenue/i);
});

test("duplicate variants remain distinct review items while complete risk stays unknown", () => {
  const ui = renderHealth(health({
    identity_issues: [
      { product_id: 7, sku_id: "SHARED", name: "Fast variant", current_on_hand: 10, message: "Review" },
      { product_id: 8, sku_id: "SHARED", name: "Slow variant", current_on_hand: 80, message: "Review" },
    ],
  }));
  assert.equal(ui.riskKpi.props.value, "Unknown");
  assert.match(ui.text, /2 products need mapping review/);
  assert.match(ui.text, /Fast variant/);
  assert.match(ui.text, /Slow variant/);
  assert.match(ui.text, /Forecasts and recommendations for these products are withheld/);
  assert.match(ui.text, /history or product mapping review/);
  assert.equal(ui.nodes.filter(node => node.type === "li").length, 2);
});
