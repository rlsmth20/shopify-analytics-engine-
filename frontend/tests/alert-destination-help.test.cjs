const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(path.join(__dirname, "../components/alert-destination-help.tsx"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function harness(channel, clipboard) {
  let state = "";
  const jsx = (type, props) => ({ type, props }), exported = {};
  vm.runInNewContext(code, { exports: exported, navigator: clipboard ? { clipboard } : {}, Error,
    require: name => name === "react" ? { useState: () => [state, value => { state = value; }] } : { jsx, jsxs: jsx },
  });
  function render() {
    const nodes = [], words = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string") { words.push(node); return; }
      if (!node || typeof node !== "object") return;
      nodes.push(node); walk(node.props?.children);
    }
    walk(exported.AlertDestinationHelp({ channel, className: "guide-fixture" }));
    return { nodes, text: words.join(" ") };
  }
  async function copy() {
    render().nodes.find(node => node.type === "button").props.onClick();
    await new Promise(setImmediate);
    return render();
  }
  return { render, copy, sample: exported.WEBHOOK_EXAMPLE_JSON };
}

test("Slack guide selects a merchant workspace/channel and follows save, test, check, enable", () => {
  const ui = harness("slack").render();
  assert.equal(ui.nodes.filter(node => node.type === "li").length, 4);
  assert.match(ui.text, /incoming webhook from your Slack workspace/);
  assert.match(ui.text, /Join a private channel before selecting it/);
  assert.ok(ui.text.indexOf("Save destination") < ui.text.indexOf("Send test"));
  assert.ok(ui.text.indexOf("Check that the Skubase test") < ui.text.indexOf("enable this channel"));
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href === "https://api.slack.com/apps"));
  assert.ok(ui.nodes.some(node => node.type === "a" && node.props.href.startsWith("https://docs.slack.dev/")));
  assert.ok(ui.nodes.filter(node => node.type === "a").every(node => node.props.rel.includes("noopener")));
  assert.equal(ui.nodes.filter(node => node.type === "button").length, 0);
});

test("webhook guide describes the real public HTTPS receiver contract without inventing a destination", () => {
  const h = harness("webhook"), ui = h.render(), payload = JSON.parse(h.sample);
  assert.equal(ui.nodes.filter(node => node.type === "li").length, 4);
  assert.deepEqual(Object.keys(payload).sort(), ["body", "emitted_at", "source", "subject"]);
  assert.equal(payload.source, "skubase");
  assert.ok(Number.isFinite(Date.parse(payload.emitted_at)));
  assert.match(payload.body, /Example only/);
  assert.match(ui.text, /public HTTPS URL on port 443/);
  assert.match(ui.text, /custom authorization headers and request signatures are not configured/);
  assert.match(ui.text, /receiver accepted the request/);
  assert.match(ui.text, /sends a real test to your saved destination/);
  assert.equal(ui.nodes.filter(node => node.type === "a").length, 0);
  const textarea = ui.nodes.find(node => node.type === "textarea");
  assert.equal(textarea.props.readOnly, true);
  assert.ok(ui.nodes.some(node => node.type === "label" && node.props.children.some(child => child === textarea)));
});

test("copy copies only the synthetic envelope and never sends a notification", async () => {
  const values = [], h = harness("webhook", { writeText: async value => { values.push(value); } });
  const ui = await h.copy();
  assert.deepEqual(values, [h.sample]);
  assert.match(ui.text, /Example JSON copied. No notification was sent/);
  assert.ok(ui.nodes.some(node => node.props?.role === "status"));
  assert.equal(ui.nodes.find(node => node.type === "button").props.type, "button");
});

test("missing or denied clipboard keeps a labeled, selectable manual fallback", async () => {
  for (const clipboard of [undefined, { writeText: async () => { throw new Error("Denied"); } }]) {
    const h = harness("webhook", clipboard), ui = await h.copy();
    assert.match(ui.text, /Select the example JSON and copy it manually/);
    assert.equal(ui.nodes.find(node => node.type === "textarea").props.value, h.sample);
    assert.doesNotMatch(ui.text, /Example JSON copied/);
  }
});
