const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.join(__dirname, "..");
function compile(file, extra = "") {
  return ts.transpileModule(fs.readFileSync(path.join(root, file), "utf8") + extra, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
}
const context = { exports: {} };
vm.runInNewContext(compile("lib/forecast-presentation.ts"), context);
const view = context.exports;
const observed = {
  sku_id: "OBSERVED", forecast_available: true, demand_signal: "observed", horizon_days: 30,
  method: "seasonal_ema", trend: "steady", seasonality: "flat", weekly_index: [1, 1, 1, 1, 1, 1, 1],
  confidence: "high", projected_30_day_demand: 60, projected_60_day_demand: 120,
  projected_90_day_demand: 180, stockout_probability_30d: 0.7,
  points: [{ day_offset: 1, expected_units: 2, lower_bound: 1, upper_bound: 3 }],
  explain: "Recorded daily demand estimate.", history_days: 90, adjusted_stockout_days: 0,
  data_quality_warnings: [], backtest_mae_14d: 0, backtest_mape_14d: 0,
  forecast_bias_14d: "balanced", trust_reasons: [],
};
const missing = { ...observed, sku_id: "MISSING", forecast_available: false, demand_signal: "missing_history",
  history_days: 0, projected_30_day_demand: 0, projected_60_day_demand: 0, projected_90_day_demand: 0,
  stockout_probability_30d: 0, data_quality_warnings: ["No recorded sales history."] };

test("missing history masks numeric placeholders, confidence and apparently perfect backtests", () => {
  const result = view.forecastView(missing);
  for (const key of ["demand30", "demand60", "demand90", "risk", "error"]) assert.equal(result[key], null);
  assert.equal(result.confidence, "Unknown");
  assert.equal(result.bias, "Unknown");
  assert.equal(result.history, "0 days");
  assert.equal(result.available, false);
});

test("recorded zero sales remain a zero estimate without invented backtest proof", () => {
  const result = view.forecastView({ ...missing, forecast_available: true, demand_signal: "no_recent_sales", history_days: 90, confidence: "low" });
  assert.equal(result.available, true);
  assert.equal(result.noRecentSales, true);
  assert.equal(result.demand30, 0);
  assert.equal(result.risk, 0);
  assert.equal(view.forecastNumber(result.demand30), "0");
  assert.equal(result.history, "90 days");
  assert.equal(result.error, null);
  assert.equal(result.bias, "Unknown");
  const measured = view.forecastView(observed);
  assert.equal(measured.error, 0);
  assert.equal(view.forecastPercent(measured.error), "0%");
  assert.equal(measured.bias, "balanced");
});

test("risk formatting avoids rounded certainty without capping backtest error percentages", () => {
  for (const value of [0.995, 0.999, 1]) assert.equal(view.forecastRiskPercent(value), ">99%");
  assert.equal(view.forecastRiskPercent(0.994), "99%");
  assert.equal(view.forecastRiskPercent(0.7), "70%");
  assert.equal(view.forecastRiskPercent(0), "0%");
  for (const value of [null, NaN, Infinity, -0.1, 1.1]) assert.equal(view.forecastRiskPercent(value), "Unknown");
  assert.equal(view.forecastPercent(1), "100%");
  assert.equal(view.forecastPercent(1.42), "142%");
});

test("old responses and omitted sample history stay unknown, not zero", () => {
  const result = view.forecastView({ ...observed, forecast_available: undefined, demand_signal: undefined, history_days: undefined });
  assert.equal(result.available, false);
  assert.equal(result.demand30, null);
  assert.equal(result.risk, null);
  assert.equal(result.history, "Unknown");
  assert.equal(result.error, null);
  const malformed = view.forecastView({ ...observed, projected_30_day_demand: NaN, stockout_probability_30d: 7, backtest_mape_14d: Infinity, history_days: -1 });
  assert.equal(malformed.demand30, null);
  assert.equal(malformed.risk, null);
  assert.equal(malformed.error, null);
  assert.equal(malformed.history, "Unknown");
});

test("risk and confidence filters exclude unavailable rows and preserve known zero versus unknown ranking", () => {
  const falseHigh = { ...missing, stockout_probability_30d: 1 };
  const zero = { ...observed, sku_id: "ZERO", demand_signal: "no_recent_sales", projected_30_day_demand: 0, stockout_probability_30d: 0, confidence: "low" };
  const rows = [falseHigh, zero, observed];
  for (const filter of ["high-risk", "at-risk", "high-confidence"]) assert.equal(view.filterForecasts(rows, filter, "").map(row => row.sku_id).join(","), "OBSERVED");
  assert.equal(view.filterForecasts(rows, "all", "missing")[0], falseHigh);
  assert.equal(view.rankForecastsByStockoutRisk(rows).map(row => row.sku_id).join(","), "OBSERVED,ZERO,MISSING");
  assert.equal(rows[0], falseHigh);
});

function harness(fetcher) {
  let cursor = 0;
  const slots = new Map(), effects = [], calls = [], exports = {};
  const jsx = (type, props) => ({ type, props });
  const deps = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, initial); return [slots.get(key), next => slots.set(key, typeof next === "function" ? next(slots.get(key)) : next)]; },
      useMemo: calculate => calculate(),
      useEffect(callback, dependencies) { const key = cursor++, old = slots.get(key); if (!old || dependencies.some((value, index) => value !== old.dependencies[index])) {
        const value = { dependencies, cleanup: old?.cleanup }; slots.set(key, value); effects.push(() => { value.cleanup?.(); value.cleanup = callback(); });
      } },
    },
    "next/link": { __esModule: true, default: "a" },
    "@/components/gated-feature": { GatedFeature: "gated" },
    "@/components/charts": { ChartPanel: "chart-panel", ForecastBandChart: "forecast-band", WeekdayIndexBars: "weekday-bars" },
    "@/lib/api-v2": { fetchForecasts: async signal => { calls.push(signal); return fetcher(); } },
    "@/lib/forecast-presentation": view,
  };
  vm.runInNewContext(compile("app/(app-shell)/forecast/page.tsx", "\nexport { ForecastContent as TestContent };"), {
    exports, AbortController, require(name) { assert.ok(name in deps, `Unexpected import ${name}`); return deps[name]; },
  });
  function render() {
    cursor = 0;
    const tree = exports.TestContent(), nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string" || typeof node === "number") { texts.push(String(node)); return; }
      if (!node?.props) return;
      nodes.push(node);
      if (typeof node.type === "function") walk(node.type(node.props)); else walk(node.props.children);
    }
    walk(tree);
    while (effects.length) effects.shift()();
    return { nodes, text: texts.join(" "), button: title => nodes.find(node => node.type === "button" && node.props.children === title) };
  }
  async function settle() { for (let i = 0; i < 5; i++) { render(); await new Promise(setImmediate); } return render(); }
  return { render, settle, calls };
}

