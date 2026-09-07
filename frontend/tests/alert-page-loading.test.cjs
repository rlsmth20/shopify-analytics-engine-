const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const compile = file => ts.transpileModule(readFileSync(path.join(__dirname, file), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const setup = {};
vm.runInNewContext(compile("../lib/alert-setup.ts"), { exports: setup, URL, Error });
const code = compile("../app/(app-shell)/alerts/page.tsx");
const channel = { channel: "email", target: "inventory@merchant.test", enabled: true, verified: true, available: true, configured: true };
const rule = { id: "rule", name: "Reorder risk", trigger: "stockout_risk", enabled: true, channels: ["email"], target_skus: [], categories: [], tags: [], collections: [], locations: [], suppliers: [] };
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

function harness(overrides = {}) {
  let cursor = 0, userId = 1;
  const slots = new Map(), effects = [], calls = [];
  const jsx = (type, props) => ({ type, props });
  const defaults = { rules: async () => ({ rules: [rule] }), channels: async () => ({ channels: [channel], scheduler_enabled: true, evaluation_interval_seconds: 900 }), history: async () => ({ events: [] }) };
  const api = Object.fromEntries([["fetchAlertRules", "rules"], ["fetchChannels", "channels"], ["fetchAlertEvents", "history"]].map(([name, section]) => [name, async signal => {
    calls.push([section, signal]); return (overrides[section] || defaults[section])(signal);
  }]));
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, initial); return [slots.get(key), value => slots.set(key, typeof value === "function" ? value(slots.get(key)) : value)]; },
      useRef(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, { current: initial }); return slots.get(key); },
      useEffect(callback, deps) { const key = cursor++, old = slots.get(key); if (!old || deps.some((value, i) => value !== old.deps[i])) { const next = { deps, cleanup: old?.cleanup }; slots.set(key, next); effects.push(() => { next.cleanup?.(); next.cleanup = callback(); }); } },
    },
    "next/link": { __esModule: true, default: "a" },
    "@/components/auth-guard": { useAuth: () => ({ user: { id: userId, is_admin: true } }) },
    "@/components/data-quality-note": { DataQualityNote: "note" },
    "@/lib/entitlements": {}, "@/lib/api-v2": api, "@/lib/alert-setup": setup,
    "./page.module.css": { __esModule: true, default: {} },
  };
  const exports = {};
  vm.runInNewContext(code, { exports, AbortController, Error, require: name => dependencies[name] || {} });
  function render() {
    cursor = 0; const tree = exports.default(); const nodes = [], text = [];
    function walk(node) { if (Array.isArray(node)) return node.forEach(walk); if (typeof node === "string" || typeof node === "number") { text.push(node); return; } if (!node || typeof node !== "object") return; nodes.push(node); walk(node.props?.children); }
    walk(tree); while (effects.length) effects.shift()();
    return { nodes, text: text.join(" "), panel: name => nodes.find(node => node.type?.name === name), button: label => nodes.find(node => node.type === "button" && JSON.stringify(node.props.children).replace(/[\[\]",]/g, "").trim() === label) };
  }
  async function settle() { for (let i = 0; i < 3; i++) { render(); await new Promise(setImmediate); } return render(); }
  return { render, settle, calls, changeUser(id) { userId = id; }, unmount() { for (const slot of slots.values()) slot?.cleanup?.(); } };
}

test("failed activity cannot hide confirmed channels or report zero configured rules", async () => {
  const h = harness({ history: async () => { throw new Error("History timeout"); } });
  const ui = await h.settle();
  assert.ok(ui.panel("ChannelsPanel"));
  assert.match(ui.text, /1 tested channel enabled/);
  assert.match(ui.text, /Recent activity is unavailable/);
  assert.equal(ui.button("Preview evaluation").props.disabled, false);
  assert.ok(ui.button("Retry recent activity"));
});

test("a slow activity request does not block independently loaded destinations", async () => {
  const pending = deferred(), h = harness({ history: () => pending.promise });
  const ui = await h.settle();
  assert.ok(ui.panel("ChannelsPanel"));
  assert.match(ui.text, /1 tested channel enabled/);
  pending.resolve({ events: [] }); await h.settle();
});

test("failed settings remain unknown and retry loads only the failed section", async () => {
  let attempts = 0;
  const h = harness({ channels: async () => { if (++attempts === 1) throw new Error("Channel timeout"); return { channels: [channel] }; } });
  let ui = await h.settle();
  assert.equal(ui.panel("ChannelsPanel"), undefined);
  assert.match(ui.text, /Setup status unavailable/);
  assert.doesNotMatch(ui.text, /0 tested channels enabled/);
  assert.equal(ui.button("Preview evaluation").props.disabled, true);
  ui.button("Retry channels").props.onClick(); ui = await h.settle();
  assert.ok(ui.panel("ChannelsPanel"));
  assert.equal(h.calls.filter(([section]) => section === "rules").length, 1);
  assert.equal(h.calls.filter(([section]) => section === "history").length, 1);
});

test("malformed saved rules cannot open an editable default rule form", async () => {
  const h = harness({ rules: async () => ({ rules: [{ id: "incomplete" }] }) });
  let ui = await h.settle();
  ui.button("Choose rules").props.onClick(); ui = h.render();
  assert.equal(ui.panel("RulesPanel"), undefined);
  assert.match(ui.text, /Saved rules could not be confirmed/);
  assert.equal(ui.button("Preview evaluation").props.disabled, true);
});

test("late settings from the previous workspace cannot replace current channels", async () => {
  const pending = deferred(); let count = 0;
  const h = harness({ channels: () => ++count === 1 ? pending.promise : Promise.resolve({ channels: [{ ...channel, target: "new@merchant.test" }] }) });
  h.render(); await new Promise(setImmediate); h.changeUser(2);
  let ui = await h.settle();
  assert.equal(ui.panel("ChannelsPanel").props.channels[0].target, "new@merchant.test");
  pending.resolve({ channels: [channel] }); ui = await h.settle();
  assert.equal(ui.panel("ChannelsPanel").props.channels[0].target, "new@merchant.test");
  assert.equal(h.calls.find(([section]) => section === "channels")[1].aborted, true);
  h.unmount();
});
