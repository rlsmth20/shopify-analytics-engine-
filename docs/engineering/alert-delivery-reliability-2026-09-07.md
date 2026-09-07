# Inventory alert delivery and readiness

This release makes inventory alert setup describe what is configured and what a provider accepted, and preserves incident/channel delivery evidence across API and worker restarts. It uses the existing application database and background scheduler; it does not introduce another worker service or paid provider.

## Channels and configuration

| Channel | Implemented behavior | Required configuration | Meaning of a successful test |
| --- | --- | --- | --- |
| Email | Resend transactional email with an acceptance receipt and stable idempotency key for each incident/channel attempt | Server `RESEND_API_KEY`; `WAITLIST_FROM_EMAIL` and `WAITLIST_REPLY_TO`; the merchant's saved destination | Resend accepted the test to that saved destination. Inbox delivery is not established. |
| Slack | Incoming webhook POST over public HTTPS | Merchant-supplied `https://hooks.slack.com/services/...` destination | Slack returned a successful HTTP response. |
| Webhook | JSON POST containing subject, body, emitted_at and source | Merchant-supplied public HTTPS destination on port 443; optional `GENERIC_WEBHOOK_TIMEOUT` (default 10 seconds, clamped to 1–30) | The endpoint returned a successful HTTP response. |
| SMS | Unavailable; rejected for new enabled settings and tests | None in this release | No SMS sends or Twilio charges occur. |

The deployment configuration audit reported an existing Resend key and `skubase <info@skubase.io>` sender/reply-to, one enabled merchant email destination, and no configured Slack, webhook or SMS destinations. No merchant destination was changed, and implementation tests did not call a live provider. A configured server key alone does not verify domain acceptance or delivery.

`NotificationChannelConfig.available` describes whether the server driver/provider is available. `configured` describes whether the saved destination passes format validation. `enabled` remains the merchant's choice. `verified` means the provider accepted the last test of the currently saved destination. Changing the destination resets verification; a failed retest clears it. A conditional update prevents a concurrent test for an old destination from verifying a new one. Test outcomes are audited with a destination hash, not the raw webhook token.

Existing enabled destinations remain eligible even when the old UI never persisted verification. The release does not silently disable those merchants. The UI recommends saving, testing and checking the actual destination.

Public webhook requests reject internal addresses, resolve and pin a public IP while preserving TLS hostname verification, and do not follow redirects. Errors and delivery audit history do not include destination credentials. Email targets must be a single real address; placeholder Shopify admin addresses and comma/semicolon recipient lists are rejected.

## Worker behavior

The existing FastAPI lifespan starts the background loop. Its configuration remains:

- `ALERT_AUTO_EVALUATION_ENABLED=true` by default.
- `ALERT_EVALUATION_INTERVAL_SECONDS=900` by default.
- `ALERT_DELIVERY_COOLDOWN_SECONDS=21600` by default; incident cycling has a minimum 60-second safety floor.

The channel response reports these configured values, not a process heartbeat or proof that a worker is currently healthy. Shops without an enabled, valid, available destination referenced by an enabled rule are skipped before loading inventory or producing forecasts. Preview still evaluates without sending or persisting a delivery. An exception rolls back the per-shop session before the next shop is processed.

Daily inventory snapshots retain their once-per-UTC-day behavior. Scheduled report and buy-list runners are revisited on each tick so a failed send is not hidden for the rest of its eligible day. Their own entitlement, schedule and durable delivery checks determine whether a send is allowed; see their separate implementation and tests.

Supplier slip alerts now use recorded purchase-order receipt observations. SKU alerts receive actual product title, supplier and category metadata. New tag, collection and location filters, and unimplemented price-drop/bundle-break triggers, are rejected until their source data is supported. Existing unsupported rules are preserved for review. New high-probability defaults use a 70% threshold; only the exact old misleading default name is renamed, preserving existing merchant thresholds.

## Durable incidents and recovery

`alert_events` preserves matched rule/SKU (or supplier) incidents and their original message. `alert_deliveries` records one channel and hashed destination per incident, attempt history, provider receipt, acceptance time, retry time and lease. The existing startup `Base.metadata.create_all` mechanism creates these new tables. Existing rule and channel rows are preserved; no existing-column migration is required for this release.

