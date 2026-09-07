const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const output = {};
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/inventory-health-check.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
// The diagnostic needs no browser storage, HTTP client or server dependency.
vm.runInNewContext(compiled, { exports: output, TextEncoder });
const { analyzeInventoryHealth, healthResultsCsv, containsSampleHealthRows, HEALTH_CHECK_MAX_ROWS, HEALTH_CHECK_MAX_BYTES, HEALTH_CHECK_TEMPLATE } = output;
const settings = { salesDays: 30, defaultLeadDays: 14, targetCoverDays: 60 };
const header = "sku,on_hand,units_sold,unit_cost,lead_time_days,safety_stock";
const analyze = (lines, overrides = {}) => analyzeInventoryHealth([header, ...lines].join("\n"), { ...settings, ...overrides });

test("CSV accepts a UTF-8 BOM, CRLF, reordered/case-normalized headers and blank lines", () => {
  const result = analyzeInventoryHealth("\uFEFFUNITS SOLD,SKU,ON HAND\r\n30,SHIRT-S,90\r\n\r\n", settings);
  assert.equal(result.errors.length, 0);
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].sku, "SHIRT-S");
  assert.equal(result.rows[0].unitsSold, 30);
  assert.equal(result.rows[0].onHand, 90);
});

test("quoted commas, escaped quotes and embedded newlines survive CSV parsing", () => {
  const result = analyze(['"TEE, size ""L""",90,30,,,', '"TWO\nLINES",90,30,,,']);
  assert.equal(result.errors.length, 0);
  assert.equal(result.rows.some(row => row.sku === 'TEE, size "L"'), true);
  assert.equal(result.rows.some(row => row.sku === "TWO\nLINES"), true);
});

test("malformed quotes and field counts reject the entire file instead of a partial analysis", () => {
  for (const invalid of ['"unfinished,2,3,,,', 'BAD"QUOTE,2,3,,,', '"CLOSED"extra,2,3,,,', "SHORT,2,3", "LONG,2,3,,,,"]) {
    const result = analyze(["VALID,90,30,,,", invalid]);
    assert.equal(result.rows.length, 0, invalid);
    assert.ok(result.errors.length > 0, invalid);
  }
});

test("missing or duplicate required headers and empty input cannot silently remap merchant inputs", () => {
  for (const csv of [
    "sku,on_hand\nA,1", "sku,units_sold\nA,1", "on_hand,units_sold\n1,1",
    "sku,on_hand,units_sold,ON HAND\nA,1,1,1", "sku,on_hand,units_sold\n", "\n\n",
  ]) {
    const result = analyzeInventoryHealth(csv, settings);
    assert.equal(result.rows.length, 0);
    assert.ok(result.errors.length > 0);
  }
});

test("SKUs are trimmed and duplicates are rejected without double-counting a variant", () => {
  const result = analyze([" SHIRT-S ,90,30,,,", "shirt-s,30,10,,,"]);
  assert.equal(result.rows.length, 0);
  assert.match(result.errors[0], /duplicate SKU/);
  for (const sku of ["", "X".repeat(121)]) {
    assert.ok(analyze([`${sku},90,30,,,`]).errors.length > 0);
  }
});

test("numeric fields reject missing required values, currency/grouping, signs, exponents and nonfinite values", () => {
  for (const bad of ["", "-1", "+1", "$1", '"1,000"', "1e3", "Infinity", "NaN", "10000001"]) {
    assert.ok(analyze([`SKU,${bad},30,,,`]).errors.length > 0, `on_hand=${bad}`);
    assert.ok(analyze([`SKU,90,${bad},,,`]).errors.length > 0, `units_sold=${bad}`);
  }
  for (const bad of ["-1", "$2", "no", "NaN"]) {
    assert.ok(analyze([`SKU,90,30,${bad},,`]).errors.length > 0, `unit_cost=${bad}`);
    assert.ok(analyze([`SKU,90,30,,${bad},`]).errors.length > 0, `lead_time=${bad}`);
    assert.ok(analyze([`SKU,90,30,,,${bad}`]).errors.length > 0, `safety_stock=${bad}`);
  }
});

test("unknown optional cost stays null, while known zero cost and blank lead/buffer remain distinct", () => {
  const result = analyze(["UNKNOWN-COST,100,30,,,", "FREE-COST,100,30,0,,"]);
  assert.equal(result.errors.length, 0);
  const unknown = result.rows.find(row => row.sku === "UNKNOWN-COST");
  const free = result.rows.find(row => row.sku === "FREE-COST");
  assert.equal(unknown.leadDays, 14);
  assert.equal(unknown.safetyStock, 0);
  assert.equal(unknown.excessUnits, 40);
  assert.equal(unknown.unitCost, null);
  assert.equal(unknown.excessCost, null);
  assert.equal(free.unitCost, 0);
  assert.equal(free.excessCost, 0);
});

