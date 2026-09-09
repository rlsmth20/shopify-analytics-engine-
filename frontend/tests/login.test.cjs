const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const output = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/login.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: output });

test('login email destinations preserve imports and reject external redirects', () => {
  for (const route of ['/dashboard', '/import-stocky', '/import-shipstation']) {
    assert.equal(output.loginDestination(route), route);
  }
  for (const route of [null, undefined, '//evil.example', '/\\evil.example', 'https://evil.example', '/%2f%2fevil.example']) {
    assert.equal(output.loginDestination(route), null);
  }
});

test('validation and provider errors always render text instead of crashing React', () => {
  assert.equal(output.loginError({ detail: [{ loc: ['body', 'email'], msg: 'Invalid email' }] }), 'Check your email address and try again.');
  assert.equal(output.loginError({ detail: { code: 'email_delivery_failed', message: 'Please retry.' } }), 'Please retry.');
  for (const body of [null, {}, { detail: {} }, { detail: 12 }]) assert.equal(typeof output.loginError(body), 'string');
});
