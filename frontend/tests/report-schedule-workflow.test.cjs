const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function compile(relative, extra = "") {
  return ts.transpileModule(fs.readFileSync(path.join(__dirname, relative), "utf8") + extra, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
}
const helpers = {};
vm.runInNewContext(compile("../lib/email-schedule.ts"), { exports: helpers, Error });
const pageCode = compile("../app/(app-shell)/reports/page.tsx", "\nexport { ReportSchedulePanel as TestPanel };");
const saved = { id: 1, report_type: "actions", cadence: "monthly", channel: "email", recipient_email: "saved@merchant.test", enabled: true };
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }

function harness({ demo = false, load = async () => ({ schedules: [saved] }), save = async payload => ({ id: 1, ...payload }) } = {}) {
  let cursor = 0, selectedReport = "actions", updates = 0;
  const slots = new Map(), effects = [], calls = [], notices = [];
  const jsx = (type, props) => ({ type, props });
  const exports = {};
  const dependencies = {
    "react/jsx-runtime": { jsx, jsxs: jsx },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, initial); return [slots.get(key), value => { updates++; slots.set(key, typeof value === "function" ? value(slots.get(key)) : value); }]; },
      useRef(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, { current: initial }); return slots.get(key); },
      useEffect(callback, deps) {
        const key = cursor++, previous = slots.get(key);
        if (!previous || deps.some((value, index) => value !== previous.deps[index])) {
          const next = { deps, cleanup: previous?.cleanup };
          slots.set(key, next);
          effects.push(() => { next.cleanup?.(); next.cleanup = callback(); });
        }
      },
    },
    "next/link": { __esModule: true, default: "a" },
    "@/components/auth-guard": { useAuth: () => ({ user: { id: demo ? 0 : 1, email: "owner@merchant.test" } }) },
    "@/lib/api-v2": {
      fetchReportSchedules: async signal => { calls.push(["load", signal]); return load(signal); },
      saveReportSchedule: async (payload, signal) => { calls.push(["save", payload, signal]); return save(payload, signal); },
    },
    "@/lib/email-schedule": helpers,
    "@/components/reports/report-components": { ReportStatusBadge: "badge" },
    "@/components/scheduled-email-status": { ScheduledEmailStatus: "delivery-status" },
  };
  vm.runInNewContext(pageCode, { exports, Error, AbortController, Number, Array, Date,
    require: name => dependencies[name] || {},
  });
  function render(report = selectedReport) {
    selectedReport = report; cursor = 0;
    const tree = exports.TestPanel({ selectedReport, onSaved: value => notices.push(value) });
    const nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string") { texts.push(node); return; }
      if (!node || typeof node !== "object") return;
      nodes.push(node); walk(node.props?.children);
    }
    walk(tree);
    while (effects.length) effects.shift()();
    return { nodes, text: texts.join(" "), button: text => nodes.find(node => node.type === "button" && node.props.children === text) };
  }
  async function settle(report = selectedReport) { for (let i = 0; i < 4; i++) { render(report); await new Promise(setImmediate); } return render(report); }
  return { render, settle, calls, notices, updateCount: () => updates,
    unmount() { for (const slot of slots.values()) if (slot && typeof slot === "object" && "cleanup" in slot) slot.cleanup?.(); },
  };
}

test("a failed settings read blocks writes and retry restores the actual saved destination", async () => {
  let attempts = 0;
  const h = harness({ load: async () => { if (++attempts === 1) throw new Error("Schedule service unavailable"); return { schedules: [saved] }; } });
  assert.equal(h.render().button("Save schedule"), undefined);
  let ui = await h.settle();
  assert.match(ui.text, /Schedule service unavailable/);
  assert.equal(ui.button("Save schedule"), undefined);
  assert.equal(h.calls.some(call => call[0] === "save"), false);
  ui.button("Retry schedule settings").props.onClick();
  ui = await h.settle();
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.type === "email").props.value, saved.recipient_email);
  assert.equal(ui.nodes.find(node => node.type === "select").props.value, "monthly");
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.type === "checkbox").props.checked, true);
});

test("malformed settings cannot default into an editable enabled schedule", async () => {
  const h = harness({ load: async () => ({ schedules: [{ ...saved, cadence: "unexpected" }] }) });
  const ui = await h.settle();
  assert.match(ui.text, /settings are incomplete/);
  assert.equal(ui.button("Save schedule"), undefined);
});

test("demo scheduling is informational and performs no API calls", async () => {
  const h = harness({ demo: true });
  const ui = await h.settle();
  assert.match(ui.text, /No schedule is saved and no report emails are sent/);
  assert.equal(ui.button("Save schedule"), undefined);
  assert.equal(h.calls.length, 0);
});

test("new schedules default paused and success requires the server to confirm the requested values", async () => {
  const h = harness({ load: async () => ({ schedules: [] }) });
  let ui = await h.settle();
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.type === "checkbox").props.checked, false);
  ui.button("Save schedule").props.onClick();
  ui = await h.settle();
  assert.equal(h.calls.find(call => call[0] === "save")[1].enabled, false);
  assert.equal(h.notices.length, 1);
  assert.match(ui.text, /Schedule saved paused/);
  const wrong = harness({ save: async payload => ({ ...saved, ...payload, recipient_email: "different@merchant.test" }) });
  (await wrong.settle()).button("Save schedule").props.onClick();
  const error = await wrong.settle();
  assert.match(error.text, /server did not confirm/);
  assert.equal(wrong.notices.length, 0);
});

test("a response for the previous report cannot claim the newly selected report was saved", async () => {
  const pending = deferred();
  const h = harness({ save: () => pending.promise });
  (await h.settle()).button("Save schedule").props.onClick();
  await h.settle("stockout");
  pending.resolve(saved);
  const ui = await h.settle();
  assert.equal(h.notices[0].report_type, "actions");
  assert.doesNotMatch(ui.text, /Schedule enabled/);
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.type === "email").props.value, "owner@merchant.test");
  assert.equal(ui.nodes.find(node => node.type === "input" && node.props.type === "checkbox").props.checked, false);
});

test("an obsolete settings response does not update state after navigation", async () => {
  const pending = deferred();
  const h = harness({ load: () => pending.promise });
  h.render(); h.unmount();
  const before = h.updateCount();
  pending.resolve({ schedules: [saved] });
  await new Promise(setImmediate);
  assert.equal(h.updateCount(), before);
  assert.equal(h.calls[0][1].aborted, true);
});
