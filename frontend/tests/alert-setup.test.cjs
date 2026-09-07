const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, dependencies = {}, extra = "") {
  const source = ts.transpileModule(readFileSync(path.join(__dirname, file), "utf8") + extra, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = { exports: {}, URL, Number, Math, Date, Set, Object, Error, require(name) {
    if (name in dependencies) return dependencies[name];
    throw new Error(`Unexpected runtime import ${name}`);
  } };
  vm.runInNewContext(source, context);
  return context.exports;
}
const setup = load("../lib/alert-setup.ts");
const channel = { channel: "email", target: "inventory@merchant.test", enabled: true, verified: true, available: true, configured: true };
const rule = { id: "rule", name: "Inventory rule", trigger: "stockout_risk", enabled: true, channels: ["email"], target_skus: [], categories: [], tags: [], collections: [], locations: [], suppliers: [] };

test("enabled does not imply a ready delivery channel", () => {
  for (const change of [{ available: false }, { available: undefined }, { configured: false }, { verified: false }, { enabled: false }, { target: "" }, { target: "alerts@example.com" }]) {
    assert.equal(setup.channelState({ ...channel, ...change }, true).ready, false);
  }
  assert.equal(setup.channelState(channel, false).ready, false);
  assert.equal(setup.channelState({ ...channel, channel: "sms" }, true).ready, false);
  assert.equal(setup.channelState(channel, true).ready, true);
});

test("rule readiness requires its selected channel and plan access", () => {
  assert.equal(setup.ruleHasReadyChannel(rule, [channel], () => true), true);
  assert.equal(setup.ruleHasReadyChannel({ ...rule, channels: ["slack"] }, [channel], () => true), false);
  assert.equal(setup.ruleHasReadyChannel(rule, [channel], () => false), false);
  assert.equal(setup.ruleHasReadyChannel(rule, [{ ...channel, verified: false }], () => true), false);
});

test("destination validation rejects placeholder email and misleading webhook URLs", () => {
  for (const value of ["", "alerts@example.com", "owner@shop.test, other@shop.test", "<owner@shop.test>", "owner;other@shop.test", "owner@shop.test,", "shopify-admin+123@shop.test", "invalid"]) assert.ok(setup.targetError("email", value));
  assert.equal(setup.targetError("email", " owner@merchant.test "), null);
  for (const value of ["http://hooks.slack.com/services/A/B/C", "https://hooks.slack.com.evil.test/services/A/B/C", "https://user:password@hooks.slack.com/services/A/B/C", "https://hooks.slack.com/services/A/B", "https://hooks.slack.com/services/A/B/C#secret"]) assert.ok(setup.targetError("slack", value));
  assert.equal(setup.targetError("slack", "https://hooks.slack.com/services/A/B/C"), null);
  assert.equal(setup.targetError("webhook", "https://workflow.test/incoming"), null);
  assert.equal(setup.targetError("webhook", "https://workflow.test:443/incoming"), null);
  for (const value of ["https://workflow.test:8443/incoming", "https://localhost/hook", "https://workflow.local/hook", "https://metadata.google.internal/hook", "https://10.0.0.1/hook", "https://127.0.0.1/hook", "https://169.254.169.254/hook", "https://172.16.0.1/hook", "https://192.168.0.1/hook", "https://[::1]/hook", "https://work flow.test/hook"]) assert.ok(setup.targetError("webhook", value), value);
});

test("empty thresholds cannot become zero and percentages stay in range", () => {
  for (const value of ["", " ", "NaN", "Infinity", "-1"]) assert.ok(setup.thresholdError("stockout_risk", value));
  assert.equal(setup.thresholdError("stockout_risk", "0"), null);
  assert.ok(setup.thresholdError("forecast_miss", "101"));
  assert.equal(setup.thresholdError("dead_stock", "1000"), null);
});

test("preview, partial delivery and unknown outcomes never become blanket delivery claims", () => {
  const event = { delivered: true, channels_sent: [] };
  assert.match(setup.eventDeliveryLabel(event), /Preview/);
  assert.match(setup.eventDeliveryLabel({ ...event, delivered: false, preview: true }), /not sent/);
  assert.match(setup.eventDeliveryLabel({ ...event, channels_sent: ["email"], delivery_status: "partial" }), /Some channels/);
  assert.match(setup.eventDeliveryLabel({ ...event, delivery_status: "unknown" }), /unknown/);
  assert.match(setup.eventDeliveryLabel({ ...event, delivery_status: "failed" }), /failed/);
  assert.equal(setup.eventDeliveryLabel({ ...event, channels_sent: ["email"], delivery_status: "accepted" }), "Request accepted");
});

test("unsupported scopes remain distinguishable from implemented product metadata", () => {
  assert.equal(setup.unsupportedTargeting({ ...rule, suppliers: ["Supplier"], categories: ["Apparel"] }).length, 0);
  assert.equal(setup.unsupportedTargeting({ ...rule, tags: ["sale"], locations: ["Warehouse"] }).join(","), "tags,locations");
  assert.equal(setup.unsupportedTargeting({ ...rule, trigger: "supplier_slip", target_skus: ["SKU"], categories: ["Apparel"] }).join(","), "SKUs,categories");
});

function renderChannel(config = channel, { testResult, failSave = false, failTest = false, failRetry = false, demo = false } = {}) {
  let cursor = 0;
  const states = new Map();
  const calls = [];
  const jsx = (type, props) => ({ type, props });
  const api = {
    updateChannel: async (payload) => { calls.push(["save", payload]); if (failSave) throw new Error("Save rejected"); return payload; },
    sendTestAlert: async (payload) => { calls.push(["test", payload]); if (failTest) throw new Error("Request timed out"); return testResult ?? { delivered: true, status: "accepted", persisted_verified: true }; },
    retryUncertainAlert: async (id, channel) => { calls.push(["retry", id, channel]); if (failRetry) throw new Error("Destination changed; test the new destination"); return { queued: true }; },
  };
  const page = load("../app/(app-shell)/alerts/page.tsx", {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: { useEffect() {}, useState(initial) { const key = cursor++; if (!states.has(key)) states.set(key, initial); return [states.get(key), (value) => states.set(key, typeof value === "function" ? value(states.get(key)) : value)]; } },
    "next/link": { __esModule: true, default: "a" },
    "@/components/data-quality-note": { DataQualityNote: "DataQualityNote" },
    "@/components/auth-guard": {}, "@/lib/entitlements": {}, "@/lib/plans": {},
    "@/lib/api-v2": api, "@/lib/alert-setup": setup,
    "./page.module.css": { __esModule: true, default: {} },
  }, "\nexport { ChannelCard as renderCardForTest, UncertainRetry as renderRetryForTest };");
  function render(retryEvent) {
    cursor = 0;
    const tree = retryEvent ? page.renderRetryForTest({ event: retryEvent, demo, onChange: () => calls.push(["refresh"]) })
      : page.renderCardForTest({ channel: config, locked: false, demo, onChange: () => calls.push(["refresh"]) });
    const nodes = [];
    const text = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string") { text.push(node); return; }
      if (!node || typeof node !== "object") return;
      nodes.push(node); walk(node.props?.children);
    }
    walk(tree);
    return { nodes, text: text.join(" "), button: (label) => nodes.find((node) => node.type === "button" && node.props.children === label) };
  }
  return { render, calls };
}

