const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/financial-values.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: exportsObject });
const { financialValue, financialTotal, knownPointValue } = exportsObject;

test("canonical unknown overrides legacy estimated money without hiding recorded zero", () => {
  assert.equal(financialValue({ financial_values: { total_cost: null } }, "total_cost", 17000), null);
  assert.equal(financialValue({ financial_values: { total_cost: 0 } }, "total_cost", 17000), 0);
  assert.equal(financialValue({ cost_source: "recorded" }, "unit_cost", 0), 0);
});

test("missing and price-inferred costs never become known through legacy fallback", () => {
  for (const row of [{ cost_source: "missing" }, { cost_source: "estimated_from_price" }, { financial_values_known: false }]) {
    assert.equal(financialValue(row, "unit_cost", 40), null);
  }
  assert.equal(financialValue({}, "unit_cost", 40), 40);
  assert.equal(financialValue({}, "unit_cost", Number.NaN), null);
});

test("an incomplete financial total stays unknown instead of becoming a partial sum", () => {
  assert.equal(financialTotal([100, null, 20]), null);
  assert.equal(financialTotal([100, 0, 20]), 120);
  assert.equal(financialTotal([]), 0);
  assert.equal(financialTotal([Infinity]), null);
});

test("chart and KPI canonical unknown does not become a zero or a legacy estimate", () => {
  assert.equal(knownPointValue({ value: 17000, value_known: false }), null);
  assert.equal(knownPointValue({ value: 17000, known_value: null }), null);
  assert.equal(knownPointValue({ value: 17000, known_value: 0 }), 0);
  assert.equal(knownPointValue({ value: 17000, known_value: 120 }), 120);
  assert.equal(knownPointValue({ value: 42 }), 42);
});
