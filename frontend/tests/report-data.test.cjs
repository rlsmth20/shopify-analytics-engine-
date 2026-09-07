const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.join(__dirname, "..");

function harness(overrides = {}) {
  const calls = [];
  const fixtures = { actions: [{ sku_id: "shirt" }], forecasts: [{ sku_id: "shirt" }], suggestions: [{ sku_id: "shirt" }], scorecards: [{ sku_id: "shirt" }] };
  const request = (name) => async (...args) => {
    calls.push(name);
    return overrides[name] ? overrides[name](...args) : fixtures;
  };
  const modules = new Map([
    ["lib/api.ts", { fetchInventoryActions: request("actions") }],
    ["lib/api-v2.ts", { fetchForecasts: request("forecast"), fetchReorderSuggestions: request("reorder"), fetchScorecards: request("scorecards") }],
  ]);
  function load(relative) {
    if (modules.has(relative)) return modules.get(relative);
    const exports = {};
    modules.set(relative, exports);
    const compiled = ts.transpileModule(fs.readFileSync(path.join(root, relative), "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    vm.runInNewContext(compiled, { exports, process, console, Error, URLSearchParams, URL,
      require: (name) => name.startsWith("@/") ? load(name.slice(2) + ".ts") : require(name),
    });
    return exports;
  }
  const api = load("lib/report-data.ts");
  const plans = load("lib/plans.ts");
  const entitlements = (plan) => ({
    plan_id: plan,
    capabilities: Object.keys(plans.PLAN_CAPABILITIES).filter((key) => plans.hasCapability(plan, key)),
  });
  return { ...api, calls, fixtures, entitlements };
}
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

test("Starter basic reports do not request Growth-only forecast or reorder endpoints", async () => {
  const h = harness();
  const starter = h.entitlements("starter");
  assert.ok(starter.capabilities.includes("reports_basic"));
  assert.ok(starter.capabilities.includes("action_queue_basic"));
  assert.ok(!starter.capabilities.includes("forecast"));
  const updates = [];
  await h.loadReportData(starter, false, new AbortController().signal, (state) => updates.push(state));
  assert.deepEqual(h.calls.sort(), ["actions", "scorecards"]);
  const state = updates.at(-1);
  assert.equal(state.sources.actions.status, "ready");
  assert.equal(state.sources.forecasts.status, "locked");
  assert.equal(state.sources.reorder.status, "locked");
  assert.equal(state.data.actions[0].sku_id, "shirt");
  assert.equal(h.reportDataset("dead-stock"), "actions");
  assert.equal(h.reportContextWarning("actions", state.sources), null);
});

test("Growth forecast failure preserves completed action and reorder reports", async () => {
  const h = harness({ forecast: async () => { throw new Error("Forecast temporarily unavailable"); } });
  let state;
  await h.loadReportData(h.entitlements("growth"), false, new AbortController().signal, (update) => { state = update; });
  assert.equal(state.sources.forecasts.status, "error");
  assert.equal(state.sources.forecasts.message, "Forecast temporarily unavailable");
  assert.equal(state.sources.actions.status, "ready");
  assert.equal(state.sources.reorder.status, "ready");
  assert.equal(state.data.actions.length, 1);
  assert.equal(state.data.reorder.length, 1);
  assert.match(h.reportContextWarning("actions", state.sources), /supporting data/);
});

test("completed action data is published before a slow forecast finishes", async () => {
  const forecast = deferred();
  const h = harness({ forecast: () => forecast.promise });
  const updates = [];
  const loading = h.loadReportData(h.entitlements("growth"), false, new AbortController().signal, (state) => updates.push(state));
  await new Promise(setImmediate);
  assert.equal(updates.at(-1).sources.actions.status, "ready");
  assert.equal(updates.at(-1).sources.forecasts.status, "loading");
  assert.equal(updates.at(-1).data.actions.length, 1);
  forecast.resolve({ forecasts: [] });
  await loading;
  assert.equal(updates.at(-1).sources.forecasts.status, "ready");
  assert.equal(updates.at(-1).data.actions.length, 1);
});

test("action and optional scorecard failures do not hide permitted forecast rows", async () => {
  const fail = async () => { throw new Error("Unavailable"); };
  const h = harness({ actions: fail, scorecards: fail });
  let state;
  await h.loadReportData(h.entitlements("growth"), false, new AbortController().signal, (update) => { state = update; });
  assert.equal(state.sources.actions.status, "error");
  assert.equal(state.sources.scorecards.status, "error");
  assert.equal(state.sources.forecasts.status, "ready");
  assert.equal(state.data.forecasts.length, 1);
  assert.match(h.reportContextWarning("stockout", state.sources), /marked unavailable/);
});

test("unknown plan access keeps basic reports usable without guessing paid access", async () => {
  const h = harness();
  let state;
  await h.loadReportData(null, false, new AbortController().signal, (update) => { state = update; });
  assert.deepEqual(h.calls.sort(), ["actions", "scorecards"]);
  assert.equal(state.sources.actions.status, "ready");
  assert.equal(state.sources.forecasts.status, "unverified");
  assert.equal(state.sources.reorder.status, "unverified");
});

test("sample workspace retains all report previews while backend denials remain errors", async () => {
  const h = harness({ reorder: async () => { throw new Error("Your current plan does not include this feature."); } });
  let state;
  await h.loadReportData(null, true, new AbortController().signal, (update) => { state = update; });
  assert.deepEqual(h.calls.sort(), ["actions", "forecast", "reorder", "scorecards"]);
  assert.equal(state.sources.reorder.status, "error");
  assert.equal(state.sources.actions.status, "ready");
  assert.equal(state.data.reorder.length, 0);
});

test("aborted or superseded report loads never publish late data or errors", async () => {
  const response = deferred();
  const h = harness(Object.fromEntries(["actions", "forecast", "reorder", "scorecards"].map((name) => [name, () => response.promise])));
  const controller = new AbortController();
  const updates = [];
  const loading = h.loadReportData(h.entitlements("growth"), false, controller.signal, (state) => updates.push(state));
  assert.equal(updates.length, 1);
  controller.abort();
  response.resolve(h.fixtures);
  await loading;
  assert.equal(updates.length, 1);
  await h.loadReportData(h.entitlements("growth"), false, controller.signal, (state) => updates.push(state));
  assert.equal(updates.length, 1);
});
