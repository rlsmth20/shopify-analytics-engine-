const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const ts = require("typescript");
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/account-data.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: exportsObject });
const { readAccountConnection, accountPlanConfirmed } = exportsObject;

test("unavailable or malformed connection responses cannot become disconnected", () => {
  for (const body of [null, {}, {detail:"unavailable"}, {connected:"false"}, {connected:true,shopify_domain:null}]) assert.throws(() => readAccountConnection(body));
  assert.equal(readAccountConnection({connected:false,shopify_domain:null}).connected, false);
  assert.equal(readAccountConnection({connected:true,shopify_domain:"fixture.myshopify.com"}).shopify_domain, "fixture.myshopify.com");
});
test("billing failure is unknown even if a stale active or inactive label is present", () => {
  const base = {billing_status_loaded:true,plan_name:"Starter",subscription_status:"active"};
  assert.equal(accountPlanConfirmed(base), true);
  for (const body of [null, {}, {...base,billing_status_loaded:false}, {...base,billing_status_error:"shopify_unauthorized"}]) assert.equal(accountPlanConfirmed(body), false);
  assert.equal(accountPlanConfirmed({...base,subscription_status:"canceled"}), true);
});
