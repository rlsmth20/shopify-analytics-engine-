# Easier setup and reliable notifications

The September 7 release makes the next step clearer for a merchant and distinguishes configured settings from actual delivery evidence.

## Customer-facing changes

- Task search finds pages for phrases such as “email alerts,” “weekly email,” “reorder,” and “upload CSV.” Menu labels explain what each area does, and the owner growth dashboard stays out of merchant navigation.
- Account and header status checks show loading, unavailable, and retry states instead of falsely reporting an inactive plan or disconnected store. Plan caches are cleared on session changes, and a late prior-session response cannot repopulate them.
- New merchants see the Shopify review status and current CSV/health-check/access-help options. Shipment imports explain that recommendations also require current stock and expose skipped rows instead of presenting a zero-row upload as success.
- Report datasets load independently. A failed or unavailable higher-tier forecast does not erase permitted basic reports. Email scheduling blocks writes after a failed settings read, defaults new schedules paused, and only confirms matching server responses.
- Alert setup guides destination → test → enable, hides webhook secrets, shows supported targeting and actual channel readiness, and separates preview from persisted activity. Weekly buy lists and scheduled reports show delivery status separately from the saved schedule.
- Mobile pages reserve space below the final controls so the floating help button does not cover them.

## Real channel readiness

The production email provider accepted one internal test from `info@skubase.io` to the same approved business inbox. The message was visibly present in that Gmail inbox on September 7 at 2:40 PM Pacific. Provider receipt: `44c5c110-a7d2-4209-896e-c6c640e0bc5f`; durable growth evidence: `5272`. This is a service check, not merchant outreach, a substantive reply, or a conversion.

No configured Slack or generic webhook destinations were found in the production audit. Those channels require each merchant's destination and test. SMS remains unavailable and is labeled planned. No merchant notification settings were changed during implementation.

## Reliability and verification

See [alert delivery](alert-delivery-reliability-2026-09-07.md) and [scheduled email delivery](scheduled-email-delivery-2026-09-07.md) for the durable tables, per-channel/per-period claims, bounded retries, unknown holds, provider acceptance semantics, and deployment requirements. Tenant redaction and rollback cover stored message payloads and receipts.

Isolated browser/API verification used synthetic inventory and replaced every notification transport. Preview persisted zero delivery events; a seven-alert evaluation was followed by zero duplicate sends. A partial email/Slack incident retained the accepted email, held uncertain Slack, required acknowledgement, then retried only Slack (email attempts 1, Slack attempts 2, external sends 0). Weekly schedule save, reload and pause were verified against the real route with temporary SQLite. Mobile alert/activity/account layouts and task search were checked at 390px; account connection failure displayed unavailable while the independently loaded plan remained visible.

Final full-suite verification passed: **228 backend tests**, **147 frontend tests**, frontend typecheck and production build. The isolated weekly report runner accepted one synthetic message and an immediate repeat accepted zero; the schedule API reported the acceptance and attempt count. Production deployment references are recorded after rollout. Advertising remains disabled; this release does not change the 20-new-merchants-per-rolling-24-hours ceiling or outreach cohorts.
