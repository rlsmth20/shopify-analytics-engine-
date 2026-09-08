const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
function load(file, dependencies = {}, globals = {}) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, Error, Number, Date, Map, Set, JSON, Promise, AbortController, setTimeout, clearTimeout, ...globals,
    require(name) { assert.ok(name in dependencies, `Unexpected import ${name}`); return dependencies[name]; } });
  return exports;
}
const helper = load("lib/inventory-chat.ts");
const response = (overrides = {}) => ({ answer: "1. Review **A100**\n2. Confirm supplier lead time", mode: "ai", model: "gpt-5.6-luna", data_source: "db", context_summary: "2 products", related_links: [{ label: "Actions", href: "/actions" }], ...overrides });
const ok = value => ({ ok: true, status: 200, json: async () => value });
const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };

function harness(fetcher, initialUser = { id: 4, shop_id: 8 }, fakeTimers) {
  let cursor = 0, user = initialUser;
  const slots = new Map(), effects = [], calls = [];
  const jsx = (type, props) => ({ type, props });
  const page = load("components/ask-skubase-chat.tsx", {
    "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "fragment" },
    react: {
      useState(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, typeof initial === "function" ? initial() : initial); return [slots.get(key), next => slots.set(key, typeof next === "function" ? next(slots.get(key)) : next)]; },
      useRef(initial) { const key = cursor++; if (!slots.has(key)) slots.set(key, { current: initial }); return slots.get(key); },
      useEffect(callback, dependencies) { const key = cursor++, old = slots.get(key); if (!old || dependencies.some((value, index) => value !== old.dependencies[index])) {
        const value = { dependencies, cleanup: old?.cleanup }; slots.set(key, value); effects.push(() => { value.cleanup?.(); value.cleanup = callback(); });
      } },
    },
    "next/link": { default: "a" },
    "@/components/auth-guard": { useAuth: () => ({ user }) },
    "@/lib/api-base": { API_BASE_URL: "https://private.example" },
    "@/lib/inventory-chat": helper,
    "@/lib/shopify-embedded": { authenticatedFetch: async (url, options) => { calls.push({ url, ...options }); return fetcher(options, calls.length); } },
  }, fakeTimers || {});
  function render() {
    cursor = 0;
    const nodes = [], texts = [];
    function walk(node) {
      if (Array.isArray(node)) return node.forEach(walk);
      if (typeof node === "string" || typeof node === "number") { texts.push(String(node)); return; }
      if (!node || typeof node !== "object") return;
      if (typeof node.type === "function") return walk(node.type(node.props));
      nodes.push(node); walk(node.props?.children);
    }
    walk(page.AskSkubaseChat());
    while (effects.length) effects.shift()();
    const text = node => { const result = []; const read = n => { if (Array.isArray(n)) n.forEach(read); else if (typeof n === "string") result.push(n); else if (n && typeof n === "object") read(n.props?.children); }; read(node); return result.join(" "); };
    return { nodes, text: texts.join(" "), button: label => nodes.find(node => node.type === "button" && text(node) === label), find: type => nodes.find(node => node.type === type), users: nodes.filter(node => node.type === "article" && node.props.className === "ask-message ask-message-user") };
  }
  function open() { render(); render().button("Ask Skubase").props.onClick(); return render(); }
  function ask(question) { render().find("textarea").props.onChange({ target: { value: question } }); render().find("form").props.onSubmit({ preventDefault() {} }); }
  return { render, open, ask, calls, switchUser(next) { user = next; return render(); } };
}

test("reply parsing labels actual models, preserves old local contracts and filters unsafe related links", () => {
  assert.equal(helper.chatReplyLabel(helper.parseChatReply(response())), "Luna");
  const local = helper.parseChatReply(response({ mode: "local", model: "gpt-5.6-luna", fallback_reason: "missing_api_key" }));
  assert.equal(local.model, null);
  assert.match(helper.chatFallbackExplanation(local), /not enabled/);
  assert.equal(helper.chatReplyLabel(local), "Local inventory summary");
  assert.equal(helper.chatReplyLabel(helper.parseChatReply(response({ model: undefined }))), "Model reply · model not reported");
  const links = helper.parseChatReply(response({ related_links: [
    { label: "Bad", href: "https://example.com" }, { label: "Bad", href: "//evil.test" },
    { label: "Bad", href: "/\\evil.test" }, { label: "Bad", href: "/\nevil.test" },
    { label: "Actions", href: "/actions" }, { label: "Duplicate", href: "/actions" },
  ] })).related_links;
  assert.equal(JSON.stringify(links), JSON.stringify([{ label: "Actions", href: "/actions" }]));
  assert.throws(() => helper.parseChatReply(response({ answer: " " })), /Invalid/);
  const history = helper.chatRequestMessages([{ id: "welcome", role: "assistant", content: "Welcome" }, ...Array.from({ length: 12 }, (_, id) => ({ id: String(id), role: "user", content: "a".repeat(2100), status: id === 11 ? "sending" : undefined, sample: true }))]);
  assert.equal(history.length, 10);
  assert.equal(history[0].content.length, 2000);
  assert.equal(Object.keys(history[0]).join(","), "role,content");
});

