const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

function load(file, require) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, { exports, require, Headers, URL, URLSearchParams });
  return exports;
}

test('Shopify root launches reach dashboard before hydration with launch parameters intact', () => {
  const middleware = load('middleware.ts', id => {
    assert.equal(id, 'next/server');
    return { NextResponse: {
      redirect: url => ({ url, headers: new Headers(), kind: 'redirect' }),
      next: options => ({ ...options, kind: 'next' }),
    } };
  }).middleware;
  const request = value => {
    const nextUrl = new URL(value);
    nextUrl.clone = () => new URL(nextUrl);
    return { nextUrl, headers: new Headers({ 'x-skubase-embedded': '1' }) };
  };
  for (const query of ['embedded=1&shop=fixture.myshopify.com&host=opaque&hmac=signature', 'shop=fixture.myshopify.com&host=opaque']) {
    const result = middleware(request(`https://app.test/?${query}`));
    assert.equal(result.kind, 'redirect');
    assert.equal(result.url.pathname, '/dashboard');
    assert.equal(result.url.searchParams.get('embedded'), '1');
    for (const [key, value] of new URLSearchParams(query)) assert.equal(result.url.searchParams.get(key), value);
    assert.equal(result.headers.get('Cache-Control'), 'private, no-store');
  }
  for (const suffix of ['/', '/?shop=fixture.myshopify.com', '/?demo=1']) {
    const result = middleware(request(`https://app.test${suffix}`));
    assert.equal(result.kind, 'next');
    assert.equal(result.request.headers.has('x-skubase-embedded'), false);
  }
  const dashboard = middleware(request('https://app.test/dashboard?embedded=1&shop=fixture.myshopify.com'));
  assert.equal(dashboard.kind, 'next');
  assert.equal(dashboard.request.headers.get('x-skubase-embedded'), '1');
});

test('real dashboard requests never load sample fixtures; demo requests load them only on demand', async () => {
  for (const demo of [false, true]) {
    let fixtureLoads = 0, requests = 0;
    const data = { kpis: [{ label: demo ? 'Sample' : 'Actual' }] };
    const api = load('lib/api-v2.ts', id => {
      if (id === '@/lib/api-base') return { API_BASE_URL: 'https://private.test' };
      if (id === '@/lib/receipt-submission') return {};
      if (id === '@/lib/shopify-embedded') return {
        isDemoActive: () => demo,
        authenticatedFetch: async () => { requests++; return { ok: true, status: 200, json: async () => data }; },
      };
      if (id === '@/lib/demo-fixtures') { fixtureLoads++; return { getDemoFixture: () => data }; }
      throw new Error(`Unexpected import: ${id}`);
    });
    assert.equal(fixtureLoads, 0);
    assert.equal(await api.fetchDashboard(), data);
    assert.equal(fixtureLoads, demo ? 1 : 0);
    assert.equal(requests, demo ? 0 : 1);
  }
});