test("actual missing-history page shows next steps and Unknown metrics without charts or green safety", async () => {
  const h = harness(() => ({ forecasts: [missing] }));
  const ui = await h.settle();
  assert.match(ui.text, /Sales history is needed for this SKU/);
  assert.match(ui.text, /30-day demand Unknown/);
  assert.match(ui.text, /14-day backtest error Unknown/);
  assert.match(ui.text, /Recorded history 0 days/);
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/store-sync"));
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/import-shipstation"));
  assert.equal(ui.nodes.some(node => node.type === "forecast-band" || node.type === "weekday-bars"), false);
  assert.equal(ui.nodes.some(node => String(node.props.className || "").includes("risk-low")), false);
  assert.ok(ui.button("High 30-day risk"));
});

test("actual known-zero page retains an estimate with an explicit caution and no green safety tone", async () => {
  const h = harness(() => ({ forecasts: [{ ...missing, forecast_available: true, demand_signal: "no_recent_sales", history_days: 90, confidence: "low" }] }));
  const ui = await h.settle();
  assert.match(ui.text, /30-day demand 0/);
  assert.match(ui.text, /not proof that future demand or stockout risk is zero/);
  assert.match(ui.text, /14-day backtest error Unknown/);
  assert.equal(ui.nodes.some(node => String(node.props.className || "").includes("risk-low")), false);
  assert.ok(ui.nodes.some(node => node.type === "forecast-band"));
});

