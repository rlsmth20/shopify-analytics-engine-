# Growth execution repair — September 8

The owner confirmed that the computer and Codex were running. A healthy worker
and repeated quiet inbox checks did not establish that acquisition work was being
executed. This release fixes three concrete breaks in the research-to-operator path.

- Research previously fetched a topic's first page even when evaluating a later
  comment. It now retrieves the exact numbered post and verifies the participant.
- A topic-wide cache could hide a second participant. Evidence and caches now
  distinguish numbered posts and authors; repeated observations retain history.
- Qualified research previously left a generic draft without an executable
  browser handoff. It now creates a stable-key operator task with a lease, bounded
  crash recovery, retained completion evidence and a next action.

Canonical community identity aliases share suppression and first-contact checks.
Merchant-built spreadsheets are not automatically vendor promotion. The operator
still verifies product fit and channel rules before using the separate admission
gate. No queue item creates send authority, and neither research nor completion
counts as a merchant contacted.

The existing hourly Codex automation was updated in place to consume the bounded
queue export, claim work and complete it with evidence. Replies and Shopify review
mail remain first priority. The Railway worker remains continuous; neither reaching
20 new merchants per rolling 24 hours nor an empty inbox pauses independent work.

## Verification

93 growth tests passed. Eight discovery tests passed again after refining vendor
matching to avoid treating “my apparel” as “my app”. Coverage includes later
comments, independent participants, immutable outcomes, stale leases, bounded
recovery, suppressed aliases, prior-contact aliases and pending work hidden behind
more than 100 terminal records. A public live read verified the exact numbered
community endpoint returns post 94 in the bounded response.

Live database task `2bd71c82fa711e332bda65075dc57e534d058a29497e527fe31c1253be099357`
was exported, claimed and completed with evidence **7536**. The result records
named inventory-app review observations and excludes unsupported freight, sync,
bundle and generic billing complaints from outreach. A fresh export returns its
persisted successor, which must resolve the current relevance of a historical
planning-affordability observation within two source reads. No contact is
authorized by that historical review alone.

No new merchant contact was sent during this repair. The live ledger at verification
held two first contacts in the rolling window, 18 remaining slots and no unresolved
send intents. These are the two earlier September 8 community replies, not new
results of this release. Qualified-user and revenue improvement remain unproven.

Code commit: `5e87f34`. Deployment and runtime verification are recorded below.

Railway deployment `157cbaf7-97fd-459b-bbda-8651ae0ee128` reached **SUCCESS**.
Production `/health` returned HTTP 200, application startup completed, and the
worker resumed with `health: running`, `paused: false` and no failed work in the
preceding 15 minutes. Live release evidence **7548** retains the verification.
The shared ledger remained 2/20 with no unresolved intents, and the next operator
task remained pending after deployment.
