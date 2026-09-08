const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const { randomUUID } = require("node:crypto");

const source = fs.readFileSync(path.join(__dirname, "../app/(app-shell)/lead-time-settings/page.tsx"), "utf8");
const compiled = ts.transpileModule(source + "\nexport { LeadTimeSettingsContent as TestContent };", {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const defaults = { shop_id: 1, shopify_domain: "merchant.myshopify.com", global_default_lead_time_days: 21, global_safety_buffer_days: 8, allow_mock_fallback: false, is_persisted: true };
const fixtures = {
  defaults,
  suppliers: { items: [{ vendor: "Vendor A", lead_time_days: 30 }] },
  categories: { items: [{ category: "Apparel", lead_time_days: 35 }] },
  skus: { items: [{ sku_id: "SKU-1", lead_time_days: 12 }] },
  catalog: [{ sku_id: "SKU-1", name: "Shirt", vendor: "Vendor A", category: "Apparel", sku_lead_time_days: 12 }],
};
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const identity = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/product-identity.ts"), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, identity);

function harness({ demo = false, reads = {}, writes = {} } = {}) {
  let cursor = 0, updateCount = 0;
  const slots = new Map(), effects = [], calls = [], exports = {};
  const jsx = (type, props) => ({ type, props });
  const api = {};
  for (const [method, section] of Object.entries({ fetchShopSettings: "defaults", fetchVendorLeadTimes: "suppliers", fetchCategoryLeadTimes: "categories", fetchSkuLeadTimes: "skus", fetchSkus: "catalog" })) {
    api[method] = async (...args) => { calls.push(["read", section, args.at(-1)]); return reads[section] ? reads[section](...args) : fixtures[section]; };
  }
  for (const [method, section] of Object.entries({ saveShopSettings: "defaults", saveVendorLeadTimes: "suppliers", saveCategoryLeadTimes: "categories", saveSkuLeadTimes: "skus" })) {
    api[method] = async (payload, signal) => { calls.push(["write", section, payload, signal]); return writes[section] ? writes[section](payload, signal) : section === "defaults" ? { ...defaults, ...payload } : { items: payload.items }; };
  }
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, typeof initial === "function" ? initial() : initial); return [slots.get(key), value => { updateCount++; slots.set(key, typeof value === "function" ? value(slots.get(key)) : value); }]; },
      useRef(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, { current: initial }); return slots.get(key); },
      useMemo: calculate => calculate(),
      useEffect(callback, deps) { const key = cursor++, previous = slots.get(key); if (!previous || deps.some((value, index) => value !== previous.deps[index])) { const next = { deps, cleanup: previous?.cleanup }; slots.set(key, next); effects.push(() => { next.cleanup?.(); next.cleanup = callback(); }); } },
    },
    "next/link": { __esModule: true, default: "a" },
    "@/components/auth-guard": { useAuth: () => ({ user: { id: demo ? 0 : 1 } }) },
    "@/components/section-card": { SectionCard: "section" },
    "@/components/empty-state": { EmptyState: "empty-state" },
    "@/components/gated-feature": { GatedFeature: "gated" },
    "@/lib/use-stored-shop-domain": { useStoredShopDomain: () => ({ shopifyDomain: defaults.shopify_domain, hasHydrated: true, setShopifyDomain() {} }) },
    "@/lib/api": api,
    "@/lib/product-identity": identity.exports,
    "./page.module.css": { __esModule: true, default: { page: "lead-time-page" } },
  };
  vm.runInNewContext(compiled, { exports, Number, Array, Set, Map, Error, Object, JSON, AbortController, crypto: { randomUUID },
    require(name) { if (!(name in dependencies)) throw new Error(`Unexpected import: ${name}`); return dependencies[name]; },
  });
  function render() {
    cursor = 0;
    const tree = exports.TestContent(), nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string") { texts.push(node); return; }
      if (!node || typeof node !== "object") return;
      nodes.push(node);
      if (node.type === "empty-state") texts.push(node.props.title, node.props.description);
      walk(node.props?.children);
    }
    walk(tree);
    while (effects.length) effects.shift()();
    return { nodes, text: texts.join(" "), button: label => nodes.find(node => node.type === "button" && node.props.children === label) };
  }
  async function settle() { for (let i = 0; i < 5; i++) { render(); await new Promise(setImmediate); } return render(); }
  async function save() { await render().nodes.find(node => node.type === "form").props.onSubmit({ preventDefault() {} }); return settle(); }
  function editAll() {
    let ui = render();
    ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "22" } });
    for (const name of ["Supplier", "Category"]) {
      const table = render().nodes.find(node => node.props?.nameLabel === name);
      table.props.onRowsChange(table.props.rows.map(row => ({ ...row, lead_time_days: String(Number(row.lead_time_days) + 1) })));
    }
    render().nodes.find(node => node.type === "input" && node.props.value === "12").props.onChange({ target: { value: "13" } });
  }
  return { render, settle, save, editAll, calls, updates: () => updateCount,
    unmount() { for (const value of slots.values()) if (value && typeof value === "object" && "cleanup" in value) value.cleanup?.(); },
  };
}

