# Inventory health check organic experiment

Enroll this experiment **after the deployed tool and telemetry have been verified**. This document does not enroll it or authorize a send. Use the existing experiment row if `inventory-health-check-v1` already exists; preserve its start, original specification and evidence.

Set `started_at` to the actual verified enrollment time and `stop_at` to 28 days later. The experiment is observational: it tests demand for one useful tool, not a causal comparison against the reorder calculator. A stop date closes this experiment's review window, not the persistent growth mission.

Exact initial enrollment fields:

```json
{
  "key": "inventory-health-check-v1",
  "status": "active",
  "specification": {
    "hypothesis": "A free browser-based SKU inventory diagnostic generates qualified health-check requests and connected Shopify stores without requiring app installation.",
    "channel": "organic_search",
    "landing_page": "/tools/inventory-health-check",
    "target_customer": "Shopify owner/operators with physical inventory who can supply a SKU sales and stock summary and need to review reorder triggers or excess inventory.",
    "message_positioning": "Review stockout risk, reorder triggers and above-target stock from your own summary; no account or app installation required.",
    "action": "Publish one useful browser-only inventory health tool with a concise invitation to request a Skubase Inventory Health Check.",
    "primary_metric": "distinct connected stores attributed to inventory-health-check-v1",
    "secondary_metrics": ["health-check requests", "unique tool users", "signup", "activation", "payment"],
    "cost": {"advertising_usd": 0, "model_api_usd": 0, "owner_attention_minutes": null},
    "stop_condition": "Review after 28 days; investigate downstream friction before expanding promotion when qualified intent fails to progress.",
    "success_condition": "At least one attributable connected store; tool uses alone do not establish success.",
    "variables_changed": ["new useful tool"],
    "max_contacts": 0
  }
}
```

Use `utm_campaign=inventory-health-check-v1`, `utm_source=free_tool` and `utm_medium=organic` on this tool's health-check handoff. Retain the campaign through the existing request form. The shared rolling 20-first-contact ceiling continues to govern separate merchant outreach; `max_contacts: 0` here describes this page experiment, not an outbound allowance.

The browser emits the existing `CALCULATOR_USED` event for a real diagnostic run. Its historical result field remains `calculator_users` for compatibility. Sample runs must not emit that event. Neither tool use nor a sample output counts as activation, store connection or payment. The submitted summary stays in the browser; growth telemetry contains the event, page and attribution rather than inventory rows. Tracking exclusions such as demo sessions and Do Not Track continue to apply.

Evaluation rules:

- An explicit event campaign must match the experiment key. A different campaign cannot enter this experiment through its page path.
- Without an explicit campaign, a tool-use event can match the experiment's configured `landing_page`. Paths must be local, at most 200 characters, and contain only ordinary path segments; no host, query, fragment, traversal or encoded segments. Trailing slashes are normalized.
- Existing experiments with no `landing_page` retain `/tools/reorder-point-calculator` as the legacy fallback. An explicitly invalid new field disables page-based attribution rather than borrowing the fallback; `landing_page_config_valid` is false in the result. Explicit campaign attribution remains available.
- Unique visitor identities are counted once per experiment. Pre-enrollment events remain in history but do not enter its sample. Health-check requests and store connections retain their existing separate identity-linkage requirements. Page matching alone never attributes a store connection.
- An acquired store requires this campaign's request, a verified account link, and the store's first-ever verified connection strictly later than the request. Earlier or tied connections and reconnects are reported as baseline stores; static attribution memory alone cannot establish acquisition. Missing identity links are reported separately. This ordered association is still not proof that the tool caused the conversion.

The original reorder-calculator cohort is retained unchanged. Do not combine samples or call either tool a winner based on a handful of uses. Preserve failed and inconclusive outcomes, and review the request-to-connection path before increasing promotion.
