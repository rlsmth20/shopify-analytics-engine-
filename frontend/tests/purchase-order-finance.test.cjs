const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, dependencies = {}, extraSource = "", globals = {}) {
  const source = ts.transpileModule(readFileSync(path.join(__dirname, file), "utf8") + extraSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, Number, Math, Date, Map, Set, Intl, Error, ...globals, require(name) {
    if (name in dependencies) return dependencies[name];
    throw new Error(`Unexpected runtime import: ${name}`);
  } };
  vm.runInNewContext(source, context);
  return context.exports;
}

const financial = load("../lib/financial-values.ts");
const identity = load("../lib/product-identity.ts");
const helpers = load("../lib/purchase-order-finance.ts", { "./financial-values": financial });
const line = { sku_id: "SKU", name: "Product", qty: 5, received_qty: 0, unit_cost: 30, extended_cost: 150 };
const po = {
  po_id: "PO-test", vendor: "Supplier", created_at: "2026-09-07T00:00:00Z", expected_arrival_date: "2026-09-12",
  status: "draft", source: "recommended", lines: [line], subtotal_cost: 150, shipping_cost: 10, total_cost: 160,
  rationale: "Replenish tested demand.", receipts: [],
};
const unknownLine = { ...line, cost_source: "estimated_from_price", financial_values_known: false,
  financial_values: { unit_cost: null, extended_cost: null } };
const unknownPo = { ...po, lines: [unknownLine], financial_values_known: false,
  financial_values: { subtotal_cost: null, total_cost: null } };

test("estimated supplier prices cannot seed editable prices or appear as confirmed spend", () => {
  assert.equal(helpers.editableUnitCost(unknownLine), "");
  assert.equal(helpers.purchaseOrderCostsKnown(unknownPo), false);
  assert.equal(helpers.sumPoTotals([po, unknownPo]), null);
  assert.equal(helpers.sumPoTotals([po]), 160);
  assert.equal(helpers.editableUnitCost(line), "30.00");
  assert.equal(helpers.purchaseOrderCostsKnown(po), true);
});

test("blank, invalid and estimated cost remain distinct from an explicitly entered zero", () => {
  for (const input of ["", "  ", "-1", "Infinity", "1e308", "not a number"]) assert.equal(helpers.parseMoney(input), null);
  assert.equal(helpers.parseMoney("0"), 0);
  const editable = { sku_id: "SKU", name: "Product", qty: "5", unit_cost: "", received_qty: 0 };
  assert.equal(helpers.normalizeEditableLine(editable), null);
  const recorded = helpers.normalizeEditableLine({ ...editable, unit_cost: "12.50" });
  assert.equal(recorded.cost_source, "recorded");
  assert.equal(recorded.financial_values_known, true);
  assert.equal(recorded.financial_values.unit_cost, 12.5);
  assert.equal(recorded.financial_values.extended_cost, 62.5);
  assert.equal(helpers.normalizeEditableLine({ ...editable, unit_cost: "0" }).unit_cost, 0);
});

test("invalid line quantities cannot silently become valid orders", () => {
  const editable = { sku_id: "SKU", name: "Product", qty: "5", unit_cost: "12", received_qty: 2 };
  for (const qty of ["", "0", "1", "1.5", "-3", "Infinity"]) {
    assert.equal(helpers.normalizeEditableLine({ ...editable, qty }), null);
  }
  assert.equal(helpers.normalizeEditableLine(editable).qty, 5);
});

test("an incomplete edit cannot display a partial subtotal as a complete total", () => {
  const editable = { ...po, shipping_cost: "10", lines: [
    { sku_id: "A", name: "A", qty: "2", unit_cost: "5", received_qty: 0 },
    { sku_id: "B", name: "B", qty: "3", unit_cost: "", received_qty: 0 },
  ] };
  const preview = helpers.previewEditablePoTotals(editable);
  assert.equal(preview.subtotal, null);
  assert.equal(preview.total, null);
  assert.equal(preview.shipping, 10);
  editable.lines[1].unit_cost = "4";
  assert.equal(helpers.previewEditablePoTotals(editable).total, 32);
});

function renderPurchaseOrder(draft, expanded = true, { receiving = false, receiptError = null } = {}) {
  let hook = 0;
  const calls = [];
  const stateUpdates = [];
  const window = { location: { href: "" }, localStorage: { getItem: () => null, setItem: () => {} } };
  const stateOverrides = new Map([[0, [draft]], [2, draft.total_cost], [7, false], [9, expanded ? draft.po_id : null]]);
  if (receiving) {
    stateOverrides.set(11, draft.po_id);
    stateOverrides.set(12, { [draft.po_id]: { receivedAt: "2026-09-07", lines: Object.fromEntries(draft.lines.map(line => [line.sku_id, { qty: String(line.qty - line.received_qty), cost: String(line.unit_cost) }])) } });
  }
  const jsx = (type, props) => ({ type, props });
  const api = {
    currency: (value) => value === null ? "Unknown" : `$${value}`,
    savePurchaseOrder: async (value) => { calls.push(["save", value]); return { po: value }; },
    updatePurchaseOrderStatus: async (id, status) => { calls.push(["status", id, status]); return { po: { ...draft, status } }; },
    receivePurchaseOrder: async (id, payload) => { calls.push(["receive", id, payload]); if (receiptError) throw new Error(receiptError); return { po: draft }; },
  };
  const page = load("../app/(app-shell)/purchase-orders/page.tsx", {
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "fragment" },
    react: { useEffect() {}, useState(initial) {
      const index = hook++;
      return [stateOverrides.has(index) ? stateOverrides.get(index) : initial, (value) => stateUpdates.push([index, value])];
    } },
    "@/lib/shopify-embedded": { isDemoActive: () => true },
    "@/components/buy-list-email-card": { BuyListEmailCard: "BuyListEmailCard" },
    "@/components/cash-plan-card": { CashPlanCard: "CashPlanCard" },
    "@/components/gated-feature": { GatedFeature: "GatedFeature" },
    "@/lib/api-v2": api,
    "@/lib/report-export": {},
    "@/lib/financial-values": financial,
    "@/lib/purchase-order-finance": helpers,
    "@/lib/product-identity": identity,
    "@/components/identity-review-notice": { IdentityReviewNotice: "identity-review" },
  }, "\nexport { PurchaseOrdersContent as renderForTest };", { window });
  const tree = page.renderForTest();
  const buttons = [], nodes = [];
  const elementsById = new Map();
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== "object") return;
    nodes.push(node);
    if (node.type === "button") buttons.push(node);
    if (node.props?.id) elementsById.set(node.props.id, node);
    walk(node.props?.children);
  }
  walk(tree);
  return { calls, window, buttons, elementsById, stateUpdates, nodes };
}