test("failed reads retain successful sections and block replacement writes until retried", async () => {
  let attempts = 0;
  const h = harness({ reads: { suppliers: async () => { if (++attempts === 1) throw new Error("Supplier rules unavailable"); return fixtures.suppliers; } } });
  let ui = await h.settle();
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "21"));
  assert.equal(ui.nodes.find(node => node.props?.nameLabel === "Category").props.rows[0].lead_time_days, "35");
  assert.equal(ui.button("Save lead-time rules").props.disabled, true);
  await h.save();
  assert.equal(h.calls.some(call => call[0] === "write"), false);
  h.render().button("Retry failed reads").props.onClick();
  ui = await h.settle();
  assert.equal(h.calls.filter(call => call[0] === "read" && call[1] === "suppliers").length, 2);
  for (const key of ["defaults", "categories", "skus", "catalog"]) assert.equal(h.calls.filter(call => call[0] === "read" && call[1] === key).length, 1);
  assert.equal(ui.button("Save lead-time rules").props.disabled, false);
  assert.equal(ui.nodes.find(node => node.props?.nameLabel === "Supplier").props.rows[0].name, "Vendor A");
});

test("a partial save names confirmed sections, retains failed edits, and retries only unsaved sections", async () => {
  let attempts = 0;
  const h = harness({ writes: { suppliers: async payload => { if (++attempts === 1) throw new Error("Temporary supplier save error"); return { items: payload.items }; } } });
  await h.settle(); h.editAll();
  let ui = await h.save();
  assert.match(ui.text, /Saved: Global defaults, Category rules, SKU rules/);
  assert.match(ui.text, /Not confirmed: Supplier rules/);
  assert.equal(ui.nodes.find(node => node.props?.nameLabel === "Supplier").props.rows[0].lead_time_days, "31");
  assert.equal(h.calls.filter(call => call[0] === "write").length, 4);
  ui = await h.save();
  assert.match(ui.text, /Saved: Supplier rules/);
  assert.equal(h.calls.filter(call => call[0] === "write").length, 5);
  assert.equal(h.calls.filter(call => call[0] === "write").at(-1)[1], "suppliers");
});

test("optional product lookup failure does not erase rules or block a confirmed global-only change", async () => {
  const h = harness({ reads: { catalog: async () => { throw new Error("Product lookup unavailable"); } } });
  let ui = await h.settle();
  assert.equal(ui.button("Save lead-time rules").props.disabled, false);
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "12"));
  ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "24" } });
  await h.save();
  assert.equal(h.calls.filter(call => call[0] === "write").length, 1);
  assert.equal(h.calls.find(call => call[0] === "write")[1], "defaults");
});

test("malformed saved rows and decimal lead times cannot be silently replaced or truncated", async () => {
  const broken = harness({ reads: { categories: async () => ({ items: [{}] }) } });
  assert.equal((await broken.settle()).button("Save lead-time rules").props.disabled, true);
  await broken.save();
  assert.equal(broken.calls.some(call => call[0] === "write"), false);
  const h = harness();
  let ui = await h.settle();
  ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "2.5" } });
  ui = await h.save();
  assert.match(ui.text, /Use whole numbers/);
  assert.equal(h.calls.some(call => call[0] === "write"), false);
});

test("demo settings are informational and never call store settings APIs", async () => {
  const h = harness({ demo: true });
  const ui = await h.settle();
  assert.match(ui.text, /No store settings are loaded or changed/);
  assert.equal(h.calls.length, 0);
  assert.equal(ui.button("Save lead-time rules"), undefined);
});

