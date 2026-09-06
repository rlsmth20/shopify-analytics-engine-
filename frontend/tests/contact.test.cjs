const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const output = {};
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/contact.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(compiled, { exports: output });
const { contactResponseError, isShopifyIdentityEmail } = output;

test("embedded Shopify identities are not treated as reply inboxes", () => {
  for (const email of [
    "shopify-admin+42@fixture.myshopify.com",
    "shopify-owner@fixture.myshopify.com",
    " Shopify-Admin+42@fixture.myshopify.com ",
  ]) assert.equal(isShopifyIdentityEmail(email), true);
  for (const email of ["buyer@example.com", "buyer+shopify@example.com", "shopify-admin+42@example.com"]) {
    assert.equal(isShopifyIdentityEmail(email), false);
  }
});

test("success requires an explicit acknowledgement as well as successful HTTP status", () => {
  assert.equal(contactResponseError(true, { ok: true }), null);
  for (const body of [null, {}, { ok: false }, { ok: "true" }]) {
    assert.match(contactResponseError(true, body), /couldn't confirm/);
  }
  assert.match(contactResponseError(false, { ok: true }), /couldn't confirm/);
});

test("delivery and validation failures produce readable errors", () => {
  const detail = "We couldn't send your message. Please email hello@skubase.io directly.";
  assert.equal(contactResponseError(false, { detail }), detail);
  assert.equal(
    contactResponseError(false, { detail: [{ loc: ["body", "email"], msg: "Invalid email" }] }),
    "Check your name, reply email, and message, then try again.",
  );
});