test("opening a vendor email draft never records sending; explicit acknowledgement does", async () => {
  const { calls, window, buttons } = renderPurchaseOrder(po);
  const openDraft = buttons.find((button) => button.props.children === "Open vendor email draft");
  assert.ok(openDraft);
  openDraft.props.onClick();
  assert.match(window.location.href, /^mailto:/);
  assert.equal(calls.length, 0);
  const markSent = buttons.find((button) => button.props.children === "Mark as sent");
  assert.ok(markSent);
  assert.equal(markSent.props.disabled, false);
  markSent.props.onClick();
  await new Promise(setImmediate);
  assert.equal(calls[0][0], "save");
  assert.deepEqual(calls[1], ["status", "PO-test", "sent"]);
});

test("unknown costs disable direct save and supplier sending while leaving editing available", () => {
  const { buttons } = renderPurchaseOrder(unknownPo);
  for (const label of ["Add unit costs first", "Open vendor email draft", "Mark as sent", "Approve PO", "Receive all"]) {
    const button = buttons.find((item) => item.props.children === label);
    assert.ok(button, label);
    assert.equal(button.props.disabled, true, label);
  }
  assert.equal(buttons.find((item) => item.props.children === "Edit PO").props.disabled, false);
});

test("purchase-order headers are native disclosure buttons linked to their details", () => {
  for (const expanded of [false, true]) {
    const view = renderPurchaseOrder(po, expanded);
    const toggle = view.buttons.find((item) => item.props.className === "po-card-head");
    assert.ok(toggle);
    assert.equal(toggle.props.type, "button");
    assert.equal(toggle.props["aria-expanded"], expanded);
    assert.equal(toggle.props["aria-label"], "Purchase order PO-test from Supplier");
    const details = view.elementsById.get(toggle.props["aria-controls"]);
    assert.ok(details);
    assert.equal(details.props.hidden, !expanded);
    toggle.props.onClick();
    assert.deepEqual(view.stateUpdates.at(-1), [9, expanded ? null : po.po_id]);
  }
});

test("ambiguous PO lines block receive-all but a partial receipt still sends only unique aliases", async () => {
  const mixed = { ...po, source: "saved", lines: [{ ...line, product_id: 1, identity_ambiguous: true }, { ...line, sku_id: "UNIQUE", product_id: 3 }] };
  const ui = renderPurchaseOrder(mixed, true, { receiving: true });
  assert.equal(ui.buttons.find(button => button.props.children === "Receive all").props.disabled, true);
  assert.equal(ui.buttons.find(button => button.props.children === "Receive partial").props.disabled, false);
  assert.ok(ui.nodes.some(node => node.type === "input" && node.props.value === "0" && node.props.disabled));
  ui.buttons.find(button => button.props.children === "Record receipt").props.onClick();
  await new Promise(setImmediate);
  const sent = ui.calls.find(call => call[0] === "receive");
  assert.ok(sent);
  assert.equal(sent[2].lines.length, 1);
  assert.equal(sent[2].lines[0].sku_id, "UNIQUE");
  assert.equal(sent[2].lines[0].received_qty, 5);
});

test("duplicate PO aliases remain in review even with different product IDs and no explicit flag", async () => {
  const ambiguous = { ...po, lines: [1, 2].map(product_id => ({ ...line, product_id })) };
  const ui = renderPurchaseOrder(ambiguous);
  assert.equal(ui.buttons.find(button => button.props.children === "Receive all").props.disabled, true);
  assert.equal(ui.buttons.find(button => button.props.children === "Receive partial").props.disabled, true);
  ui.buttons.find(button => button.props.children === "Receive all").props.onClick();
  await new Promise(setImmediate);
  assert.equal(ui.calls.length, 0);
});

test("a new server-side receipt conflict retains the mapping explanation without claiming receipt", async () => {
  const reason = "SKU matches multiple active variants. Review the mapping before receiving stock.";
  const ui = renderPurchaseOrder(po, true, { receiving: true, receiptError: reason });
  ui.buttons.find(button => button.props.children === "Record receipt").props.onClick();
  await new Promise(setImmediate);
  assert.ok(ui.stateUpdates.some(([index, value]) => index === 16 && value === reason));
  assert.equal(ui.stateUpdates.some(([index, value]) => index === 15 && typeof value === "string" && value.startsWith("Recorded")), false);
});
