# Dedicated outreach email

The conditional EmailPal adapter is separate from operational Resend/Gmail. No real
provider send has been verified yet. The info@skubase.io account and Skubase workspace
were created on September 9 using Google's signup route. No subscription or payment
transaction exists. See outbound-provider-evaluation.md.

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

Before live activation verify test delivery, an actual reply, signed event/replay,
unsubscribe and sender/domain identity. Require documented provider acceptance of
Skubase's public-business-contact sourcing. Keep email off while these are unresolved.
