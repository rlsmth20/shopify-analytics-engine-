# Owner outreach history

Open `/growth/outreach`, or choose **View messages sent** on the growth dashboard.
Search by merchant, username or email and filter by contact method and send status.
Confirmed first contacts are the default; reservations and uncertain submissions
remain separate. Older pages load on demand without retrieving the entire ledger.

The owner-only `GET /growth/outreach-history` endpoint projects existing
first-contact receipts, original reservation evidence, imported historical evidence
and matching sent email records. No new sends, retries, qualification decisions or
counter changes are performed. Message text must match the retained body hash;
current drafts are never substituted. Historical normalized spacing and approximate
timestamps are labeled. Original source URLs and retained receipt text remain
available when a temporary form confirmation page changes.

The endpoint supports `status`, `method`, `search`, `before` (opaque record ID),
and `limit` (1–50, default 25). Responses require the existing admin role and use
`Cache-Control: private, no-store`. Link protocols are restricted to HTTP(S).

Validation: 13 backend history/dashboard tests, 10 frontend dashboard tests,
frontend typecheck and production build. Read-only production projection verified
36 confirmed records with message text and source links; three historical messages
retain normalized spacing, and two receipts have text without a URL.
