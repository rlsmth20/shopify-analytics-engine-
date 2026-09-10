# Channel uncertainty and confirmed acquisition capacity

The owner's latest policy restores a shared ceiling of 20 confirmed first
contacts per Pacific day. The separate Workspace email ramp and controlled
mailbox-test ceiling remain unchanged. Unknown form outcomes never count as
confirmed contacts and never trigger a hold by their number.

Removed the ten-uncertain-contact global gate from reservation and final
authorization. The existing transactional dispatch lock, single live permit,
one-use authorization, permanent merchant duplicate fence, suppressions and
affirmative no-effect reconciliation remain. Late confirmations retain their
receipts and stop further dispatch at the ceiling, including already reserved
messages at final authorization.

Status now reports confirmed, in-flight and uncertain counts by channel. Explicit
operational incidents can be stored in `outreach_channel_health/<channel>` with
`paused` and `reason`; only that channel's admission and authorization are
blocked. Uncertainty does not populate this state. Existing Workspace provider,
authentication and ramp checks remain in force.

The dashboard and executor instructions explain that uncertain forms protect
those merchants while leaving other merchants eligible. The persistent owner
policy and heartbeat must use the same confirmed ceiling. No historical send,
reservation or suppression should be reset during release.

Validation: 38 outbound, executor and controlled-mailbox tests passed, including
the 11 confirmed plus 10 uncertain forms case, email and form admission through
20 confirmed sends, cross-channel incident isolation, concurrency, late-receipt
fencing and executor selection. All 12 dashboard checks and frontend typecheck
passed. A pre-existing warm-up test used wall-clock time near midnight; its
fixture now starts at noon so a delayed reply tests the intended same-day limit.
