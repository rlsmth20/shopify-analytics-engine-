const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../app/import-shipstation/page.tsx"), "utf8");
const compiled = ts.transpileModule(source + "\nexport { shipmentFileError, isImportResult };", {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const valid = {
  shop_id: 1, shopify_domain: "merchant.myshopify.com", rows_processed: 3,
  line_items_inserted: 2, rows_skipped: 1, distinct_skus: 1,
  skip_reasons: ["Row 4: unparseable date"], earliest_ship_date: "2026-08-01", latest_ship_date: "2026-09-01",
  top_skus_by_velocity: [{ sku: "SKU-1", units_30d: 2, units_90d: 4, units_180d: 4, daily_average_180d: 0.022 }],
};

function harness({ status = 200, body = valid } = {}) {
  let cursor = 0;
  const states = new Map();
  const calls = [];
  const redirects = [];
  const exports = {};
  const jsx = (type, props) => ({ type, props });
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: { useState(initial) { const key = cursor++; if (!states.has(key)) states.set(key, initial); return [states.get(key), (value) => states.set(key, value)]; } },
    "next/link": { __esModule: true, default: "a" },
    "next/navigation": { useRouter: () => ({ replace: (value) => redirects.push(value) }) },
    "@/lib/api-base": { API_BASE_URL: "https://api.example.test" },
    "@/components/marketing-footer": { MarketingFooter: "footer" },
    "@/lib/shopify-embedded": {
      authenticatedFetch: async (url, options) => { calls.push({ url, options }); return { status, ok: status >= 200 && status < 300, json: async () => body }; },
      getEmbeddedShopifyContext: () => null, redirectToShopifyInstall: () => {},
    },
  };
  vm.runInNewContext(compiled, {
    exports, Number, Array, Error, encodeURIComponent,
    FormData: class { append() {} },
    require(name) { if (!(name in dependencies)) throw new Error(`Unexpected import ${name}`); return dependencies[name]; },
  });
  function render() {
    cursor = 0;
    const nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string") { texts.push(node); return; }
      if (!node || typeof node !== "object") return;
      nodes.push(node); walk(node.props?.children);
    }
    walk(exports.default());
    return { nodes, text: texts.join(" ") };
  }
  async function submit(file = { name: "shipments.csv", size: 100 }) {
    render().nodes.find(node => node.type === "input" && node.props.type === "file").props.onChange({ target: { files: [file] } });
    await render().nodes.find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
    return render();
  }
  return { render, submit, calls, redirects, ...exports };
}

test("invalid uploads are rejected before any request and match server size limits", async () => {
  for (const file of [{ name: "orders.xlsx", size: 1 }, { name: "orders.csv", size: 0 }, { name: "orders.csv", size: 50 * 1024 * 1024 + 1 }]) {
    const view = harness();
    const ui = await view.submit(file);
    assert.equal(view.calls.length, 0);
    assert.ok(ui.nodes.some(node => node.props?.role === "alert"));
  }
  assert.equal(harness().shipmentFileError({ name: "SHIPMENTS.CSV", size: 50 * 1024 * 1024 }), null);
});

test("a partial successful import retains row issues and hands off to current inventory", async () => {
  const view = harness();
  const ui = await view.submit();
  assert.equal(view.calls.length, 1);
  assert.match(ui.text, /Imported 2 shipment line items/);
  assert.match(ui.text, /Row 4: unparseable date/);
  assert.match(ui.text, /Shipment history does not include stock on hand/);
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/import-stocky" && node.props.children === "Add current inventory"));
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/actions"));
});

test("a zero-row result cannot become a successful planning handoff", async () => {
  const ui = await harness({ body: { ...valid, line_items_inserted: 0, rows_skipped: 3, distinct_skus: 0, top_skus_by_velocity: [] } }).submit();
  assert.match(ui.text, /No shipment rows were imported/);
  assert.ok(ui.nodes.some(node => node.props?.role === "alert"));
  assert.equal(ui.nodes.some(node => node.type === "a" && node.props.children === "Add current inventory"), false);
  assert.equal(ui.nodes.some(node => node.type === "a" && node.props.href === "/actions"), false);
});

test("malformed HTTP success cannot claim an import completed", async () => {
  for (const body of [null, {}, { ...valid, line_items_inserted: "2" }, { ...valid, top_skus_by_velocity: [{ sku: "SKU" }] }]) {
    const ui = await harness({ body }).submit();
    assert.match(ui.text, /result could not be confirmed/);
    assert.doesNotMatch(ui.text, /Imported 2 shipment/);
  }
});

test("expired access has a billing recovery link and signed-out uploads preserve their destination", async () => {
  const upgrade = await harness({ status: 402, body: { detail: "Your trial has ended." } }).submit();
  assert.match(upgrade.text, /Your trial has ended/);
  assert.ok(upgrade.nodes.some(node => node.type === "a" && node.props.href === "/billing"));
  const signedOut = harness({ status: 401, body: {} });
  await signedOut.submit();
  assert.deepEqual(signedOut.redirects, ["/login?return_to=%2Fimport-shipstation"]);
});
