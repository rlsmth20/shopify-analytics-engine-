const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/spreadsheet-export.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness(response) {
  const output = {}, requests = [], actions = [];
  const link = { click() { actions.push("clicked"); }, remove() { actions.push("removed"); } };
  vm.runInNewContext(compiled, {
    exports: output, require: () => ({ API_BASE_URL: "https://api.example.com" }), AbortSignal,
    fetch: async (...args) => { requests.push(args); return response; },
    URL: { createObjectURL: () => "blob:test", revokeObjectURL: url => actions.push(url) },
    document: { createElement: () => link, body: { appendChild() {} } },
    setTimeout: callback => callback(),
  });
  return { ...output, requests, actions, link };
}

test("only an explicit download posts report data and keeps sample labeling", async () => {
  const h = harness({ ok: true, headers: new Headers({ "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), blob: async () => new Blob(["xlsx"]) });
  assert.equal(h.requests.length, 0);
  const payload = { kind: "inventory_history", sample: true, points: [{ date: "2026-09-18", cost_value: null, retail_value: 0, total_units: 2 }] };
  await h.downloadSpreadsheet(payload, "inventory-sample.xlsx");
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0][0], "https://api.example.com/exports/workbook.xlsx");
  assert.deepEqual(JSON.parse(h.requests[0][1].body), payload);
  assert.equal(h.link.download, "inventory-sample.xlsx");
  assert.deepEqual(h.actions, ["clicked", "removed", "blob:test"]);
});

test("service errors and non-workbook responses do not download corrupt files", async () => {
  const busy = harness({ ok: false, json: async () => ({ detail: "Excel exports are busy." }) });
  await assert.rejects(busy.downloadSpreadsheet({}, "test.xlsx"), /exports are busy/);
  assert.equal(busy.actions.length, 0);
  const html = harness({ ok: true, headers: new Headers({ "content-type": "text/html" }) });
  await assert.rejects(html.downloadSpreadsheet({}, "test.xlsx"), /download CSV/);
  assert.equal(html.actions.length, 0);
});
