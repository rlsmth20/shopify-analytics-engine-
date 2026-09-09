# Dedicated outreach email

The conditional EmailPal adapter is separate from operational Resend/Gmail. No real
provider send has been verified yet. The EmailPal account using info@skubase.io and
its Skubase workspace were created on September 9 using Google's signup route.
The Google mailbox already had September 6 activity. No EmailPal subscription or
payment transaction exists. See outbound-provider-evaluation.md and email-ramp.md.

The dedicated read/write API key and webhook signing secret are saved in Railway;
neither is committed or exposed in output. Real authenticated GETs returned HTTP 200
for the Skubase account and owned subdomain. Webhook resource
`97935d29-0f74-4e67-aa3b-c5c8af313659` points to the deployed growth endpoint.
OUTREACH_EMAIL_ENABLED remains false, SAFE_TEST_MODE true, and test destination
info@skubase.io. The unsubscribe signing secret is independently generated. Account
access is verified; provider policy approval and actual delivery/reply testing are not.

## Configuration

Secrets belong in Railway environment configuration, never source control:

| Variable | Purpose |
| --- | --- |
| OUTREACH_PROVIDER | `emailpal` |
| OUTREACH_EMAIL_ENABLED | `false` until setup is verified |
| OUTREACH_SAFE_TEST_MODE | defaults `true`; queued test intent cannot become a live send |
| OUTREACH_EMAILPAL_API_KEY | Provider API credential |
| OUTREACH_EMAILPAL_MAILBOX_ID | Provider-issued mailbox resource ID |
| OUTREACH_EMAILPAL_WEBHOOK_SECRET | Raw signing secret issued for the webhook |
| OUTREACH_SENDER | `rainer@outreach.skubase.io` |
| OUTREACH_REPLY_TO | Same monitored provider mailbox; operational primary MX stays intact |
| OUTREACH_TEST_ADDRESSES | Explicit approved test recipients; the first receives safe sends |
| OUTREACH_UNSUBSCRIBE_SECRET | Random secret of at least 32 characters |
| BUSINESS_NAME | Actual business name, supplied/verified by owner |
| BUSINESS_POSTAL_ADDRESS | Actual business mailing address, supplied/verified by owner |

Provider mailbox display name must be `Rainer from Skubase`. The adapter verifies the
mailbox before dispatch. EmailPal does not document arbitrary Reply-To/custom headers;
use its monitored sending mailbox and a working body opt-out link, plus reply opt-out.

Owner-controlled `strategic/outreach_provider_approval` records provider, terms_verified,
source, account_verified, cost_authorized, domain_verified, inbound_verified and
safe_test_verified. These are evidence-backed setup attestations, not model guesses.
`strategic/outreach_email_pilot` records active, started_at and max_messages. Initial
pilot sizing must be explicitly selected after provider setup; it does not auto-grow.
After a verified successful pilot, store completed=true, successful=true, completed_at
and an evidence source. This ends the lifetime pilot ceiling; the persistent email
ramp then governs increases. Genuine replies do not consume the first-contact ceiling.
The email-status response includes the current ramp, today's actual email count,
authentication evidence, last increase and any reason increases are paused.

Use Railway variable changes with `--skip-deploys`, followed by a controlled release
of the current tested source. The linked Git main was older than the deployed growth
branch on September 9; an automatic settings rebuild temporarily restored that older
code. Do not assume a successful settings-triggered deployment contains recent fixes.

## Work and receipts

`email-queue` accepts prospect_id, recipient, campaign_id, subject, body and immutable
cohort (icp, offer, message_version, hook, source). Optional kind is first_contact,
reply or followup; replies require the verified inbound reply_to_id. A campaign may
enable followups_enabled and followup_spacing_seconds; one prewritten followup_body
can be supplied with the first message. The worker cancels it after a human reply.

Send intent commits before external effects. A 202 response is only queued: the worker
retrieves the send receipt before recording a first contact. Timeout/crash keeps the
merchant protected. Known pre-queue rate-limit rejections may retry with bounded queue
attempts and the same provider idempotency key; ambiguous submissions never auto-retry.

