# Inbox visibility and tested merchant destinations

The growth dashboard now distinguishes a successful business-inbox poll from evidence that Gmail copies reached the agent. Merchants cannot bypass the saved-destination test by replaying a stale settings request. Signup pages explain the available CSV and browser paths while Shopify review is pending.

## Merchant alert destinations

New, changed and paused untested destinations reject an enable request with HTTP 422. Save the destination paused, send a successful test to that exact saved target, then enable it. A stale browser tab cannot enable a replacement or restore a formerly tested target with an enable request. Shop/channel transactions serialize concurrent changes. Unchanged already-enabled legacy destinations remain live; once paused, an untested legacy destination needs a test before it can be enabled again. A transient failed retest does not silently disable an already-live channel.

Tests cover successful activation, withheld automatic delivery before a test, new and replaced targets, stale saves, failed tests, legacy compatibility, tenant separation, route responses and concurrent saves. No live merchant settings were changed. Slack workspace/channel and receiving-webhook service details are still required to configure actual destinations; the implemented guides do not imply those accounts exist or that live notifications arrived.

## Business inbox evidence

The owner sees last check/result, last successful check, latest ingestion count, receipt arrival, first local observation and independent delivery verification. Empty successful checks are normal. Internal test mail is transport evidence and stays out of merchant reply metrics. Old pages do not refresh receipt age, and replayed verification cannot change the historical verification time.

Malformed optional metadata on already-processed provider rows no longer blocks subsequent replies. New malformed messages still fail ingestion visibly. A separate transaction records poll failure without swallowing the original retry classification or erasing prior successful checks and receipts.

The existing Google Workspace dual-delivery configuration was independently verified during activation. Its retained receiving receipts are `42ce49e5-168f-4f16-bb87-bd7442aee329` and `ec78cd75-934c-4a88-89ee-6c29dd6b2865`. The historical verification time is September 7, 2026 at 05:23:06.905 UTC. Deployment records that existing proof; it does not pretend a new live test happened. See [operations and the trusted evidence helper](growth-agent-operations.md#inbox-transport-observability).

## Setup copy and browser checks

The homepage, pricing and Stocky pages state that Skubase is under Shopify review and not listed yet. Sign-in forms accurately describe account/trial behavior. CSV-only stock snapshots, Shopify-owned stock, cost/lead-time enrichment and non-Shopify shipment history are distinguished. Product CSV imports are no longer described as importing sales history or performing receiving.

The owner inbox panel was checked at 390px with no horizontal overflow and distinct check, arrival and verification dates. The pricing notice is readable before the main offer. An isolated merchant webhook was saved paused, tested and enabled through the real UI/API; synthetic provider receipts and saved settings confirmed the sequence with zero external sends. The final server also rejected both new-target and saved-untested enable requests with HTTP 422 before a browser test enabled the saved channel successfully. The complete backend suite passed 285 tests; 181 frontend tests and typecheck passed. Production rollout and build are recorded after verification.
