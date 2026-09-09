const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const compiled = ts.transpileModule(
  readFileSync(path.join(__dirname, "../lib/shopify-embedded.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText;

function fixture({ embedded = true, idToken = async () => "fixture-token", blockedStorage = false, response, fastTimeout = false } = {}) {
  const calls = [];
  const scripts = [];
  const window = {
    location: { search: embedded ? "?embedded=1&shop=fixture.myshopify.com" : "", href: "https://app.example.test/dashboard" },
    shopify: idToken ? { idToken } : undefined,
  };
  window.top = embedded ? { location: { href: "https://admin.shopify.com" } } : window;
  window.self = window;
  const storage = new Map();
  const exports = {};
  const context = {
    exports, window, Headers, URLSearchParams, AbortSignal,
    process: { env: { NODE_ENV: "test" } },
    require: (name) => {
      assert.equal(name, "@/lib/api-base");
      return { API_BASE_URL: "https://api.example.test" };
    },
    setTimeout: (fn, ms) => setTimeout(fn, fastTimeout ? 5 : ms),
    clearTimeout,
    sessionStorage: {
      getItem: (key) => { if (blockedStorage) throw new Error("Storage blocked"); return storage.get(key) || null; },
      setItem: (key, value) => { if (blockedStorage) throw new Error("Storage blocked"); storage.set(key, value); },
    },
    document: {
      querySelector: (selector) => selector.startsWith("meta") ? {} : scripts[0] || null,
      createElement: () => {
        const script = { dataset: {}, addEventListener() {}, remove() { scripts.splice(scripts.indexOf(script), 1); } };
        return script;
      },
      head: { appendChild: (script) => scripts.push(script) },
    },
    fetch: async (url, init) => {
      calls.push({ url, init });
      return response || new Response("{}", { status: 200 });
    },
  };
  vm.runInNewContext(compiled, context);
  return { api: exports, calls, scripts, window };
}

test("embedded requests use Shopify tokens and never website cookies", async () => {
  const { api, calls } = fixture({ blockedStorage: true });
  await api.authenticatedFetch("https://api.example.test/auth/me", { credentials: "include" });
  assert.equal(calls[0].init.headers.get("Authorization"), "Bearer fixture-token");
  assert.equal(calls[0].init.credentials, "omit");
});

test("App Bridge recovery uses the synchronous CDN script required by Shopify", async () => {
  const { api, scripts, window } = fixture({ idToken: null });
  const token = api.getShopifySessionToken();
  assert.equal(scripts.length, 1);
  assert.equal(scripts[0].src, "https://cdn.shopify.com/shopifycloud/app-bridge.js");
  assert.equal(scripts[0].async, false);
  assert.notEqual(scripts[0].defer, true);
  window.shopify = { idToken: async () => "recovered-token" };
  scripts[0].onload();
  assert.equal(await token, "recovered-token");
});

test("website authentication retains its cookie contract", async () => {
  const { api, calls } = fixture({ embedded: false });
  await api.authenticatedFetch("https://api.example.test/auth/me");
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[0].init.headers.has("Authorization"), false);
  assert.equal(calls[0].init.cache, "no-store");
  assert.ok(calls[0].init.signal instanceof AbortSignal);
});

test("cached data is forbidden and caller cancellation is retained", async () => {
  const { api, calls } = fixture({ embedded: false });
  const controller = new AbortController();
  await api.authenticatedFetch("https://api.example.test/dashboard", { cache: "force-cache", signal: controller.signal });
  assert.equal(calls[0].init.cache, "no-store");
  controller.abort();
  assert.equal(calls[0].init.signal.aborted, true);
});

test("rejected Shopify authentication cannot silently fall back to cookies", async () => {
  const { api, calls } = fixture({ idToken: async () => { throw new Error("Token rejected"); } });
  await assert.rejects(api.authenticatedFetch("https://api.example.test/auth/me"), /Token rejected/);
  assert.equal(calls.length, 0);
});

test("an empty Shopify token cannot send an unauthenticated API request", async () => {
  const { api, calls } = fixture({ idToken: async () => "" });
  await assert.rejects(api.authenticatedFetch("https://api.example.test/auth/me"), /did not return a session/);
  assert.equal(calls.length, 0);
});

test("a stalled Shopify token request reaches a retryable timeout", async () => {
  const { api } = fixture({ idToken: () => new Promise(() => {}), fastTimeout: true });
  await assert.rejects(api.getShopifySessionToken(), /took too long/);
});

test("simultaneous requests share App Bridge loading and can retry a failed load", async () => {
  const { api, scripts } = fixture({ idToken: null, fastTimeout: true });
  const first = api.getShopifySessionToken();
  const second = api.getShopifySessionToken();
  assert.equal(scripts.length, 1);
  const outcomes = await Promise.allSettled([first, second]);
  assert.ok(outcomes.every((outcome) => outcome.status === "rejected"));
  assert.equal(scripts.length, 0);
  await assert.rejects(api.getShopifySessionToken(), /Could not load Shopify authentication/);
});

test("reconnect uses the authorized URL returned by the backend", async () => {
  const authorizeUrl = "https://fixture.myshopify.com/admin/oauth/authorize?fixture=1";
  const { api, calls, window } = fixture({ response: new Response(JSON.stringify({ authorize_url: authorizeUrl })) });
  await api.reconnectShopify();
  assert.equal(calls.length, 1);
  assert.equal(window.top.location.href, authorizeUrl);
});

test("failed reconnect surfaces an error without navigating", async () => {
  const { api, window } = fixture({ response: new Response(JSON.stringify({ detail: "Integration unavailable" }), { status: 503 }) });
  await assert.rejects(api.reconnectShopify(), /Integration unavailable/);
  assert.equal(window.top.location.href, "https://admin.shopify.com");
});

test("invalid session responses trigger exactly one fresh-token auth retry", async () => {
  let tokenCalls = 0;
  const { api, calls } = fixture({ idToken: async () => `fixture-${++tokenCalls}`,
    response: new Response("{}", { status: 401, headers: { "X-Shopify-Retry-Invalid-Session-Request": "1" } }) });
  const response = await api.authenticatedFetch("https://api.example.test/auth/me");
  assert.equal(response.status, 401);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].init.headers.get("Authorization"), "Bearer fixture-2");
});

test("sync writes are never automatically replayed", async () => {
  const { api, calls } = fixture({ response: new Response("{}", { status: 401, headers: { "X-Shopify-Retry-Invalid-Session-Request": "1" } }) });
  await api.authenticatedFetch("https://api.example.test/integrations/shopify/sync", { method: "POST" });
  assert.equal(calls.length, 1);
});