PostgreSQL row locks serialize incident creation and send claims across processes. A unique event/channel/destination constraint is a second safeguard. First-time rule/channel seeding also locks the shop; local SQLite seeding uses an immediate transaction. Deleting all rules no longer causes the next page read to recreate them while the shop's channel configuration remains.

Before provider I/O, a send claim is committed with a fresh 120-second lease. Each completion uses a fresh clock for acceptance and retry timing. Accepted channels are not replayed while other channels are retried. Explicit rejections and unavailable configurations receive at most three attempts per incident/channel, with 60-second exponential backoff (effective retry time also depends on the scheduler interval). The normal cooldown permits a new notification cycle for an ongoing condition after six hours; its acceptance timestamp is scoped to the rule and SKU instead of suppressing every other SKU under that rule.

A lost response, connection reset, broken pipe, or worker crash after a committed claim leaves an **unknown** result. The system does not automatically replay that uncertain send. Other unaccepted channels can proceed. This is deliberate duplicate protection, not proof of a failed delivery. Provider HTTP failures and manually acknowledged retries can still have duplicate risk; this system does not claim exactly-once external delivery.

An unknown result holds that unresolved incident until the merchant checks the destination and explicitly requests a retry, or a fresh evaluation finds that the inventory condition has resolved. A later recurrence can create a new incident. Resolution excludes incidents created after the evaluation began, and a resolved event cannot claim a pending send. Old rule-wide cooldown timestamps are honored once when no ledger history exists, because historical per-SKU provider receipts cannot be reconstructed.

`POST /alerts/events/{event_id}/retry` requires current shop access, channel entitlement, an unresolved event owned by that shop, an unknown attempt to the current saved enabled destination, and `acknowledge_possible_duplicate: true`. It queues only that channel, records the actor and acknowledgement, and does not send in the API request. The next qualifying evaluation performs the retry; accepted channels are unchanged. A changed destination or already accepted attempt cannot be retried through this endpoint. `uncertain_channels` identifies channels with unknown historical outcomes; a stale action after a destination edit can return a validation message to refresh/review settings.

The database history survives restarts. Alert history returns bounded, shop-scoped results; preview is explicitly `preview=true`, `delivered=false`. Legacy `delivered` means at least one provider accepted a channel, and `channels_sent` lists those accepted channels. There is no inbox/bounce receipt integration for these product alert events in this release.

Each claim also has a unique lease token. Recovery and explicit retry invalidate that token; an old worker cannot overwrite a newer accepted receipt after returning late. Shopify shop redaction explicitly removes alert delivery children, event payloads and scheduled-email payloads in the same tenant transaction. The unused process-local notification sink was removed, so it cannot retain destination/message copies outside the durable tenant deletion path. Uninstall still revokes access and invalidates billing cache while preserving merchant data until redaction.

## Verification

Forecast alert precision follow-up: the model's numeric risk still selects incidents against the saved threshold, but messages with fewer than 30 usable history days or low confidence omit a precise percentage. They preserve the possible-stockout warning, disclose the usable history/confidence limitation, and ask the merchant to verify recent sales, available stock and incoming orders before ordering. Better-supported forecasts explicitly describe an estimate and use "over 99%" instead of rounding to a certainty label. Product names are used when available. Forecast algorithms, probabilities and trigger thresholds are unchanged.

A synthetic reproduction with one observed day of 30 sales and 10 units on hand previously sent "100% stockout probability" while the forecast itself said low confidence. Focused regression coverage now verifies that warning is retained with its one-day limitation, longer low-confidence histories still disclose uncertainty, supported estimates retain their estimated likelihood, and below-threshold risk does not fire.

`python -m unittest tests.test_alert_delivery` exercises mocked provider acceptance, partial failure, bounded retry, committed-lease crash recovery, restart/session continuity, unknown acknowledgement and ownership, new-SKU cooldown scope, old cooldown migration, resolved/newer incident guards, fresh lease clocks, saved-target verification, concurrent first-time seeding, real targeting metadata, unsupported filters, private destination blocking, Resend receipt/idempotency use, disabled-destination cheap skips, scheduler rollback and daily retry cadence.

All provider calls are mocked and all database fixtures are local/temporary. Production configuration inspection and any explicitly scoped deployment smoke are separate from these tests. Multiple-worker correctness relies on PostgreSQL row locking; the local SQLite delivery tests do not establish cross-process SQLite dispatch guarantees.
