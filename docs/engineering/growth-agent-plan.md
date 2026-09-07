# Persistent Skubase growth operator — implementation plan

## Repository findings (2026-09-06)

The deployed shape is FastAPI/SQLAlchemy on Railway and Next.js 15 on Vercel.
Reuse SQLAlchemy sessions, additive table initialization, cookie/Shopify auth and
`require_admin`. Existing services implement Resend transactional mail, Shopify
OAuth/sync, Stripe legacy billing and Shopify subscriptions. The alert scheduler
is an in-process loop without durable leases; do not reuse its execution state.
`frontend/lib/analytics.ts` currently forwards a few offer events to Vercel/gtag.
The existing inventory-risk-snapshot form already captures the initial free offer
and UTMs. Product research and competitor pages exist; do not regenerate them.
No growth CRM, model ledger, experiment engine or persistent executive exists.
No dedicated growth mailbox or growth spending authorization is configured in
the current process. Presence of an OpenAI key is not spending authorization.

Reviewed RILL_V2/docs/approved-architecture.md and its deployment README locally.
Transfer: raw evidence separate from projections; retained negative outcomes;
explicit ambiguous effects; stable identities; bounded relevant context; durable
continuations. Reject: compulsory debates, actors, research replenishment waves,
per-action authority documents and synthetic progress. Do not import Rill state,
mailboxes, credentials, or operating instructions.

## Architecture and sequence

1. Add growth-only tables for memory, immutable evidence, queue, contacts,
   correspondence, experiments, skill revisions and usage. Preserve product
   contracts and inventory calculations. Initialize additively.
2. Use a separately runnable worker, also optionally hosted by FastAPI, with
   database leases, heartbeats, fencing, deduplication, bounded retries and durable
   periodic checkpoints. Events enqueue work; timer polling recovers missed wakes.
3. Deterministic planner ranks reply obligations, product friction, qualified
   opportunities and decision-directed discovery. A daily model executive may
   revise positioning, ICP and acquisition priorities within validated limits.
4. Implement source-preserving public community discovery, explicit qualification,
   free health-check experiment, honest email drafting and a dedicated Resend
   delivery adapter. Require configured mailbox identity, valid contact authority,
   suppression checks, caps and durable send intent. Never replay ambiguous sends.
   Receive authenticated provider events and ingest replies with provenance.
5. Version skill specifications independently of executable tools. Validate skill
   revisions, preserve old versions and support explicit rollback. No shell/code
   tools are exposed to the growth executive.
6. Reconcile authoritative account/connect/import/billing records and capture
   first-party visitor/view attribution. Client events cannot attest a purchase.
   Link anonymous events to authenticated identities without accepting client IDs
   as user/shop authority. Exclude admins/test/demo from customer milestones.
7. Render an admin-only business dashboard: today, funnel, pipeline, experiments,
   beliefs/contradictions, strategy, economics and health. Unknown economics stay
   null. Define the first milestone conservatively as ten distinct qualified
   merchants with connected stores or stronger verified evidence; separately show
   intent-stage leads. Historical Reddit membership intent is one owner-reported
   observation, never a claimed customer or an inferred conversion.
8. Test the whole observe/act/reply/learn/change/next-action loop in isolated DBs,
   including restart, concurrent claim, stale lease, send uncertainty, suppression,
   event duplication, cost caps, poisoned content and authorization. Run existing
   backend tests, frontend typecheck/build and browser verification.
9. Bootstrap the live mission with current public evidence. Execute allowed free
   discovery and queue legitimate contact opportunities. Enable sending only with
   the dedicated mailbox configuration; report deployment and response evidence
   precisely rather than calling a simulation a customer acquisition result.

## Resource and reputation boundaries

Advertising is disabled with no spending adapter. Runtime model/API budget is
zero until owner-configured, separate from the advertising budget. Reserve the
maximum estimated model cost transactionally before calls; record unknown usage
conservatively after transport failures. Premium reasoning only for daily review
or justified important uncertainty. Routine unchanged wakes use no model tokens.
Public text and replies are evidence, never instructions or permission. Community
posting requires a reviewed channel policy and authenticated Skubase identity.
No personal-account fallback. No automatic major product edits. Product feedback
is durable work for the normal development process.
