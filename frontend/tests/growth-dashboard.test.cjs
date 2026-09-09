const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const source = ts.transpileModule(readFileSync(path.join(__dirname, "../lib/growth-dashboard.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const context = { exports: {}, Intl, Date, Number, Math };
vm.runInNewContext(source, context);
const view = context.exports;

test("unknown amounts and absent counts remain distinct from observed zero", () => {
  for (const value of [null, undefined, NaN, Infinity]) {
    assert.equal(view.growthNumber(value), "Unknown");
    assert.equal(view.growthMoney(value), "Unknown");
    assert.equal(view.growthPercent(value), "Unknown");
  }
  assert.equal(view.growthNumber(0), "0");
  assert.equal(view.growthMoney(0), "$0.00");
  assert.equal(view.growthPercent(0), "0%");
  assert.equal(view.growthMoney(.0007), "$0.0007");
});

test("unlinked contacts cannot turn into zero conversions", () => {
  assert.equal(view.outcomeLabel(0, 0, 13), "Unknown");
  assert.equal(view.outcomeLabel(0, 2, 13), "Unknown");
  assert.equal(view.outcomeLabel(1, 2, 13), "1+");
  assert.equal(view.outcomeLabel(0, 13, 13), "0");
  assert.equal(view.outcomeLabel(1, 13, 13), "1");
  assert.equal(view.outcomeLabel(0, 0, 0), "Unknown");
});

test("empty, negative and overflow chart measurements stay within bounds", () => {
  assert.equal(view.chartWidth(13, 20), 65);
  assert.equal(view.chartWidth(30, 20), 100);
  assert.equal(view.chartWidth(-1, 20), 0);
  assert.equal(view.chartWidth(null, 20), 0);
  assert.equal(view.chartWidth(4, 0), 0);
  assert.equal(view.chartWidth(NaN, 20), 0);
  assert.ok(!view.FUNNEL_STAGES.some(([stage]) => stage === "CALCULATOR_USED"));
});

test("older growth snapshots keep inbox monitoring unknown without inventing a failed check", () => {
  const inbox = view.growthInboxView();
  assert.equal(inbox.label, "Inbox status unknown");
  assert.equal(inbox.lastPollAt, null);
  assert.equal(inbox.lastPollResult, "Unknown");
  assert.equal(inbox.latestReplies, null);
  assert.equal(inbox.verifiedAt, null);
  assert.equal(inbox.warning, false);
});

const checkedInbox = {
  status: "verification_unrecorded", last_poll_at: 1000, last_poll_status: "success",
  last_successful_poll_at: 1000, latest_poll_replies_ingested: 0,
  last_bridge_verified_at: null, verification_due_after_seconds: 604800,
};

test("a successful empty inbox is observed zero, not failure or forwarding proof", () => {
  const inbox = view.growthInboxView(checkedInbox);
  assert.equal(inbox.latestReplies, 0);
  assert.equal(inbox.lastPollResult, "Successful");
  assert.equal(inbox.verifiedAt, null);
  assert.equal(inbox.label, "Reply delivery not yet verified");
  assert.equal(inbox.verificationWindowDays, 7);
  assert.equal(inbox.lastReceiptAt, null);
});

test("fresh polls and copied receipts cannot replace old independent delivery verification", () => {
  const inbox = view.growthInboxView({ ...checkedInbox, status: "verification_stale",
    label: "The reply path needs a fresh check", explanation: "Polling succeeded; independent proof is old.",
    last_approved_receipt_at: 800, last_approved_receipt_observed_at: 950, last_bridge_verified_at: 100 });
  assert.equal(inbox.label, "The reply path needs a fresh check");
  assert.equal(inbox.explanation, "Polling succeeded; independent proof is old.");
  assert.equal(inbox.lastPollAt, 1000);
  assert.equal(inbox.lastReceiptAt, 800);
  assert.equal(inbox.receiptObservedAt, 950);
  assert.equal(inbox.verifiedAt, 100);
  assert.equal(inbox.warning, true);
});

test("failed checks keep prior successes visible without recycling their reply count", () => {
  const inbox = view.growthInboxView({ ...checkedInbox, status: "poll_failed", last_poll_at: 1100,
    last_poll_status: "failed", latest_poll_replies_ingested: 3, last_bridge_verified_at: 900 });
  assert.equal(inbox.lastPollAt, 1100);
  assert.equal(inbox.lastSuccessfulPollAt, 1000);
  assert.equal(inbox.lastPollResult, "Failed");
  assert.equal(inbox.latestReplies, null);
  assert.equal(inbox.verifiedAt, 900);
  assert.equal(inbox.label, "Latest inbox check failed");
});

test("verified status requires recorded independent proof and malformed evidence stays unknown", () => {
  for (const timestamp of [null, undefined, NaN, Infinity, -1]) {
    const inbox = view.growthInboxView({ ...checkedInbox, status: "verified", last_bridge_verified_at: timestamp,
      last_approved_receipt_at: timestamp, latest_poll_replies_ingested: -1 });
    assert.equal(inbox.label, "Inbox status unknown");
    assert.equal(inbox.verifiedAt, null);
    assert.equal(inbox.lastReceiptAt, null);
    assert.equal(inbox.latestReplies, null);
  }
  const verified = view.growthInboxView({ ...checkedInbox, status: "verified", last_bridge_verified_at: 900 });
  assert.equal(verified.label, "Reply delivery recently verified");
  assert.equal(verified.warning, false);
  assert.equal(verified.latestReplies, 0);
});

test("business inbox panel shows its evidence distinctions without additional network requests", () => {
  const source = ts.transpileModule(readFileSync(path.join(__dirname, "../app/growth/page.tsx"), "utf8")
    + "\nexport { InboxMonitoring as TestInboxMonitoring };", {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  const jsx = (type, props) => ({ type, props });
  const dependencies = {
    react: {}, "react/jsx-runtime": { jsx, jsxs: jsx },
    "next/link": { __esModule: true, default: "a" },
    "@/lib/api-base": { API_BASE_URL: "https://not-called.invalid" },
    "@/lib/shopify-embedded": { authenticatedFetch() { assert.fail("Inbox presentation must reuse the dashboard snapshot"); } },
    "@/lib/growth-dashboard": view,
    "./page.module.css": { __esModule: true, default: {} },
  };
  vm.runInNewContext(source, { exports, require(name) {
    assert.ok(name in dependencies, `Unexpected import ${name}`);
    return dependencies[name];
  } });
  const text = [];
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (typeof node === "string" || typeof node === "number") { text.push(String(node)); return; }
    if (node?.props) walk(node.props.children);
  }
  walk(exports.TestInboxMonitoring({ transport: checkedInbox }));
  const rendered = text.join(" ");
  assert.match(rendered, /info@skubase\.io/);
  assert.match(rendered, /Replies ingested on latest check 0/);
  assert.match(rendered, /Last copied receipt arrived Unknown/);
  assert.match(rendered, /Last verified reply delivery Unknown/);
  assert.match(rendered, /An empty successful check is normal/);
  assert.match(rendered, /does not prove that Gmail is forwarding replies/);
  assert.match(rendered, /separate from merchant reply metrics/);
});

test("confirmed outreach excludes uncertainty across deployment versions", () => {
  assert.equal(view.confirmedOutreach({used:20,unresolved:8}),12);
  assert.equal(view.confirmedOutreach({used:12,unresolved:8,confirmed_sent_count:12}),12);
  assert.equal(view.confirmedOutreach({used:21,unresolved:7,confirmed_sent_count:21}),21);
});

function renderDashboardCapacity(limit, confirmed, uncertain = 0, blocker = null) {
  const capacity = { limit, confirmed_sent_count: confirmed, used: confirmed, unresolved: uncertain,
    uncertain_contact_count: uncertain, in_flight_send_count: 0, remaining: limit === null ? null : Math.max(0, limit - confirmed),
    blocker, day_timezone: 'America/Los_Angeles', next_slot_at: null };
  const snapshot = {
    mission: {}, today: {}, pipeline: { contacts: [] }, economics: {}, recent_actions: [],
    experiments: { counts: {}, items: [] }, learning: { recent_changes: [], contradictions: [], beliefs: [] },
    strategy: { bottleneck: {} }, agent: { first_contact_capacity: capacity, errors: [], health: 'running' },
    execution: { daily_new_contact_cap: limit, sent_today: confirmed, remaining_capacity: capacity.remaining },
  };
  const code = ts.transpileModule(readFileSync(path.join(__dirname, '../app/growth/page.tsx'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  let stateIndex = 0;
  const jsx = (type, props) => ({ type, props });
  const dependencies = {
    react: { useState(initial) { return [stateIndex++ === 0 ? snapshot : initial, () => {}]; },
      useRef: initial => ({ current: initial }), useCallback: fn => fn, useEffect() {} },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    'next/link': { __esModule: true, default: 'a' }, '@/lib/api-base': { API_BASE_URL: '' },
    '@/lib/shopify-embedded': { authenticatedFetch() { assert.fail('Render cannot send requests'); } },
    '@/lib/growth-dashboard': view, './page.module.css': { __esModule: true, default: {} },
  };
  vm.runInNewContext(code, { exports, require(name) {
    assert.ok(name in dependencies, `Unexpected import ${name}`); return dependencies[name];
  }, Intl, Date, Number, Math });
  const text = [], meters = [];
  function walk(node) {
    if (Array.isArray(node)) return node.forEach(walk);
    if (typeof node === 'string' || typeof node === 'number') { text.push(String(node)); return; }
    if (node?.props?.role === 'meter') meters.push(node.props);
    if (node?.props) walk(typeof node.type === 'function' ? node.type(node.props) : node.props.children);
  }
  walk(exports.default());
  return { text: text.join(' '), meters };
}

test('uncapped dashboard shows actual outreach above twenty with no misleading quota meter', () => {
  const rendered = renderDashboardCapacity(null, 24, 8);
  assert.match(rendered.text, /Daily outreach limit No daily limit/);
  assert.match(rendered.text, /Confirmed first contacts 24 Uncertain contacts 8/);
  assert.match(rendered.text, /24  confirmed first contacts/);
  assert.match(rendered.text, /8\s+uncertain contacts protected from retry/);
  assert.match(rendered.text, /Continue outreach to other eligible merchants/);
  assert.doesNotMatch(rendered.text, /\/ null|\/ 0|ceiling reached|above the ceiling|count toward 20/);
  assert.equal(rendered.meters.length, 0);
});

test('finite historical snapshots retain quota meters and independent uncertainty holds', () => {
  const finite = renderDashboardCapacity(20, 12, 8);
  assert.equal(finite.meters.length, 1);
  assert.equal(finite.meters[0]['aria-valuemax'], 20);
  assert.equal(finite.meters[0]['aria-valuenow'], 12);
  assert.match(finite.text, /Only confirmed submissions count toward the 20-contact ceiling/);
  const held = renderDashboardCapacity(null, 24, 10, 'OUTREACH_UNCERTAINTY_SAFETY_HOLD');
  assert.match(held.text, /Receipt uncertainty needs attention before another send/);
  assert.equal(held.meters.length, 0);
});
