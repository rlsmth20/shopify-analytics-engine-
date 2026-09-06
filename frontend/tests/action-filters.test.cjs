const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.join(__dirname, "..");
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file);
  const exports = {};
  cache.set(file, exports);
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(compiled, { exports, process, Intl, URLSearchParams, require: (name) => name.startsWith("@/") ? load(path.join(root, name.slice(2) + ".ts")) : require(name) });
  return exports;
}
const { filterInventoryActions, readActionFilters, DEFAULT_ACTION_FILTERS: defaults } = load(path.join(root, "lib/action-filters.ts"));
const { isHistoryReviewAction } = load(path.join(root, "lib/action-quality.ts"));
const actions = [
  { sku_id: "blue-1", name: "Blue Shirt", status: "urgent", data_quality_confidence: "high", days_until_stockout: 3, days_of_inventory: 3, priority_score: 20, estimated_profit_impact: 400 },
  { sku_id: "blue-2", name: "Blue Jacket", status: "urgent", data_quality_confidence: "low", days_until_stockout: 12, days_of_inventory: 12, priority_score: 90, estimated_profit_impact: 200 },
  { sku_id: "red-1", name: "Red Scarf", status: "dead", data_quality_confidence: "high", days_of_inventory: 300, priority_score: 10, cash_tied_up: 900 },
];
test("search, confidence, and stockout window combine correctly", () => {
  const result = filterInventoryActions(actions, { ...defaults, query: " BLUE ", confidence: "high", stockoutDays: "7" });
  assert.equal(result.length, 1);
  assert.equal(result[0].sku_id, "blue-1");
});
test("stockout window excludes non-urgent actions", () => {
  assert.equal(filterInventoryActions(actions, { ...defaults, stockoutDays: "14" }).length, 2);
});
test("priority and impact sorts are explicit and do not mutate the source", () => {
  assert.equal(filterInventoryActions(actions, defaults)[0].sku_id, "blue-2");
  assert.equal(filterInventoryActions(actions, { ...defaults, sort: "impact" })[0].sku_id, "red-1");
  assert.equal(actions[0].sku_id, "blue-1");
});
test("chart links restore valid filters and reject invalid enum values", () => {
  const restored = readActionFilters(new URLSearchParams("status=dead&sort=impact&q=red&confidence=unknown&stockout=900"));
  assert.equal(restored.status, "dead");
  assert.equal(restored.sort, "impact");
  assert.equal(restored.confidence, "all");
  assert.equal(restored.stockoutDays, "all");
  assert.equal(filterInventoryActions(actions, restored)[0].sku_id, "red-1");
});
test("unmatched searches return an empty result", () => {
  assert.equal(filterInventoryActions(actions, { ...defaults, query: "unmatched" }).length, 0);
});
test("insufficient history is distinct from established excess and urgent stockout risk", () => {
  assert.equal(isHistoryReviewAction({ status: "optimize", sales_history_complete: false }), true);
  assert.equal(isHistoryReviewAction({ status: "optimize", sales_history_complete: true }), false);
  assert.equal(isHistoryReviewAction({ status: "optimize" }), false);
  assert.equal(isHistoryReviewAction({ status: "urgent", sales_history_complete: false }), false);
});