test("actual chat retries one failed question without duplicate bubbles and keeps mode on each reply", async () => {
  const chat = harness(async (_, attempt) => attempt === 1 ? { ok: false, status: 503 } : ok(response(attempt === 3 ? { mode: "local", model: null, fallback_reason: "global_budget_exhausted" } : {})));
  chat.open(); chat.ask("Which item first?"); await flush();
  let view = chat.render();
  assert.equal(view.users.length, 1); assert.match(view.text, /could not answer/); assert.doesNotMatch(view.text, /private.example/);
  view.button("Retry question").props.onClick(); await flush(); view = chat.render();
  assert.equal(view.users.length, 1); assert.match(view.text, /Skubase · Luna/);
  assert.equal(chat.calls[0].body, chat.calls[1].body);
  assert.ok(view.nodes.some(node => node.type === "ol")); assert.ok(view.nodes.some(node => node.type === "strong"));
  chat.ask("What else?"); await flush(); view = chat.render();
  assert.equal(view.users.length, 2); assert.match(view.text, /Skubase · Luna/); assert.match(view.text, /Skubase · Local inventory summary/);
  assert.match(view.text, /Model usage is currently limited/); assert.equal(chat.calls.length, 3);
});

test("editing a failed question replaces the pending bubble and excludes its old content from request history", async () => {
  const chat = harness(async (_, attempt) => attempt === 1 ? { ok: false, status: 422 } : ok(response()));
  chat.open(); chat.ask("Old question"); await flush();
  chat.render().button("Edit question").props.onClick(); chat.ask("Short question"); await flush();
  assert.equal(chat.render().users.length, 1);
  assert.doesNotMatch(chat.render().text, /Old question/);
  assert.equal(JSON.parse(chat.calls[1].body).messages[0].content, "Short question");
});

test("workspace switches abort and hide old messages immediately and ignore late tenant responses", async () => {
  let resolve;
  const chat = harness((_, attempt) => attempt === 1 ? new Promise(done => { resolve = done; }) : Promise.resolve(ok(response({ answer: "New store result" }))));
  chat.open(); chat.ask("Private old store question");
  const first = chat.switchUser({ id: 5, shop_id: 9 });
  assert.doesNotMatch(first.text, /Private old store question/);
  assert.equal(chat.calls[0].signal.aborted, true);
  resolve(ok(response({ answer: "Private old store result" }))); await flush();
  chat.open(); chat.ask("New question"); await flush();
  assert.doesNotMatch(chat.render().text, /Private old/);
  assert.match(chat.render().text, /New store result/);
  assert.deepEqual(JSON.parse(chat.calls[1].body).messages, [{ role: "user", content: "New question" }]);
});

test("timeout also bounds response-body parsing and requires a manual retry", async () => {
  let expire;
  const chat = harness(async () => ({ ok: true, json: () => new Promise(() => {}) }), undefined,
    { setTimeout(callback, duration) { assert.equal(duration, 30000); expire = callback; return 1; }, clearTimeout() {} });
  chat.open(); chat.ask("Question"); await flush();
  assert.equal(chat.render().find("textarea").props.disabled, true);
  expire(); await flush();
  assert.equal(chat.calls[0].signal.aborted, true);
  assert.match(chat.render().text, /took too long/);
  assert.equal(chat.render().find("textarea").props.disabled, false);
  assert.equal(chat.calls.length, 1);
});

test("double submission sends once, malformed replies stay retryable, and demo performs no request", async () => {
  const chat = harness(async () => ok(response({ answer: "" })));
  chat.open(); chat.render().find("textarea").props.onChange({ target: { value: "Question" } });
  const form = chat.render().find("form");
  form.props.onSubmit({ preventDefault() {} }); form.props.onSubmit({ preventDefault() {} }); await flush();
  assert.equal(chat.calls.length, 1); assert.equal(chat.render().users.length, 1);
  assert.ok(chat.render().button("Retry question"));
  const demo = harness(async () => { throw new Error("Demo must not call API"); }, { id: 0, shop_id: 0 });
  demo.open(); demo.ask("Question"); await flush();
  assert.equal(demo.calls.length, 0); assert.match(demo.render().text, /Sample workspace/);
  assert.match(demo.render().text, /not yet listed/); assert.doesNotMatch(demo.render().text, /Skubase · Luna/);
});