test("editing a tested destination pauses the draft and prevents testing unsaved changes", () => {
  const view = renderChannel();
  let ui = view.render();
  ui.nodes.find((node) => node.type === "input" && node.props.type === "email").props.onChange({ target: { value: "new@merchant.test" } });
  ui = view.render();
  assert.equal(ui.button("Send test").props.disabled, true);
  assert.equal(ui.nodes.find((node) => node.type === "input" && node.props.type === "checkbox").props.checked, false);
  assert.match(ui.text, /new destination is saved paused/);
  assert.equal(view.calls.length, 0);
});

test("saving and testing errors remain visible instead of silently succeeding", async () => {
  const saving = renderChannel(channel, { failSave: true });
  let ui = saving.render();
  ui.nodes.find((node) => node.type === "input" && node.props.type === "email").props.onChange({ target: { value: "new@merchant.test" } });
  ui = saving.render(); ui.button("Save destination").props.onClick();
  await new Promise(setImmediate);
  assert.match(saving.render().text, /Save rejected/);
  const testing = renderChannel(channel, { failTest: true });
  testing.render().button("Send test").props.onClick();
  await new Promise(setImmediate);
  assert.match(testing.render().text, /Request timed out/);
});

test("saving a channel toggle names the action and does not ask to repeat its successful test", async () => {
  for (const enabled of [false, true]) {
    const view = renderChannel({ ...channel, enabled });
    let ui = view.render();
    ui.nodes.find((node) => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: !enabled } });
    ui = view.render();
    ui.button(enabled ? "Pause channel" : "Enable channel").props.onClick();
    await new Promise(setImmediate);
    assert.equal(view.calls[0][1].enabled, !enabled);
    assert.match(view.render().text, enabled ? /Channel paused/ : /Channel enabled/);
    assert.doesNotMatch(view.render().text, /Destination saved\. Send a test/);
  }
});

