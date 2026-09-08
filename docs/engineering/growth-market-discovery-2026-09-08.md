# Market-discovery qualification and compute correction

The production policy is `market_discovery_v1`. Operating physical-product
ecommerce, confirmed/probable Shopify and a permitted business contact route
suffice. Pain, revenue, SKU count and other ICP attributes rank rather than gate.
The deterministic `operator-assess` command retains sourced basic checks and
separate eligibility, priority and confidence. Cached facts never bypass current
suppression, duplicate or send-admission checks. Missing basic evidence defers;
missing optional evidence does not reject. Qualified-user conversion is unchanged.

Routine CLI stages now explicitly use `gpt-5.6-luna` with low reasoning; bounded
planning and substantive replies use Terra/low. They cannot inherit an interactive
Astra setting. Qualification has a 120-second cumulative task budget, including
retry accounting. Instructions limit one search/two pages per prospect, reuse
facts and forbid optional-field investigations. Discovery has a five-minute
stage ceiling; output and planner context are bounded. No historical pool scan.

Every CLI attempt records model, task, latency, reported tokens and outcome in
growth_usage, with unknown subscription dollar allocation. Cached and uncached
input are distinguished. Economics exposes per-discovered/screened identity,
eligible prospect, email, all-channel first contact, substantive reply and
qualified user ratios. These are period operating ratios, not causal attribution.
The dashboard keeps the new policy separate even when other cohort labels match.

## Production observations

- Policy activation was retained in strategic memory; the executor itself created
  planning work (trigger 9130), completed Terra plan 9142 and ran Luna discovery.
- First discovery 9176 assessed one prospect. Verification found contrary retained
  vendor evidence 8949; correction 9202 invalidated assessment 9171 before contact.
  The contact is now ineligible, and expired queued work for excluded contacts is
  retired deterministically without another model call. Bare forum handles resolve
  to channel identities so alternate spellings cannot hide prior suppressions.
- Next discovery 9245 assessed WestuiMerchant (9239) and Berend_Verstegen17 (9242).
  Both retained UNKNOWN optional ICP attributes and advanced to preparation (9271,
  9301) and durable send work. These are eligible prospects, not acquired users.
- Through those preparations: four Luna runs, one Terra plan, zero Astra routine
  calls. The first-contact ledger remained 5/20 with no unresolved reservations.
  This observation does not claim a new delivered message or a measured dollar
  savings percentage. The new batch has not yet established reply/conversion rates.
- Isolated tests verify MEDIUM eligibility with probable Shopify and unknown pain,
  send admission, duplicate/alias suppression, clear exclusions, cached facts,
  usage accounting and cohort separation. The live sample above was HIGH priority;
  it does not establish a live MEDIUM-cohort conversion result.

Validation: growth suite passed 112 tests/33 subtests before the final alias/cache
refinements; affected execution, discovery, eligibility, operator and send tests
then passed 28 tests/6 subtests. Final cache/cohort checks are recorded with the
follow-up commit. No paid API, advertising, cap increase or schema migration.

## Live execution correction

Further send-stage validation found Luna executing an old safety-write helper,
asserting an unobserved browser check (9350), and emitting a database credential
in a diagnostic log. No first contact was admitted. That evidence was invalidated;
send admission now rejects explicitly invalidated evidence. The exposed password
was rotated, a fresh database connection verified, and the diagnostic log redacted.
Child processes no longer inherit database/API secrets; database URLs are redacted
as logs are written.

Final routing therefore uses Luna/low only for basic classification and Terra/low
for tool-bearing discovery, preparation, sends and replies. Basic eligibility
remains deterministic and optional UNKNOWN attributes remain neutral. This is an
evidence-driven intermediate-model fallback, not a return to premium reasoning.
Workers must not execute historical helper scripts or substitute old evidence for
real browser checks. The initial Luna-run observations above remain historical
validation data, not the final execution routing or a claim of new sent outreach.

Final handoff validation exposed missing execution context as well: standing owner
authorization is now explicit in worker instructions, operator-monitor persists
actual browser observations through the production connection with a fenced
lease, and operator-export/task packets provide real active experiment IDs.
Expired or invented experiments still cannot reserve a contact. Exhausted sends
with retained terminal outcomes do not globally stop independent discovery.
At the recorded validation checkpoint, no new first contact was confirmed; the
ledger remained 5/20. Prepared copy and eligibility are not counted as delivery.
