# Continuous growth and first-contact ceiling

Current policy **market_discovery_v1** supersedes older qualification language in
this document: basic physical-product Shopify merchant eligibility is sufficient;
public pain and unknown ICP fields are not gates. See executor-instructions.md.

## Autonomous queue replenishment

The local persistent supervisor now invokes `acquisition_planner.replenish` when
the browser acquisition queue is empty. It checks the existing verified mission
count, rolling contact capacity, unresolved work/retries, holds and reply priority.
An exhausted search is evidence for selecting another hypothesis, never a request
for the owner or hourly Codex wake to seed work.

The planner ranks retained candidate hypotheses using observed source yield and
vendor/no-result penalties. When none remain, it creates a leased `plan` stage on
the existing Codex subscription. That stage receives bounded strategy, beliefs,
ICP/channel knowledge, experiments, funnel and search history and may propose at
most two new hypotheses. Deterministic admission rejects near-identical queries,
including date-only changes and common inventory synonyms. A selected hypothesis
creates discovery work automatically and retains lineage through qualification.
Raw evidence and observed result counts/rejection reasons are preserved in
`acquisition_search`; unknown costs/counts stay null. Failed searches remain
available to future planning. Terminal exclusions and send receipts are unchanged.

Owner update: there is no daily planning/discovery-run quota. Acquisition keeps
replenishing while permitted contact capacity remains; old research-budget waits
are retired automatically with audit evidence. Each stage still has bounded time,
context and retries, at most two branches, and two searches/four source reads per
discovery. Per-prospect limits remain one search/two pages/two minutes. Qualified
work and replies retain priority. The shared 20-new-merchant rolling ceiling still
includes reservations with uncertain outcomes; never send to fill a quota. TRUE_IDLE
requires concrete attempted evidence and an external condition; it is reconsidered
after six hours. Duplicate-only plans back off 15 minutes within the daily bound.

`operator-state` exposes planner status alongside executor health. The read-only
`scripts/verify-growth-planner.py` reports queue-empty triggers, autonomous planning,
hypothesis selection, executor ownership, raw results and task lineage. It never
creates a task. The hourly automation provides oversight only; no queue seeding
or manual batch is needed.

## Current execution architecture — September 8 repair

The persistent pull executor in `app.growth.browser_executor` now consumes the
production browser queue continuously. `scripts/install-growth-executor.ps1`
supervises it at Windows logon and restarts failures; it uses the installed desktop
Codex executable and existing subscription. The hourly heartbeat retains review
and oversight duties and is no longer the acquisition execution trigger. The
computer, signed-in browser and local executor must remain available. A missing
executor is an operational fault, not healthy acquisition idleness.

The scheduled task launches the Python executor directly. Its Windows job object
terminates Codex and adapter children if the supervisor stops; a PowerShell parent
alone does not provide that guarantee. Production database credentials are loaded
from the existing Railway login into process memory. An expired task lease is
reclaimed from the database after restart, never reset to zero attempts.

P0 replies/safety checks precede P1 acquisition. Routine reconciliation and review
cannot outrank acquisition merely through a numerical task score. Each successful
browser stage atomically retains its evidence and queues concrete successors; the
supervisor immediately claims the next stage. There is no three-contact-per-wake
limit. Stages have a 15-minute runtime bound, renewable fenced leases, and bounded
failure retries. Failed or ambiguous sends still require receipt reconciliation;
restarting never releases their capacity. Research waiting on its shared provider
window remains queued with a durable due time rather than being marked complete.

Read `scripts/growth-review.ps1 -Action operator-state` or the dashboard API's
`execution` field for cap, rolling sent count, reservations, remaining capacity,
ready prospects, discovery, running tasks, pending age, last acquisition action,
last send, blocker, fault, next action and retry. Ten minutes of pending acquisition
without progress is starvation; an absent browser heartbeat is executor offline.
Task ownership/heartbeat alone is not acquisition progress.

This section and `executor-instructions.md` supersede the older hourly execution,
per-wake contact and source limits below. Existing source permissions, quality
requirements, message revision, cohort attribution and the hard 20-contact gate
remain authoritative. Each discovery stage uses at most two searches/four reads;
it yields real qualification successors or evidenced exhaustion, not repetitive
search work. No paid APIs or new services are enabled.

