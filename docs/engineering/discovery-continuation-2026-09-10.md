# Discovery outcomes and idempotent continuation

The previous empty-search completion fix still required zero qualified merchants
and known result counts. A real email search found two eligible stores with only
contact forms, so the validator rejected its completed result. A retry found a
merchant whose preparation task was already finished, which triggered another
rejection and exhausted the branch's research budget. The planner then treated
the blocked branch as a mission-wide execution failure.

Discovery now uses the ordinary evidence-backed completion contract: actual
observation, source URLs, valid outcome and next decision. Counts may be unknown;
merchant eligibility is distinct from an executable channel opportunity. Terminal
successor tasks are retained and skipped, never reopened. Learning counts only
executable successors while preserving the model's original result as evidence.

Exhausted per-task research budgets remain enforced. They do not prevent choosing
other acquisition hypotheses and are reported as branch exhaustion rather than a
provider outage. Other operational fault gates, send limits, suppressions and
uncertain-contact protections are unchanged.

Validation: 19 executor tests and 9 acquisition planner tests pass, covering the
two observed failures, missing observations, deduplication, return to autonomous
planning, and an exhausted branch budget. Recover the retained result and fault
history without repeating searches, creating discovery tasks, or sending messages.

These modules run in the local persistent executor. The server imports the
planner but does not call its replenishment function; no web release is needed.
