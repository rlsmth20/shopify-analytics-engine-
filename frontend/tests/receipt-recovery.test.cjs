const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const crypto = require("node:crypto");
const root = path.join(__dirname, "..");
function load(file, dependencies = {}, globals = {}, extra = "") {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, file), "utf8") + extra, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, Error, Number, Date, Map, Set, JSON, crypto, AbortController, ...globals,
    require(name) { assert.ok(name in dependencies, `Unexpected import ${name}`); return dependencies[name]; } });
  return exports;
}
const receipts = load("lib/receipt-submission.ts");
const scope = receipts.receiptScope(8, 3);
const input = { received_at: "2026-09-07T12:00:00.000Z", lines: [{ sku_id: "SKU", received_qty: 3, received_unit_cost: 12 }] };
function storage() {
  const values = new Map();
  return { get length() { return values.size; }, key: index => [...values.keys()][index] ?? null,
    getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key), values };
}
function locks() {
  const chains = new Map();
  return { request(name, action) { const result = (chains.get(name) ?? Promise.resolve()).then(action); chains.set(name, result.catch(() => {})); return result; } };
}

test("pending receipts preserve one exact payload across repeated preparation and scope isolation", () => {
  const store = storage();
  const first = receipts.retainReceiptSubmission(store, scope, "PO-1", input);
  const second = receipts.retainReceiptSubmission(store, scope, "PO-1", { ...input, lines: [{ ...input.lines[0], received_qty: 7 }] });
  assert.equal(JSON.stringify(second), JSON.stringify(first));
  assert.equal(receipts.listPendingReceipts(store, receipts.receiptScope(8, 4)).length, 0);
  assert.equal(receipts.listPendingReceipts(store, receipts.receiptScope(9, 3)).length, 0);
  assert.equal(receipts.listPendingReceipts(store, scope).length, 1);
  receipts.clearReceiptSubmission(store, scope, first);
  const newDelivery = receipts.retainReceiptSubmission(store, scope, "PO-1", input);
  assert.notEqual(newDelivery.payload.request_id, first.payload.request_id);
});

test("simultaneous tabs prepare one receipt under a shared browser lock", async () => {
  const store = storage(), manager = locks();
  let ids = 0;
  const prepare = () => receipts.withReceiptLock(manager, scope, "PO-1", () => receipts.retainReceiptSubmission(store, scope, "PO-1", input, () => { ids++; return crypto.randomUUID(); }));
  const [left, right] = await Promise.all([prepare(), prepare()]);
  assert.equal(ids, 1);
  assert.equal(JSON.stringify(left), JSON.stringify(right));
  assert.equal(receipts.listPendingReceipts(store, scope).length, 1);
});

test("missing locks, blocked storage and corrupted pending data fail before replacing a submission", async () => {
  let called = false;
  await assert.rejects(receipts.withReceiptLock(undefined, scope, "PO-1", () => { called = true; }), /cannot safely coordinate/);
  assert.equal(called, false);
  const store = storage();
  store.setItem = () => { throw new Error("Storage blocked"); };
  assert.throws(() => receipts.retainReceiptSubmission(store, scope, "PO-1", input), /No receipt was submitted/);
  const corrupt = storage();
  corrupt.values.set(`${scope}PO-1`, "{broken");
  assert.throws(() => receipts.retainReceiptSubmission(corrupt, scope, "PO-1", input), /Do not enter this delivery again/);
  assert.equal(corrupt.values.get(`${scope}PO-1`), "{broken");
});

function apiClient(fetcher) {
  return load("lib/api-v2.ts", {
    "@/lib/api-base": { API_BASE_URL: "https://private-api.test" },
    "@/lib/demo-data": {},
    "@/lib/receipt-submission": receipts,
    "@/lib/shopify-embedded": { isDemoActive: () => false, authenticatedFetch: fetcher },
  });
}
test("only a matching definitive preflight rejection authorizes correction, not generic conflicts or transport errors", async () => {
  const request = { ...input, request_id: crypto.randomUUID() };
  for (const [status, detail, expected] of [
    [409, { message: "Too many units", receipt_status: "not_applied", request_id: request.request_id }, request.request_id],
    [409, "This request ID already has a different payload", null],
    [409, { message: "Different operation", receipt_status: "not_applied", request_id: crypto.randomUUID() }, null],
    [503, { message: "Unavailable", receipt_status: "not_applied", request_id: request.request_id }, null],
  ]) {
    const client = apiClient(async () => ({ ok: false, status, json: async () => ({ detail }) }));
    await assert.rejects(client.receivePurchaseOrder("PO-1", request), error => error instanceof receipts.ReceiptSubmissionError && error.notAppliedRequestId === expected);
  }
  const offline = apiClient(async () => { throw new Error("private-url?secret=value"); });
  await assert.rejects(offline.receivePurchaseOrder("PO-1", request), error => !/private|secret/.test(error.message) && error.notAppliedRequestId === null);
});

