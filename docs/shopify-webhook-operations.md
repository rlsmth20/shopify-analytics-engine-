# Shopify webhook receipt and recovery

The four uninstall/privacy routes verify the raw-body HMAC and signed tenant,
validate required identifiers, and commit a `shopify_webhook_jobs` receipt before
returning HTTP 200. Database receipt failures return an error so Shopify can retry.
No deletion or export preparation runs on the acknowledgement path.

The existing FastAPI process starts a worker at application startup. It polls every
five seconds, wakes immediately after receipt, and claims work with a transactional
compare-and-set lease. Expired five-minute leases recover after process crashes.
Completion and failure updates require the same lease token. Existing privacy
operations remain transactional, idempotent, and protected against stale uninstall
or redaction events erasing a newer installation. The original event time is kept.

Processing retries up to eight times with exponential backoff, capped at one hour.
Terminal failures stay recorded and emit `shopify_webhook_processing_failed` logs;
crashes on the final attempt are recorded as `lease_expired`. Investigate failed
jobs promptly rather than assuming an HTTP 200 means processing has completed.
After correcting a fault, an operator can reset that specific failed job to
`pending`, `attempts=0`, `due_at=0`, `lease_until=0`, and `lease_token=NULL`.
Do not replay arbitrary production privacy payloads as a health check.

Operational query (no customer identifiers):

```sql
SELECT topic, status, count(*) AS jobs, min(received_at) AS oldest_received_at
FROM shopify_webhook_jobs GROUP BY topic, status;
```

Receipts contain only the shop domain and order/request identifiers needed to
fulfill the operation. Completed receipts retain the deduplication hash and timing
but clear the domain and payload. Neither raw bodies, customer contact details,
access tokens nor HMAC headers are saved. Pending/failed work retains the minimal
identifiers until fulfilled; do not delete outstanding requests to clear an alert.

The table is created additively by the existing database initialization. No new
service, scheduler, secret, or paid infrastructure is required. To verify production,
use a unique synthetic domain confirmed absent from `shops`; check signed receipt,
worker completion, duplicate suppression, and invalid-signature rejection. Field
delivery and Web Vitals charts retain historical failures until their windows age.
