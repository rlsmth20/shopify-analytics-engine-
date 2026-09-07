const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const ts = require("typescript");
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/workspace-navigation.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: exportsObject });
const { findWorkspacePages, productDataPresent } = exportsObject;

test("merchant tasks find the relevant pages without knowing product navigation labels", () => {
  for (const [query, route] of [["How do I set up email alerts", "/alerts"], ["send email alerts", "/alerts"], ["weekly email", "/purchase-orders"], ["buy list", "/purchase-orders"], ["email suppliers", "/purchase-orders"], ["reorder", "/purchase-orders"], ["upload csv", "/import-stocky"], ["lead-time", "/lead-time-settings"], ["cancel subscription", "/billing"]]) {
    assert.ok(findWorkspacePages(query, false).some(item => item.href === route), query);
  }
});
test("owner growth links are hidden from merchant results even on exact searches", () => {
  assert.equal(findWorkspacePages("growth", false).length, 0);
  assert.equal(findWorkspacePages("growth", true)[0].href, "/growth");
  assert.equal(findWorkspacePages("", false).some(item => item.adminOnly), false);
});
test("search includes direct import routes without expanding the default menu", () => {
  assert.equal(findWorkspacePages("", false).some(item => item.searchOnly), false);
  assert.ok(findWorkspacePages("shipstation", false).some(item => item.href === "/import-shipstation"));
  assert.equal(findWorkspacePages("unrelated banana", false).length, 0);
});
test("failed or malformed inventory checks cannot label a real workspace empty or sample", () => {
  for (const body of [null, {}, { detail: "Service unavailable" }, { product_count: "0" }, { product_count: -1 }, { product_count: NaN }]) assert.equal(productDataPresent(body), null);
  assert.equal(productDataPresent({ product_count: 0 }), false);
  assert.equal(productDataPresent({ product_count: 15 }), true);
});
