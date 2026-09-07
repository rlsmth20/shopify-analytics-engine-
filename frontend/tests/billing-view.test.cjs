const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const output = {};
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/billing-view.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(compiled, { exports: output });
const { getStripePortalAction } = output;
const stripe = { billing_provider: "stripe", is_shopify_installed: false, stripe_configured: true };

test("legacy merchants with overdue or unpaid subscriptions can update payment in their existing portal", () => {
  for (const subscription_status of ["past_due", "unpaid"]) {
    assert.equal(getStripePortalAction({ ...stripe, subscription_status }), "update_payment");
  }
  for (const subscription_status of ["active", "trialing"]) {
    assert.equal(getStripePortalAction({ ...stripe, subscription_status }), "manage");
  }
});

test("Shopify billing wins even if stale Stripe status and configuration remain in a response", () => {
  for (const subscription_status of ["active", "trialing", "past_due", "unpaid"]) {
    assert.equal(getStripePortalAction({ ...stripe, subscription_status, is_shopify_installed: true }), null);
    assert.equal(getStripePortalAction({ ...stripe, subscription_status, billing_provider: "shopify_managed_pricing" }), null);
  }
});

test("non-Stripe accounts, terminal subscriptions and unavailable Stripe billing do not get a recovery action", () => {
  for (const subscription_status of ["inactive", "canceled", "incomplete_expired", "unknown", ""]) {
    assert.equal(getStripePortalAction({ ...stripe, subscription_status }), null);
  }
  assert.equal(getStripePortalAction({ ...stripe, subscription_status: "trialing", billing_provider: "none" }), null);
  assert.equal(getStripePortalAction({ ...stripe, subscription_status: "past_due", stripe_configured: false }), null);
  assert.equal(getStripePortalAction({ ...stripe, subscription_status: "past_due", stripe_configured: undefined }), null);
});
