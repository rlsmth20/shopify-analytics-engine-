# Confirmed first-contact accounting

Owner policy: 20 confirmed new first-contact submissions per rolling 24 hours.
Receipts for provider-accepted mail, accepted forms and published messages count.
Pending reservations, unsuccessful attempts and uncertain outcomes do not.

`outbound.status` exposes confirmed count, remaining confirmed capacity, current
live permits, and uncertain contacts separately. The existing `used`/`sent` fields
now mean confirmed messages. The dashboard's number and meter count confirmations
only; uncertainty appears separately. The frontend handles older API snapshots
during a rolling deployment without subtracting uncertainty twice.

The unique contact/action records remain duplicate fences. Expired reservations
are classified as uncertain for safety and cannot be reused. No reservation is
deleted merely because it expires or ceases to consume quota. Release still needs
retained affirmative no-external-effect evidence. A confirmed receipt is idempotent.

Admission, final one-use submission authorization and receipt completion use the
same database dispatch lock. One live ten-minute permit is allowed, and the final
authorization must be consumed within 30 seconds. This prevents concurrent senders
from independently claiming the last confirmed slot. A late confirmation arriving
before final authorization fences the pending submission at 20. The existing
executor performs the authorization itself; this release does not send messages.

There is a distinct incident circuit breaker at 10 unresolved contacts, preventing
unbounded possibly-sent exposure. It does not turn those contacts into quota usage.
Late receipts always remain truthful: if they reveal an overage after other messages
were already sent, all further dispatch stops until enough confirmations age out.
Absolute certainty of no more than 20 actual external messages is incompatible
with treating potentially sent messages as zero. The safeguards bound uncertainty,
serialize new dispatch and disclose any revealed overage rather than hiding receipts.

Receipt-only queues and exhausted individual send tasks no longer globally prevent
the acquisition planner from replenishing. Their contact-level restrictions remain.
Genuine owner pauses, incident holds, provider failures and reply priorities remain.
The related recovered-send successor-key fix from concurrent development is included;
it preserves one idempotent successor after a verified unused reservation is released.

Verification: 127 growth regression tests and 31 subtests passed. The final planner,
executor, reconciliation and accounting checks passed (36 tests); the added owner
pause/final-authorization check passed with the outbound suite (9 tests). The
frontend's 237 tests, typecheck and production build passed. Fixtures demonstrate
12 confirmed + 8 uncertain -> 8 remaining, eight distinct new confirmed messages,
permanent duplicate exclusion for the uncertain contacts, live-permit concurrency,
late-receipt fencing/overage visibility, expiry, and autonomous planning with receipt
backlog. No production messages or discovery tasks were manually seeded for testing.

Code: `b6b8bb5` and final backend `8fae1f2`. Frontend deployment
`dpl_EEwUM9KcBhodTQRNygmjKNfEFoSw` READY at https://www.skubase.io.
Final Railway deployment `16d346f5-b916-40eb-93dd-ffa588862488` SUCCESS.
The existing local supervisor was drained and restarted, preserving owner control
and all contact fences. Policy evidence: `14186`, final rollout policy `14278`.

The live ledger had already advanced beyond the owner's earlier 12/8 snapshot.
At final rollout it reported 14 confirmed, four uncertain, zero live permits and
six remaining. Initial protected reservations were either still retained or had
affirmative no-send release evidence (14204). Duplicate contact rows: zero.
Preparation progress 14226 and the subsequent safety-recovery/send selection
occurred in the persistent executor without a manually queued continuation.
The worker's send attempt 14315 made no external submission: Reddit Chat had
rendered only its initial shell, so the worker retained the safety block. The
supervisor independently created monitor recovery 14319, obtained fresh clear
observations 14346, recorded recovery 14352 and claimed the unsent prospect again
at 14357. These are execution/recovery observations, not additional sent messages.
The subsequent attempt 14374 encountered the same incomplete Chat rendering and
again stopped before reservation or submission. Release verification evidence
14380 retains the 14/20 confirmed counter, four protected uncertain contacts, six
remaining slots, and the observed automatic transitions. The accounting blocker
is cleared; this separate browser-check issue still prevents a new confirmed send
in the observed window. The supervisor remains running with bounded recovery.
The browser used for this check lacked owner-dashboard access; its sign-in gate
was preserved. Dashboard arithmetic was verified by regression fixtures and the
production-data status query, not by granting another account owner permissions.