test("a test uses the saved destination and explicit uncertain result does not count as accepted", async () => {
  const accepted = renderChannel();
  accepted.render().button("Send test").props.onClick();
  await new Promise(setImmediate);
  assert.equal(accepted.calls[0][1].target, channel.target);
  assert.match(accepted.render().text, /Test request accepted/);
  assert.match(accepted.render().text, /inbox and spam folder/);
  const uncertain = renderChannel(channel, { testResult: { delivered: true, status: "unknown", error: "Outcome unavailable", persisted_verified: false } });
  uncertain.render().button("Send test").props.onClick();
  await new Promise(setImmediate);
  assert.match(uncertain.render().text, /Outcome unavailable/);
  assert.doesNotMatch(uncertain.render().text, /Test request accepted/);
});

test("demo never exposes enabled send or save actions", () => {
  const ui = renderChannel(channel, { demo: true }).render();
  assert.equal(ui.button("Send test").props.disabled, true);
  assert.equal(ui.button("Save destination").props.disabled, true);
  assert.match(ui.text, /No test messages are sent/);
});

test("uncertain retries require explicit acknowledgement and exclude accepted channels", async () => {
  const event = { id: "event", resolved: false, channels_sent: ["email"], uncertain_channels: ["slack"] };
  const view = renderChannel();
  let ui = view.render(event);
  assert.equal(ui.button("Retry slack").props.disabled, true);
  assert.equal(ui.button("Retry email"), undefined);
  ui.button("Retry slack").props.onClick();
  await new Promise(setImmediate);
  assert.equal(view.calls.length, 0);
  ui.nodes.find((node) => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  ui = view.render(event);
  assert.equal(ui.button("Retry slack").props.disabled, false);
  ui.button("Retry slack").props.onClick();
  await new Promise(setImmediate);
  assert.deepEqual(view.calls[0], ["retry", "event", "slack"]);
  ui = view.render(event);
  assert.match(ui.text, /fresh slack check is queued/);
  assert.equal(ui.button("Retry slack").props.disabled, true);
  assert.equal(renderChannel().render({ ...event, resolved: true }).nodes.length, 0);
});

test("a stale uncertain retry surfaces the server rejection without claiming it was queued", async () => {
  const event = { id: "event", resolved: false, uncertain_channels: ["slack"] };
  const view = renderChannel(channel, { failRetry: true });
  let ui = view.render(event);
  ui.nodes.find((node) => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  view.render(event).button("Retry slack").props.onClick();
  await new Promise(setImmediate);
  ui = view.render(event);
  assert.match(ui.text, /Destination changed/);
  assert.doesNotMatch(ui.text, /fresh slack check is queued/);
});