Owner policy, September 7, 2026: operate persistently with a **hard ceiling of 20 new merchants per rolling 24 hours**, never a volume target. This replaces the old ten/twenty lifetime campaign caps and the temporary overnight stop. Apply the shared ceiling conservatively across email, business forms and individually addressed public replies. A public broadcast is not twenty contacts. Legitimate replies to engaged merchants and narrowly requested services do not consume first-contact capacity.

The Railway worker continuously handles inexpensive observation, inbox ingestion, classification, delivery failures, requested service, experiments and funnel work. The Codex operator wakes every hour for bounded qualified outreach and obligations; it performs the deeper executive review once per day after 9 a.m. Pacific. Desktop/Codex availability is necessary for browser actions. Reaching capacity never pauses the worker or the operator's independent work.

September 8 execution correction: worker health is not evidence of acquisition
execution. The server cannot publish browser-operated outreach by itself. The
hourly operator must advance the next unscreened prospect or useful acquisition
task from the leased `operator_task` queue after handling replies. Maintain source,
decision to resolve, status, evidence, and next step in that durable backlog.
An empty inbox or unchanged server-discovery delta alone does not justify ending
while unprocessed sources remain. Preserve exclusions and move to a different
source when a discussion repeatedly yields vendors. No progress or send quota
permits weak prospects, repeated contact, or unnecessary research.

## Durable browser handoff

Run `scripts/growth-review.ps1 -Action operator-export` for the next six available
tasks, active claims, exhausted recoveries, support-monitor context, recent send
receipts and shared capacity. It imports pending legacy `working/operator_pipeline`
entries once. Terminal history cannot hide an older pending task.

Use `operator-enqueue -File <JSON>` to retain a new decision-directed task with
`key`, `source` (HTTPS or null), `decision`, `evidence_id`, optional `contact_id`
and `priority`. Keys are stable: repeating a source never resets completed work.
Claim with `operator-claim -File <JSON>` containing `task_id` before working it.
Claims last 30 minutes and recover at most three times after crashes. Do not act
under an expired claim; another invocation may own its replacement.

Complete with `operator-complete -File <JSON>` containing `task_id`, the returned
`lease_token`, new retained outcome `evidence_id`, `outcome` (`done`, `excluded`
or `blocked`) and a concrete `next_step`. A task marked done means its stated
decision was resolved, not that a merchant was contacted. Preserve raw evidence;
only verified external receipts count as outreach. Enqueue the next useful task
before ending if work remains. An exhausted task needs diagnosis and a separately
audited successor if justified, never automatic resetting or unlimited retries.

Server research now retrieves the exact numbered community post and verifies its
author, including replies beyond the first page. Cache keys include post and
participant. Qualified, current research creates this handoff instead of leaving
a stale generic draft. Historical underscore/hyphen and case variants of community
identities share suppression and prior-contact checks without rewriting history.
The browser operator still checks live channel rules and product fit. Queue claims
never authorize submissions: the separate first-contact admission gate below is
required for each individually addressed first contact.

Check Shopify App Store review mail addressed to `support@skubase.io` in the
dedicated `info@skubase.io` Gmail account each operator wake, including mail outside
Inbox and spam/trash. Support is an existing alias of that account. Server-side
dual delivery is verified only for `info@skubase.io`; its empty poll is not a
support-inbox check. Retain review correspondence as a high-priority operator
obligation with a message reference, and surface it promptly. Review mail and
internal delivery tests are not merchant leads or acquisition outcomes.

The daily-review helper and worker use `America/Los_Angeles` calendar dates,
including daylight-saving changes. `review-export` returns `not_due` before
9 a.m. or `already_reviewed` when a review exists for that Pacific date. Skip
only the executive review in either case and continue other permitted work.
Otherwise copy the exported ISO `day` exactly into `review-import`; a packet
cannot be imported on another Pacific date. UTC midnight does not expire it.
Historical UTC-keyed reviews remain unchanged and are recognized by their actual
timestamps. The worker retires obsolete pending review jobs after downtime and
never runs a backlog of deep reviews. Its next-review time is the next local
9 a.m., independently of UTC-based model-spend windows and the rolling contact cap.

Owner's latest priority: focus autonomous work on outreach and customer acquisition.
Handle substantive replies, requested health checks and suppression/delivery
failures first, then qualified prospect preparation and permitted outreach.
Use experiment and funnel evidence to improve acquisition. Defer optional UI
upgrades and speculative product work; investigate product issues when observed
evidence shows they block acquisition or customer use. Work unattended within
existing authorization and provide a concise, receipt-backed overnight report
on the first morning wake at or after 9 a.m. Pacific. Do not ask routine
permission questions or count research/drafts as completed outreach.

