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
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root, relative), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(compiled, {
    exports, process, Intl, URLSearchParams,
    require: (name) => {
      if (name.endsWith(".module.css")) return { default: {} };
      if (name === "@/components/action-card") return { ActionCard: () => null };
      if (name.startsWith("@/")) return load(name.slice(2) + (name.startsWith("@/components/") ? ".tsx" : ".ts"));
      return require(name);
    },
  });
  return exports;
}
const { labelRevenueDays, formatDashboardMoney, formatForecastVariance, dashboardKpiNote } = load("lib/dashboard-presentation.ts");
const { actionTableMetrics } = load("lib/action-presentation.ts");
const { ActionTable } = load("components/action-table.tsx");
const urgent = {
  sku_id: "shirt-blue-s", name: "Blue shirt / Small", status: "urgent", urgency_level: "critical",
  current_on_hand: 12, days_until_stockout: 3, days_of_inventory: 3, lead_time_days_used: 14,
  target_inventory_units: 80, estimated_profit_impact: 1234, priority_score: 85,
  data_quality_confidence: "high", data_quality_warnings: [],
};

test("revenue day labels use completed UTC dates anchored to the response across year boundaries", () => {
  const input = [{ label: "30", value: 15 }, { label: "1", value: 10 }];
  const points = labelRevenueDays(input, "2026-01-01T00:05:00Z");
  assert.equal(points[0].label, "Dec 2");
  assert.equal(points[1].label, "Dec 31");
  assert.equal(points[1].value, 10);
  assert.equal(input[1].label, "1");
});
test("unknown date labels and invalid response timestamps are preserved without guessing", () => {
  const points = [{ label: "Aug 3", value: 0 }, { label: "0", value: 1 }];
  assert.equal(labelRevenueDays(points, "not-a-date"), points);
  assert.equal(labelRevenueDays(points, "2026-01-01T00:00:00Z")[0].label, "Aug 3");
  assert.equal(labelRevenueDays(points, "2026-01-01T00:00:00Z")[1].label, "0");
});
test("small money amounts remain visible and forecast direction is explicit", () => {
  assert.equal(formatDashboardMoney(12.34), "$12.34");
  assert.equal(formatDashboardMoney(1000000), "$1,000,000");
  assert.equal(formatDashboardMoney(NaN), "Unavailable");
  assert.equal(formatForecastVariance(8.5), "+8.5%");
  assert.equal(formatForecastVariance(-8.5), "-8.5%");
  assert.equal(formatForecastVariance(0), "0.0%");
});
test("KPI descriptions distinguish catalog-price revenue from current inventory value", () => {
  assert.match(dashboardKpiNote("Revenue (30d)"), /current catalog prices/);
  assert.match(dashboardKpiNote("Inventory value"), /on-hand inventory at cost/);
});
test("urgent comparison exposes replenishment need and a lead-time shortfall", () => {
  const metrics = actionTableMetrics(urgent);
  assert.equal(metrics.reorderUnits, 68);
  assert.equal(metrics.runsOutBeforeDelivery, true);
  assert.equal(metrics.impact, 1234);
  assert.equal(actionTableMetrics({ ...urgent, days_until_stockout: 14 }).runsOutBeforeDelivery, false);
});
test("missing history and missing numeric values do not become zero-risk claims", () => {
  const history = actionTableMetrics({ ...urgent, status: "optimize", sales_history_complete: false, cash_tied_up: 0 });
  assert.equal(history.historyReview, true);
  assert.equal(history.coverage, null);
  assert.equal(history.impact, null);
  assert.equal(history.reorderUnits, null);
  const unknown = actionTableMetrics({ ...urgent, current_on_hand: null, days_until_stockout: null, days_of_inventory: null, lead_time_days_used: null });
  assert.equal(unknown.coverage, null);
  assert.equal(unknown.stock, null);
  assert.equal(unknown.reorderUnits, null);
  assert.equal(unknown.runsOutBeforeDelivery, false);
});
test("comparison table provides units, exposure type, lead-time warning and an accessible review control", () => {
  const html = renderToStaticMarkup(React.createElement(ActionTable, { actions: [urgent] }));
  assert.match(html, /12 units/);
  assert.match(html, /68 units/);
  assert.match(html, /Lead time: 14 days/);
  assert.match(html, /May run out before delivery/);
  assert.match(html, /Estimated profit at risk/);
  assert.match(html, /monetary estimates in USD/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /Review recommendation for Blue shirt \/ Small/);
});
test("history-review table rows distinguish unestablished exposure and display quality warnings", () => {
  const action = { ...urgent, status: "optimize", sales_history_complete: false, cash_tied_up: 0, data_quality_confidence: "low", data_quality_warnings: ["Import more history"] };
  const html = renderToStaticMarkup(React.createElement(ActionTable, { actions: [action] }));
  assert.match(html, /Needs history/);
  assert.match(html, /Not established/);
  assert.match(html, /1 warning in details/);
  assert.doesNotMatch(html, /May run out before delivery/);
});

test("ambiguous comparison masks stale purchasing and risk numbers while retaining recorded stock", () => {
  const held = { ...urgent, identity_ambiguous: true };
  const metrics = actionTableMetrics(held);
  assert.equal(metrics.identityReview, true);
  assert.equal(metrics.stock, 12);
  for (const key of ["coverage", "impact", "reorderUnits", "leadTime"]) assert.equal(metrics[key], null);
  const html = renderToStaticMarkup(React.createElement(ActionTable, { actions: [held] }));
  assert.match(html, /Review SKU mapping/);
  assert.match(html, /Withheld until mapping review/);
  assert.doesNotMatch(html, /68 units|May run out before delivery/);
});

test("table expansion follows product identity when two variants share a SKU and rows reorder", () => {
  let expanded = null;
  const jsx = (type, props, key) => ({ type, props, key });
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: { Fragment: "fragment", useId: () => "table", useState: () => [expanded, value => { expanded = value; }] },
    "@/components/action-card": { ActionCard: "action-card" },
    "@/lib/action-presentation": { actionTableMetrics },
    "@/lib/product-identity": load("lib/product-identity.ts"),
    "@/lib/app-helpers": load("lib/app-helpers.ts"),
    "./action-table.module.css": { default: {} },
  };
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, "components/action-table.tsx"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, require: name => { assert.ok(name in dependencies, name); return dependencies[name]; } });
  const variants = [1, 2].map(product_id => ({ ...urgent, product_id, sku_id: "SHARED", name: `Variant ${product_id}` }));
  function render(actions) {
    const nodes = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (!node?.props) return;
      nodes.push(node); walk(node.props.children);
    }
    walk(exports.ActionTable({ actions }));
    return nodes;
  }
  let nodes = render(variants);
  const rows = nodes.filter(node => node.type === "fragment");
  assert.equal(new Set(rows.map(node => node.key)).size, 2);
  nodes.filter(node => node.type === "button")[1].props.onClick();
  nodes = render([...variants].reverse());
  assert.equal(nodes.filter(node => node.type === "button" && node.props["aria-expanded"]).length, 1);
  assert.equal(nodes.find(node => node.type === "action-card").props.action.product_id, 2);
});
