# Defer capped email work before model execution

After five confirmed Workspace first contacts, pending email send tasks were
still claimed. The model correctly declined to reserve or send, but the receipt
validator rejected the result as an unproven completed send. Repeated pre-send
checks consumed retries and compute without contacting anyone.

The local executor now checks the persistent email ramp before task selection.
Pending first-contact tasks with an explicit `channel=email` declaration and no
existing first-contact intent wait until the next Pacific-day reset. This wait
does not consume a lease, model call, retry or send slot. Receipt validation is
unchanged: a claimed send still requires its actual reservation outcome.

Only this explicit email-cap wait is ignored when determining whether the
planner can replenish other channels. Ordinary failure backoff, provider holds
and active leases remain respected. Replies, forms, warm-up tests and uncertain
send reconciliation remain independent. Channel-specific tasks automatically
become available after their persisted resume time.

All 41 Workspace, executor and planner tests passed. Coverage includes day
rollover, planning other work with deferred emails, no model claim for capped
email, no extra quota usage, and preserving uncertain intents and failure backoff.
Recover affected live pre-admission tasks only with retained no-send results and
no first-contact intent. Preserve the original failure/attempt history separately;
do not reset or retry an uncertain external action.

These changes run in the existing local executor; no API or frontend release is
needed. Both mailbox ramp and the shared 20-confirmed-contact ceiling remain.
