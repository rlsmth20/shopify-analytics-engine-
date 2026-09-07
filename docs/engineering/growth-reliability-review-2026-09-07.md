# Growth reliability review — September 7, 2026

Deployment update: commit `0c4843c` is now live. Railway deployment `9fd59128-d455-4e22-8161-150556746ec7` succeeded; Vercel deployment `dpl_CQQfPwtexPTV3EQe6kLgPvVoC3jH` is ready and aliased to `www.skubase.io`. Public page and API health checks returned 200. Retained deployment evidence is `5082`; requested-service skill version 2 was activated through the audited revision workflow. The worker remained running with 13 of 20 first-contact slots used and no unresolved reservations at verification. The report below describes the original development pass; the separate billing fix is covered in `stripe-webhook-reliability-2026-09-07.md`.

This development pass fixes observed failures in local isolated fixtures. It did not send merchant messages, spend on advertising/APIs, alter the rolling 20-contact ceiling, or deploy to production. Simulated responses and payments are not campaign evidence.

## Changes and evidence

| Failure reproduced | Resulting behavior | Regression coverage |
| --- | --- | --- |
| A signed bounce/complaint arrives before the provider receipt is saved; the contact remains eligible. | Webhook ingestion and receipt persistence share the dispatch lock and reconcile retained signed events. Later delivery/duplicate events cannot undo suppression. Missing provider IDs cannot match unsent drafts. | `backend/tests/test_growth_delivery.py`: early delivery/bounce/complaint, missing IDs, duplicate and out-of-order events. |
| “I don't want a health check. Please leave us alone.” is classified positively and triggers another assistance email. | Explicit opt-outs and declines take precedence over positive keywords. The complete simulated response loop sends no further message. | `backend/tests/test_growth_delivery.py`: classification and requested-service dispatch regression. |
| A form contact created after the forward-only signup cursor never acquires the known account's shop ID. | A bounded server-side email join links eligible accounts and late contacts, with an idempotent identity record; claimed store URLs grant no authority. | `backend/tests/test_growth_attribution.py`: same-batch and late requests, old unmatched contacts, excluded accounts. |
| A campaign-tagged landing followed by an untagged internal health-check form drops campaign attribution. | The form and event tracker share validated 30-day attribution. Explicit new campaign fields replace old fields. Only bounded UTM fields enter the form; DNT/demo and malformed storage are handled. | `frontend/tests/growth-attribution.test.cjs`: actual form submission, expiry, malformed/blocked storage, campaign changes, privacy. |
| Enrollment reaching its limit marks a fresh cohort inconclusive immediately and removes it from ordinary observation. Delayed send-specific evaluations existed but the cohort lifecycle was misleading. | Enrollment closes separately from observation. `observing` cohorts stay in periodic/executive evaluation across restarts until sent messages mature; unknown sends remain unresolved. New cohorts retain current allocation without premature learning. | `backend/tests/test_growth_learning.py`: full cohort, enrollment deadline, restart/periodic wake, uncertain send. |
| Two contacts for the same shop satisfy a two-store success condition. | Qualified-store outcomes count distinct shop IDs across both message arms. | `backend/tests/test_growth_learning.py`: two contacts, one store, no false win. |
| Deterministic requested-service templates still introduce an automated assistant and omit the owner's review-status notice. | New drafts identify Skubase, preserve narrow requested-service scope and include the Shopify App Store review notice. | Existing full simulated growth loop checks the initial and assistance messages. |

## Validation

- Full backend suite: **99 tests passed**.
- Full frontend test suite: **30 tests passed**.
- Frontend TypeScript check and production build passed.
- No product database migration or frontend/backend contract change is required.
- Provider ordering is exercised through signed synthetic webhooks and isolated database fixtures; this is not a live-mail delivery test or a PostgreSQL load test.

## Rollout notes

Use the normal reviewed deployment workflow. Existing authorized message bodies and historical messages remain unchanged; changing a permitted body invalidates its recorded hash. For an existing installation, the requested-service skill seed also needs a versioned proposal/activation using the retained owner instructions and validation evidence; bootstrap intentionally does not overwrite an active skill revision.

An uncertain send whose provider receipt was never recovered remains blocked. Retained unmatched delivery events do not justify guessing the recipient or retrying the send. Review the signed event and provider receipt through the existing reconciliation workflow.

## Separate billing follow-up

`backend/app/api/routes/billing.py:162` catches verified Stripe handler exceptions and still returns HTTP 200. A transient database or growth-projection failure can therefore lose a payment/cancellation notification. This pass leaves billing behavior unchanged. A billing-focused patch should acknowledge successful persistence only, verify replay safety after the subscription handler's own commit, and cover duplicate/out-of-order events before rollout. Subscription/payment attribution remains observational; do not infer that a campaign caused an existing account's payment from an email identity match alone.
