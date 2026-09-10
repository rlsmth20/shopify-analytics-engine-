# Preserve search-rejection feedback in bounded planning

The live planner had unused all-channel capacity but repeatedly proposed semantic
duplicates. Its context builder trimmed search history before verbose strategic
memories, while admission checked against all retained searches. The model could
therefore repeat a query that deterministic code knew was already exhausted,
then wait fifteen minutes without receiving the rejection reason.

The planner now includes a compact protected search-policy section with twelve
recent known searches and three admission results. Duplicate rejection records
identify the matching prior search. The existing overall context limit is kept;
verbose history and memories are trimmed around that compact feedback.

One duplicate-only proposal gets a thirty-second correction opportunity. A
second consecutive invalid plan retains the fifteen-minute backoff, preventing
runaway model retries. An older duplicate wait gets one audited refresh with
feedback. No search is manually seeded, no duplicates are admitted, and explicit
operator pauses, provider holds, contact capacity, email ramp and suppression
remain unchanged.

Validation: all thirteen planner tests passed. New regression cases cover
feedback surviving oversized memory, matching-query attribution, one bounded
quick correction, and automatic recovery of a legacy duplicate-only wait.