test("sales period, default lead and target settings reject invalid ranges before calculating", () => {
  for (const key of ["salesDays", "defaultLeadDays", "targetCoverDays"]) {
    for (const value of [0, -1, 3651, NaN, Infinity]) {
      assert.ok(analyze(["SKU,90,30,,,"], { [key]: value }).errors.length > 0, `${key}=${value}`);
    }
  }
  assert.ok(analyze(["SKU,90,30,,,"], { defaultLeadDays: 61 }).errors.length > 0);
  assert.ok(analyze(["SKU,90,30,,61,"]).errors.length > 0);
  assert.ok(analyze(["SKU,90,30,,3651,"]).errors.length > 0);
});

test("planning periods below one day are rejected consistently with the documented lower bound", () => {
  for (const key of ["salesDays", "defaultLeadDays", "targetCoverDays"]) {
    for (const value of [0.5, 14.5]) {
      assert.ok(analyze(["SKU,90,30,,,"], { [key]: value }).errors.length > 0, `${key}=${value}`);
    }
  }
});

test("the row ceiling accepts exactly 1,000 unique SKUs and rejects the next row", () => {
  const lines = Array.from({ length: HEALTH_CHECK_MAX_ROWS }, (_, index) => `SKU-${index},90,30,,,`);
  assert.equal(analyze(lines).rows.length, HEALTH_CHECK_MAX_ROWS);
  const oversized = analyze([...lines, "ONE-TOO-MANY,90,30,,,"]);
  assert.equal(oversized.rows.length, 0);
  assert.match(oversized.errors[0], /1,000/);
});

test("the file ceiling measures encoded bytes, including multibyte Unicode", () => {
  for (const csv of ["A".repeat(HEALTH_CHECK_MAX_BYTES + 1), "é".repeat(HEALTH_CHECK_MAX_BYTES / 2 + 1)]) {
    const result = analyzeInventoryHealth(csv, settings);
    assert.equal(result.rows.length, 0);
    assert.match(result.errors[0], /500 KB/);
  }
});

test("a valid file at the byte ceiling is accepted and ignored columns do not affect the result", () => {
  const prefix = "sku,on_hand,units_sold,ignored_note\nSKU-1,90,30,";
  const csv = prefix + "x".repeat(HEALTH_CHECK_MAX_BYTES - new TextEncoder().encode(prefix).byteLength);
  assert.equal(new TextEncoder().encode(csv).byteLength, HEALTH_CHECK_MAX_BYTES);
  const result = analyzeInventoryHealth(csv, settings);
  assert.equal(result.errors.length, 0);
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].onHand, 90);
});

test("validation errors are bounded even when many inventory rows need correction", () => {
  const result = analyze(Array.from({ length: 100 }, (_, index) => `SKU-${index},invalid,30,,,`));
  assert.equal(result.rows.length, 0);
  assert.equal(result.errors.length, 8);
});

test("coverage, safety-stock trigger and excess capital use the selected sales and cover periods", () => {
  const result = analyze(["EXCESS,70,60,3,10,5"], { targetCoverDays: 30 });
  assert.equal(result.errors.length, 0);
  const row = result.rows[0];
  assert.equal(row.dailySales, 2);
  assert.equal(row.daysCover, 35);
  assert.equal(row.reorderPoint, 25);
  assert.equal(row.excessUnits, 5);
  assert.equal(row.excessCost, 15);
  assert.equal(row.status, "excess_stock");
});

test("review priority respects stockout/reorder boundaries and separates zero recorded demand", () => {
  const result = analyze([
    "WITHIN,26,60,3,10,5", "EXCESS,70,60,3,10,5", "ZERO-SALES,300,0,,10,5",
    "REORDER,25,60,3,10,5", "STOCKOUT,19,60,3,10,5",
  ], { targetCoverDays: 30 });
  assert.equal(result.errors.length, 0);
  assert.deepEqual(Array.from(result.rows, row => row.status), ["stockout_risk", "reorder_review", "excess_stock", "no_recent_sales", "within_range"]);
  assert.equal(analyze(["AT-LEAD,20,60,,10,0"]).rows[0].status, "reorder_review");
  assert.equal(analyze(["OUT,0,60,,10,0"]).rows[0].status, "stockout_risk");
});

