const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const output = {};
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/sync-summary.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(compiled, { exports: output });
const { getSyncNotice, isSyncResult, isSyncRunStatus, isSyncRunActive } = output;
const complete = { status: "succeeded", variants_imported: 26, order_line_items_count: 0 };

test("an empty paid-order window does not tell merchants to reconnect", () => {
  const notice = getSyncNotice({ ...complete, no_eligible_recent_orders_found: true });
  assert.equal(notice.warning, false);
  assert.match(notice.message, /No reconnect is needed/);
});
test("permission and partial failures take precedence over an empty-order flag", () => {
  const missing = getSyncNotice({ ...complete, token_lacks_read_orders: true, no_eligible_recent_orders_found: true });
  assert.equal(missing.warning, true);
  assert.match(missing.message, /Reconnect Shopify/);
  const partial = getSyncNotice({ ...complete, status: "partial", no_eligible_recent_orders_found: true });
  assert.equal(partial.warning, true);
  assert.equal(partial.title, "Order history is incomplete");
});
test("partially unmatched sales remain visible even when other lines imported", () => {
  const notice = getSyncNotice({ ...complete, order_line_items_count: 4, line_items_skipped: 2 });
  assert.equal(notice.warning, true);
  assert.match(notice.title, /could not be matched/);
  assert.equal(getSyncNotice({ ...complete, order_line_items_count: 4 }), null);
});
test("a repeat import does not mistake existing sales for unmatched items", () => {
  assert.equal(getSyncNotice({ ...complete, line_items_skipped: 8, line_item_skip_reasons: { already_imported: 8 } }), null);
  assert.equal(getSyncNotice({ ...complete, line_items_skipped: 9, line_item_skip_reasons: { already_imported: 8, missing_variant: 1 } }).warning, true);
});
test("malformed successful HTTP responses cannot become a completed sync", () => {
  for (const value of [null, {}, { status: "succeeded" }, { ...complete, status: "failed" }, { ...complete, variants_imported: -1 }, { ...complete, order_line_items_count: "0" }]) {
    assert.equal(isSyncResult(value), false);
  }
  assert.equal(isSyncResult(complete), true);
  assert.equal(isSyncResult({ ...complete, status: "partial" }), true);
});
test("sync runs are followed only while queued or running, and only when well formed", () => {
  for (const value of [null, {}, { run_id: 0, status: "queued" }, { run_id: 1, status: "done" }, { run_id: "1", status: "queued" }]) {
    assert.equal(isSyncRunStatus(value), false);
  }
  assert.equal(isSyncRunStatus({ run_id: 7, status: "failed", error_message: "x", result: null }), true);
  assert.equal(isSyncRunActive({ run_id: 1, status: "queued" }), true);
  assert.equal(isSyncRunActive({ run_id: 1, status: "running" }), true);
  for (const status of ["succeeded", "partial", "failed"]) assert.equal(isSyncRunActive({ run_id: 1, status }), false);
});
