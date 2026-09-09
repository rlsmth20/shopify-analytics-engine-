const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');
const compile = file => ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const user = { id: 1, shop_id: 10, email: 'fixture@example.com', is_admin: false, in_trial: true, trial_ends_at: null };
const response = (status, body) => ({ ok: status === 200, status, json: async () => body });

function harness(reply) {
  const states = new Map(), effects = [], listeners = new Map(), redirects = [], calls = [];
  let cursor = 0, changed = 0;
  const jsx = (type, props, key) => ({ type, props, key });
  const modules = {
    'react/jsx-runtime': { jsx, jsxs: jsx },
    react: {
      createContext: () => ({ Provider: 'provider' }), useContext: () => null,
      useState(initial) { const i = cursor++; if (!states.has(i)) states.set(i, initial); return [states.get(i), v => states.set(i, typeof v === 'function' ? v(states.get(i)) : v)]; },
      useRef(initial) { const i = cursor++; if (!states.has(i)) states.set(i, { current: initial }); return states.get(i); },
      useEffect(fn, deps) { const i = cursor++, prior = states.get(i); if (!prior || deps.some((d, j) => d !== prior.deps[j])) { const next = { deps, cleanup: prior?.cleanup }; states.set(i, next); effects.push(() => { next.cleanup?.(); next.cleanup = fn(); }); } },
    },
    'next/navigation': { useRouter: () => router },
    '@/lib/api-base': { API_BASE_URL: 'https://fixture.test' },
    '@/lib/entitlements': { invalidateEntitlementsCache() {} },
    '@/lib/browser-session': { SESSION_CHANGED_KEY: 'session', announceSessionChange() { changed++; } },
    '@/lib/shopify-embedded': { getEmbeddedShopifyContext: () => null, authenticatedFetch: async (url, init) => { calls.push({ url, init }); return reply(url); } },
  };
  const router = { replace: url => redirects.push(url) };
  const exports = {};
  vm.runInNewContext(compile('../components/auth-guard.tsx'), { exports, require: id => modules[id], URLSearchParams, AbortController, AbortSignal,
    sessionStorage: { getItem: () => null, removeItem() {} },
    window: { location: { search: '' }, addEventListener: (key, fn) => listeners.set(key, fn), removeEventListener: key => listeners.delete(key) },
  });
  function render() { cursor = 0; const tree = exports.AuthGuard({ children: 'workspace' }); while (effects.length) effects.shift()(); return tree; }
  async function settle() { for (let i = 0; i < 4; i++) { render(); await new Promise(setImmediate); } return render(); }
  return { render, settle, redirects, listeners, calls, get changed() { return changed; } };
}

test('server/network failures offer retry without pretending the customer signed out', async () => {
  for (const fn of [() => response(503, {}), () => { throw new Error('offline'); }, () => response(200, {})]) {
    const f = harness(fn);
    const tree = await f.settle();
    assert.deepEqual(f.redirects, []);
    assert.match(JSON.stringify(tree), /Try again/);
  }
  const f = harness(() => response(401, {}));
  await f.settle();
  assert.ok(f.redirects.includes('/login'));
});

test('failed logout cannot claim the session was revoked', async () => {
  const f = harness(url => response(url.endsWith('/logout') ? 503 : 200, user));
  const tree = await f.settle();
  await tree.props.value.logout();
  assert.deepEqual(f.redirects, []);
  assert.equal(f.changed, 0);
  assert.match(JSON.stringify(f.render()), /Sign-out couldn't be confirmed/);
});

test('cross-tab session changes and browser restoration recheck identity', async () => {
  let current = user;
  const f = harness(() => response(200, current));
  const before = await f.settle();
  current = { ...user, id: 2, shop_id: 20 };
  f.listeners.get('storage')({ key: 'session' });
  const after = await f.settle();
  assert.notEqual(before.key, after.key);
  assert.equal(after.props.value.user.shop_id, 20);
  const count = f.calls.length;
  f.listeners.get('pageshow')({ persisted: true });
  await f.settle();
  assert.ok(f.calls.length > count);
});

test('malformed checklist preferences and workspace identities stay isolated', () => {
  const exports = {};
  vm.runInNewContext(compile('../lib/browser-session.ts'), { exports });
  for (const value of ['null', '[]', 'true', '{broken']) assert.equal(Object.keys(exports.readChecklist(value)).length, 0);
  assert.equal(exports.readChecklist('{"done":true,"notdone":"yes"}').done, true);
  assert.equal(exports.readChecklist('{"done":true,"notdone":"yes"}').notdone, undefined);
  assert.notEqual(exports.workspaceStorageKey('steps', user), exports.workspaceStorageKey('steps', { ...user, shop_id: 20 }));
  assert.doesNotThrow(() => exports.announceSessionChange());
});