test("zero recorded demand does not establish dead stock, days of cover or excess value", () => {
  const row = analyze(["NO-SALES,300,0,12,14,5"]).rows[0];
  assert.equal(row.status, "no_recent_sales");
  assert.equal(row.daysCover, null);
  assert.equal(row.excessUnits, null);
  assert.equal(row.excessCost, null);
});

test("fractional demand rounds stock triggers up without treating triggers as order quantities", () => {
  const row = analyze(["SLOW,1,1,,14,0"]).rows[0];
  assert.equal(row.dailySales, 1 / 30);
  assert.equal(row.reorderPoint, 1);
  assert.equal(row.excessUnits, 0);
  assert.equal(row.status, "reorder_review");
});

test("CSV export escapes quotes/commas and neutralizes formula-looking merchant SKU values", () => {
  const base = analyze(["BASE,90,30,2,,"]).rows[0];
  for (const sku of ['=HYPERLINK("https://example.invalid","x")', "+123", "-123", "@SUM(1,1)", "\t=1", "\r=1"]) {
    const row = healthResultsCsv([{ ...base, sku }]).split("\r\n")[1];
    assert.ok(row.startsWith('"\''), sku);
  }
  const quoteCsv = healthResultsCsv([{ ...base, sku: 'TEE, size "L"' }]);
  assert.ok(quoteCsv.includes('"TEE, size ""L"""'));
  assert.match(quoteCsv, /reorder_trigger_units/);
  assert.doesNotMatch(quoteCsv, /order_quantity/);
});

test("CSV export leaves unknown coverage, excess capital and no-sales reorder triggers blank", () => {
  const rows = analyze(["NO-SALES,300,0,,14,5"]).rows;
  const row = healthResultsCsv(rows).split("\r\n")[1];
  assert.ok(row.startsWith('"NO-SALES","No recorded sales","300","0","","","","",'), row);
});

test("bundled examples are valid demonstration inputs with explicitly unknown no-sales values", () => {
  const result = analyzeInventoryHealth(HEALTH_CHECK_TEMPLATE, settings);
  assert.equal(result.errors.length, 0);
  assert.equal(result.rows.length, 3);
  assert.equal(result.rows.find(row => row.sku === "EXAMPLE-NO-SALES").daysCover, null);
});

test("sample rows remain identifiable after CSV upload, whitespace edits and case changes", () => {
  for (const csv of [HEALTH_CHECK_TEMPLATE, `\uFEFF${HEALTH_CHECK_TEMPLATE.replace(/\n/g, "\r\n")}\r\n`, HEALTH_CHECK_TEMPLATE.replace(/EXAMPLE-/g, "example-")]) {
    const result = analyzeInventoryHealth(csv, settings);
    assert.equal(result.errors.length, 0);
    assert.equal(containsSampleHealthRows(result.rows), true);
  }
  const merchant = analyze(["REAL-SKU,90,30,,,"]).rows;
  assert.equal(containsSampleHealthRows(merchant), false);
  const mixed = [...merchant, ...analyzeInventoryHealth(HEALTH_CHECK_TEMPLATE, settings).rows];
  assert.equal(containsSampleHealthRows(mixed), true);
  assert.equal(containsSampleHealthRows([]), false);
});

test("results export carries selected currency and the assumptions needed to interpret the amounts", () => {
  const rows = analyze(["SKU,100,30,2,20,5"]).rows;
  const cad = healthResultsCsv(rows, "CAD", settings);
  const usd = healthResultsCsv(rows, "USD", settings);
  assert.match(cad.split("\r\n")[0], /"cost_currency","sales_period_days","target_cover_days","lead_time_days","safety_stock_units","unit_cost"$/);
  assert.ok(cad.split("\r\n")[1].endsWith('"CAD","30","60","20","5","2"'));
  assert.equal(cad.replace('"CAD"', '"USD"'), usd, "currency labels must not silently convert supplied costs");
});

test("exports leave unspecified periods and unknown unit costs blank and reject unknown currency labels", () => {
  const rows = analyze(["SKU,100,30,,,0"]).rows;
  const standard = healthResultsCsv(rows).split("\r\n")[1];
  assert.ok(standard.endsWith('"USD","","","14","0",""'), standard);
  const unknownCurrency = healthResultsCsv(rows, "INVALID").split("\r\n")[1];
  assert.ok(unknownCurrency.endsWith('"UNKNOWN","","","14","0",""'), unknownCurrency);
});
