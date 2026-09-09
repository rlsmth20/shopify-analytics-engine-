const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const ts = require("typescript");
const plan = plan_id => ({plan_id, plan_name: plan_id, subscription_status:"active", billing_status_loaded:true, capabilities:[]});

function fixture() {
  const requests = [];
  const exportsObject = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/entitlements.ts"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, { exports: exportsObject, require: name => name.endsWith("api-base") ? {API_BASE_URL:"https://fixture.invalid"} : {
    authenticatedFetch: url => new Promise(resolve => requests.push({url, resolve: body => resolve({ok:true,json:async()=>body})})),
  }});
  return {...exportsObject, requests};
}

test("routine consumers share one request and reuse confirmed plan data", async () => {
  const f = fixture();
  const a = f.fetchEntitlements(); const b = f.fetchEntitlements();
  assert.equal(f.requests.length, 1);
  f.requests[0].resolve(plan("starter"));
  assert.equal((await a).plan_id, "starter"); assert.equal((await b).plan_id, "starter");
  assert.equal((await f.fetchEntitlements()).plan_id, "starter");
  assert.equal(f.requests.length, 1);
});

test("a response from the prior session cannot repopulate cache or clear the next session request", async () => {
  const f = fixture();
  const old = f.fetchEntitlements();
  f.invalidateEntitlementsCache();
  const current = f.fetchEntitlements();
  f.requests[0].resolve(plan("scale")); await old;
  const sharing = f.fetchEntitlements();
  assert.equal(f.requests.length, 2);
  f.requests[1].resolve(plan("starter"));
  assert.equal((await current).plan_id, "starter"); assert.equal((await sharing).plan_id, "starter");
  assert.equal((await f.fetchEntitlements()).plan_id, "starter");
  assert.equal(f.requests.length, 2);
});

test("a fresh billing refresh cannot be overwritten by an older in-flight result", async () => {
  const f = fixture(); const old = f.fetchEntitlements(); const fresh = f.fetchEntitlements({fresh:true});
  assert.match(f.requests[1].url, /fresh=1/);
  f.requests[1].resolve(plan("scale")); await fresh;
  f.requests[0].resolve(plan("starter")); await old;
  assert.equal((await f.fetchEntitlements()).plan_id, "scale");
  assert.equal(f.requests.length, 2);
});

test("unavailable or malformed plans are not cached as a downgrade", async () => {
  for (const body of [{}, {...plan('scale'), billing_status_loaded:false}, {...plan('scale'), capabilities:null}]) {
    const f = fixture();
    const failed = f.fetchEntitlements();
    f.requests[0].resolve(body);
    await assert.rejects(failed, /could not be checked/);
    const retry = f.fetchEntitlements();
    assert.equal(f.requests.length, 2);
    f.requests[1].resolve(plan('scale'));
    assert.equal((await retry).plan_id, 'scale');
    assert.equal(f.entitlementHas({}, 'forecast'), false);
  }
});
