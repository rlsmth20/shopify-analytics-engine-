const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const source = ts.transpileModule(readFileSync(path.join(__dirname, "../lib/growth-dashboard.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const context = { exports: {}, Intl, Date, Number, Math };
vm.runInNewContext(source, context);
const view = context.exports;

test("unknown amounts and absent counts remain distinct from observed zero", () => {
  for (const value of [null, undefined, NaN, Infinity]) {
    assert.equal(view.growthNumber(value), "Unknown");
    assert.equal(view.growthMoney(value), "Unknown");
    assert.equal(view.growthPercent(value), "Unknown");
  }
  assert.equal(view.growthNumber(0), "0");
  assert.equal(view.growthMoney(0), "$0.00");
  assert.equal(view.growthPercent(0), "0%");
  assert.equal(view.growthMoney(.0007), "$0.0007");
});

test("unlinked contacts cannot turn into zero conversions", () => {
  assert.equal(view.outcomeLabel(0, 0, 13), "Unknown");
  assert.equal(view.outcomeLabel(0, 2, 13), "Unknown");
  assert.equal(view.outcomeLabel(1, 2, 13), "1+");
  assert.equal(view.outcomeLabel(0, 13, 13), "0");
  assert.equal(view.outcomeLabel(1, 13, 13), "1");
  assert.equal(view.outcomeLabel(0, 0, 0), "Unknown");
});

test("empty, negative and overflow chart measurements stay within bounds", () => {
  assert.equal(view.chartWidth(13, 20), 65);
  assert.equal(view.chartWidth(30, 20), 100);
  assert.equal(view.chartWidth(-1, 20), 0);
  assert.equal(view.chartWidth(null, 20), 0);
  assert.equal(view.chartWidth(4, 0), 0);
  assert.equal(view.chartWidth(NaN, 20), 0);
  assert.ok(!view.FUNNEL_STAGES.some(([stage]) => stage === "CALCULATOR_USED"));
});
