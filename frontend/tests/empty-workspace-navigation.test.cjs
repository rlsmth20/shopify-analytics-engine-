const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const root = path.join(__dirname, "..");
const publicTool = "/tools/inventory-health-check";

function compile(file) {
  return ts.transpileModule(fs.readFileSync(path.join(root, file), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
}

// Exercise the actual component branches and effects with controlled API responses.
// Public navigation remains a link; no network or account mutation is simulated.
function harness(file, { props, component = "default", dashboard, connection } = {}) {
  let cursor = 0;
  const slots = new Map(), effects = [], cache = new Map(), calls = [];
  const jsx = (type, props) => ({ type, props });
  const window = {
    location: { search: "", href: "https://skubase.test/actions" },
    localStorage: { getItem: () => null, setItem() {} },
    history: { state: null, replaceState() {} },
    addEventListener() {}, removeEventListener() {},
  };
  const mocks = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) {
        const key = cursor++;
        if (!slots.has(key)) slots.set(key, typeof initial === "function" ? initial() : initial);
        return [slots.get(key), next => slots.set(key, typeof next === "function" ? next(slots.get(key)) : next)];
      },
      useMemo: calculate => calculate(),
      useEffect(callback, dependencies) {
        const key = cursor++, old = slots.get(key);
        if (!old || dependencies.some((value, index) => value !== old.dependencies[index])) {
          const slot = { dependencies, cleanup: old?.cleanup };
          slots.set(key, slot);
          effects.push(() => { slot.cleanup?.(); slot.cleanup = callback(); });
        }
      },
    },
    "next/link": { __esModule: true, default: "a" },
    "@/components/auth-guard": { useAuth: () => ({ user: { id: 42 } }) },
    "@/components/charts": { AreaLineChart: "chart", ChartPanel: "chart-panel", DivergingBarChart: "chart", DonutChart: "chart", HorizontalBarChart: "chart" },
    "@/components/action-card": { ActionCard: "action-card" },
    "@/components/action-table": { ActionTable: "action-table" },
    "@/lib/analytics": { trackGrowthEvent: async () => {} },
    "@/lib/api-v2": {
      currency: value => `$${value}`,
      fetchDashboard: async signal => { calls.push({ kind: "dashboard", signal }); return dashboard(); },
    },
    "@/lib/api-base": { API_BASE_URL: "https://api.skubase.test" },
    "@/lib/shopify-embedded": {
      authenticatedFetch: async (url, options) => { calls.push({ kind: "connection", url, options }); return connection(); },
      getEmbeddedShopifyContext: () => null,
      reconnectShopify: async () => { throw new Error("Unexpected Shopify mutation"); },
    },
    "@/lib/app-helpers": {
      statusLabel: { urgent: "Urgent", optimize: "Optimize", dead: "Dead" },
      summarizeDataSource: () => "Imported inventory",
      getActionImpactValue: action => action.estimated_profit_impact ?? null,
    },
    "@/lib/report-export": { exportActionsReport() { throw new Error("Unexpected export"); } },
  };
  function load(moduleFile) {
    if (cache.has(moduleFile)) return cache.get(moduleFile);
    const exports = {};
    cache.set(moduleFile, exports);
    vm.runInNewContext(compile(moduleFile), {
      exports, window, Error, AbortController, AbortSignal, URL, URLSearchParams,
      require(name) {
        if (name in mocks) return mocks[name];
        if (name.endsWith(".module.css")) return { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) };
        assert.ok(name.startsWith("@/"), `Unexpected import ${name}`);
        const base = name.slice(2);
        const extension = fs.existsSync(path.join(root, `${base}.tsx`)) ? ".tsx" : ".ts";
        return load(`${base}${extension}`);
      },
    });
    return exports;
  }
  const renderComponent = load(file)[component];
  function render() {
    cursor = 0;
    const nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string" || typeof node === "number") { texts.push(String(node)); return; }
      if (!node?.props) return;
      nodes.push(node);
      if (typeof node.type === "function") walk(node.type(node.props)); else walk(node.props.children);
    }
    walk(renderComponent(props));
    while (effects.length) effects.shift()();
    return {
      nodes, text: texts.join(" "),
      links: href => nodes.filter(node => node.type === "a" && node.props.href === href),
      button: label => nodes.find(node => node.type === "button" && node.props.children === label),
    };
  }
  async function settle() {
    for (let i = 0; i < 5; i++) { render(); await new Promise(setImmediate); }
    return render();
  }
  return { render, settle, calls };
}

const emptyDashboard = { revenue_trend_30d: [], stock_health_breakdown: [], top_movers: [] };
const emptyFeed = { actions: [], dataSource: null, isLoading: false, errorMessage: null, errorStatus: null };
function assertPublicOption(ui) {
  assert.equal(ui.links(publicTool).length, 1);
  assert.equal(ui.links(publicTool)[0].props.onClick, undefined);
  assert.match(ui.text, /SKU, on_hand and units_sold/);
  assert.match(ui.text, /sales period in days/);
  assert.match(ui.text, /browser-only check does not import data or results into your account/);
}

