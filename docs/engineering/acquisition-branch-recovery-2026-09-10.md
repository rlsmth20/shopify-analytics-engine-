# Acquisition branch recovery and forum inbox

The executor was alive but unable to replenish its acquisition queue. Preparation
for Orchard Street Apparel found a published email and no general business form.
The worker returned `done` without a successor or stop reason three times. A query
in `acquisition_planner.replenish` treated that exhausted preparation task as a
global blocker, although no sending incident or operator pause existed.

Exhausted planning/discovery/qualification/preparation tasks now remain terminal
and receive an idempotent `ACQUISITION_BRANCH_EXHAUSTED` evidence record. Compact
failure context is available to the next planner. They do not prevent another
hypothesis. Send reservations, contact suppression, retry counts and explicit
global holds are preserved. A genuinely excluded qualification/preparation route
can finish without a manufactured successor when it supplies a rejection code.
An invalid `done` result remains invalid; validation was not removed.

The same investigation found an unrecorded positive Shopify Community reply from
Anshul_Sandal (topic 637085, post 96) about Excel purchase orders and reorder
recommendations. `community-reply` records the exact source text against the
existing merchant and first-contact experiment, deduplicates topic/post identity,
and queues an existing-conversation reply ahead of acquisition. It creates no
first contact or customer conversion. Explicit opt-outs override classification
and suppress the linked merchant identities.

The existing supervisor now schedules one bounded Shopify Community inbox check
every three hours when `working/community_inbox.enabled` is true. It checks the
authenticated account and up to three reply threads, retains seen reply URLs,
and uses the existing leased monitor/reply stages. It does not refresh Gmail or
Reddit send-safety evidence or pause unrelated channels. No new service, paid API,
schema migration, or campaign SaaS was introduced.

Validation: 40 focused planner/executor/operator/community tests passed, including
empty-queue continuation after exhausted preparation, explicit route exclusion,
campaign attribution, duplicate inbound receipt, suppression, reply priority,
bounded monitoring across restarts, and unchanged first-contact accounting.

Production: recorded Anshul's reply as evidence 35118 and message
47a4fa6973154b5fa392a609dfea6593. Restarted the local scheduled executor after
checking there was no active task or in-flight send. It independently claimed the
reply as task 5897784d6e36d746e1aa390ec09598f13e2823c11201f1af15c26b68964ea274.
Discovery is not manually seeded for the recovery verification.

The executor published its answer at topic 637085/post 97. The UI initially
retained the composer, so it correctly avoided a second submission and created
receipt-review work. Verification exposed an older migration that converted any
uncertain reply into reconciliation of the original first contact. That migration
now excludes already-confirmed sends and conversation replies, and restores any
affected pending task to read-only conversation review. The original confirmed
first-contact record is unchanged. A regression test covers both admission and
repair. Inbox checks no longer update the executor's acquisition-progress clock.
The completed first scheduled forum check is evidence 35240; the supervisor also
created a new acquisition plan on its own (evidence 35195).