September 8 multi-channel update: use the owner's signed-in Chrome account
`u/skubase` for permitted Reddit outreach. Monitor the existing public offer
and individual conversation in [today's ledger](campaign-2026-09-08.md); never
repost or resend them. General business forms and merchants' own explicit
inventory statements are additional discovery/contact paths. A clearance sale
alone is not proof of an inventory problem. Preserve source age and uncertainty.

The owner explicitly authorized messaging individuals who describe their own
Shopify inventory problems. This supersedes blanket local prohibitions on all
community private messages. It does not override platform, subreddit or recipient
restrictions. Check the source, relevance, contact preferences, existing chat
history and shared admission before a single tailored invitation. Do not use
private messages to bypass explicit solicitation restrictions or turn this into
mass messaging. No repeated invitations or follow-ups to silence. Every newly
contacted person counts against the same ceiling across channels. The owner's
question about the merits of twenty per day did not authorize a cap increase.

Keep Reddit broadcasts, individual chat invitations and business forms in
separate experiments. Form acceptance and a sent invitation do not establish
delivery, readership, substantive interest or an acquired qualified user. The
hourly operator checks the existing Reddit offer and chat, merchant email replies,
and Shopify review correspondence before new acquisition. Automation remains
active; durable receipts and a first-response monitoring task retain continuity.

Respect existing no-follow-up promises. No silent-prospect follow-up automation. Suppress declines, opt-outs, bounces and channel restrictions immediately. Advertising remains $0 and no new paid services are authorized. The current Resend integration remains requested-service-only; this limit does not authorize prohibited cold email or bypass via Gmail.

## Required admission before every new merchant contact

Use `scripts/growth-review.ps1 -Action outreach-status` for the current rolling count. Historical sent contacts are imported once with `-Action outreach-backfill`; receipt import timestamps conservatively determine their initial window. This is a database ledger shared with the runtime, not a per-wake counter.

Before clicking any first-contact Submit/Reply/Send, prepare an exact JSON payload in ignored `.growth-deploy/` and run `scripts/growth-review.ps1 -Action outreach-reserve -File <absolute JSON path>`. Required shape:

```json
{
  "identity": "shopify-community:actual-merchant-name",
  "organization": "Verified merchant organization",
  "source": "https://community.shopify.com/t/observed-topic/12345",
  "action_key": "unique-first-contact-key",
  "channel": "shopify_community",
  "channel_rules_source": "URL and concise reviewed rule permitting this specific reply",
  "qualified": true,
  "relevance_evidence": "Verified merchant need, current relevance and supported Skubase capability",
  "facts": [{"text": "One verified public fact", "source": "https://observed-source", "verified": true}],
  "experiment_id": "existing-active-experiment-id",
  "cohort": {"icp": "stable segment label", "offer": "free_inventory_health_check", "message_version": 3},
  "body": "Exact final submitted message"
}
```

Check existing identities, organizations, email aliases and source history first; reuse the merchant's canonical identity across channels. Storefront fit alone does not establish a strong inventory prospect. A relevant participant's own stated inventory need can qualify a contextual reply even without a store URL; do not restrict outreach to original posters. Do not claim unobserved pain or private data access. Use [messaging revision 3](outreach-messaging.md), explicit promotional disclosure, one sourced fact, one question/offer, honest feature limits and the Shopify App Store review disclosure. Keep messages concise. Attribute new sends to revision 3 separately from historical cohorts.

A successful reservation supplies an ID and a ten-minute submit-before timestamp. **Only that invocation may submit that exact message once.** A retry or duplicate reservation does not permit another submission. If blocked by capacity or eligibility, do other work. If the deadline passes before submission, do not send: retain it for reconciliation. Never bypass the gate because a script or database is unavailable.

After verified submission, run `-Action outreach-complete -File <JSON path>` with `reservation_id`, `outcome: "sent"` and the exact provider/publication/form receipt in `receipt`. For an uncertain result use `outcome: "uncertain"`; never retry the external send. Record the full message and evidence in the campaign ledger too. Form success means form accepted, not delivered email or readership. Unresolved reservations retain capacity even after 24 hours until explicitly reconciled; there is deliberately no automatic timeout release. Previously contacted merchant identities remain blocked permanently for first contact.

Do not use the old ledger importers for new sends: they record after the action and cannot reserve capacity. They are historical import tools only. Successful sends release rolling capacity 24 hours after their recorded send time; an unresolved intent keeps its slot. A lower internal research/send-per-wake bound is allowed; never increase the hard ceiling automatically.

For a verified failure before any external effect, retain an `OUTREACH_NOT_SENT_VERIFIED` evidence record from `owner_operator`, subject equal to the reservation ID, with `no_external_effect: true` and the concrete verified reason. Then `outreach-reconcile` accepts a JSON containing `reservation_id` and `evidence_id`. It releases that slot with an audit record and invalidates the old reservation. An uncertain outcome, timeout or accepted/delivered message cannot use this path. A bounce still counts as an attempted first contact and suppresses the recipient.

## Learning and cohort stability

Keep the historical campaign cohorts and original messages; attribute new revision 3 messages separately in the [September 8 ledger](campaign-2026-09-08.md). Every new admission snapshots experiment, ICP segment, offer, message version, qualification and fact sources. Do not change positioning after a handful of sends or mix versions without attribution. Requested-service comparisons require at least ten contacts per arm with seven days of observation and posterior superiority of at least 0.95 before changing future allocation. Strong negative evidence can justify an earlier stop, never an automatic increase in send volume.

Before recommending a higher ceiling, report delivered/bounced denominators, substantive reply rate, positive interest, signup, Shopify connection, activation and paid conversion separately by segment and offer/version. Keep missing or unlinked outcomes UNKNOWN. Preserve delivery status separately from public publication/form acceptance. A recommendation requires a mature cohort and reliable outcome linkage; the cap can only change after explicit owner authorization and an audited implementation change.

When an experiment ends, evaluate its observation window and open obligations. Continue research and existing conversations. A subsequent experiment may use the same stable offer/ICP; create new attribution when a variable changes. Neither a cohort boundary nor the 20-contact ceiling is an instruction to stop the persistent mission.
# Current qualification override — market_discovery_v1

For new discovery, real physical-product ecommerce merchants with confirmed or
probable Shopify use and permitted business contact are eligible. Public pain,
SKU count, revenue and other ICP attributes rank; unknowns never reject. Use the
deterministic operator-assess command and executor-instructions.md budgets. Routine
Basic extraction uses Luna/low; tool-bearing CLI work uses Terra/low after live
Luna execution failures. Neither inherits
premium defaults. No retrospective reprocessing. Preserve 20/rolling24h and all
suppression/channel gates. Older narrow qualification instructions below are
superseded. Usage records retain actual completed-turn tokens and unknown dollar
allocation; the dashboard economics API exposes acquisition_efficiency ratios.

Historical `ACQUISITION_RESEARCH_RESUMED` records remain evidence only. No owner
renewal is needed for aggregate research runs. Duplicate-search backoff, actual
provider restrictions, spending limits and safety holds remain enforced.
# Submission recovery

The dashboard counts confirmed sends separately from held admissions. When
holds occupy capacity, the blocker is OUTREACH_OUTCOMES_UNRESOLVED, not a claim
that 20 messages were sent. The continuous executor queues leased reconciliation
after the submission window expires, including at zero available send capacity.
It reviews retained browser traces and releases only verified unused reservations.
Unconfirmed clicks remain held; missing receipts and elapsed time never authorize
replay. Reviewed uncertainty is deferred for 24 hours to avoid a recovery busy
loop. A fresh send stage also reports its submission outcome for atomic persistence
and immediate release of verified unused capacity. This does not raise the shared
20-new-merchant rolling safety ceiling.
Once capacity is available, P1 preparation/sends take precedence over further
receipt reviews. Browser checks use operator-monitor-start before reading the
live channels and pass its check_id to operator-monitor afterward. Freshness is
measured conservatively from the machine-recorded start; old observations cannot
be refreshed by recording them later or guessing a new timestamp.
Receipt recovery resumes the original Codex session identified by the retained
submission trace, so the original browser tab remains accessible across executor
stages and worker restarts. It never resubmits. Failed structured results are
retained alongside errors, including later provider observations. Existing
uncertain reviews receive one new review when this recovery capability is
upgraded; the upgrade does not release capacity or fabricate confirmation.