const initialPo = { po_id: "PO-1", vendor: "Vendor", created_at: "2026-09-01T00:00:00Z", source: "saved", status: "sent",
  expected_arrival_date: "2026-09-08", lines: [{ sku_id: "SKU", name: "Tote", qty: 10, received_qty: 0, unit_cost: 12, extended_cost: 120 }],
  subtotal_cost: 120, shipping_cost: 0, total_cost: 120, rationale: "Recorded supplier order", receipts: [], received_at: null, sent_at: "2026-09-01T00:00:00Z" };
const financial = load("lib/financial-values.ts");
const finance = load("lib/purchase-order-finance.ts", { "./financial-values": financial });
const identity = load("lib/product-identity.ts");
function harness({ store = storage(), manager = locks(), user = { id: 3, shop_id: 8 }, fetchPo = () => initialPo, receive } = {}) {
  let cursor = 0;
  const slots = new Map(), effects = [], calls = [], jsx = (type, props) => ({ type, props });
  const window = { localStorage: store, location: { href: "" }, addEventListener() {}, removeEventListener() {} };
  const recoveryPanel = load("components/receipt-recovery-panel.tsx", { "react/jsx-runtime": { jsx, jsxs: jsx } }).ReceiptRecoveryPanel;
  const api = {
    currency: value => value === null ? "Unknown" : `$${value}`,
    fetchPurchaseOrders: async () => ({ drafts: [fetchPo()] }), fetchBuyingCalendar: async () => ({ events: [] }),
    savePurchaseOrder: async po => { calls.push(["save", po]); return { po }; },
    receivePurchaseOrder: async (poId, payload) => { calls.push(["receive", poId, JSON.parse(JSON.stringify(payload))]); return receive(poId, payload); },
  };
  const page = load("app/(app-shell)/purchase-orders/page.tsx", {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, typeof initial === "function" ? initial() : initial); return [slots.get(key), next => slots.set(key, typeof next === "function" ? next(slots.get(key)) : next)]; },
      useRef(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, { current: initial }); return slots.get(key); },
      useEffect(callback, dependencies) { const key = cursor++, old = slots.get(key); if (!old || dependencies.some((value, index) => value !== old.dependencies[index])) {
        const value = { dependencies, cleanup: old?.cleanup }; slots.set(key, value); effects.push(() => { value.cleanup?.(); value.cleanup = callback(); });
      } },
    },
    "@/components/auth-guard": { useAuth: () => ({ user }) },
    "@/lib/shopify-embedded": { isDemoActive: () => user.id === 0 },
    "@/components/buy-list-email-card": { BuyListEmailCard: "buy-email" },
    "@/components/cash-plan-card": { CashPlanCard: "cash-plan" },
    "@/components/gated-feature": { GatedFeature: "gated" },
    "@/components/identity-review-notice": { IdentityReviewNotice: "identity-notice" },
    "@/components/receipt-recovery-panel": { ReceiptRecoveryPanel: recoveryPanel },
    "@/lib/receipt-submission": receipts, "@/lib/financial-values": financial,
    "@/lib/purchase-order-finance": finance, "@/lib/product-identity": identity,
    "@/lib/report-export": {}, "@/lib/api-v2": api,
  }, { window, navigator: { locks: manager } }, "\nexport { PurchaseOrdersContent as TestContent };");
  function render() {
    cursor = 0; const nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string" || typeof node === "number") { texts.push(String(node)); return; }
      if (!node?.props) return;
      nodes.push(node);
      if (typeof node.type === "function") walk(node.type(node.props)); else walk(node.props.children);
    }
    walk(page.TestContent()); while (effects.length) effects.shift()();
    return { nodes, text: texts.join(" ").replace(/\s+/g, " "), button: label => nodes.find(node => node.type === "button" && node.props.children === label) };
  }
  async function settle() { for (let i = 0; i < 6; i++) { render(); await new Promise(setImmediate); } return render(); }
  async function enterReceipt(qty) {
    let ui = await settle();
    const head = ui.nodes.find(node => node.type === "button" && node.props.className === "po-card-head");
    if (!head.props["aria-expanded"]) { head.props.onClick(); ui = render(); }
    ui.button("Receive partial").props.onClick(); ui = render();
    ui.nodes.find(node => node.type === "input" && node.props.max !== undefined).props.onChange({ target: { value: String(qty) } });
    render().button("Record receipt").props.onClick();
    return settle();
  }
  return { render, settle, enterReceipt, calls, store, unmount() { for (const slot of slots.values()) if (slot && typeof slot === "object" && "cleanup" in slot) slot.cleanup?.(); } };
}