test("empty signed-in dashboard offers a browser check and distinguishes supported sales sources", async () => {
  const h = harness("app/(app-shell)/dashboard/page.tsx", { dashboard: () => emptyDashboard });
  const ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /Import non-Shopify shipment history/);
  assert.match(ui.text, /Shopify orders come through approved Shopify sync/);
  assert.match(ui.text, /Shopify App Store review and is not listed yet/);
  assert.match(ui.text, /stock quantities, not sales history/);
  for (const href of ["/store-sync", "/import-stocky", "/import-shipstation", "/lead-time-settings"]) assert.equal(ui.links(href).length, 1);
  assert.equal(h.calls.length, 1);
});

test("an empty dashboard with held products shows mapping review instead of silently hiding them", async () => {
  const h = harness("app/(app-shell)/dashboard/page.tsx", { dashboard: () => ({ ...emptyDashboard,
    identity_issues: [{ product_id: 11, sku_id: "sku_SHARED", name: "Blue variant", current_on_hand: 9, message: "Duplicate SKU" }],
  }) });
  const ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /1\s+product needs\s+mapping review/);
  assert.match(ui.text, /Forecasts and recommendations for these products are withheld/);
  assert.match(ui.text, /Blue variant/);
  assert.match(ui.text, /sku_SHARED/);
});

test("dashboard request failure keeps the independent browser check usable while retry recovers account data", async () => {
  let attempts = 0;
  const h = harness("app/(app-shell)/dashboard/page.tsx", { dashboard: () => {
    if (++attempts === 1) throw new Error("Inventory is temporarily unavailable.");
    return emptyDashboard;
  } });
  let ui = await h.settle();
  assert.match(ui.text, /Could not load dashboard/);
  assertPublicOption(ui);
  assert.equal(ui.links(publicTool)[0].props.href, publicTool);
  assert.equal(h.calls.length, 1);
  ui.button("Try again").props.onClick();
  ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /Add inventory to start planning/);
  assert.equal(h.calls.length, 2);
});

test("empty actions retain account import recovery and do not claim healthy stock", async () => {
  const h = harness("components/action-feed.tsx", { component: "ActionFeed", props: emptyFeed });
  const ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /No inventory recommendations yet/);
  assert.match(ui.text, /empty queue alone does not confirm that every product has healthy stock/);
  assert.equal(ui.links("/store-sync").length, 1);
  assert.equal(ui.links("/lead-time-settings").length, 1);
  assert.equal(h.calls.length, 0);
});

test("failed live action feed still exposes the independent tool and connection recovery", async () => {
  const h = harness("components/action-feed.tsx", { component: "ActionFeed", props: {
    ...emptyFeed, errorMessage: "Inventory data could not be loaded.", errorStatus: 503,
  } });
  const ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /Live feed unavailable/);
  assert.equal(ui.links("/store-sync").length, 1);
  assert.doesNotMatch(ui.text, /No inventory recommendations yet/);
});

test("filtering a populated action queue to no results offers filter recovery without empty-workspace onboarding", async () => {
  const h = harness("components/action-feed.tsx", { component: "ActionFeed", props: {
    ...emptyFeed, actions: [{ sku_id: "OBSERVED", name: "Canvas tote", status: "urgent", priority_score: 8 }],
  } });
  let ui = await h.settle();
  ui.nodes.find(node => node.type === "input" && node.props.type === "search").props.onChange({ target: { value: "does not match" } });
  ui = h.render();
  assert.match(ui.text, /No matching actions/);
  assert.equal(ui.links(publicTool).length, 0);
  ui.button("Show all actions").props.onClick();
  ui = h.render();
  assert.ok(ui.nodes.some(node => node.type === "action-table" && node.props.actions.length === 1));
});

test("Store Sync offers the tool during a pending connection read and after failure without sending mutations", async () => {
  let rejectConnection;
  const pending = new Promise((_, reject) => { rejectConnection = reject; });
  const h = harness("app/(app-shell)/store-sync/page.tsx", { connection: () => pending });
  let ui = h.render();
  assert.match(ui.text, /Checking Shopify connection/);
  assertPublicOption(ui);
  rejectConnection(new Error("Connection check temporarily unavailable."));
  ui = await h.settle();
  assert.match(ui.text, /Connection unavailable/);
  assertPublicOption(ui);
  assert.equal(ui.links("/import-stocky").length, 1);
  assert.equal(ui.links("/import-shipstation").length, 1);
  assert.match(ui.text, /ShipStation imports supply non-Shopify shipment history/);
  assert.ok(ui.button("Try again"));
  assert.equal(h.calls.length, 1);
  assert.match(h.calls[0].url, /\/integrations\/shopify\/connection$/);
  assert.equal(h.calls[0].options.method, undefined);
});

test("disconnected Shopify account shows one public option and honest review status", async () => {
  const h = harness("app/(app-shell)/store-sync/page.tsx", { connection: () => ({
    ok: true, json: async () => ({ connected: false, shopify_domain: null, last_sync_at: null, scope: null }),
  }) });
  const ui = await h.settle();
  assertPublicOption(ui);
  assert.match(ui.text, /Shopify App Store review and is not listed yet/);
  assert.ok(ui.links("mailto:info@skubase.io?subject=Skubase%20Shopify%20access").length);
  assert.equal(ui.button("Sync now"), undefined);
  assert.equal(h.calls.length, 1);
});