POST `/growth/webhooks/emailpal` authenticates the raw payload, stores it durably and
enqueues processing. Provider GETs establish actual identity and status. The safe test
must confirm the actual event envelope; public docs do not specify every payload key.
Inbound messages match provider/RFC thread IDs and sender, not subject alone.

GET `/growth/outreach/unsubscribe/{message_id}?token=...` displays confirmation; POST
opts out. Link scanners cannot unsubscribe through GET. Suppression applies across
linked merchant identities and future campaigns. No account/login is needed to opt out.

Owner-only `/growth/email-status` and CLI `email-status` expose readiness and campaign
results. Existing growth/outreach history retains sent message and source evidence.
Safe-test sends do not mark the intended merchant contacted or inflate acquisition.

## DNS and live acceptance

Primary DNS uses Vercel nameservers. Connect the owned `outreach.skubase.io` subdomain
with EmailPal `mode=connect,dns_method=manual`, after approved account access. Read
the exact provider-issued records; apply only records below that subdomain using the
accessible DNS account. Do not change primary MX, nameservers or existing SPF records.
Do not fabricate DKIM or return-path values. DNS remains pending provider issuance.

The provider accepted `outreach.skubase.io` (resource
`92cca13e-7db3-4f8e-81ce-157a93f70d4d`) in manual-DNS mode. Its domain page currently
shows no signing keys or DNS records, including after requesting record generation.
It also labels the new domain “Ready in 60 days.” These are unresolved provider
conditions; no primary DNS or MX changes have been made. Support ticket
`0caeac82-bdc3-45ba-bb93-851dcc97998c` requests actual sourcing-policy/subdomain
confirmation. Billing shows $69/month plus $0.60 per warmed mailbox/month, no
subscription and no transactions. Do not authorize payment or infer readiness.
Authenticated `/jobs` inspection showed domain setup/verification jobs queued with
zero attempts. Do not keep enqueueing duplicates or guess DNS values while the
provider has not processed these jobs. Its empty `dns.records` list is not verified
DNS even though the response currently labels the empty set `healthy: true`.

### Later September 9 update: DNS published

The provider's setup jobs subsequently succeeded and issued eight real records.
All eight were added using the authenticated Vercel DNS interface and independently
matched public DNS at 21:20 UTC. Primary Google Workspace MX and operational Resend
records were preserved. Evidence 22820 retains the issued records and resolver checks.
See `outreach-dns-20260909.json` for the exact public configuration. The MX priority
is 10; the provider contract supplied the destination without a priority.

Verification job `830ce101-0834-40f9-97de-eda5175eab71` was queued after publication.
Poll that existing job rather than requesting another rewrite or verification job.
Do not equate public DNS publication with provider readiness or a delivered message.
Once the domain is ready, provision exactly one mailbox with first_name=Rainer,
pattern=first, cold_daily_limit=5 and warming=false. Match an existing sender before
creating it and inspect the create receipt before retrying any ambiguous response.
Set its display name to `Rainer from Skubase` using the documented mailbox update.

Support ticket `0caeac82-bdc3-45ba-bb93-851dcc97998c` received a 14:21 Pacific update
with the completed DNS checks, job ID, no-network-warming requirement, sourcing
clarification and subscription activation issue. Billing still shows $69/month,
no subscription, no trial and no transactions. The Starter-current button is disabled;
only more expensive upgrades are offered. Do not buy an upgrade to work around this.
The existing provider support question must resolve the correct Starter activation
route and whether its displayed 60-day eligibility restriction applies to this setup.
No subscription charge, warming traffic, mailbox or real test send was created by
the DNS publication itself. Cost authorization remains separate from DNS readiness.

Before live activation verify test delivery, an actual reply, signed event/replay,
unsubscribe and sender/domain identity. Require documented provider acceptance of
Skubase's public-business-contact sourcing. Keep email off while these are unresolved.
