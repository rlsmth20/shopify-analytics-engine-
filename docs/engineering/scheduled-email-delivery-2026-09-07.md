# Scheduled report and buy-list delivery

Scheduled Reports and Weekly Buy List emails use the existing background scheduler and Resend sender (`info@skubase.io`). Merchants must explicitly enable a saved email schedule. Both the API and worker verify active access, the canonical Scale `scheduled_reports` capability, and access to the particular report before sending. Report titles and cadences are validated; weekly buy lists require a weekly cadence.

Weekly schedules are eligible on Monday in UTC; monthly schedules on the first day of the month in UTC. The scheduler revisits due schedules on each tick. Empty reports are skipped. This is not a promise of delivery at a particular local time. Existing accepted entries in `DigestSendLog` prevent a duplicate during the rollout period.

## Durable behavior

The new `scheduled_email_deliveries` table records one delivery per schedule and calendar period. Startup's existing `Base.metadata.create_all` creates this table; this release does not add columns to an existing table. Deployment verification should confirm startup database initialization completed.

The ledger preserves the rendered payload, original recipient, provider receipt, status, attempts and error history. Report content and sender parameters are frozen for retries so a stable Resend idempotency key identifies the same request. Changing the recipient after preparation holds that period's email; a later period uses the new recipient. A concurrent pause or schedule change is reread after acquiring the schedule lock.

PostgreSQL row locks serialize preparation and send claims; the schedule/period unique constraint adds duplicate protection. Local SQLite uses an immediate transaction for claims. A fresh 120-second lease and unique claim token are committed before provider I/O. Report generation does not consume that lease. A report that finishes outside its eligible day or calendar period is not sent. Completions are token-fenced so a stale worker cannot overwrite a recovered state.

Explicit provider failures are retried at most three times, with exponential backoff beginning at 60 seconds. The scheduler cadence determines actual retry timing. A missing server configuration makes no provider request and does not consume the send-attempt allowance. Provider retry identity is used only within a 23-hour window, leaving margin below Resend's 24-hour retention. Forced runs do not bypass acceptance, uncertainty, retry limits or the safe window.

An uncertain provider response, a committed claim whose worker disappears, or a database failure after acceptance produces an **unknown** hold for that period. It is not automatically replayed. An operator should check the recipient mailbox and provider records before arranging any manual resend; the UI directs the merchant to `info@skubase.io`. The next calendar period has a separate report identity. This release does not promise exactly-once inbox delivery or provide an automatic unknown-retry endpoint.

## Merchant status

Schedule responses add `last_delivery_status`, `last_sent_at`, `last_delivery_error`, `delivery_attempts` and `last_delivery_period`. Status metadata is scoped through the current shop's schedules; the API does not expose stored email bodies or provider credentials. `accepted` and `last_sent_at` mean a provider acceptance receipt was recorded, not that the message reached an inbox. Bounce or inbox delivery tracking is outside this ledger. Pending claims whose lease has expired appear as unknown even before the worker revisits them.

## Verification

`python -m unittest tests.test_scheduled_delivery tests.test_report_schedule_access tests.test_cost_provenance` passes 42 tests. New delivery tests use a temporary SQLite database and mocked provider calls, including simultaneous workers, payload freezing, changed recipients and pauses, slow generation, calendar boundaries, lost responses, crashes before/after provider acceptance, bounded retries, provider-window expiry and legacy deduplication. No live emails are sent by these tests.
