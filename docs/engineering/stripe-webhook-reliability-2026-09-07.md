# Stripe webhook persistence and replay

Verified Stripe deliveries previously returned HTTP 200 even when a subscription write or growth projection failed. The endpoint now rolls back unfinished work, logs the failure and returns HTTP 503. Successful persistence still returns the existing `{ "received": true }` response; invalid signatures still return HTTP 400.

The subscription handler retains its existing transaction boundary. A growth projection failure can therefore occur after the subscription commit. Replaying the delivery safely finishes the projection: payment evidence is unique by invoice, cancellation evidence by subscription, and payment wakes by invoice. Receipt keys written by the previous cancellation handler remain recognized for the same event.

## State and ordering

- Checkout associates a subscription. Replayed checkout cannot reactivate an already cancelled subscription or replace Shopify billing.
- Cancellation is terminal for a subscription ID. Events for an old subscription cannot overwrite a replacement through the shared customer ID.
- Mutable subscription snapshots use current provider state, because event timestamps are not a total order. A new or replacement checkout also verifies the referenced subscription before applying it.
- Those cases add one read-only Stripe subscription request, with a 10-second HTTP timeout and zero SDK retries. Synchronous persistence and provider reads run in the existing thread pool so the API event loop remains responsive. An unavailable or inconsistent response returns HTTP 503. Straightforward invoice deliveries, duplicate invoices and terminal cancellations require no provider lookup.
- Conflicting active subscription associations return HTTP 503 and leave the existing association intact. They require account reconciliation; the handler does not guess which active contract should win.
- Historical subscription invoices remain payment evidence but cannot change the replacement contract's MRR or status. Standalone invoices and test-mode invoices do not become subscription-purchase evidence.
- A payment cannot reactivate cancelled economics. Earlier billing periods cannot replace a later observed price; conflicting same-period prices remain unknown. Missing recurring-price details also remain unknown.

This follows Stripe's guidance on [delivery retries, ordering and duplicate events](https://docs.stripe.com/webhooks#event-delivery-behaviors). The provider retry window is finite, so repeated HTTP 503 responses need investigation.

## Verification

`python -m unittest discover -s tests -p test_billing_webhook.py -q` passed **24 tests** against real SDK signatures and isolated transactional SQLite storage. Coverage includes failed writes and commits, replay after the subscription commit, duplicate provider events for one invoice, same-timestamp and out-of-order events, replacement and Shopify boundaries, standalone/test invoices, stale billing periods, unknown prices and execution outside the API event loop.

All provider lookups are mocked. No Stripe API request, financial transaction, production write, credential change or schema migration was performed by this development pass. PostgreSQL row-lock behavior is used by the implementation but was not load-tested here.

## Rollout limits

Deploy through the existing backend workflow and inspect webhook HTTP 503 logs after rollout. Existing authenticated reconciliation remains available. Events already acknowledged successfully by the old handler will not automatically be resent; recovery requires reviewing the provider's retained event history and using its normal resend process when applicable.

The patch does not introduce a provider-event inbox or reconstruct missing account associations. Events for customers with no local subscription mapping remain ignored as before. Attribution remains observational: a known account's payment is not proof that an outreach campaign caused it.
