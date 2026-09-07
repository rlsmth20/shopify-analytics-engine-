const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const key = "skubase-growth-attribution-v1";
const compile = (file) => ts.transpileModule(readFileSync(path.join(__dirname, file), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const analyticsSource = compile("../lib/analytics.ts");
const formSource = compile("../components/inventory-risk-snapshot-form.tsx");

function fixture({ stored, doNotTrack = "0", demo = false, blockedStorage = false } = {}) {
  const storage = new Map(stored === undefined ? [] : [[key, stored]]);
  const calls = [];
  const window = { location: { search: "", pathname: "/" } };
  const context = {
    exports: {}, window, location: window.location, navigator: { doNotTrack },
    document: { referrer: "https://community.example.test/topic?private=token" },
    URL, URLSearchParams, crypto: { randomUUID },
    localStorage: {
      getItem: (name) => { if (blockedStorage) throw new Error("blocked"); return storage.get(name) ?? null; },
      setItem: (name, value) => { if (blockedStorage) throw new Error("blocked"); storage.set(name, value); },
    },
    require: (name) => {
      if (name === "@/lib/api-base") return { API_BASE_URL: "https://api.example.test" };
      assert.equal(name, "@/lib/shopify-embedded");
      return { isDemoActive: () => demo, authenticatedFetch: async (url, init) => { calls.push(JSON.parse(init.body)); } };
    },
  };
  vm.runInNewContext(analyticsSource, context);
  return { api: context.exports, context, storage, calls, window };
}

const plain = (value) => JSON.parse(JSON.stringify(value));

test("a tagged landing survives internal navigation into the actual health-check submission", async () => {
  const f = fixture();
  f.window.location.search = "?utm_source=community&utm_campaign=cohort-a&utm_content=message-2";
  await f.api.trackGrowthEvent("VISITOR");
  f.window.location.search = "";
  f.window.location.pathname = "/inventory-risk-snapshot";
  let payload;
  let stateIndex = 0;
  const formContext = { ...f.context, exports: {},
    require: (name) => {
      if (name === "@/lib/analytics") return f.api;
      if (name === "@/lib/api-base") return { API_BASE_URL: "https://api.example.test" };
      if (name === "next/navigation") return { useRouter: () => ({ push() {} }) };
      if (name === "react") return {
        useEffect() {}, useState: (initial) => [stateIndex++ === 0 ? {
          first_name: "Merchant", email: "merchant@example.test", store_url: "https://merchant.example.test",
          approximate_sku_count: "50-250", biggest_inventory_issue: "Stockouts",
        } : initial, () => {}],
      };
      assert.equal(name, "react/jsx-runtime");
      return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
    },
    fetch: async (url, init) => {
      payload = JSON.parse(init.body);
      return { ok: true, json: async () => ({ id: 1 }) };
    },
  };
  vm.runInNewContext(formSource, formContext);
  const form = formContext.exports.InventoryRiskSnapshotForm({});
  await form.props.onSubmit({ preventDefault() {} });
  assert.equal(payload.utm_campaign, "cohort-a");
  assert.equal(payload.utm_source, "community");
  assert.equal(payload.utm_content, "message-2");
  assert.equal(payload.visitor_id, undefined);
  assert.equal(payload.referrer, undefined);
});

test("new explicit campaign fields replace the prior cohort without mixing variants", async () => {
  const f = fixture();
  f.window.location.search = "?utm_source=community&utm_campaign=cohort-a&utm_content=old-message";
  await f.api.trackGrowthEvent("VISITOR");
  f.window.location.search = "?utm_source=calculator&utm_campaign=cohort-b";
  assert.deepEqual(plain(f.api.getGrowthAttribution()), { utm_source: "calculator", utm_campaign: "cohort-b" });
  await f.api.trackGrowthEvent("VISITOR");
  assert.equal(f.calls[0].visitor_id, f.calls[1].visitor_id);
  assert.deepEqual(plain(f.calls[1].attribution), {
    utm_source: "calculator", utm_campaign: "cohort-b", referrer: "https://community.example.test",
  });
});

test("expired, malformed, and future-dated storage cannot attach stale campaigns", async () => {
  for (const stored of ["{broken", JSON.stringify({ at: Date.now(), attribution: { utm_campaign: "invalid" } }),
    ...[-31 * 86400000, 86400000].map((offset) => JSON.stringify({
      visitor_id: randomUUID(), at: Date.now() + offset, landing_page: "/", attribution: { utm_campaign: "stale" },
    }))]) {
    const f = fixture({ stored });
    assert.deepEqual(plain(f.api.getGrowthAttribution()), {});
    f.window.location.search = "?utm_campaign=current";
    await f.api.trackGrowthEvent("VISITOR");
    assert.equal(f.calls[0].attribution.utm_campaign, "current");
  }
});

test("DNT and demo sessions contribute neither telemetry nor submission attribution", async () => {
  for (const options of [{ doNotTrack: "1" }, { demo: true }]) {
    const f = fixture(options);
    f.window.location.search = "?utm_campaign=ignored";
    assert.deepEqual(plain(f.api.getGrowthAttribution()), {});
    await f.api.trackGrowthEvent("VISITOR");
    assert.equal(f.calls.length, 0);
    assert.equal(f.storage.size, 0);
  }
});

test("blocked storage preserves explicit form campaigns without breaking submission", async () => {
  const f = fixture({ blockedStorage: true });
  f.window.location.search = "?utm_campaign=current";
  assert.deepEqual(plain(f.api.getGrowthAttribution()), { utm_campaign: "current" });
  await f.api.trackGrowthEvent("VISITOR");
  assert.equal(f.calls.length, 0);
});
