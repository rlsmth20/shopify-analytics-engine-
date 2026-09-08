# Receipt recovery verification — September 7, 2026

A delivery could previously be counted twice after the server committed it but
the browser lost the response. A repeated submission now carries the same durable
UUID and returns the saved result without adding received units or receipt history.
The browser retains the exact pending submission across reloads, exposes recovery
at the top of the PO page, and coordinates preparation across tabs. Receiving
requires a saved PO; it no longer saves a potentially stale draft before receiving.

The additive submission ledger, receipt rows, received quantities and success
audit commit together. Draft saves preserve server-recorded received counts.
Only a matching, explicit server rejection that proves nothing was applied allows
the pending delivery to be corrected. Network failures and generic conflicts keep
the original pending operation. See [the HTTP contract](purchase-order-receipt-recovery.md).

The browser verification used an isolated synthetic shop on localhost with all
external notification transports disabled. The server committed a three-unit
delivery and deliberately replaced its success response with HTTP 503. After a
full browser reload, the recovery panel retained the delivery. Retrying cleared
the panel and left exactly three received units, one receipt row, one success
audit and one submission record. The mobile viewport and document width were
both 390px. No live merchant delivery or outreach was created by this check.

Backend tests additionally cover concurrent replays, competing deliveries,
transaction rollback, equivalent payloads, conflicting payloads, tenant isolation,
existing database initialization, privacy deletion and stale ORM state. PostgreSQL
locking was reviewed; executable concurrency tests used SQLite. Frontend tests
cover storage and lock failures, reload recovery, rejection distinctions and a
separate subsequent delivery. All 347 backend tests (plus 184 subtests) and 222
frontend tests passed. Frontend production build and typecheck passed.

Rollout order: deploy the backend protection before the frontend. An older open
browser missing the submission ID receives an actionable reload error. Do not
roll back the backend to an unprotected receiver while clients use recovery IDs.
The new table is created through the existing database initializer and requires
no alteration of historical receipt rows.

Production verification: release `065858f` is live on Railway
`a67bdc6c-a5ce-4155-a292-cb749df81696` and Vercel
`dpl_ELwroVtXzrb7tSd6m9kh58RqrFnn` at `www.skubase.io`. Health, the public
receipt response contract and the deployed submission table passed. Durable
growth evidence is `5653`; the worker remains running, with 13 first contacts
inside its rolling 20-merchant ceiling and no unresolved outbound sends.