test("actual low-confidence page separates saturated risk estimates from relative backtest error", async () => {
  const h = harness(() => ({ forecasts: [{ ...observed, confidence: "low", stockout_probability_30d: 1,
    backtest_mape_14d: 1.42, history_days: 45 }] }));
  const ui = await h.settle();
  assert.match(ui.text, />99%\s+estimated risk/);
  assert.match(ui.text, /Estimated stockout risk \(30d\) >99%/);
  assert.match(ui.text, /14-day backtest error 142%/);
  assert.match(ui.text, /Low confidence: short or sparse sales history/);
  assert.match(ui.text, /divided by the larger of actual sales and one unit/);
  assert.match(ui.text, /It can exceed 100%/);
  assert.doesNotMatch(ui.text, /100% estimated risk|stockout risk \(30d\) 100%/);
});

test("filtered forecast details follow a visible selection and clear when no SKU matches", async () => {
  const h = harness(() => ({ forecasts: [observed, missing] }));
  let ui = await h.settle();
  ui.nodes.filter(node => node.type === "button" && node.props.className === "sku-list-button").at(-1).props.onClick();
  ui = h.render();
  assert.match(ui.text, /Sales history is needed for this SKU/);
  ui.button("High confidence").props.onClick();
  ui = h.render();
  assert.doesNotMatch(ui.text, /Sales history is needed for this SKU/);
  assert.match(ui.text, /30-day demand 60/);
  const buttons = ui.nodes.filter(node => node.type === "button" && node.props.className === "sku-list-button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].props["aria-pressed"], true);
  ui.nodes.find(node => node.type === "input" && node.props.placeholder === "Search SKU").props.onChange({ target: { value: "no such SKU" } });
  ui = h.render();
  assert.match(ui.text, /No SKUs match this quick view/);
  assert.match(ui.text, /Clear the quick view or search to select a forecast/);
  assert.doesNotMatch(ui.text, /30-day demand 60|Sales history is needed for this SKU/);
  assert.equal(ui.nodes.some(node => node.type === "forecast-band"), false);
  ui.button("Show all SKUs").props.onClick();
  ui = h.render();
  assert.match(ui.text, /Sales history is needed for this SKU/);
  assert.equal(ui.nodes.filter(node => node.type === "button" && node.props.className === "sku-list-button").at(-1).props["aria-pressed"], true);
});

test("forecast load failure is actionable, redacts transport details and retries the real request", async () => {
  let attempts = 0;
  const h = harness(() => { if (++attempts === 1) throw new Error("private-api.invalid/?token=secret"); return { forecasts: [observed] }; });
  let ui = await h.settle();
  assert.match(ui.text, /Forecasts could not be loaded/);
  assert.doesNotMatch(ui.text, /private-api|secret/);
  ui.button("Retry forecasts").props.onClick();
  ui = await h.settle();
  assert.equal(h.calls.length, 2);
  assert.equal(h.calls[0].aborted, true);
  assert.match(ui.text, /30-day demand 60/);
  assert.ok(ui.nodes.some(node => node.type === "forecast-band"));
});

test("explicit sample forecasts retain charts while omitted history and backtests stay unknown", () => {
  const exports = {};
  vm.runInNewContext(compile("lib/demo-data.ts"), { exports });
  assert.ok(exports.DEMO_FORECASTS.forecasts.length > 0);
  for (const forecast of exports.DEMO_FORECASTS.forecasts) {
    const result = view.forecastView(forecast);
    assert.equal(result.available, true);
    assert.equal(result.history, "Unknown");
    assert.equal(result.error, null);
    assert.ok(forecast.points.length > 0);
  }
});
