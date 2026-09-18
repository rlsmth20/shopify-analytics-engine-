# Acquisition identity recovery, September 18

A Workspace reservation could use a storefront identity while its assigned send
task used that store's published email identity. Receipt validation correctly
rejected the mismatched task, but recovery searched only the reservation's exact
contact row and missed the original execution trace. An unused reservation then
blocked new dispatch while older uncertain form receipts were revisited.

Reservation requests supplying a contact ID now require its assessed identity
before creating any new prospect. Recovery searches existing verified merchant
aliases and exact stored email routes for the original task and trace. Reserved
admissions are reviewed before historical uncertain submissions. A verified
no-send release also retires obsolete send tasks across those linked identities.

The receipt belongs to the reservation's contact throughout recovery. Evidence,
lease and original-session checks still apply; names alone never link merchants,
and uncertain submissions are never released or replayed based on a timeout.

Validation: 11 reconciliation tests and 20 outbound tests, including alias trace
recovery, priority over uncertain backlog, unrelated-evidence exclusion and
preventing duplicate prospect creation. These paths run in the existing local
production executor and trusted CLI; reload the executor at a completed stage
boundary. No new scheduler, schema, campaign or manually seeded discovery task.