test("saving real lead-time changes preserves either saved compatibility value without a sample-data control", async () => {
  for (const savedFlag of [false, true]) {
    const h = harness({ reads: { defaults: async () => ({ ...defaults, allow_mock_fallback: savedFlag }) } });
    let ui = await h.settle();
    assert.doesNotMatch(ui.text, /Use sample data when live data is unavailable/);
    ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "25" } });
    ui = await h.save();
    assert.match(ui.text, /Saved: Global defaults/);
    const writes = h.calls.filter(call => call[0] === "write");
    assert.equal(writes.length, 1);
    assert.equal(writes[0][2].allow_mock_fallback, savedFlag);
    assert.equal(writes[0][2].global_default_lead_time_days, 25);
  }
});

test("a successful HTTP response must confirm stored values before the editor claims a save", async () => {
  const h = harness({ writes: { defaults: async payload => ({ ...defaults, ...payload, is_persisted: false }) } });
  let ui = await h.settle();
  ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "25" } });
  ui = await h.save();
  assert.match(ui.text, /stored defaults were not confirmed/);
  assert.doesNotMatch(ui.text, /Saved: Global defaults/);
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "25"));
});

test("a late load after navigation cannot change the displayed workspace settings", async () => {
  const pending = deferred();
  const h = harness({ reads: Object.fromEntries(Object.keys(fixtures).map(key => [key, () => pending.promise])) });
  h.render(); h.unmount();
  const before = h.updates();
  pending.resolve({});
  await new Promise(setImmediate);
  assert.equal(h.updates(), before);
  assert.ok(h.calls.every(call => call[2].aborted));
});

test("shared-SKU products remain visible but cannot select or edit an ambiguous rule", async () => {
  const h = harness({ reads: {
    catalog: async () => [1, 2].map(product_id => ({ ...fixtures.catalog[0], product_id, name: `Variant ${product_id}`, identity_ambiguous: true })),
    skus: async () => ({ ...fixtures.skus, warnings: ["SKU-1 has multiple active products; existing override retained."] }),
  } });
  let ui = await h.settle();
  assert.match(ui.text, /Mapping review needed/);
  assert.match(ui.text, /existing override retained/);
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.value === "12").props.disabled, true);
  ui.nodes.find(node => node.type === "input" && node.props.type === "search").props.onChange({ target: { value: "SKU-1" } });
  ui = h.render();
  const choices = ui.nodes.filter(node => node.type === "button" && node.props.className === "lead-time-suggestion");
  assert.equal(choices.length, 2);
  assert.ok(choices.every(node => node.props.disabled));
  choices[1].props.onClick(); // The handler also defends against a stale/enabled control.
  ui = h.render();
  assert.match(ui.text, /More than one product uses this SKU/);
  ui.nodes.find(node => node.type === "input" && node.props.value === "21").props.onChange({ target: { value: "26" } });
  await h.save();
  const writes = h.calls.filter(call => call[0] === "write");
  assert.equal(writes.length, 1);
  assert.equal(writes[0][1], "defaults");
});

test("saved unresolved rules return with warnings rather than false removals or repeated replacement writes", async () => {
  const h = harness({ writes: { skus: async payload => ({ items: [...payload.items, { sku_id: "RETAINED", lead_time_days: 20 }],
    warnings: ["RETAINED was not cleared because its mapping is ambiguous."] }) } });
  let ui = await h.settle();
  ui.nodes.find(node => node.type === "input" && node.props.value === "12").props.onChange({ target: { value: "13" } });
  ui = await h.save();
  assert.match(ui.text, /Saved: SKU rules/);
  assert.match(ui.text, /RETAINED was not cleared/);
  assert.doesNotMatch(ui.text, /Not confirmed/);
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "20"));
  ui = await h.save();
  assert.match(ui.text, /No unsaved rule changes/);
  assert.equal(h.calls.filter(call => call[0] === "write").length, 1);
});

test("a server mapping conflict preserves the precise review explanation and unsaved SKU edit", async () => {
  const h = harness({ writes: { skus: async () => { throw new Error("SKU-1 matches multiple active variants. Review its mapping before changing this rule."); } } });
  let ui = await h.settle();
  ui.nodes.find(node => node.type === "input" && node.props.value === "12").props.onChange({ target: { value: "13" } });
  ui = await h.save();
  assert.match(ui.text, /SKU-1 matches multiple active variants/);
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "13"));
  assert.doesNotMatch(ui.text, /Saved: SKU rules/);
});