test("lost success, page reload and retry reuse one frozen delivery; a later acknowledged delivery gets a new ID", async () => {
  const store = storage(), ledger = new Map();
  let serverPo = JSON.parse(JSON.stringify(initialPo)), loseFirst = true, applied = 0;
  const receive = async (_poId, payload) => {
    if (ledger.has(payload.request_id)) return { po: serverPo, replayed: true, request_id: payload.request_id };
    applied++;
    serverPo = { ...serverPo, lines: [{ ...serverPo.lines[0], received_qty: serverPo.lines[0].received_qty + payload.lines[0].received_qty }], status: "partially_received" };
    ledger.set(payload.request_id, true);
    if (loseFirst) { loseFirst = false; throw new Error("Response interrupted."); }
    return { po: serverPo, replayed: false, request_id: payload.request_id };
  };
  const first = harness({ store, fetchPo: () => serverPo, receive });
  let ui = await first.enterReceipt(3);
  assert.match(ui.text, /Check unconfirmed receipts/);
  assert.equal(receipts.listPendingReceipts(store, scope)[0].payload.lines[0].received_qty, 3);
  assert.equal(first.calls.filter(call => call[0] === "save").length, 0);
  const firstPayload = first.calls.find(call => call[0] === "receive")[2];
  first.unmount();
  const recovered = harness({ store, fetchPo: () => serverPo, receive });
  ui = await recovered.settle();
  assert.ok(ui.button("Retry same receipt"));
  ui.button("Retry same receipt").props.onClick();
  ui = await recovered.settle();
  assert.match(ui.text, /Already recorded: 3 units/);
  assert.match(ui.text, /No additional received units were counted/);
  assert.deepEqual(recovered.calls.find(call => call[0] === "receive")[2], firstPayload);
  assert.equal(applied, 1); assert.equal(serverPo.lines[0].received_qty, 3);
  assert.equal(receipts.listPendingReceipts(store, scope).length, 0);
  ui = await recovered.enterReceipt(3);
  assert.match(ui.text, /Recorded 3 received units/);
  const lastPayload = recovered.calls.filter(call => call[0] === "receive").at(-1)[2];
  assert.notEqual(lastPayload.request_id, firstPayload.request_id);
  assert.equal(applied, 2); assert.equal(serverPo.lines[0].received_qty, 6);
});

test("only a confirmed not-applied rejection offers explicit correction; ordinary conflicts keep frozen recovery", async () => {
  for (const definite of [false, true]) {
    const h = harness({ receive: async (_id, payload) => { throw new receipts.ReceiptSubmissionError("Review the remaining quantity.", definite ? payload.request_id : null); } });
    let ui = await h.enterReceipt(3);
    assert.equal(Boolean(ui.button("Correct rejected receipt")), definite);
    assert.equal(Boolean(ui.button("Retry same receipt")), !definite);
    assert.equal(receipts.listPendingReceipts(h.store, scope).length, 1);
    if (definite) {
      ui.button("Correct rejected receipt").props.onClick(); ui = await h.settle();
      assert.match(ui.text, /No receipt was recorded/);
      assert.equal(receipts.listPendingReceipts(h.store, scope).length, 0);
    }
  }
});

test("new receipt sends fail closed without coordination/storage and cannot autosave an unsaved PO", async () => {
  // Explicitly remove the browser primitive (default options otherwise provide it).
  const noLocks = harness({ manager: null, receive: async () => { throw new Error("Should not send"); } });
  assert.match((await noLocks.enterReceipt(3)).text, /cannot safely coordinate/);
  assert.equal(noLocks.calls.length, 0);
  const blocked = storage(); blocked.setItem = () => { throw new Error("Browser storage blocked"); };
  const h = harness({ store: blocked, receive: async () => { throw new Error("Should not send"); } });
  assert.match((await h.enterReceipt(3)).text, /No receipt was submitted/);
  assert.equal(h.calls.length, 0);
  const unsaved = harness({ fetchPo: () => ({ ...initialPo, source: "recommended", status: "draft" }) });
  let ui = await unsaved.settle(); ui.nodes.find(node => node.type === "button" && node.props.className === "po-card-head").props.onClick(); ui = unsaved.render();
  assert.match(ui.text, /Save this draft before recording a delivery/);
  assert.equal(ui.button("Receive all").props.disabled, true);
  ui.button("Receive all").props.onClick(); await unsaved.settle();
  assert.equal(unsaved.calls.length, 0);
});
