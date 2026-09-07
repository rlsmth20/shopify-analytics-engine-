const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../app/import-stocky/page.tsx"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const valid = { shop_id: 1, shopify_domain: "merchant.myshopify.com", products_processed: 2, products_inserted: 0, products_updated: 1, inventory_rows_inserted: 0, rows_skipped: 1, skip_reasons: ["Row 3: multiple variants use this SKU"], inventory_source: "shopify", inventory_rows_skipped: 2, warnings: ["Sync Shopify for current stock."] };
function harness({ body = valid, failNetwork = false } = {}) {
  let cursor = 0; const slots = new Map(), calls = [];
  const jsx = (type, props) => ({ type, props });
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: { useEffect() {}, useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, initial); return [slots.get(key), value => slots.set(key, value)]; } },
    "next/link": { __esModule: true, default: "a" }, "next/navigation": { useRouter: () => ({ replace() {} }) },
    "@/lib/api-base": { API_BASE_URL: "https://api.example.test" }, "@/components/marketing-footer": { MarketingFooter: "footer" },
    "@/lib/shopify-embedded": { isEmbeddedShopifyContext: () => false, getEmbeddedShopifyContext: () => null, redirectToShopifyInstall() {},
      authenticatedFetch: async (...args) => { calls.push(args); if (failNetwork) throw new Error("Failed to fetch"); return { ok: true, status: 200, json: async () => body }; } },
  };
  const exports = {};
  vm.runInNewContext(code, { exports, Error, FormData: class { append() {} }, require: name => dependencies[name] || {} });
  function render() {
    cursor = 0; const nodes = [], texts = [];
    function walk(node) { if (Array.isArray(node)) return node.forEach(walk); if (typeof node === "string" || typeof node === "number") { texts.push(node); return; } if (!node || typeof node !== "object") return; nodes.push(node); walk(node.props?.children); }
    walk(exports.default()); return { nodes, text: texts.join(" ") };
  }
  async function submit() { render().nodes.find(node => node.type === "input" && node.props.type === "file").props.onChange({ target: { files: [{ name: "stocky.csv", size: 200 }] } }); await render().nodes.find(node => node.type === "form").props.onSubmit({ preventDefault() {} }); return render(); }
  return { render, submit, calls };
}

test("Shopify enrichment result explains preserved stock and displays skipped-row evidence", async () => {
  const ui = await harness().submit();
  assert.match(ui.text, /Shopify stock on hand was preserved/);
  assert.match(ui.text, /does not add another inventory count/);
  assert.match(ui.text, /multiple variants use this SKU/);
  assert.match(ui.text, /Sync Shopify for current stock/);
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "/store-sync" && node.props.children === "Check Shopify sync"));
});

test("no-change and CSV-only results cannot claim an activated sales-based recommendation", async () => {
  const unchanged = await harness({ body: { ...valid, products_updated: 0 } }).submit();
  assert.match(unchanged.text, /No product records changed/);
  assert.ok(unchanged.nodes.some(node => node.props?.role === "alert"));
  const csv = await harness({ body: { ...valid, inventory_source: "csv", warnings: [], inventory_rows_inserted: 1, inventory_rows_skipped: 0 } }).submit();
  assert.match(csv.text, /this file does not include sales history/);
  assert.doesNotMatch(csv.text, /ranks them within seconds/);
});

test("malformed success responses cannot masquerade as completed imports", async () => {
  for (const body of [null, {}, { ...valid, products_updated: "1" }, { ...valid, inventory_rows_skipped: -1 }, { ...valid, warnings: [null] }]) {
    const ui = await harness({ body }).submit();
    assert.match(ui.text, /result could not be confirmed/);
    assert.doesNotMatch(ui.text, /Imported or updated/);
  }
});

test("a lost POST response is not automatically resent through the proxy", async () => {
  const h = harness({ failNetwork: true }), ui = await h.submit();
  assert.equal(h.calls.length, 1);
  assert.match(ui.text, /may already have been saved/);
  assert.match(ui.text, /Check your catalog before uploading again/);
});

test("choosing a different file clears the old import result", async () => {
  const h = harness(); await h.submit();
  h.render().nodes.find(node => node.type === "input" && node.props.type === "file").props.onChange({ target: { files: [{ name: "another.csv", size: 100 }] } });
  assert.doesNotMatch(h.render().text, /Imported or updated 1/);
});
