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

## September 9, 2026 production verification

- Code release: `be10072`.
- Railway deployment: `b5051732-1002-4de3-b985-8b971482bf62`, SUCCESS.
- Vercel deployment: `dpl_32oQcYGTPtfYobt1FZPcVDmLH8tU`, READY, aliased to www.skubase.io.
- Shopify's historical failure detail reported no response after 6,000 ms for
  `shop/redact`. Those failures subsequently succeeded on retry. That evidence
  establishes timeouts, but does not isolate database work from a temporary outage.
- Signed production tests against a unique synthetic domain verified absent from
  `shops` returned 200 in 1,268 / 1,173 / 1,185 / 1,209 ms for shop redaction,
  customer redaction, data requests, and uninstall respectively. All four durable
  jobs completed with one attempt; duplicate submissions created no repeat work.
  Completed payloads/domain were cleared. Invalid HMAC returned 401.
- Production API health returned 200. Browser demo dashboard populated its cards
  and charts. Legacy embedded-root redirect returned private/no-store 307 with
  launch parameters preserved; all four WOFF2 font assets returned 200.
- Backend regression suite: 446 tests passed. The separately run eight queue tests
  also passed, including the concurrent claim test added after suite discovery.
  Frontend: 239 tests, typecheck and production build passed.
- Dashboard initial JavaScript gzip: 153,063 to 142,148 bytes. Fonts gzip:
  645,953 to 442,386 bytes, with original glyphs and metrics preserved.
  These are asset measurements, not measured field LCP/INP improvements. The
  screenshot's 408 ms aggregate INP has no isolated interaction diagnosis yet.
